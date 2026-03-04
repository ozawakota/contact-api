"""
Task 8.1 VectorService ユニットテスト

TDD-RED フェーズ: 失敗するテストを先に作成
- VectorService の単体テスト
- モック・スタブ作成（PostgreSQL、pgvector）
- エラーケース・境界値・セキュリティテスト
"""

import pytest
import numpy as np
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from typing import List, Dict, Any, Optional

from sqlmodel import Session
from sqlalchemy.exc import SQLAlchemyError, OperationalError

from backend.app.services.vector_service import VectorService
from backend.app.services.gemini_service import GeminiService
from backend.app.models.contact_vector import ContactVector
from backend.app.error_handling.exceptions import DatabaseConnectionError, AIProcessingError


@pytest.fixture
def mock_db_session():
    """モックデータベースセッション"""
    session = Mock(spec=Session)
    session.add = Mock()
    session.commit = Mock()
    session.rollback = Mock()
    session.close = Mock()
    session.query = Mock()
    session.execute = Mock()
    return session


@pytest.fixture
def mock_gemini_service():
    """モックGeminiService"""
    service = Mock(spec=GeminiService)
    service.generate_embedding = AsyncMock(return_value=np.random.rand(768).tolist())
    return service


@pytest.fixture
def sample_contact_vector():
    """サンプルContactVector"""
    return ContactVector(
        contact_id="contact_123",
        embedding=np.random.rand(768).tolist(),
        model_version="gemini-embedding-001",
        metadata={"text_length": 100, "language": "ja"},
        vectorized_at=datetime.now()
    )


class TestVectorServiceInitialization:
    """VectorService初期化テスト"""
    
    def test_vector_service_initialization_success(self, mock_db_session, mock_gemini_service):
        """正常な初期化テスト"""
        service = VectorService(
            db_session=mock_db_session,
            gemini_service=mock_gemini_service
        )
        
        assert service.db_session == mock_db_session
        assert service.gemini_service == mock_gemini_service
        assert service.vector_dimension == 768
        assert service.similarity_threshold == 0.7
        
    def test_vector_service_initialization_missing_db_session(self, mock_gemini_service):
        """データベースセッション未設定時のエラーテスト"""
        with pytest.raises(ValueError, match="Database session is required"):
            VectorService(db_session=None, gemini_service=mock_gemini_service)
            
    def test_vector_service_initialization_missing_gemini_service(self, mock_db_session):
        """GeminiService未設定時のエラーテスト"""
        with pytest.raises(ValueError, match="Gemini service is required"):
            VectorService(db_session=mock_db_session, gemini_service=None)


class TestVectorServiceCreateEmbedding:
    """VectorService 埋め込み作成テスト"""
    
    @pytest.mark.asyncio
    async def test_create_embedding_success(self, mock_db_session, mock_gemini_service):
        """埋め込み作成成功テスト"""
        service = VectorService(
            db_session=mock_db_session,
            gemini_service=mock_gemini_service
        )
        
        contact_id = "contact_123"
        text = "商品について詳しく教えてください"
        
        # モック設定
        expected_embedding = np.random.rand(768).tolist()
        mock_gemini_service.generate_embedding.return_value = expected_embedding
        
        result = await service.create_embedding(contact_id, text)
        
        assert result["contact_id"] == contact_id
        assert len(result["embedding"]) == 768
        assert result["model_version"] == "gemini-embedding-001"
        assert result["text_length"] == len(text)
        
        # GeminiServiceが呼び出されたことを確認
        mock_gemini_service.generate_embedding.assert_called_once_with(text)
        
        # データベースに保存されたことを確認
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_create_embedding_empty_text(self, mock_db_session, mock_gemini_service):
        """空のテキストでのエラーテスト"""
        service = VectorService(
            db_session=mock_db_session,
            gemini_service=mock_gemini_service
        )
        
        with pytest.raises(ValueError, match="Text cannot be empty"):
            await service.create_embedding("contact_123", "")
            
    @pytest.mark.asyncio
    async def test_create_embedding_text_too_long(self, mock_db_session, mock_gemini_service):
        """テキストが長すぎる場合のテスト"""
        service = VectorService(
            db_session=mock_db_session,
            gemini_service=mock_gemini_service
        )
        
        # 50,000文字の長いテキスト
        long_text = "あ" * 50000
        
        with pytest.raises(ValueError, match="Text too long"):
            await service.create_embedding("contact_123", long_text)
            
    @pytest.mark.asyncio
    async def test_create_embedding_gemini_service_error(self, mock_db_session, mock_gemini_service):
        """GeminiServiceエラー時のテスト"""
        service = VectorService(
            db_session=mock_db_session,
            gemini_service=mock_gemini_service
        )
        
        # GeminiServiceがエラーを返すように設定
        mock_gemini_service.generate_embedding.side_effect = AIProcessingError("Gemini API error")
        
        with pytest.raises(AIProcessingError, match="Gemini API error"):
            await service.create_embedding("contact_123", "テストテキスト")
            
        # エラー時はデータベースに保存されないことを確認
        mock_db_session.add.assert_not_called()
        mock_db_session.commit.assert_not_called()
        
    @pytest.mark.asyncio
    async def test_create_embedding_database_error(self, mock_db_session, mock_gemini_service):
        """データベースエラー時のテスト"""
        service = VectorService(
            db_session=mock_db_session,
            gemini_service=mock_gemini_service
        )
        
        # データベースエラーを設定
        mock_db_session.commit.side_effect = OperationalError("DB connection lost", None, None)
        
        with pytest.raises(DatabaseConnectionError):
            await service.create_embedding("contact_123", "テストテキスト")
            
        # ロールバックが呼び出されることを確認
        mock_db_session.rollback.assert_called_once()


