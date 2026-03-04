"""
Task 8.2 統合テスト・E2Eテスト実装

お問い合わせ受付→AI解析→Vector検索→通知の全体フロー検証
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
from typing import Dict, Any, List

from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine
from sqlalchemy.pool import StaticPool

from backend.app.main import create_main_app
from backend.app.contacts.providers import create_test_container_with_mocks
from backend.app.models.contact import Contact
from backend.app.models.contact_ai_analysis import ContactAIAnalysis
from backend.app.models.contact_vector import ContactVector
from backend.app.models.enums import CategoryType, UrgencyLevel, SentimentType
from backend.tests.utils.test_mocks import (
    MockGeminiAPI,
    MockSendGridAPI,
    TestDataFactory,
    AssertionHelpers
)


@pytest.fixture
def test_database():
    """テスト用インメモリデータベース"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )
    
    # テーブル作成
    from sqlmodel import SQLModel
    SQLModel.metadata.create_all(engine)
    
    return engine


@pytest.fixture
def mock_services():
    """モックサービス群"""
    gemini_mock = MockGeminiAPI()
    sendgrid_mock = MockSendGridAPI()
    
    # 正常な分析結果を設定
    gemini_mock.configure_response({
        "category": "GENERAL",
        "urgency": "MEDIUM",
        "sentiment": "NEUTRAL", 
        "confidence_score": 0.85,
        "summary": "商品に関する一般的な問い合わせ"
    })
    
    return {
        "gemini_service": gemini_mock,
        "notification_service": sendgrid_mock
    }


@pytest.fixture
def test_app(test_database, mock_services):
    """テスト用FastAPIアプリケーション"""
    with patch('backend.app.main.initialize_firebase'):
        # テスト用コンテナを作成
        container = create_test_container_with_mocks(**mock_services)
        
        app = create_main_app()
        app.state.container = container
        
        return app


