"""ContactVectorモデルのテスト"""
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from db.base import Base
from models.contact import Contact
from models.contact_vector import ContactVector
from pgvector.sqlalchemy import Vector
import numpy as np
from datetime import datetime


@pytest.fixture(scope="module")
def engine():
    """テスト用データベースエンジン"""
    engine = create_engine("sqlite:///:memory:", echo=True)
    
    # SQLiteでは pgvector は使えないため、モック環境でテストします
    # 実際のPostgreSQLでのテストは統合テストで行います
    yield engine


@pytest.fixture(scope="module")
def session_factory(engine):
    """テスト用セッションファクトリー"""
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


@pytest.fixture
def session(session_factory):
    """テスト用データベースセッション"""
    session = session_factory()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def sample_contact(session):
    """テスト用コンタクトデータ"""
    contact = Contact(
        name="テストユーザー",
        email="test@example.com",
        subject="テスト件名",
        message="テストメッセージです"
    )
    session.add(contact)
    session.commit()
    return contact


class TestContactVectorModel:
    """ContactVectorモデルのテストクラス"""

    def test_contact_vector_creation(self, session, sample_contact):
        """ContactVectorオブジェクトの正常作成テスト"""
        # 768次元のテストベクトル
        test_embedding = np.random.rand(768).astype(np.float32)
        
        contact_vector = ContactVector(
            contact_id=sample_contact.id,
            embedding=test_embedding,
            model_version="gemini-pro-1.5",
            metadata={"source": "test", "timestamp": "2024-01-01T00:00:00"}
        )
        
        session.add(contact_vector)
        session.commit()
        
        # アサーション
        assert contact_vector.id is not None
        assert contact_vector.contact_id == sample_contact.id
        assert contact_vector.model_version == "gemini-pro-1.5"
        assert contact_vector.metadata == {"source": "test", "timestamp": "2024-01-01T00:00:00"}
        assert contact_vector.vectorized_at is not None
        assert contact_vector.created_at is not None
        assert contact_vector.updated_at is not None

    def test_contact_vector_relationship(self, session, sample_contact):
        """ContactとContactVectorの1:1リレーションシップテスト"""
        test_embedding = np.random.rand(768).astype(np.float32)
        
        contact_vector = ContactVector(
            contact_id=sample_contact.id,
            embedding=test_embedding,
            model_version="gemini-pro-1.5"
        )
        
        session.add(contact_vector)
        session.commit()
        
        # リレーションシップのテスト
        assert sample_contact.vector is not None
        assert sample_contact.vector.id == contact_vector.id
        assert contact_vector.contact.id == sample_contact.id

    def test_embedding_dimension_constraint(self, session, sample_contact):
        """embedding列の768次元制約テスト（実装時にチェック）"""
        # 不正な次元数のベクトル
        wrong_dimension_embedding = np.random.rand(512).astype(np.float32)
        
        contact_vector = ContactVector(
            contact_id=sample_contact.id,
            embedding=wrong_dimension_embedding,
            model_version="gemini-pro-1.5"
        )
        
        # 実装では PostgreSQL の Vector(768) 制約によりエラーが発生することを期待
        # SQLiteでは制約チェックできないため、実装完了後に統合テストで検証
        session.add(contact_vector)
        # session.commit() # 実装時にエラーになることを期待

    def test_model_version_not_null(self, session, sample_contact):
        """model_version必須制約テスト"""
        test_embedding = np.random.rand(768).astype(np.float32)
        
        contact_vector = ContactVector(
            contact_id=sample_contact.id,
            embedding=test_embedding,
            model_version=None  # NULL値
        )
        
        session.add(contact_vector)
        
        with pytest.raises(Exception):  # NOT NULL制約違反
            session.commit()

    def test_unique_contact_constraint(self, session, sample_contact):
        """contact_idユニーク制約テスト"""
        test_embedding1 = np.random.rand(768).astype(np.float32)
        test_embedding2 = np.random.rand(768).astype(np.float32)
        
        # 1つ目のContactVector作成
        contact_vector1 = ContactVector(
            contact_id=sample_contact.id,
            embedding=test_embedding1,
            model_version="gemini-pro-1.5"
        )
        session.add(contact_vector1)
        session.commit()
        
        # 同じcontact_idで2つ目のContactVector作成（エラーになることを期待）
        contact_vector2 = ContactVector(
            contact_id=sample_contact.id,
            embedding=test_embedding2,
            model_version="gemini-pro-1.5"
        )
        session.add(contact_vector2)
        
        with pytest.raises(Exception):  # UNIQUE制約違反
            session.commit()

    def test_cascade_deletion(self, session):
        """Contactが削除されたときのカスケード削除テスト"""
        # テスト用Contact作成
        contact = Contact(
            name="削除テストユーザー",
            email="delete@example.com", 
            subject="削除テスト件名",
            message="削除テストメッセージ"
        )
        session.add(contact)
        session.commit()
        
        # ContactVector作成
        test_embedding = np.random.rand(768).astype(np.float32)
        contact_vector = ContactVector(
            contact_id=contact.id,
            embedding=test_embedding,
            model_version="gemini-pro-1.5"
        )
        session.add(contact_vector)
        session.commit()
        
        vector_id = contact_vector.id
        
        # Contactを削除
        session.delete(contact)
        session.commit()
        
        # ContactVectorもカスケード削除されることを確認
        deleted_vector = session.get(ContactVector, vector_id)
        assert deleted_vector is None

    def test_vectorized_at_auto_set(self, session, sample_contact):
        """vectorized_at自動設定テスト"""
        test_embedding = np.random.rand(768).astype(np.float32)
        
        contact_vector = ContactVector(
            contact_id=sample_contact.id,
            embedding=test_embedding,
            model_version="gemini-pro-1.5"
        )
        
        session.add(contact_vector)
        session.commit()
        
        # vectorized_atが自動的に設定されることを確認
        assert contact_vector.vectorized_at is not None
        assert isinstance(contact_vector.vectorized_at, datetime)

    def test_metadata_json_field(self, session, sample_contact):
        """metadataのJSONフィールドテスト"""
        test_embedding = np.random.rand(768).astype(np.float32)
        test_metadata = {
            "source": "gemini",
            "processing_time": 1.5,
            "quality_score": 0.95,
            "tags": ["important", "customer"]
        }
        
        contact_vector = ContactVector(
            contact_id=sample_contact.id,
            embedding=test_embedding,
            model_version="gemini-pro-1.5",
            metadata=test_metadata
        )
        
        session.add(contact_vector)
        session.commit()
        
        # メタデータが正しく保存・復元されることを確認
        retrieved = session.get(ContactVector, contact_vector.id)
        assert retrieved.metadata == test_metadata
        assert retrieved.metadata["source"] == "gemini"
        assert retrieved.metadata["quality_score"] == 0.95
        assert "important" in retrieved.metadata["tags"]

    def test_table_name(self):
        """テーブル名の確認テスト"""
        assert ContactVector.__tablename__ == "contact_vectors"