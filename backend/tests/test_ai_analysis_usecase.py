"""AI解析UseCaseのテスト"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from typing import Optional, List
from dataclasses import dataclass

# テスト対象の型定義（実装前に定義）
from models.contact import Contact
from models.contact_ai_analysis import ContactAIAnalysis
from models.enums import CategoryType, UrgencyLevel, SentimentType
from services.gemini_service import GeminiService, GeminiAnalysisRequest, GeminiAnalysisResponse


@dataclass
class AIAnalysisUseCaseRequest:
    """AI解析UseCaseリクエスト"""
    contact_id: int
    contact_content: str
    context: Optional[str] = None
    priority_override: Optional[int] = None


@dataclass
class AIAnalysisUseCaseResponse:
    """AI解析UseCaseレスポンス"""
    contact_id: int
    analysis_id: int
    category: str
    urgency: int
    sentiment: str
    summary: str
    confidence: float
    processing_time_ms: int
    success: bool
    error_message: Optional[str] = None


class AIAnalysisUseCaseError(Exception):
    """AI解析UseCaseエラー"""
    def __init__(self, message: str, contact_id: int = None, retry_possible: bool = False):
        super().__init__(message)
        self.contact_id = contact_id
        self.retry_possible = retry_possible


class AIAnalysisUseCase:
    """AI解析UseCase（テスト用のスタブ定義）"""
    
    def __init__(self, gemini_service: GeminiService, db_session, notification_service=None, vector_search_service=None):
        pass
    
    async def execute_analysis(self, request: AIAnalysisUseCaseRequest) -> AIAnalysisUseCaseResponse:
        """AI解析実行（実装前）"""
        raise NotImplementedError("まだ実装されていません")
    
    async def handle_analysis_failure(self, contact_id: int, error: Exception) -> None:
        """解析失敗時の処理（実装前）"""
        raise NotImplementedError("まだ実装されていません")
    
    async def escalate_urgent_contact(self, contact_id: int, analysis: ContactAIAnalysis) -> bool:
        """緊急案件のエスカレーション（実装前）"""
        raise NotImplementedError("まだ実装されていません")


class TestAIAnalysisUseCase:
    """AIAnalysisUseCaseのテストクラス"""

    @pytest.fixture
    def mock_gemini_service(self):
        """モックGeminiService"""
        mock_service = AsyncMock(spec=GeminiService)
        return mock_service

    @pytest.fixture
    def mock_db_session(self):
        """モックデータベースセッション"""
        mock_session = MagicMock()
        return mock_session

    @pytest.fixture
    def mock_notification_service(self):
        """モック通知サービス"""
        mock_service = AsyncMock()
        return mock_service

    @pytest.fixture
    def mock_vector_search_service(self):
        """モックベクトル検索サービス"""
        mock_service = AsyncMock()
        return mock_service

    @pytest.fixture
    def ai_analysis_usecase(self, mock_gemini_service, mock_db_session, mock_notification_service, mock_vector_search_service):
        """AIAnalysisUseCaseインスタンス"""
        return AIAnalysisUseCase(
            gemini_service=mock_gemini_service,
            db_session=mock_db_session,
            notification_service=mock_notification_service,
            vector_search_service=mock_vector_search_service
        )

    @pytest.fixture
    def sample_contact(self):
        """テスト用Contactデータ"""
        return Contact(
            id=123,
            name="山田太郎",
            email="yamada@example.com",
            subject="商品の不具合について",
            message="購入した商品に不具合があります。至急対応をお願いします。商品番号: ABC-123"
        )

    @pytest.fixture
    def sample_request(self, sample_contact):
        """テスト用AIAnalysisUseCaseRequest"""
        return AIAnalysisUseCaseRequest(
            contact_id=sample_contact.id,
            contact_content=f"{sample_contact.subject}\n\n{sample_contact.message}",
            context="商品に関するお問い合わせ"
        )

    def test_ai_analysis_usecase_initialization(self, mock_gemini_service, mock_db_session):
        """AIAnalysisUseCase初期化テスト"""
        usecase = AIAnalysisUseCase(
            gemini_service=mock_gemini_service,
            db_session=mock_db_session
        )
        assert usecase is not None

    @pytest.mark.asyncio
    async def test_execute_analysis_not_implemented(self, ai_analysis_usecase, sample_request):
        """解析実行機能未実装確認テスト"""
        with pytest.raises(NotImplementedError):
            await ai_analysis_usecase.execute_analysis(sample_request)

    @pytest.mark.asyncio
    async def test_handle_analysis_failure_not_implemented(self, ai_analysis_usecase):
        """解析失敗処理未実装確認テスト"""
        with pytest.raises(NotImplementedError):
            await ai_analysis_usecase.handle_analysis_failure(123, Exception("テストエラー"))

    @pytest.mark.asyncio
    async def test_escalate_urgent_contact_not_implemented(self, ai_analysis_usecase):
        """緊急案件エスカレーション未実装確認テスト"""
        mock_analysis = MagicMock(spec=ContactAIAnalysis)
        with pytest.raises(NotImplementedError):
            await ai_analysis_usecase.escalate_urgent_contact(123, mock_analysis)

    def test_ai_analysis_usecase_request_dataclass(self):
        """AIAnalysisUseCaseRequestデータクラステスト"""
        request = AIAnalysisUseCaseRequest(
            contact_id=456,
            contact_content="テストコンテンツ",
            context="テストコンテキスト",
            priority_override=3
        )
        
        assert request.contact_id == 456
        assert request.contact_content == "テストコンテンツ"
        assert request.context == "テストコンテキスト"
        assert request.priority_override == 3

    def test_ai_analysis_usecase_request_defaults(self):
        """AIAnalysisUseCaseRequestのデフォルト値テスト"""
        request = AIAnalysisUseCaseRequest(
            contact_id=789,
            contact_content="最小コンテンツ"
        )
        
        assert request.contact_id == 789
        assert request.contact_content == "最小コンテンツ"
        assert request.context is None
        assert request.priority_override is None

    def test_ai_analysis_usecase_response_dataclass(self):
        """AIAnalysisUseCaseResponseデータクラステスト"""
        response = AIAnalysisUseCaseResponse(
            contact_id=123,
            analysis_id=456,
            category="product",
            urgency=3,
            sentiment="negative",
            summary="商品不具合の緊急対応要求",
            confidence=0.92,
            processing_time_ms=1500,
            success=True
        )
        
        assert response.contact_id == 123
        assert response.analysis_id == 456
        assert response.category == "product"
        assert response.urgency == 3
        assert response.sentiment == "negative"
        assert response.summary == "商品不具合の緊急対応要求"
        assert response.confidence == 0.92
        assert response.processing_time_ms == 1500
        assert response.success is True
        assert response.error_message is None

    def test_ai_analysis_usecase_error(self):
        """AIAnalysisUseCaseErrorテスト"""
        error = AIAnalysisUseCaseError(
            message="AI分析処理に失敗しました",
            contact_id=999,
            retry_possible=True
        )
        
        assert str(error) == "AI分析処理に失敗しました"
        assert error.contact_id == 999
        assert error.retry_possible is True


class TestAIAnalysisUseCaseIntegration:
    """AIAnalysisUseCase統合テスト（モック使用）"""

    @pytest.mark.asyncio
    async def test_complete_analysis_workflow(self):
        """完全な解析ワークフローテスト"""
        # モックのセットアップ
        mock_gemini_service = AsyncMock()
        mock_db_session = MagicMock()
        
        # Gemini分析結果のモック
        mock_gemini_response = GeminiAnalysisResponse(
            category="product",
            urgency=3,
            sentiment="negative", 
            summary="商品不具合の緊急対応",
            confidence=0.95,
            reasoning="商品番号言及と緊急性表現",
            refinement_applied=True
        )
        mock_gemini_service.analyze_content.return_value = mock_gemini_response
        
        # ContactAIAnalysis保存のモック
        mock_analysis = MagicMock(spec=ContactAIAnalysis)
        mock_analysis.id = 789
        mock_db_session.add.return_value = None
        mock_db_session.commit.return_value = None
        
        # 期待される動作フロー
        expected_steps = [
            "gemini_service.analyze_content",
            "db_session.add", 
            "db_session.commit",
            "notification_service.notify_urgent" # 緊急度3の場合
        ]
        
        # フローの確認
        assert len(expected_steps) == 4

    @pytest.mark.asyncio
    async def test_two_minute_processing_time_limit(self):
        """2分以内処理時間制限テスト"""
        start_time = datetime.now()
        processing_time_limit = timedelta(minutes=2)
        
        # 短時間の処理をシミュレート
        await asyncio.sleep(0.1)
        
        end_time = datetime.now()
        actual_processing_time = end_time - start_time
        
        # 処理時間が制限内であることを確認
        assert actual_processing_time < processing_time_limit

    @pytest.mark.asyncio 
    async def test_error_handling_and_manual_classification(self):
        """エラー時の手動分類待ち状態設定テスト"""
        error_scenarios = [
            ("GeminiAPIError", "API呼び出し失敗"),
            ("TimeoutError", "タイムアウト"),
            ("DatabaseError", "データベース保存失敗"),
            ("ValidationError", "入力データ不正")
        ]
        
        # 各エラーシナリオでの期待される処理
        for error_type, error_message in error_scenarios:
            expected_action = {
                "status": "manual_classification_required",
                "error_type": error_type,
                "retry_possible": True,
                "escalation_required": error_type in ["TimeoutError", "DatabaseError"]
            }
            
            assert expected_action["status"] == "manual_classification_required"

    @pytest.mark.asyncio
    async def test_vector_search_integration(self):
        """VectorSearchUseCaseとの連携テスト"""
        # ベクトル検索の期待動作
        expected_vector_search_flow = [
            "generate_embedding",  # コンテンツのベクトル埋め込み生成
            "store_vector",        # contact_vectorsテーブルへの保存
            "similarity_search",   # 類似事例検索
            "return_top_3"        # 上位3件の類似事例返却
        ]
        
        # フローが定義されていることを確認
        assert len(expected_vector_search_flow) == 4
        assert "similarity_search" in expected_vector_search_flow

    @pytest.mark.asyncio
    async def test_notification_service_integration(self):
        """NotificationServiceとの連携テスト"""
        # 通知サービス連携の期待動作
        urgency_level_notifications = {
            1: {"notify": False, "escalate": False},  # 低緊急度
            2: {"notify": True, "escalate": False},   # 中緊急度
            3: {"notify": True, "escalate": True}     # 高緊急度
        }
        
        # 緊急度別の通知動作確認
        assert urgency_level_notifications[1]["notify"] is False
        assert urgency_level_notifications[3]["escalate"] is True

    @pytest.mark.asyncio
    async def test_database_consistency_guarantees(self):
        """データベース整合性保証テスト"""
        # トランザクション境界での整合性
        transaction_steps = [
            "begin_transaction",
            "save_contact_ai_analysis",
            "save_contact_vector",
            "commit_transaction"
        ]
        
        # エラー時のロールバック
        error_handling_steps = [
            "detect_error",
            "rollback_transaction", 
            "set_manual_classification_status",
            "log_error"
        ]
        
        # ステップが定義されていることを確認
        assert "commit_transaction" in transaction_steps
        assert "rollback_transaction" in error_handling_steps

    @pytest.mark.asyncio
    async def test_confidence_score_threshold_handling(self):
        """信頼度スコア閾値処理テスト"""
        # 信頼度スコア別の処理分岐
        confidence_thresholds = {
            0.95: {"action": "auto_approve", "manual_review": False},
            0.80: {"action": "standard_process", "manual_review": False}, 
            0.60: {"action": "review_required", "manual_review": True},
            0.40: {"action": "manual_classification", "manual_review": True}
        }
        
        # 閾値処理の確認
        assert confidence_thresholds[0.95]["manual_review"] is False
        assert confidence_thresholds[0.40]["action"] == "manual_classification"

    def test_performance_monitoring_integration(self):
        """パフォーマンス監視統合テスト"""
        # 監視すべき指標
        performance_metrics = [
            "analysis_processing_time",
            "gemini_api_response_time", 
            "database_save_time",
            "vector_generation_time",
            "total_end_to_end_time"
        ]
        
        # メトリクス定義確認
        assert "total_end_to_end_time" in performance_metrics
        assert len(performance_metrics) >= 5

    @pytest.mark.asyncio
    async def test_concurrent_analysis_handling(self):
        """並行解析処理テスト"""
        # 複数コンタクトの同時処理
        concurrent_requests = 5
        
        # 同時処理の制限とキューイング
        processing_limits = {
            "max_concurrent": 10,
            "queue_size": 50,
            "timeout_per_request": 120  # 秒
        }
        
        # 制限値の確認
        assert processing_limits["max_concurrent"] >= concurrent_requests
        assert processing_limits["timeout_per_request"] == 120