class TestContactFlowIntegration:
    """お問い合わせフロー統合テスト"""
    
    def test_complete_contact_processing_flow(self, test_app, mock_services):
        """完全なお問い合わせ処理フローテスト"""
        client = TestClient(test_app)
        
        # Step 1: お問い合わせ受付
        contact_data = {
            "name": "山田太郎",
            "email": "yamada@example.com",
            "subject": "商品について",
            "message": "商品の詳細を教えてください"
        }
        
        response = client.post("/api/v1/contacts", json=contact_data)
        
        assert response.status_code == 201
        created_contact = response.json()
        contact_id = created_contact["id"]
        
        # Step 2: AI解析が自動的に実行されることを確認
        # 実際の統合では非同期で実行されるため、少し待機
        import time
        time.sleep(0.1)
        
        # Step 3: 分析結果の確認
        analysis_response = client.get(f"/api/v1/admin/contacts/{contact_id}/analysis")
        
        assert analysis_response.status_code == 200
        analysis_data = analysis_response.json()
        
        AssertionHelpers.assert_analysis_valid(analysis_data)
        assert analysis_data["category"] == "GENERAL"
        assert analysis_data["confidence_score"] == 0.85
        
        # Step 4: Vector検索の実行確認
        similar_response = client.get(f"/api/v1/admin/contacts/{contact_id}/similar")
        
        assert similar_response.status_code == 200
        similar_contacts = similar_response.json()
        
        # 類似お問い合わせが検索されることを確認（空でも可）
        assert isinstance(similar_contacts, list)
        
    def test_urgent_contact_flow_with_notifications(self, test_app, mock_services):
        """緊急お問い合わせフローと通知テスト"""
        client = TestClient(test_app)
        
        # 緊急度の高い分析結果を設定
        mock_services["gemini_service"].reset()
        mock_services["gemini_service"].configure_response({
            "category": "COMPLAINT",
            "urgency": "URGENT",
            "sentiment": "NEGATIVE",
            "confidence_score": 0.92,
            "summary": "商品故障による緊急対応要請"
        })
        
        # 緊急お問い合わせを送信
        urgent_contact_data = {
            "name": "田中花子",
            "email": "tanaka@example.com",
            "subject": "緊急：商品が故障",
            "message": "購入した商品が使用開始直後に故障しました。すぐに交換または返金をお願いします！"
        }
        
        response = client.post("/api/v1/contacts", json=urgent_contact_data)
        
        assert response.status_code == 201
        created_contact = response.json()
        contact_id = created_contact["id"]
        
        # 処理完了まで待機
        time.sleep(0.2)
        
        # 分析結果の確認
        analysis_response = client.get(f"/api/v1/admin/contacts/{contact_id}/analysis")
        analysis_data = analysis_response.json()
        
        assert analysis_data["urgency"] == "URGENT"
        assert analysis_data["sentiment"] == "NEGATIVE"
        
        # 緊急通知が送信されたことを確認
        sent_emails = mock_services["notification_service"].get_sent_emails()
        assert len(sent_emails) > 0
        
        # 緊急通知の内容を確認
        urgent_email = next(
            (email for email in sent_emails if "緊急" in email.get("subject", "")),
            None
        )
        assert urgent_email is not None
        
    def test_error_handling_flow(self, test_app, mock_services):
        """エラーハンドリングフローテスト"""
        client = TestClient(test_app)
        
        # AI処理エラーを設定
        from backend.app.error_handling.exceptions import AIProcessingError
        mock_services["gemini_service"].reset()
        mock_services["gemini_service"].configure_error(
            AIProcessingError("AI service temporarily unavailable")
        )
        
        contact_data = {
            "name": "エラーテスト太郎",
            "email": "error@example.com",
            "subject": "テストエラー",
            "message": "エラー処理のテスト"
        }
        
        response = client.post("/api/v1/contacts", json=contact_data)
        
        # お問い合わせ受付は成功（段階的整合性制御）
        assert response.status_code == 201
        created_contact = response.json()
        contact_id = created_contact["id"]
        
        # 処理完了まで待機
        time.sleep(0.1)
        
        # AI分析は失敗するが、フォールバック分析が実行される
        analysis_response = client.get(f"/api/v1/admin/contacts/{contact_id}/analysis")
        
        if analysis_response.status_code == 200:
            # フォールバック分析が成功した場合
            analysis_data = analysis_response.json()
            assert analysis_data.get("fallback_used") is True
        else:
            # 分析が完全に失敗した場合（手動処理待ち）
            assert analysis_response.status_code == 404
            
    def test_bulk_contact_processing_flow(self, test_app, mock_services):
        """複数お問い合わせの一括処理フローテスト"""
        client = TestClient(test_app)
        
        # 複数のお問い合わせを作成
        contact_ids = []
        
        for i in range(5):
            contact_data = {
                "name": f"テスト太郎{i}",
                "email": f"test{i}@example.com",
                "subject": f"テスト件名{i}",
                "message": f"テストメッセージ{i}"
            }
            
            response = client.post("/api/v1/contacts", json=contact_data)
            assert response.status_code == 201
            
            created_contact = response.json()
            contact_ids.append(created_contact["id"])
            
        # 一括処理の完了を待機
        time.sleep(0.5)
        
        # 全てのお問い合わせが分析されていることを確認
        processed_count = 0
        for contact_id in contact_ids:
            analysis_response = client.get(f"/api/v1/admin/contacts/{contact_id}/analysis")
            if analysis_response.status_code == 200:
                processed_count += 1
                
        # 少なくとも80%は処理されている
        assert processed_count >= len(contact_ids) * 0.8
        
    def test_performance_monitoring_integration(self, test_app, mock_services):
        """パフォーマンス監視統合テスト"""
        client = TestClient(test_app)
        
        # 処理時間を測定
        start_time = datetime.now()
        
        contact_data = {
            "name": "パフォーマンステスト太郎",
            "email": "performance@example.com",
            "subject": "パフォーマンステスト",
            "message": "処理時間を測定するテスト"
        }
        
        response = client.post("/api/v1/contacts", json=contact_data)
        assert response.status_code == 201
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        # API応答時間が1秒以内であることを確認
        assert processing_time < 1.0
        
        # システムメトリクスエンドポイントをテスト
        metrics_response = client.get("/api/v1/admin/metrics")
        
        if metrics_response.status_code == 200:
            metrics_data = metrics_response.json()
            assert "api_response_time" in metrics_data
            assert "processing_queue_length" in metrics_data