class TestVectorServiceSearchSimilar:
    """VectorService 類似検索テスト"""
    
    @pytest.mark.asyncio
    async def test_search_similar_success(self, mock_db_session, mock_gemini_service):
        """類似検索成功テスト"""
        service = VectorService(
            db_session=mock_db_session,
            gemini_service=mock_gemini_service
        )
        
        query_text = "商品の返品について"
        query_embedding = np.random.rand(768).tolist()
        mock_gemini_service.generate_embedding.return_value = query_embedding
        
        # 模擬検索結果
        mock_results = [
            Mock(
                contact_id="contact_1",
                similarity=0.9,
                metadata={"category": "RETURN", "urgency": "HIGH"}
            ),
            Mock(
                contact_id="contact_2", 
                similarity=0.8,
                metadata={"category": "RETURN", "urgency": "MEDIUM"}
            ),
            Mock(
                contact_id="contact_3",
                similarity=0.75,
                metadata={"category": "GENERAL", "urgency": "LOW"}
            )
        ]
        
        mock_db_session.execute.return_value.fetchall.return_value = mock_results
        
        results = await service.search_similar(query_text, top_k=3)
        
        assert len(results) == 3
        assert results[0]["contact_id"] == "contact_1"
        assert results[0]["similarity"] == 0.9
        assert results[0]["metadata"]["category"] == "RETURN"
        
        # 類似度順にソートされていることを確認
        assert results[0]["similarity"] >= results[1]["similarity"]
        assert results[1]["similarity"] >= results[2]["similarity"]
        
        mock_gemini_service.generate_embedding.assert_called_once_with(query_text)
        
    @pytest.mark.asyncio
    async def test_search_similar_no_results(self, mock_db_session, mock_gemini_service):
        """検索結果なしのテスト"""
        service = VectorService(
            db_session=mock_db_session,
            gemini_service=mock_gemini_service
        )
        
        query_embedding = np.random.rand(768).tolist()
        mock_gemini_service.generate_embedding.return_value = query_embedding
        
        # 検索結果なし
        mock_db_session.execute.return_value.fetchall.return_value = []
        
        results = await service.search_similar("稀なケース", top_k=3)
        
        assert len(results) == 0
        
    @pytest.mark.asyncio
    async def test_search_similar_with_similarity_threshold(self, mock_db_session, mock_gemini_service):
        """類似度閾値を使った検索テスト"""
        service = VectorService(
            db_session=mock_db_session,
            gemini_service=mock_gemini_service
        )
        
        query_embedding = np.random.rand(768).tolist()
        mock_gemini_service.generate_embedding.return_value = query_embedding
        
        # 閾値以下の結果も含む模擬データ
        mock_results = [
            Mock(contact_id="contact_1", similarity=0.9),  # 閾値以上
            Mock(contact_id="contact_2", similarity=0.8),  # 閾値以上  
            Mock(contact_id="contact_3", similarity=0.6),  # 閾値以下（デフォルト0.7）
        ]
        
        mock_db_session.execute.return_value.fetchall.return_value = mock_results
        
        results = await service.search_similar("テスト", similarity_threshold=0.7)
        
        # 閾値以上の結果のみが返される
        assert len(results) == 2
        assert all(r["similarity"] >= 0.7 for r in results)
        
    @pytest.mark.asyncio
    async def test_search_similar_invalid_top_k(self, mock_db_session, mock_gemini_service):
        """無効なtop_k値のテスト"""
        service = VectorService(
            db_session=mock_db_session,
            gemini_service=mock_gemini_service
        )
        
        with pytest.raises(ValueError, match="top_k must be positive"):
            await service.search_similar("テスト", top_k=0)
            
        with pytest.raises(ValueError, match="top_k too large"):
            await service.search_similar("テスト", top_k=1000)


