"""
管理ダッシュボード統合テスト

Task 8.2: 統合テスト・E2Eテスト実装
管理ダッシュボードAPI、検索機能、分析レポート機能の統合テストを実装
"""

import pytest
import json
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session

# テスト対象インポート
from backend.app.main import create_main_app
from backend.app.models.contact import Contact, ContactStatus, CategoryType, UrgencyLevel
from backend.app.models.contact_ai_analysis import ContactAIAnalysis
from backend.app.models.contact_vector import ContactVector
from backend.app.api.admin_dashboard import AdminDashboardAPI


class TestAdminDashboardIntegration:
    """管理ダッシュボード統合テスト"""
    
    @pytest.fixture
    def test_app(self):
        """テストアプリケーション"""
        # テスト用インメモリデータベース
        engine = create_engine("sqlite:///:memory:", echo=False)
        SQLModel.metadata.create_all(engine)
        
        app = create_main_app()
        
        # テスト用セッション
        def get_test_db():
            with Session(engine) as session:
                yield session
                
        app.dependency_overrides = {}
        return app
    
    @pytest.fixture
    def sample_dashboard_data(self, test_db_session):
        """ダッシュボード用サンプルデータ"""
        # 過去30日間のお問い合わせデータ作成
        contacts = []
        analyses = []
        
        # カテゴリ別お問い合わせ作成
        categories = [CategoryType.GENERAL, CategoryType.TECHNICAL, CategoryType.BILLING]
        urgencies = [UrgencyLevel.LOW, UrgencyLevel.MEDIUM, UrgencyLevel.HIGH]
        
        for i in range(30):
            # 日付をずらして作成
            created_date = datetime.utcnow() - timedelta(days=i)
            
            # 複数のお問い合わせを作成
            for j in range(3):
                contact_id = f"contact_{i}_{j}"
                contact = Contact(
                    id=contact_id,
                    name=f"テストユーザー{i}_{j}",
                    email=f"user{i}_{j}@example.com",
                    subject=f"テストお問い合わせ{i}_{j}",
                    message=f"テストメッセージ内容{i}_{j}",
                    status=ContactStatus.RESOLVED if i % 3 == 0 else ContactStatus.PENDING,
                    created_at=created_date,
                    updated_at=created_date
                )
                
                # AI解析結果
                analysis = ContactAIAnalysis(
                    id=f"analysis_{i}_{j}",
                    contact_id=contact_id,
                    category=categories[j % len(categories)],
                    urgency=urgencies[j % len(urgencies)],
                    confidence_score=0.8 + (i % 10) * 0.02,
                    suggested_response=f"推奨回答{i}_{j}",
                    keywords=["テスト", f"キーワード{i}", f"項目{j}"],
                    sentiment_score=0.5 + (i % 10) * 0.05,
                    created_at=created_date
                )
                
                contacts.append(contact)
                analyses.append(analysis)
        
        # データベースに保存
        test_db_session.add_all(contacts)
        test_db_session.add_all(analyses)
        test_db_session.commit()
        
        return {
            "contacts": contacts,
            "analyses": analyses,
            "total_contacts": len(contacts),
            "categories": categories,
            "urgencies": urgencies
        }
    
    def test_dashboard_overview_api(self, test_app, sample_dashboard_data):
        """ダッシュボード概要API統合テスト"""
        client = TestClient(test_app)
        
        # 認証ヘッダー設定（テスト用）
        headers = {"Authorization": "Bearer test_admin_token"}
        
        # 概要データ取得
        response = client.get("/api/v1/admin/dashboard/overview", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # 期待されるフィールドの確認
        expected_fields = [
            "total_contacts",
            "pending_contacts", 
            "resolved_contacts",
            "avg_response_time",
            "category_distribution",
            "urgency_distribution",
            "daily_volume"
        ]
        
        for field in expected_fields:
            assert field in data
        
        # 統計情報の検証
        assert data["total_contacts"] == 90  # 30日 × 3件
        assert isinstance(data["category_distribution"], dict)
        assert isinstance(data["urgency_distribution"], dict)
        assert isinstance(data["daily_volume"], list)
    
    def test_contact_search_with_filters(self, test_app, sample_dashboard_data):
        """フィルタ付きお問い合わせ検索テスト"""
        client = TestClient(test_app)
        headers = {"Authorization": "Bearer test_admin_token"}
        
        # カテゴリフィルタ検索
        response = client.get(
            "/api/v1/admin/contacts/search",
            params={
                "category": CategoryType.TECHNICAL.value,
                "limit": 10,
                "offset": 0
            },
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "contacts" in data
        assert "total_count" in data
        assert "pagination" in data
        
        # 全件がTECHNICALカテゴリであることを確認
        for contact in data["contacts"]:
            assert contact["analysis"]["category"] == CategoryType.TECHNICAL.value
    
    def test_urgency_based_search(self, test_app, sample_dashboard_data):
        """緊急度ベース検索テスト"""
        client = TestClient(test_app)
        headers = {"Authorization": "Bearer test_admin_token"}
        
        # 高緊急度のお問い合わせ検索
        response = client.get(
            "/api/v1/admin/contacts/search",
            params={
                "urgency": UrgencyLevel.HIGH.value,
                "sort_by": "created_at",
                "sort_order": "desc"
            },
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # 緊急度検証
        for contact in data["contacts"]:
            assert contact["analysis"]["urgency"] == UrgencyLevel.HIGH.value
        
        # ソート順検証（新しい順）
        if len(data["contacts"]) > 1:
            timestamps = [contact["created_at"] for contact in data["contacts"]]
            assert timestamps == sorted(timestamps, reverse=True)
    
    def test_analytics_report_generation(self, test_app, sample_dashboard_data):
        """分析レポート生成テスト"""
        client = TestClient(test_app)
        headers = {"Authorization": "Bearer test_admin_token"}
        
        # 週次レポート生成
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=7)
        
        response = client.post(
            "/api/v1/admin/analytics/report",
            json={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "report_type": "weekly",
                "include_trends": True,
                "include_predictions": True
            },
            headers=headers
        )
        
        assert response.status_code == 200
        report = response.json()
        
        # レポート構造検証
        expected_sections = [
            "summary",
            "contact_volume",
            "category_analysis",
            "response_time_analysis", 
            "customer_satisfaction",
            "ai_performance",
            "trends",
            "recommendations"
        ]
        
        for section in expected_sections:
            assert section in report
        
        # AI性能分析の検証
        ai_performance = report["ai_performance"]
        assert "classification_accuracy" in ai_performance
        assert "confidence_distribution" in ai_performance
        assert "processing_time" in ai_performance
    
    def test_real_time_monitoring(self, test_app, sample_dashboard_data):
        """リアルタイム監視機能テスト"""
        client = TestClient(test_app)
        headers = {"Authorization": "Bearer test_admin_token"}
        
        # システム状態取得
        response = client.get("/api/v1/admin/monitoring/status", headers=headers)
        
        assert response.status_code == 200
        status = response.json()
        
        # 監視項目確認
        monitoring_items = [
            "system_health",
            "api_performance", 
            "database_status",
            "ai_service_status",
            "queue_status",
            "error_rates"
        ]
        
        for item in monitoring_items:
            assert item in status
        
        # ヘルスチェック結果検証
        assert status["system_health"]["status"] in ["healthy", "warning", "critical"]
        assert isinstance(status["api_performance"]["avg_response_time"], (int, float))
        assert isinstance(status["error_rates"]["last_hour"], (int, float))


class TestWorkflowIntegration:
    """ワークフロー統合テスト"""
    
    @pytest.fixture
    def mock_notification_service(self):
        """通知サービスモック"""
        mock = AsyncMock()
        mock.send_email.return_value = {"status": "sent", "message_id": "test_123"}
        mock.send_slack_notification.return_value = {"status": "sent"}
        return mock
    
    @pytest.mark.asyncio
    async def test_complete_contact_workflow(self, test_app, mock_notification_service):
        """完全なお問い合わせワークフローテスト"""
        
        # 1. お問い合わせ投稿
        contact_data = {
            "name": "ワークフローテストユーザー",
            "email": "workflow@example.com",
            "subject": "ワークフローテスト",
            "message": "統合テスト用のワークフローテストメッセージです。技術的な問題について相談したいです。"
        }
        
        with TestClient(test_app) as client:
            # お問い合わせ作成
            response = client.post("/api/v1/contacts", json=contact_data)
            assert response.status_code == 201
            contact_id = response.json()["id"]
            
            # 2. AI解析の完了待機（モック）
            with patch('backend.app.services.gemini_service.GeminiService.analyze_contact') as mock_analyze:
                mock_analyze.return_value = {
                    "category": CategoryType.TECHNICAL,
                    "urgency": UrgencyLevel.HIGH,
                    "confidence_score": 0.92,
                    "suggested_response": "技術サポートチームに転送します",
                    "keywords": ["技術", "問題", "相談"],
                    "sentiment_score": 0.3
                }
                
                # AI解析実行
                response = client.post(f"/api/v1/contacts/{contact_id}/analyze")
                assert response.status_code == 200
            
            # 3. 管理者による確認
            headers = {"Authorization": "Bearer test_admin_token"}
            response = client.get(f"/api/v1/admin/contacts/{contact_id}", headers=headers)
            assert response.status_code == 200
            
            contact_detail = response.json()
            assert contact_detail["analysis"]["category"] == CategoryType.TECHNICAL.value
            assert contact_detail["analysis"]["urgency"] == UrgencyLevel.HIGH.value
            
            # 4. 回答作成・送信
            response_data = {
                "message": "技術サポートチームより回答いたします。詳細をお聞かせください。",
                "internal_notes": "技術チームに転送済み",
                "assign_to": "tech_support_team"
            }
            
            with patch('backend.app.services.notification_service.NotificationService.send_email') as mock_email:
                mock_email.return_value = {"status": "sent", "message_id": "email_123"}
                
                response = client.post(
                    f"/api/v1/admin/contacts/{contact_id}/respond",
                    json=response_data,
                    headers=headers
                )
                assert response.status_code == 200
            
            # 5. ステータス更新確認
            response = client.get(f"/api/v1/contacts/{contact_id}/status")
            assert response.status_code == 200
            
            status_data = response.json()
            assert status_data["status"] == ContactStatus.IN_PROGRESS.value
    
    def test_bulk_processing_workflow(self, test_app):
        """バルク処理ワークフローテスト"""
        
        # 複数お問い合わせの一括作成
        contacts_data = []
        for i in range(10):
            contacts_data.append({
                "name": f"バルクユーザー{i}",
                "email": f"bulk{i}@example.com", 
                "subject": f"バルクテスト{i}",
                "message": f"バルク処理テスト用メッセージ{i}"
            })
        
        with TestClient(test_app) as client:
            contact_ids = []
            
            # 一括作成
            for contact_data in contacts_data:
                response = client.post("/api/v1/contacts", json=contact_data)
                assert response.status_code == 201
                contact_ids.append(response.json()["id"])
            
            # バルクAI解析
            headers = {"Authorization": "Bearer test_admin_token"}
            
            with patch('backend.app.services.gemini_service.GeminiService.analyze_contact') as mock_analyze:
                mock_analyze.return_value = {
                    "category": CategoryType.GENERAL,
                    "urgency": UrgencyLevel.MEDIUM,
                    "confidence_score": 0.75,
                    "suggested_response": "一般的なお問い合わせとして対応",
                    "keywords": ["一般", "問い合わせ"],
                    "sentiment_score": 0.6
                }
                
                # 一括解析実行
                response = client.post(
                    "/api/v1/admin/contacts/bulk-analyze",
                    json={"contact_ids": contact_ids},
                    headers=headers
                )
                assert response.status_code == 200
                
                result = response.json()
                assert result["processed_count"] == 10
                assert result["success_count"] == 10
                assert result["error_count"] == 0


class TestPerformanceIntegration:
    """パフォーマンス統合テスト"""
    
    def test_concurrent_request_handling(self, test_app):
        """同時リクエスト処理テスト"""
        import threading
        import time
        
        results = []
        errors = []
        
        def make_request(thread_id):
            """リクエスト実行スレッド"""
            try:
                contact_data = {
                    "name": f"同時ユーザー{thread_id}",
                    "email": f"concurrent{thread_id}@example.com",
                    "subject": f"同時テスト{thread_id}",
                    "message": f"同時実行テスト用メッセージ{thread_id}"
                }
                
                with TestClient(test_app) as client:
                    start_time = time.time()
                    response = client.post("/api/v1/contacts", json=contact_data)
                    end_time = time.time()
                    
                    results.append({
                        "thread_id": thread_id,
                        "status_code": response.status_code,
                        "response_time": end_time - start_time,
                        "response_data": response.json() if response.status_code == 201 else None
                    })
                    
            except Exception as e:
                errors.append({
                    "thread_id": thread_id,
                    "error": str(e)
                })
        
        # 10スレッドで同時実行
        threads = []
        for i in range(10):
            thread = threading.Thread(target=make_request, args=(i,))
            threads.append(thread)
            thread.start()
        
        # 全スレッド完了待機
        for thread in threads:
            thread.join()
        
        # 結果検証
        assert len(errors) == 0, f"エラーが発生しました: {errors}"
        assert len(results) == 10
        
        # 全リクエスト成功確認
        for result in results:
            assert result["status_code"] == 201
            assert result["response_time"] < 5.0  # 5秒以内
            assert result["response_data"] is not None
        
        # 平均応答時間確認
        avg_response_time = sum(r["response_time"] for r in results) / len(results)
        assert avg_response_time < 2.0, f"平均応答時間が遅すぎます: {avg_response_time}秒"
    
    @pytest.mark.asyncio
    async def test_database_connection_pool(self, test_app):
        """データベース接続プール負荷テスト"""
        
        async def database_operation(operation_id):
            """データベース操作"""
            contact_data = {
                "name": f"プールテストユーザー{operation_id}",
                "email": f"pool{operation_id}@example.com",
                "subject": f"プールテスト{operation_id}",
                "message": f"接続プール負荷テスト{operation_id}"
            }
            
            with TestClient(test_app) as client:
                response = client.post("/api/v1/contacts", json=contact_data)
                return response.status_code, response.json() if response.status_code == 201 else None
        
        # 20個の並行データベース操作
        tasks = [database_operation(i) for i in range(20)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 結果検証
        successful_operations = 0
        for result in results:
            if isinstance(result, Exception):
                pytest.fail(f"データベース操作でエラー: {result}")
            else:
                status_code, data = result
                if status_code == 201:
                    successful_operations += 1
        
        assert successful_operations == 20, "一部のデータベース操作が失敗しました"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])