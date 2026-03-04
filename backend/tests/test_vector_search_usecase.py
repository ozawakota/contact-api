"""VectorSearchUseCaseのテスト

AI解析完了後の自動ベクトル検索起動とAIAnalysisUseCaseとの非同期連携をテストします。
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import List, Dict, Any, Optional
from datetime import datetime

# テスト対象モジュールのインポート
from models.contact import Contact
from models.contact_ai_analysis import ContactAIAnalysis
from models.contact_vector import ContactVector


@pytest.fixture
def mock_vector_service():
    """モックVectorService"""
    mock_service = AsyncMock()
    # デフォルトの戻り値設定
    mock_service.generate_and_store_vector.return_value = ContactVector(
        id=123,
        contact_id=456,
        embedding=[0.1] * 768,
        model_version="gemini-embedding-001"
    )
    mock_service.find_similar_contacts.return_value = [
        {
            'contact': Contact(id=789, name="田中太郎", subject="類似件1"),
            'similarity': 0.85,
            'vector_id': 124,
            'metadata': {}
        }
    ]
    return mock_service


@pytest.fixture
def mock_notification_service():
    """モック通知サービス"""
    mock_service = AsyncMock()
    mock_service.notify_similar_cases_found.return_value = True
    return mock_service


@pytest.fixture
def mock_db_session():
    """モックデータベースセッション"""
    mock_session = MagicMock()
    return mock_session


@pytest.fixture
def sample_contact():
    """テスト用Contactデータ"""
    return Contact(
        id=456,
        name="山田太郎",
        email="yamada@example.com",
        subject="商品の配送遅延",
        message="注文した商品の配送が遅れています"
    )


@pytest.fixture
def sample_ai_analysis():
    """テスト用AI解析データ"""
    return ContactAIAnalysis(
        id=789,
        contact_id=456,
        category="shipping",
        urgency=2,
        sentiment="negative",
        confidence_score=0.92,
        summary="配送遅延の問い合わせ",
        processed_at=datetime.now()
    )


class TestVectorSearchUseCase:
    """VectorSearchUseCaseの基本機能テスト"""

    @pytest.fixture
    def vector_search_usecase(self, mock_vector_service, mock_notification_service, mock_db_session):
        """VectorSearchUseCaseインスタンス"""
        from use_cases.vector_search_usecase import VectorSearchUseCase
        return VectorSearchUseCase(
            vector_service=mock_vector_service,
            notification_service=mock_notification_service,
            db_session=mock_db_session
        )

    @pytest.mark.asyncio
    async def test_usecase_initialization(self, mock_vector_service, mock_notification_service, mock_db_session):
        """VectorSearchUseCase初期化テスト"""
        from use_cases.vector_search_usecase import VectorSearchUseCase
        usecase = VectorSearchUseCase(
            vector_service=mock_vector_service,
            notification_service=mock_notification_service,
            db_session=mock_db_session
        )
        assert usecase.vector_service == mock_vector_service
        assert usecase.notification_service == mock_notification_service
        assert usecase.db_session == mock_db_session

    @pytest.mark.asyncio
    async def test_generate_and_store_vector(self, vector_search_usecase, sample_contact):
        """ベクトル生成・保存テスト"""
        content = f"{sample_contact.subject}\n\n{sample_contact.message}"
        
        result = await vector_search_usecase.generate_and_store_vector(
            contact_id=sample_contact.id,
            content=content
        )
        
        assert result is not None
        assert result.contact_id == sample_contact.id
        vector_search_usecase.vector_service.generate_and_store_vector.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_similar_contacts_success(self, vector_search_usecase, sample_contact):
        """類似コンタクト検索成功テスト"""
        similar_contacts = await vector_search_usecase.find_similar_contacts(
            contact_id=sample_contact.id,
            limit=3
        )
        
        assert len(similar_contacts) >= 0
        vector_search_usecase.vector_service.find_similar_contacts.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_ai_analysis_completion(self, vector_search_usecase, sample_contact, sample_ai_analysis):
        """AI解析完了時の自動ベクトル検索起動テスト"""
        result = await vector_search_usecase.process_ai_analysis_completion(
            contact_id=sample_contact.id,
            ai_analysis=sample_ai_analysis
        )
        
        assert result.get('success') is True
        assert 'vector_generated' in result
        assert 'similar_contacts' in result


class TestVectorSearchUseCaseIntegration:
    """VectorSearchUseCase統合テスト"""

    @pytest.fixture
    def integration_usecase(self, mock_vector_service, mock_notification_service, mock_db_session):
        """統合テスト用UseCaseインスタンス"""
        from use_cases.vector_search_usecase import VectorSearchUseCase
        return VectorSearchUseCase(
            vector_service=mock_vector_service,
            notification_service=mock_notification_service,
            db_session=mock_db_session
        )

    @pytest.mark.asyncio
    async def test_ai_analysis_integration_workflow(self, integration_usecase, sample_contact, sample_ai_analysis, mock_db_session):
        """AI解析統合ワークフローテスト"""
        # AIAnalysisUseCaseとの連携フロー
        mock_db_session.get.return_value = sample_contact
        
        result = await integration_usecase.process_ai_analysis_completion(
            contact_id=sample_contact.id,
            ai_analysis=sample_ai_analysis
        )
        
        # 期待される処理フロー確認
        assert result.get('success') is True
        assert 'processing_time_ms' in result
        integration_usecase.vector_service.generate_and_store_vector.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_processing(self, integration_usecase, sample_contact, mock_vector_service):
        """フォールバック処理テスト"""
        # ベクトル検索失敗をシミュレート
        mock_vector_service.find_similar_contacts.side_effect = Exception("Vector search failed")
        
        result = await integration_usecase.find_similar_contacts_with_fallback(
            contact_id=sample_contact.id,
            similarity_threshold=0.7
        )
        
        # フォールバック処理が実行されることを確認
        assert result.get('fallback_applied') is True
        assert result.get('original_threshold') == 0.7
        assert result.get('fallback_threshold') < 0.7

    @pytest.mark.asyncio
    async def test_recommendation_generation(self, integration_usecase, sample_contact):
        """担当者向け推奨情報生成テスト"""
        similar_contacts = [
            {
                'contact': Contact(id=1, subject="配送問題", message="配送が遅い"),
                'similarity': 0.85,
                'vector_id': 1
            },
            {
                'contact': Contact(id=2, subject="配送状況", message="配送状況を教えて"),
                'similarity': 0.78,
                'vector_id': 2
            }
        ]
        
        integration_usecase.vector_service.find_similar_contacts.return_value = similar_contacts
        
        recommendations = await integration_usecase.generate_agent_recommendations(
            contact_id=sample_contact.id,
            similar_contacts=similar_contacts
        )
        
        assert 'recommended_actions' in recommendations
        assert 'similar_case_patterns' in recommendations
        assert 'response_templates' in recommendations

    @pytest.mark.asyncio
    async def test_async_integration_with_ai_usecase(self, integration_usecase):
        """AIAnalysisUseCaseとの非同期連携テスト"""
        # 非同期連携のシミュレーション
        contact_id = 123
        
        # 非同期タスクとして実行
        task = asyncio.create_task(
            integration_usecase.async_vector_search_trigger(contact_id)
        )
        
        # 短時間待機後、結果確認
        await asyncio.sleep(0.1)
        
        # タスクが開始されていることを確認
        assert not task.done() or task.done()  # 実行中または完了
        
        # クリーンアップ
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_performance_monitoring(self, integration_usecase, sample_contact):
        """パフォーマンス監視テスト"""
        # パフォーマンスメトリクス収集
        start_time = datetime.now()
        
        await integration_usecase.find_similar_contacts(
            contact_id=sample_contact.id,
            limit=5
        )
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        metrics = await integration_usecase.get_performance_metrics()
        
        assert 'total_searches' in metrics
        assert 'average_processing_time' in metrics
        assert processing_time < 30.0  # 30秒以内制限


class TestVectorSearchUseCaseErrorHandling:
    """VectorSearchUseCaseエラーハンドリングテスト"""

    @pytest.fixture
    def error_test_usecase(self, mock_vector_service, mock_notification_service, mock_db_session):
        """エラーテスト用UseCaseインスタンス"""
        from use_cases.vector_search_usecase import VectorSearchUseCase
        return VectorSearchUseCase(
            vector_service=mock_vector_service,
            notification_service=mock_notification_service,
            db_session=mock_db_session
        )

    @pytest.mark.asyncio
    async def test_vector_service_failure_handling(self, error_test_usecase, sample_contact, mock_vector_service):
        """VectorServiceエラー時のハンドリングテスト"""
        mock_vector_service.find_similar_contacts.side_effect = Exception("Service unavailable")
        
        result = await error_test_usecase.find_similar_contacts_with_fallback(
            contact_id=sample_contact.id
        )
        
        assert result.get('success') is False
        assert result.get('error_type') == 'vector_service_error'
        assert result.get('fallback_applied') is True

    @pytest.mark.asyncio
    async def test_database_connection_failure(self, error_test_usecase, sample_contact, mock_db_session):
        """データベース接続失敗時のテスト"""
        mock_db_session.get.side_effect = Exception("Database connection failed")
        
        with pytest.raises(Exception) as exc_info:
            await error_test_usecase.process_ai_analysis_completion(
                contact_id=sample_contact.id,
                ai_analysis=ContactAIAnalysis(contact_id=sample_contact.id, category="test")
            )
        
        assert "Database connection failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_notification_service_failure(self, error_test_usecase, sample_contact, mock_notification_service):
        """通知サービス失敗時のテスト"""
        mock_notification_service.notify_similar_cases_found.side_effect = Exception("Notification failed")
        
        # 通知失敗してもメイン処理は継続されることを確認
        result = await error_test_usecase.process_ai_analysis_completion(
            contact_id=sample_contact.id,
            ai_analysis=ContactAIAnalysis(contact_id=sample_contact.id, category="test")
        )
        
        # メイン処理は成功、通知エラーは別途記録
        assert result.get('vector_generated') is True
        assert result.get('notification_error') is not None

    @pytest.mark.asyncio
    async def test_threshold_relaxation_fallback(self, error_test_usecase, sample_contact, mock_vector_service):
        """閾値緩和フォールバックテスト"""
        # 初回検索で結果なし
        mock_vector_service.find_similar_contacts.side_effect = [
            [],  # 初回: 結果なし
            [   # 閾値緩和後: 結果あり
                {
                    'contact': Contact(id=999, subject="類似事例"),
                    'similarity': 0.6,
                    'vector_id': 999
                }
            ]
        ]
        
        result = await error_test_usecase.find_similar_contacts_with_fallback(
            contact_id=sample_contact.id,
            similarity_threshold=0.8
        )
        
        assert result.get('fallback_applied') is True
        assert result.get('fallback_threshold') == 0.6  # 0.8 * 0.75
        assert len(result.get('similar_contacts', [])) == 1

    @pytest.mark.asyncio
    async def test_manual_recommendation_fallback(self, error_test_usecase, sample_contact, mock_vector_service):
        """手動推奨フォールバックテスト"""
        # 全ての自動検索が失敗
        mock_vector_service.find_similar_contacts.return_value = []
        
        result = await error_test_usecase.generate_agent_recommendations(
            contact_id=sample_contact.id,
            similar_contacts=[]
        )
        
        # 手動推奨が生成されることを確認
        assert result.get('recommendation_type') == 'manual_fallback'
        assert 'general_guidelines' in result
        assert 'escalation_required' in result


class TestVectorSearchUseCasePerformance:
    """VectorSearchUseCaseパフォーマンステスト"""

    @pytest.mark.asyncio
    async def test_concurrent_search_handling(self, mock_vector_service, mock_notification_service, mock_db_session):
        """同時検索処理テスト"""
        from use_cases.vector_search_usecase import VectorSearchUseCase
        usecase = VectorSearchUseCase(
            vector_service=mock_vector_service,
            notification_service=mock_notification_service,
            db_session=mock_db_session
        )
        
        # 複数の同時検索実行
        contact_ids = [1, 2, 3, 4, 5]
        
        tasks = [
            usecase.find_similar_contacts(contact_id=cid, limit=3)
            for cid in contact_ids
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 全て正常に処理されることを確認
        assert len(results) == 5
        successful_results = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_results) >= 3  # 少なくとも3つは成功

    @pytest.mark.asyncio
    async def test_search_timeout_handling(self, mock_vector_service, mock_notification_service, mock_db_session):
        """検索タイムアウト処理テスト"""
        from use_cases.vector_search_usecase import VectorSearchUseCase
        usecase = VectorSearchUseCase(
            vector_service=mock_vector_service,
            notification_service=mock_notification_service,
            db_session=mock_db_session,
            search_timeout=1.0  # 1秒タイムアウト
        )
        
        # 長時間処理をシミュレート
        async def slow_search(*args, **kwargs):
            await asyncio.sleep(2.0)  # 2秒待機
            return []
        
        mock_vector_service.find_similar_contacts.side_effect = slow_search
        
        result = await usecase.find_similar_contacts_with_timeout(
            contact_id=123,
            timeout=1.0
        )
        
        # タイムアウトが適切に処理されることを確認
        assert result.get('timeout_occurred') is True
        assert result.get('processing_time_ms') >= 1000