class TestVectorServiceUpdateEmbedding:
    """VectorService 埋め込み更新テスト"""
    
    @pytest.mark.asyncio
    async def test_update_embedding_success(self, mock_db_session, mock_gemini_service):
        """埋め込み更新成功テスト"""
        service = VectorService(
            db_session=mock_db_session,
            gemini_service=mock_gemini_service
        )
        
        contact_id = "contact_123"
        new_text = "更新されたお問い合わせ内容"
        new_embedding = np.random.rand(768).tolist()
        
        mock_gemini_service.generate_embedding.return_value = new_embedding
        
        # 既存のベクトルデータを模擬
        existing_vector = Mock(spec=ContactVector)
        mock_db_session.query.return_value.filter.return_value.first.return_value = existing_vector
        
        result = await service.update_embedding(contact_id, new_text)
        
        assert result["contact_id"] == contact_id
        assert result["updated"] is True
        
        # 既存データが更新されることを確認
        assert existing_vector.embedding == new_embedding
        assert existing_vector.vectorized_at is not None
        
        mock_db_session.commit.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_update_embedding_not_found(self, mock_db_session, mock_gemini_service):
        """存在しないベクトルデータの更新テスト"""
        service = VectorService(
            db_session=mock_db_session,
            gemini_service=mock_gemini_service
        )
        
        # 該当データなし
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        
        result = await service.update_embedding("nonexistent_contact", "テキスト")
        
        assert result["contact_id"] == "nonexistent_contact"
        assert result["updated"] is False
        assert result["reason"] == "not_found"


class TestVectorServiceDeleteEmbedding:
    """VectorService 埋め込み削除テスト"""
    
    @pytest.mark.asyncio
    async def test_delete_embedding_success(self, mock_db_session, mock_gemini_service):
        """埋め込み削除成功テスト"""
        service = VectorService(
            db_session=mock_db_session,
            gemini_service=mock_gemini_service
        )
        
        contact_id = "contact_123"
        
        # 既存のベクトルデータを模擬
        existing_vector = Mock(spec=ContactVector)
        mock_db_session.query.return_value.filter.return_value.first.return_value = existing_vector
        
        result = await service.delete_embedding(contact_id)
        
        assert result["contact_id"] == contact_id
        assert result["deleted"] is True
        
        mock_db_session.delete.assert_called_once_with(existing_vector)
        mock_db_session.commit.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_delete_embedding_not_found(self, mock_db_session, mock_gemini_service):
        """存在しないベクトルデータの削除テスト"""
        service = VectorService(
            db_session=mock_db_session,
            gemini_service=mock_gemini_service
        )
        
        # 該当データなし
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        
        result = await service.delete_embedding("nonexistent_contact")
        
        assert result["contact_id"] == "nonexistent_contact"
        assert result["deleted"] is False
        assert result["reason"] == "not_found"


class TestVectorServiceBoundaryValues:
    """VectorService 境界値テスト"""
    
    @pytest.mark.asyncio
    async def test_search_similar_top_k_boundary_values(self, mock_db_session, mock_gemini_service):
        """top_k境界値テスト"""
        service = VectorService(
            db_session=mock_db_session,
            gemini_service=mock_gemini_service
        )
        
        mock_gemini_service.generate_embedding.return_value = np.random.rand(768).tolist()
        mock_db_session.execute.return_value.fetchall.return_value = []
        
        # 最小値
        results = await service.search_similar("テスト", top_k=1)
        assert len(results) == 0  # 結果がないため
        
        # 最大値（設定値による）
        results = await service.search_similar("テスト", top_k=100)
        assert len(results) == 0
        
    @pytest.mark.asyncio
    async def test_similarity_threshold_boundary_values(self, mock_db_session, mock_gemini_service):
        """類似度閾値境界値テスト"""
        service = VectorService(
            db_session=mock_db_session,
            gemini_service=mock_gemini_service
        )
        
        mock_gemini_service.generate_embedding.return_value = np.random.rand(768).tolist()
        
        # 境界値での検索
        mock_results = [Mock(contact_id="test", similarity=0.5)]
        mock_db_session.execute.return_value.fetchall.return_value = mock_results
        
        # 閾値0.0（最小）
        results = await service.search_similar("テスト", similarity_threshold=0.0)
        assert len(results) == 1
        
        # 閾値0.6（中間値） 
        results = await service.search_similar("テスト", similarity_threshold=0.6)
        assert len(results) == 0  # 0.5 < 0.6
        
        # 閾値1.0（最大）
        results = await service.search_similar("テスト", similarity_threshold=1.0)
        assert len(results) == 0


class TestVectorServiceSecurityTests:
    """VectorService セキュリティテスト"""
    
    @pytest.mark.asyncio
    async def test_embedding_injection_protection(self, mock_db_session, mock_gemini_service):
        """埋め込みインジェクション攻撃防御テスト"""
        service = VectorService(
            db_session=mock_db_session,
            gemini_service=mock_gemini_service
        )
        
        # SQLインジェクション試行
        malicious_contact_id = "'; DROP TABLE contact_vectors; --"
        
        with pytest.raises(ValueError, match="Invalid contact ID format"):
            await service.create_embedding(malicious_contact_id, "テキスト")
            
    @pytest.mark.asyncio
    async def test_vector_manipulation_protection(self, mock_db_session, mock_gemini_service):
        """ベクトル操作攻撃防御テスト"""
        service = VectorService(
            db_session=mock_db_session,
            gemini_service=mock_gemini_service
        )
        
        # 異常なベクトル次元での攻撃試行
        with patch.object(service, '_validate_embedding_integrity') as mock_validate:
            mock_validate.return_value = False
            
            with pytest.raises(ValueError, match="Embedding integrity check failed"):
                await service.create_embedding("contact_123", "テキスト")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])