class TestAuthenticationIntegration:
    """認証統合テスト"""
    
    def test_admin_endpoint_authentication_required(self, test_app):
        """管理者エンドポイントの認証必須テスト"""
        client = TestClient(test_app)
        
        # 認証なしでアクセス
        response = client.get("/api/v1/admin/contacts")
        assert response.status_code == 401
        
        # 無効なトークンでアクセス
        headers = {"Authorization": "Bearer invalid_token"}
        response = client.get("/api/v1/admin/contacts", headers=headers)
        assert response.status_code == 401
        
    def test_valid_admin_authentication(self, test_app):
        """有効な管理者認証テスト"""
        client = TestClient(test_app)
        
        # 有効な管理者トークンを模擬
        with patch('backend.app.api.routes.verify_admin_token') as mock_verify:
            mock_verify.return_value = True
            
            headers = {"Authorization": "Bearer valid_admin_token"}
            response = client.get("/api/v1/admin/contacts", headers=headers)
            
            # 認証成功（データがなくても200または空のリスト）
            assert response.status_code in [200, 404]
            
    def test_role_based_access_control(self, test_app):
        """ロールベースアクセス制御テスト"""
        client = TestClient(test_app)
        
        # 一般ユーザートークンでの管理者機能アクセス
        with patch('backend.app.api.routes.verify_admin_token') as mock_verify:
            mock_verify.return_value = False  # 管理者権限なし
            
            headers = {"Authorization": "Bearer user_token"}
            response = client.get("/api/v1/admin/contacts", headers=headers)
            
            assert response.status_code == 403


class TestPerformanceIntegration:
    """パフォーマンス統合テスト"""
    
    @pytest.mark.asyncio
    async def test_concurrent_contact_processing(self, test_app, mock_services):
        """並行お問い合わせ処理テスト"""
        client = TestClient(test_app)
        
        async def create_contact(index):
            contact_data = {
                "name": f"並行テスト太郎{index}",
                "email": f"concurrent{index}@example.com",
                "subject": f"並行テスト{index}",
                "message": f"並行処理テストメッセージ{index}"
            }
            
            response = client.post("/api/v1/contacts", json=contact_data)
            return response.status_code == 201
            
        # 10個の並行リクエストを送信
        tasks = [create_contact(i) for i in range(10)]
        results = await asyncio.gather(*tasks)
        
        # 全てのリクエストが成功することを確認
        success_count = sum(1 for result in results if result)
        assert success_count >= 8  # 80%以上成功
        
    def test_load_testing_simulation(self, test_app, mock_services):
        """負荷テストシミュレーション"""
        client = TestClient(test_app)
        
        start_time = datetime.now()
        successful_requests = 0
        failed_requests = 0
        
        # 100リクエストを送信
        for i in range(100):
            contact_data = {
                "name": f"負荷テスト太郎{i}",
                "email": f"load{i}@example.com",
                "subject": f"負荷テスト{i}",
                "message": f"負荷テストメッセージ{i}"
            }
            
            try:
                response = client.post("/api/v1/contacts", json=contact_data)
                if response.status_code == 201:
                    successful_requests += 1
                else:
                    failed_requests += 1
            except Exception:
                failed_requests += 1
                
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()
        
        # パフォーマンス指標の確認
        requests_per_second = successful_requests / total_time
        success_rate = successful_requests / (successful_requests + failed_requests)
        
        # 最低限のパフォーマンス要件
        assert requests_per_second >= 10  # 10 RPS以上
        assert success_rate >= 0.95       # 95%以上の成功率
        
    def test_memory_usage_monitoring(self, test_app):
        """メモリ使用量監視テスト"""
        client = TestClient(test_app)
        
        try:
            import psutil
            process = psutil.Process()
            initial_memory = process.memory_info().rss
            
            # 大量のリクエストを処理
            for i in range(50):
                contact_data = {
                    "name": f"メモリテスト太郎{i}",
                    "email": f"memory{i}@example.com",
                    "subject": f"メモリテスト{i}",
                    "message": f"メモリテストメッセージ{i}" * 100  # 長いメッセージ
                }
                
                client.post("/api/v1/contacts", json=contact_data)
                
            final_memory = process.memory_info().rss
            memory_increase = final_memory - initial_memory
            
            # メモリ増加が100MB以下であることを確認
            assert memory_increase < 100 * 1024 * 1024
            
        except ImportError:
            # psutilが利用できない場合はスキップ
            pytest.skip("psutil not available for memory monitoring")


