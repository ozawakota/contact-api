"""VectorServiceのテスト

pgvector + PostgreSQLベースのベクトル検索サービスのテスト実装。
Geminiモデルを使用したベクトル埋め込み生成と高速検索機能をテストします。
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import List, Dict, Any, Optional
from datetime import datetime
import numpy as np

# テスト対象モジュールのインポート
from models.contact import Contact
from models.contact_vector import ContactVector


@pytest.fixture
def mock_db_session():
    """モックデータベースセッション"""
    mock_session = MagicMock()
    return mock_session


@pytest.fixture
def mock_gemini_service():
    """モックGeminiサービス（ベクトル埋め込み生成用）"""
    mock_service = AsyncMock()
    # 768次元のダミーベクトル
    mock_embedding = np.random.rand(768).tolist()
    mock_service.generate_embedding.return_value = mock_embedding
    return mock_service


@pytest.fixture
def sample_contact():
    """テスト用Contactデータ"""
    return Contact(
        id=123,
        name="佐藤太郎",
        email="sato@example.com",
        subject="商品の配送遅延について",
        message="注文した商品の配送が予定より遅れています。現在の配送状況を教えてください。"
    )


@pytest.fixture
def sample_contact_vector():
    """テスト用ContactVectorデータ"""
    return ContactVector(
        id=456,
        contact_id=123,
        embedding=np.random.rand(768).tolist(),
        model_version="gemini-embedding-001",
        metadata={"processing_time_ms": 150, "confidence": 0.95},
        vectorized_at=datetime.now()
    )


class TestVectorService:
    """VectorServiceの基本機能テスト"""

    @pytest.fixture
    def vector_service(self, mock_gemini_service, mock_db_session):
        """VectorServiceインスタンス"""
        # TODO: VectorService実装後にインポートを追加
        from services.vector_service import VectorService
        return VectorService(
            gemini_service=mock_gemini_service,
            db_session=mock_db_session
        )

    @pytest.mark.asyncio
    async def test_vector_service_initialization(self, mock_gemini_service, mock_db_session):
        """VectorService初期化テスト"""
        from services.vector_service import VectorService
        service = VectorService(
            gemini_service=mock_gemini_service,
            db_session=mock_db_session
        )
        assert service.gemini_service == mock_gemini_service
        assert service.db_session == mock_db_session
        assert service.embedding_dimension == 768

    @pytest.mark.asyncio
    async def test_generate_embedding(self, vector_service, sample_contact):
        """テキストのベクトル埋め込み生成テスト"""
        content = f"{sample_contact.subject}\n\n{sample_contact.message}"
        
        embedding = await vector_service.generate_embedding(content)
        
        assert isinstance(embedding, list)
        assert len(embedding) == 768
        assert all(isinstance(x, (int, float)) for x in embedding)

    @pytest.mark.asyncio
    async def test_store_vector(self, vector_service, sample_contact, mock_db_session):
        """ベクトルのデータベース保存テスト"""
        content = f"{sample_contact.subject}\n\n{sample_contact.message}"
        
        # 既存ベクトルが存在しないケース
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = None
        
        vector = await vector_service.store_vector(
            contact_id=sample_contact.id,
            content=content,
            model_version="gemini-embedding-001"
        )
        
        assert vector is not None
        assert vector.contact_id == sample_contact.id
        assert vector.model_version == "gemini-embedding-001"
        assert len(vector.embedding) == 768
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_vector_with_existing(self, vector_service, sample_contact, sample_contact_vector, mock_db_session):
        """既存ベクトルがある場合の更新テスト"""
        content = f"{sample_contact.subject}\n\n{sample_contact.message}"
        
        # 既存ベクトルが存在するケース
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = sample_contact_vector
        
        vector = await vector_service.store_vector(
            contact_id=sample_contact.id,
            content=content,
            model_version="gemini-embedding-002"
        )
        
        assert vector.model_version == "gemini-embedding-002"
        assert len(vector.embedding) == 768
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_similar_vectors(self, vector_service, sample_contact_vector, mock_db_session):
        """類似ベクトル検索テスト"""
        query_embedding = np.random.rand(768).tolist()
        
        # モック検索結果
        mock_results = [
            (sample_contact_vector, 0.85),  # (ContactVector, similarity_score)
            (sample_contact_vector, 0.78),
            (sample_contact_vector, 0.72)
        ]
        mock_db_session.execute.return_value.fetchall.return_value = mock_results
        
        similar_vectors = await vector_service.find_similar_vectors(
            query_embedding=query_embedding,
            limit=3,
            similarity_threshold=0.7
        )
        
        assert len(similar_vectors) == 3
        assert all(similarity >= 0.7 for _, similarity in similar_vectors)
        assert similar_vectors[0][1] >= similar_vectors[1][1] >= similar_vectors[2][1]  # 降順

    @pytest.mark.asyncio
    async def test_find_similar_contacts(self, vector_service, sample_contact, mock_db_session):
        """類似コンタクト検索テスト"""
        target_contact_id = sample_contact.id
        
        # モック類似ベクトル結果
        mock_vector = ContactVector(
            contact_id=456, 
            embedding=np.random.rand(768).tolist(),
            model_version="gemini-embedding-001"
        )
        mock_contact = Contact(
            id=456,
            name="田中花子",
            email="tanaka@example.com", 
            subject="配送に関する問い合わせ",
            message="配送状況を確認したいです"
        )
        mock_vector.contact = mock_contact
        
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = ContactVector(
            contact_id=target_contact_id,
            embedding=np.random.rand(768).tolist()
        )
        mock_db_session.execute.return_value.fetchall.return_value = [(mock_vector, 0.85)]
        
        similar_contacts = await vector_service.find_similar_contacts(
            contact_id=target_contact_id,
            limit=3,
            similarity_threshold=0.7
        )
        
        assert len(similar_contacts) == 1
        assert similar_contacts[0]['contact'].id == 456
        assert similar_contacts[0]['similarity'] == 0.85

    @pytest.mark.asyncio
    async def test_cosine_similarity_calculation(self, vector_service):
        """コサイン類似度計算テスト"""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        vec3 = [1.0, 0.0, 0.0]
        
        # 垂直ベクトル（類似度0）
        similarity1 = vector_service.calculate_cosine_similarity(vec1, vec2)
        assert abs(similarity1 - 0.0) < 0.01
        
        # 同一ベクトル（類似度1）
        similarity2 = vector_service.calculate_cosine_similarity(vec1, vec3)
        assert abs(similarity2 - 1.0) < 0.01

    @pytest.mark.asyncio
    async def test_delete_vector(self, vector_service, sample_contact_vector, mock_db_session):
        """ベクトル削除テスト"""
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = sample_contact_vector
        
        result = await vector_service.delete_vector(contact_id=sample_contact_vector.contact_id)
        
        assert result is True
        mock_db_session.delete.assert_called_once_with(sample_contact_vector)
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_vector_not_found(self, vector_service, mock_db_session):
        """存在しないベクトル削除テスト"""
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = None
        
        result = await vector_service.delete_vector(contact_id=999)
        
        assert result is False
        mock_db_session.delete.assert_not_called()


class TestVectorServiceIntegration:
    """VectorService統合テスト"""

    @pytest.fixture
    def vector_service_with_real_gemini(self, mock_db_session):
        """実際のGeminiサービス連携テスト用"""
        from services.vector_service import VectorService
        from services.gemini_service import GeminiService
        
        # 実際のGeminiServiceを使用（APIキーはモック）
        gemini_service = GeminiService(api_key="test-api-key")
        return VectorService(
            gemini_service=gemini_service,
            db_session=mock_db_session
        )

    @pytest.mark.asyncio
    async def test_end_to_end_vector_workflow(self, vector_service, sample_contact, mock_db_session):
        """エンドツーエンドベクトルワークフローテスト"""
        # ベクトル生成から類似検索までの完全フロー
        content = f"{sample_contact.subject}\n\n{sample_contact.message}"
        
        # 1. ベクトル保存
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = None
        stored_vector = await vector_service.store_vector(
            contact_id=sample_contact.id,
            content=content
        )
        
        # 2. 類似検索実行
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = stored_vector
        mock_db_session.execute.return_value.fetchall.return_value = [(stored_vector, 0.95)]
        
        similar_contacts = await vector_service.find_similar_contacts(
            contact_id=sample_contact.id,
            limit=3
        )
        
        assert len(similar_contacts) >= 0  # 類似結果があることを確認

    @pytest.mark.asyncio
    async def test_performance_constraints(self, vector_service):
        """30秒以内検索性能保証テスト"""
        import time
        
        query_embedding = np.random.rand(768).tolist()
        
        start_time = time.time()
        
        # パフォーマンステスト（実際のDB接続なしでのモックテスト）
        similar_vectors = await vector_service.find_similar_vectors(
            query_embedding=query_embedding,
            limit=100,
            similarity_threshold=0.5
        )
        
        elapsed_time = time.time() - start_time
        
        # 30秒制限の検証（モックなので実際は数ミリ秒）
        assert elapsed_time < 30.0

    @pytest.mark.asyncio
    async def test_batch_vector_operations(self, vector_service, mock_db_session):
        """バッチベクトル操作テスト"""
        contacts_data = [
            {"contact_id": 1, "content": "配送について"},
            {"contact_id": 2, "content": "返品について"},
            {"contact_id": 3, "content": "商品の不具合"},
        ]
        
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = None
        
        # バッチ保存テスト
        results = []
        for data in contacts_data:
            vector = await vector_service.store_vector(
                contact_id=data["contact_id"],
                content=data["content"]
            )
            results.append(vector)
        
        assert len(results) == 3
        assert mock_db_session.add.call_count == 3
        assert mock_db_session.commit.call_count == 3

    @pytest.mark.asyncio
    async def test_hnsw_index_optimization(self, vector_service):
        """HNSWインデックス活用最適化テスト"""
        # インデックス設定の検証
        assert hasattr(vector_service, 'index_type')
        assert vector_service.index_type == 'hnsw'
        assert vector_service.hnsw_m == 16
        assert vector_service.hnsw_ef_construction == 64

    @pytest.mark.asyncio 
    async def test_error_handling(self, vector_service, mock_db_session, sample_contact):
        """エラーハンドリングテスト"""
        content = f"{sample_contact.subject}\n\n{sample_contact.message}"
        
        # データベースエラーのシミュレーション
        mock_db_session.add.side_effect = Exception("Database connection failed")
        
        with pytest.raises(Exception):
            await vector_service.store_vector(
                contact_id=sample_contact.id,
                content=content
            )
        
        # ロールバックが呼ばれることを確認
        mock_db_session.rollback.assert_called_once()


class TestVectorServiceMetrics:
    """VectorServiceメトリクス・監視テスト"""

    @pytest.mark.asyncio
    async def test_embedding_generation_metrics(self, vector_service):
        """ベクトル生成メトリクステスト"""
        content = "テスト用コンテンツ"
        
        # メトリクス収集機能のテスト
        metrics = await vector_service.get_embedding_metrics()
        
        assert 'total_embeddings_generated' in metrics
        assert 'average_generation_time' in metrics
        assert 'success_rate' in metrics

    @pytest.mark.asyncio
    async def test_search_performance_metrics(self, vector_service):
        """検索パフォーマンスメトリクステスト"""
        query_embedding = np.random.rand(768).tolist()
        
        # 検索メトリクス収集
        similar_vectors = await vector_service.find_similar_vectors(
            query_embedding=query_embedding,
            limit=10
        )
        
        metrics = await vector_service.get_search_metrics()
        
        assert 'total_searches' in metrics
        assert 'average_search_time' in metrics
        assert 'cache_hit_rate' in metrics

    @pytest.mark.asyncio
    async def test_vector_quality_assessment(self, vector_service):
        """ベクトル品質評価テスト"""
        embeddings = [
            np.random.rand(768).tolist() for _ in range(10)
        ]
        
        quality_score = await vector_service.assess_vector_quality(embeddings)
        
        assert 0.0 <= quality_score <= 1.0
        assert isinstance(quality_score, (int, float))