"""
Task 8.1 AIAnalysisUseCase ユニットテスト

TDD-RED フェーズ: 失敗するテストを先に作成
- AIAnalysisUseCase の単体テスト
- モック・スタブ作成（GeminiService、NotificationService）
- エラーケース・境界値・セキュリティテスト
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from sqlmodel import Session
from sqlalchemy.exc import SQLAlchemyError

from backend.app.use_cases.ai_analysis_usecase import AIAnalysisUseCase
from backend.app.services.gemini_service import GeminiService
from backend.app.services.notification_service import NotificationService
from backend.app.models.contact import Contact
from backend.app.models.contact_ai_analysis import ContactAIAnalysis
from backend.app.models.enums import CategoryType, UrgencyLevel, SentimentType
from backend.app.error_handling.exceptions import (
    AIProcessingError,
    DatabaseConnectionError,
    ValidationError
)


@pytest.fixture
def mock_db_session():
    """モックデータベースセッション"""
    session = Mock(spec=Session)
    session.add = Mock()
    session.commit = Mock()
    session.rollback = Mock()
    session.close = Mock()
    session.query = Mock()
    session.get = Mock()
    return session


@pytest.fixture
def mock_gemini_service():
    """モックGeminiService"""
    service = Mock(spec=GeminiService)
    service.analyze_contact = AsyncMock(return_value={
        "category": CategoryType.GENERAL,
        "urgency": UrgencyLevel.MEDIUM,
        "sentiment": SentimentType.NEUTRAL,
        "confidence_score": 0.85,
        "summary": "商品に関する一般的な問い合わせ",
        "analysis_time": 12.5
    })
    return service


@pytest.fixture
def mock_notification_service():
    """モックNotificationService"""
    service = Mock(spec=NotificationService)
    service.send_notification = AsyncMock(return_value=True)
    service.send_escalation_alert = AsyncMock(return_value=True)
    return service


@pytest.fixture
def sample_contact():
    """サンプルContact"""
    return Contact(
        id="contact_123",
        name="山田太郎",
        email="yamada@example.com",
        subject="商品について",
        message="商品の詳細を教えてください",
        created_at=datetime.now(),
        status="received"
    )


@pytest.fixture
def sample_urgent_contact():
    """緊急度の高いサンプルContact"""
    return Contact(
        id="urgent_contact_456", 
        name="田中花子",
        email="tanaka@example.com",
        subject="緊急：商品が故障しました",
        message="購入した商品が使用開始直後に故障しました。すぐに交換または返金をお願いします！",
        created_at=datetime.now(),
        status="received"
    )


class TestAIAnalysisUseCaseInitialization:
    """AIAnalysisUseCase初期化テスト"""
    
    def test_ai_analysis_usecase_initialization_success(
        self, 
        mock_db_session,
        mock_gemini_service,
        mock_notification_service
    ):
        """正常な初期化テスト"""
        usecase = AIAnalysisUseCase(
            db_session=mock_db_session,
            gemini_service=mock_gemini_service,
            notification_service=mock_notification_service
        )
        
        assert usecase.db_session == mock_db_session
        assert usecase.gemini_service == mock_gemini_service
        assert usecase.notification_service == mock_notification_service
        assert usecase.max_processing_time == 120  # 2分
        
    def test_ai_analysis_usecase_initialization_missing_dependencies(self):
        """依存関係未設定時のエラーテスト"""
        with pytest.raises(ValueError, match="Database session is required"):
            AIAnalysisUseCase(
                db_session=None,
                gemini_service=Mock(),
                notification_service=Mock()
            )
            
        with pytest.raises(ValueError, match="Gemini service is required"):
            AIAnalysisUseCase(
                db_session=Mock(),
                gemini_service=None,
                notification_service=Mock()
            )
            
        with pytest.raises(ValueError, match="Notification service is required"):
            AIAnalysisUseCase(
                db_session=Mock(),
                gemini_service=Mock(),
                notification_service=None
            )


class TestAIAnalysisUseCaseProcessContact:
    """AIAnalysisUseCase お問い合わせ処理テスト"""
    
    @pytest.mark.asyncio
    async def test_process_contact_success(
        self,
        mock_db_session,
        mock_gemini_service,
        mock_notification_service,
        sample_contact
    ):
        """お問い合わせ処理成功テスト"""
        usecase = AIAnalysisUseCase(
            db_session=mock_db_session,
            gemini_service=mock_gemini_service,
            notification_service=mock_notification_service
        )
        
        # データベース取得を模擬
        mock_db_session.get.return_value = sample_contact
        
        result = await usecase.process_contact("contact_123")
        
        assert result["contact_id"] == "contact_123"
        assert result["status"] == "completed"
        assert result["analysis"]["category"] == CategoryType.GENERAL
        assert result["analysis"]["urgency"] == UrgencyLevel.MEDIUM
        assert result["analysis"]["confidence_score"] == 0.85
        assert result["processing_time"] < 120  # 2分以内
        
        # GeminiServiceが呼び出されたことを確認
        mock_gemini_service.analyze_contact.assert_called_once()
        
        # 分析結果がデータベースに保存されたことを確認
        mock_db_session.add.assert_called()
        mock_db_session.commit.assert_called()
        
    @pytest.mark.asyncio
    async def test_process_urgent_contact_with_notification(
        self,
        mock_db_session,
        mock_gemini_service,
        mock_notification_service,
        sample_urgent_contact
    ):
        """緊急お問い合わせの処理と通知テスト"""
        usecase = AIAnalysisUseCase(
            db_session=mock_db_session,
            gemini_service=mock_gemini_service,
            notification_service=mock_notification_service
        )
        
        # 緊急度の高い分析結果を模擬
        mock_gemini_service.analyze_contact.return_value = {
            "category": CategoryType.COMPLAINT,
            "urgency": UrgencyLevel.URGENT,
            "sentiment": SentimentType.NEGATIVE,
            "confidence_score": 0.92,
            "summary": "商品故障による緊急対応要請",
            "analysis_time": 8.2
        }
        
        mock_db_session.get.return_value = sample_urgent_contact
        
        result = await usecase.process_contact("urgent_contact_456")
        
        assert result["analysis"]["urgency"] == UrgencyLevel.URGENT
        assert result["notification_sent"] is True
        
        # 緊急通知が送信されたことを確認
        mock_notification_service.send_escalation_alert.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_process_contact_not_found(
        self,
        mock_db_session,
        mock_gemini_service,
        mock_notification_service
    ):
        """存在しないお問い合わせIDのテスト"""
        usecase = AIAnalysisUseCase(
            db_session=mock_db_session,
            gemini_service=mock_gemini_service,
            notification_service=mock_notification_service
        )
        
        # 該当データなし
        mock_db_session.get.return_value = None
        
        with pytest.raises(ValidationError, match="Contact not found"):
            await usecase.process_contact("nonexistent_contact")
            
    @pytest.mark.asyncio
    async def test_process_contact_already_analyzed(
        self,
        mock_db_session,
        mock_gemini_service,
        mock_notification_service,
        sample_contact
    ):
        """既に分析済みのお問い合わせのテスト"""
        usecase = AIAnalysisUseCase(
            db_session=mock_db_session,
            gemini_service=mock_gemini_service,
            notification_service=mock_notification_service
        )
        
        # 既存の分析結果を模擬
        existing_analysis = ContactAIAnalysis(
            contact_id="contact_123",
            category=CategoryType.GENERAL,
            urgency=UrgencyLevel.MEDIUM,
            sentiment=SentimentType.NEUTRAL,
            confidence_score=0.8,
            summary="既存の分析",
            created_at=datetime.now()
        )
        
        mock_db_session.get.return_value = sample_contact
        mock_db_session.query.return_value.filter.return_value.first.return_value = existing_analysis
        
        result = await usecase.process_contact("contact_123")
        
        assert result["status"] == "already_analyzed"
        assert result["existing_analysis"] is not None
        
        # 新しい分析は実行されないことを確認
        mock_gemini_service.analyze_contact.assert_not_called()


class TestAIAnalysisUseCaseErrorHandling:
    """AIAnalysisUseCase エラーハンドリングテスト"""
    
    @pytest.mark.asyncio
    async def test_process_contact_gemini_service_error(
        self,
        mock_db_session,
        mock_gemini_service,
        mock_notification_service,
        sample_contact
    ):
        """GeminiServiceエラー時の処理テスト"""
        usecase = AIAnalysisUseCase(
            db_session=mock_db_session,
            gemini_service=mock_gemini_service,
            notification_service=mock_notification_service
        )
        
        mock_db_session.get.return_value = sample_contact
        
        # GeminiServiceがエラーを返すように設定
        mock_gemini_service.analyze_contact.side_effect = AIProcessingError(
            "AI analysis failed",
            service="gemini"
        )
        
        result = await usecase.process_contact("contact_123")
        
        assert result["status"] == "failed"
        assert result["error"]["type"] == "ai_processing_error"
        assert result["fallback_analysis"] is not None  # フォールバック分析が実行される
        
        # エラーログが記録されることを確認
        assert "error_details" in result
        
    @pytest.mark.asyncio
    async def test_process_contact_database_error(
        self,
        mock_db_session,
        mock_gemini_service,
        mock_notification_service,
        sample_contact
    ):
        """データベースエラー時の処理テスト"""
        usecase = AIAnalysisUseCase(
            db_session=mock_db_session,
            gemini_service=mock_gemini_service,
            notification_service=mock_notification_service
        )
        
        mock_db_session.get.return_value = sample_contact
        
        # データベース保存時にエラーを設定
        mock_db_session.commit.side_effect = SQLAlchemyError("Database connection lost")
        
        with pytest.raises(DatabaseConnectionError):
            await usecase.process_contact("contact_123")
            
        # ロールバックが呼び出されることを確認
        mock_db_session.rollback.assert_called()
        
    @pytest.mark.asyncio
    async def test_process_contact_timeout_handling(
        self,
        mock_db_session,
        mock_gemini_service,
        mock_notification_service,
        sample_contact
    ):
        """処理タイムアウトハンドリングテスト"""
        usecase = AIAnalysisUseCase(
            db_session=mock_db_session,
            gemini_service=mock_gemini_service,
            notification_service=mock_notification_service,
            max_processing_time=1  # 1秒でタイムアウト
        )
        
        mock_db_session.get.return_value = sample_contact
        
        # 長時間の処理を模擬
        async def slow_analysis(contact_data):
            await asyncio.sleep(2)  # 2秒待機（タイムアウトより長い）
            return {"category": CategoryType.GENERAL}
            
        mock_gemini_service.analyze_contact.side_effect = slow_analysis
        
        result = await usecase.process_contact("contact_123")
        
        assert result["status"] == "timeout"
        assert result["processing_time"] >= 1
        assert result["fallback_analysis"] is not None


class TestAIAnalysisUseCaseBulkProcessing:
    """AIAnalysisUseCase バルク処理テスト"""
    
    @pytest.mark.asyncio
    async def test_process_bulk_contacts_success(
        self,
        mock_db_session,
        mock_gemini_service,
        mock_notification_service
    ):
        """複数お問い合わせの一括処理成功テスト"""
        usecase = AIAnalysisUseCase(
            db_session=mock_db_session,
            gemini_service=mock_gemini_service,
            notification_service=mock_notification_service
        )
        
        # 複数のContactを模擬
        contacts = [
            Mock(id="contact_1", message="メッセージ1"),
            Mock(id="contact_2", message="メッセージ2"),
            Mock(id="contact_3", message="メッセージ3")
        ]
        
        mock_db_session.query.return_value.filter.return_value.all.return_value = contacts
        
        results = await usecase.process_bulk_contacts(["contact_1", "contact_2", "contact_3"])
        
        assert len(results) == 3
        assert all(r["status"] in ["completed", "failed"] for r in results)
        
        # 各お問い合わせに対してGeminiServiceが呼び出されたことを確認
        assert mock_gemini_service.analyze_contact.call_count == 3
        
    @pytest.mark.asyncio
    async def test_process_bulk_contacts_partial_failure(
        self,
        mock_db_session,
        mock_gemini_service,
        mock_notification_service
    ):
        """一括処理での部分的失敗テスト"""
        usecase = AIAnalysisUseCase(
            db_session=mock_db_session,
            gemini_service=mock_gemini_service,
            notification_service=mock_notification_service
        )
        
        # 1つのお問い合わせでエラーを発生させる
        def mock_analyze(contact_data):
            if contact_data.get("message") == "エラーメッセージ":
                raise AIProcessingError("Analysis failed")
            return {
                "category": CategoryType.GENERAL,
                "urgency": UrgencyLevel.MEDIUM,
                "sentiment": SentimentType.NEUTRAL,
                "confidence_score": 0.8,
                "summary": "テスト分析"
            }
            
        mock_gemini_service.analyze_contact.side_effect = mock_analyze
        
        contacts = [
            Mock(id="contact_1", message="正常メッセージ"),
            Mock(id="contact_2", message="エラーメッセージ"),  # これがエラーになる
            Mock(id="contact_3", message="正常メッセージ")
        ]
        
        mock_db_session.query.return_value.filter.return_value.all.return_value = contacts
        
        results = await usecase.process_bulk_contacts(["contact_1", "contact_2", "contact_3"])
        
        # 1つが失敗、2つが成功
        success_count = len([r for r in results if r["status"] == "completed"])
        failure_count = len([r for r in results if r["status"] == "failed"])
        
        assert success_count == 2
        assert failure_count == 1


class TestAIAnalysisUseCaseRetryMechanism:
    """AIAnalysisUseCase リトライ機構テスト"""
    
    @pytest.mark.asyncio
    async def test_process_contact_retry_on_temporary_failure(
        self,
        mock_db_session,
        mock_gemini_service,
        mock_notification_service,
        sample_contact
    ):
        """一時的な障害時のリトライテスト"""
        usecase = AIAnalysisUseCase(
            db_session=mock_db_session,
            gemini_service=mock_gemini_service,
            notification_service=mock_notification_service,
            max_retries=3
        )
        
        mock_db_session.get.return_value = sample_contact
        
        # 2回失敗してから成功するモック
        call_count = 0
        async def mock_analyze(contact_data):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise AIProcessingError("Temporary failure", service="gemini")
            return {
                "category": CategoryType.GENERAL,
                "urgency": UrgencyLevel.MEDIUM,
                "sentiment": SentimentType.NEUTRAL,
                "confidence_score": 0.8,
                "summary": "成功した分析"
            }
            
        mock_gemini_service.analyze_contact.side_effect = mock_analyze
        
        result = await usecase.process_contact("contact_123")
        
        assert result["status"] == "completed"
        assert result["retry_count"] == 2  # 2回リトライした
        assert call_count == 3  # 合計3回呼び出し
        
    @pytest.mark.asyncio
    async def test_process_contact_max_retries_exceeded(
        self,
        mock_db_session,
        mock_gemini_service,
        mock_notification_service,
        sample_contact
    ):
        """最大リトライ回数超過テスト"""
        usecase = AIAnalysisUseCase(
            db_session=mock_db_session,
            gemini_service=mock_gemini_service,
            notification_service=mock_notification_service,
            max_retries=2
        )
        
        mock_db_session.get.return_value = sample_contact
        
        # 常に失敗するモック
        mock_gemini_service.analyze_contact.side_effect = AIProcessingError(
            "Persistent failure", 
            service="gemini"
        )
        
        result = await usecase.process_contact("contact_123")
        
        assert result["status"] == "failed"
        assert result["retry_count"] == 2
        assert result["fallback_analysis"] is not None
        
        # 最大リトライ回数分呼び出されることを確認
        assert mock_gemini_service.analyze_contact.call_count == 3  # 初回 + 2回リトライ


class TestAIAnalysisUseCasePerformanceTracking:
    """AIAnalysisUseCase パフォーマンス追跡テスト"""
    
    @pytest.mark.asyncio
    async def test_process_contact_performance_tracking(
        self,
        mock_db_session,
        mock_gemini_service,
        mock_notification_service,
        sample_contact
    ):
        """パフォーマンス追跡テスト"""
        usecase = AIAnalysisUseCase(
            db_session=mock_db_session,
            gemini_service=mock_gemini_service,
            notification_service=mock_notification_service
        )
        
        mock_db_session.get.return_value = sample_contact
        
        # 処理時間を模擬
        async def timed_analysis(contact_data):
            await asyncio.sleep(0.1)  # 0.1秒の処理時間
            return {
                "category": CategoryType.GENERAL,
                "urgency": UrgencyLevel.MEDIUM,
                "sentiment": SentimentType.NEUTRAL,
                "confidence_score": 0.85,
                "summary": "テスト分析",
                "analysis_time": 0.1
            }
            
        mock_gemini_service.analyze_contact.side_effect = timed_analysis
        
        result = await usecase.process_contact("contact_123")
        
        assert "processing_time" in result
        assert result["processing_time"] >= 0.1
        assert result["performance_metrics"] is not None
        
        # SLA（2分）以内であることを確認
        assert result["processing_time"] < 120
        
    @pytest.mark.asyncio
    async def test_get_processing_statistics(
        self,
        mock_db_session,
        mock_gemini_service,
        mock_notification_service
    ):
        """処理統計取得テスト"""
        usecase = AIAnalysisUseCase(
            db_session=mock_db_session,
            gemini_service=mock_gemini_service,
            notification_service=mock_notification_service
        )
        
        # 模擬統計データ
        mock_stats = [
            Mock(processing_time=10.5, status="completed"),
            Mock(processing_time=15.2, status="completed"),
            Mock(processing_time=8.7, status="failed"),
            Mock(processing_time=12.1, status="completed")
        ]
        
        mock_db_session.query.return_value.filter.return_value.all.return_value = mock_stats
        
        stats = await usecase.get_processing_statistics(hours=24)
        
        assert stats["total_processed"] == 4
        assert stats["success_rate"] == 0.75  # 3/4 成功
        assert stats["average_processing_time"] > 0
        assert "sla_compliance_rate" in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])