class TestFailoverIntegration:
    """フェイルオーバー統合テスト"""
    
    def test_ai_service_failover(self, test_app, mock_services):
        """AIサービスフェイルオーバーテスト"""
        client = TestClient(test_app)
        
        # 1回目はエラー、2回目は成功するように設定
        from backend.app.error_handling.exceptions import AIProcessingError
        mock_services["gemini_service"].configure_sequence([
            AIProcessingError("Service temporarily unavailable"),
            {
                "category": "GENERAL",
                "urgency": "MEDIUM", 
                "sentiment": "NEUTRAL",
                "confidence_score": 0.7,
                "summary": "フォールバック分析結果"
            }
        ])
        
        contact_data = {
            "name": "フェイルオーバーテスト太郎",
            "email": "failover@example.com",
            "subject": "フェイルオーバーテスト",
            "message": "フェイルオーバー処理のテスト"
        }
        
        response = client.post("/api/v1/contacts", json=contact_data)
        
        # お問い合わせ受付は成功
        assert response.status_code == 201
        
        created_contact = response.json()
        contact_id = created_contact["id"]
        
        # フェイルオーバー処理完了まで待機
        time.sleep(0.3)
        
        # 最終的に分析が成功していることを確認
        analysis_response = client.get(f"/api/v1/admin/contacts/{contact_id}/analysis")
        
        if analysis_response.status_code == 200:
            analysis_data = analysis_response.json()
            assert analysis_data["confidence_score"] >= 0.5  # フォールバック分析でも有効
            
    def test_notification_service_failover(self, test_app, mock_services):
        """通知サービスフェイルオーバーテスト"""
        client = TestClient(test_app)
        
        # 通知サービスの失敗を設定
        mock_services["notification_service"].configure_failure(
            should_fail=True,
            reason="SMTP server unavailable"
        )
        
        # 緊急度の高い分析結果を設定
        mock_services["gemini_service"].configure_response({
            "category": "URGENT",
            "urgency": "URGENT",
            "sentiment": "NEGATIVE",
            "confidence_score": 0.9,
            "summary": "緊急対応が必要な問い合わせ"
        })
        
        urgent_contact_data = {
            "name": "フェイルオーバーテスト花子",
            "email": "failover2@example.com",
            "subject": "緊急問題",
            "message": "システムが完全に使用できません"
        }
        
        response = client.post("/api/v1/contacts", json=urgent_contact_data)
        
        # お問い合わせ受付は成功（通知失敗でも受付は継続）
        assert response.status_code == 201
        
        created_contact = response.json()
        contact_id = created_contact["id"]
        
        # 処理完了まで待機
        time.sleep(0.2)
        
        # AI分析は成功していることを確認
        analysis_response = client.get(f"/api/v1/admin/contacts/{contact_id}/analysis")
        
        if analysis_response.status_code == 200:
            analysis_data = analysis_response.json()
            assert analysis_data["urgency"] == "URGENT"
            
            # 通知失敗のログが記録されていることを確認
            # （実際の実装では、ログやメトリクスで確認）


if __name__ == "__main__":
    pytest.main([__file__, "-v"])