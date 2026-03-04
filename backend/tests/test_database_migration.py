"""データベースマイグレーションとインデックス作成のテスト"""
import pytest
import os
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import ProgrammingError
from db.base import Base
from models import Contact, ContactAIAnalysis, ContactVector
import tempfile


@pytest.fixture(scope="module")
def test_db_engine():
    """テスト用PostgreSQLエンジン（実際のPostgreSQLが必要）"""
    # テスト用データベース接続文字列
    # 実際のPostgreSQLでのテストが必要（pgvector拡張のため）
    test_db_url = os.getenv("TEST_DATABASE_URL", "postgresql://test_user:test_pass@localhost:5432/test_contact_api")
    
    try:
        engine = create_engine(test_db_url, echo=True)
        # テスト接続確認
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        yield engine
    except Exception as e:
        pytest.skip(f"PostgreSQL test database not available: {e}")


@pytest.fixture(scope="module")
def session_factory(test_db_engine):
    """テスト用セッションファクトリー"""
    # テストでは元のテーブルをクリーンアップ
    Base.metadata.drop_all(test_db_engine)
    return sessionmaker(bind=test_db_engine)


@pytest.fixture
def db_session(session_factory):
    """テスト用データベースセッション"""
    session = session_factory()
    yield session
    session.rollback()
    session.close()


class TestDatabaseMigration:
    """データベースマイグレーション関連のテストクラス"""
    
    def test_pgvector_extension_exists(self, test_db_engine):
        """pgvector拡張が有効化されていることを確認"""
        with test_db_engine.connect() as conn:
            result = conn.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            )
            assert result.fetchone() is not None, "pgvector拡張が有効化されていません"

    def test_contact_ai_analyses_table_created(self, test_db_engine):
        """contact_ai_analysesテーブルが正しく作成されることを確認"""
        inspector = inspect(test_db_engine)
        
        # テーブルの存在確認
        assert "contact_ai_analyses" in inspector.get_table_names(), \
            "contact_ai_analysesテーブルが存在しません"
        
        # カラムの確認
        columns = {col['name']: col for col in inspector.get_columns("contact_ai_analyses")}
        required_columns = [
            'id', 'contact_id', 'category', 'urgency', 'sentiment', 
            'confidence_score', 'summary', 'reasoning', 'processed_at',
            'created_at', 'updated_at'
        ]
        
        for col_name in required_columns:
            assert col_name in columns, f"カラム {col_name} が存在しません"

    def test_contact_vectors_table_created(self, test_db_engine):
        """contact_vectorsテーブルが正しく作成されることを確認"""
        inspector = inspect(test_db_engine)
        
        # テーブルの存在確認
        assert "contact_vectors" in inspector.get_table_names(), \
            "contact_vectorsテーブルが存在しません"
        
        # カラムの確認
        columns = {col['name']: col for col in inspector.get_columns("contact_vectors")}
        required_columns = [
            'id', 'contact_id', 'embedding', 'model_version', 
            'metadata', 'vectorized_at', 'created_at', 'updated_at'
        ]
        
        for col_name in required_columns:
            assert col_name in columns, f"カラム {col_name} が存在しません"
        
        # embedding列がvector型であることを確認
        embedding_col = columns['embedding']
        assert 'vector' in str(embedding_col['type']).lower(), \
            "embedding列がvector型ではありません"

    def test_foreign_key_constraints(self, test_db_engine):
        """外部キー制約が正しく設定されていることを確認"""
        inspector = inspect(test_db_engine)
        
        # contact_ai_analyses テーブルの外部キー
        ai_analysis_fks = inspector.get_foreign_keys("contact_ai_analyses")
        assert len(ai_analysis_fks) == 1, "contact_ai_analysesの外部キー制約が不正です"
        assert ai_analysis_fks[0]['referred_table'] == 'contacts', \
            "contact_ai_analysesがcontactsテーブルを参照していません"
        
        # contact_vectors テーブルの外部キー
        vector_fks = inspector.get_foreign_keys("contact_vectors")
        assert len(vector_fks) == 1, "contact_vectorsの外部キー制約が不正です"
        assert vector_fks[0]['referred_table'] == 'contacts', \
            "contact_vectorsがcontactsテーブルを参照していません"

    def test_unique_constraints(self, test_db_engine):
        """ユニーク制約が正しく設定されていることを確認"""
        inspector = inspect(test_db_engine)
        
        # contact_ai_analyses テーブルのユニーク制約
        ai_analysis_unique = inspector.get_unique_constraints("contact_ai_analyses")
        contact_id_unique = any(
            'contact_id' in constraint['column_names'] 
            for constraint in ai_analysis_unique
        )
        assert contact_id_unique, "contact_ai_analysesのcontact_idユニーク制約が存在しません"
        
        # contact_vectors テーブルのユニーク制約
        vector_unique = inspector.get_unique_constraints("contact_vectors")
        contact_id_unique = any(
            'contact_id' in constraint['column_names'] 
            for constraint in vector_unique
        )
        assert contact_id_unique, "contact_vectorsのcontact_idユニーク制約が存在しません"

    def test_hnsw_index_created(self, test_db_engine):
        """HNSWインデックスが正しく作成されていることを確認"""
        with test_db_engine.connect() as conn:
            # HNSWインデックスの存在確認
            result = conn.execute(text("""
                SELECT indexname, indexdef 
                FROM pg_indexes 
                WHERE tablename = 'contact_vectors' 
                AND indexdef LIKE '%hnsw%'
            """))
            hnsw_indexes = result.fetchall()
            
            assert len(hnsw_indexes) > 0, "HNSWインデックスが作成されていません"
            
            # インデックス定義の詳細確認
            index_def = hnsw_indexes[0][1]
            assert "vector_cosine_ops" in index_def, \
                "HNSWインデックスがvector_cosine_opsを使用していません"
            assert "m=16" in index_def or "m = 16" in index_def, \
                "HNSWインデックスのmパラメータが16に設定されていません"
            assert "ef_construction=64" in index_def or "ef_construction = 64" in index_def, \
                "HNSWインデックスのef_constructionパラメータが64に設定されていません"

    def test_performance_indexes_created(self, test_db_engine):
        """パフォーマンス最適化インデックスが作成されていることを確認"""
        inspector = inspect(test_db_engine)
        
        # contact_ai_analyses テーブルのインデックス
        ai_analysis_indexes = inspector.get_indexes("contact_ai_analyses")
        index_columns = [col for idx in ai_analysis_indexes for col in idx['column_names']]
        
        # 重要なカラムにインデックスが設定されていることを確認
        assert 'category' in index_columns, "categoryカラムにインデックスが設定されていません"
        assert 'urgency' in index_columns, "urgencyカラムにインデックスが設定されていません" 
        assert 'created_at' in index_columns, "created_atカラムにインデックスが設定されていません"

    def test_cascade_delete_behavior(self, db_session, test_db_engine):
        """カスケード削除が正しく動作することを確認"""
        # テストデータ作成
        contact = Contact(
            name="テストユーザー",
            email="cascade@example.com", 
            subject="カスケードテスト",
            message="カスケード削除テスト用"
        )
        db_session.add(contact)
        db_session.commit()
        
        ai_analysis = ContactAIAnalysis(
            contact_id=contact.id,
            category="product",
            urgency=1,
            sentiment="neutral",
            confidence_score=0.95,
            summary="テスト要約",
            reasoning="テスト理由"
        )
        db_session.add(ai_analysis)
        db_session.commit()
        
        contact_id = contact.id
        analysis_id = ai_analysis.id
        
        # Contactを削除
        db_session.delete(contact)
        db_session.commit()
        
        # ContactAIAnalysisがカスケード削除されることを確認
        deleted_analysis = db_session.get(ContactAIAnalysis, analysis_id)
        assert deleted_analysis is None, "ContactAIAnalysisがカスケード削除されていません"

    def test_check_constraints_validation(self, db_session):
        """チェック制約が正しく動作することを確認"""
        contact = Contact(
            name="制約テストユーザー",
            email="constraints@example.com",
            subject="制約テスト", 
            message="制約テスト用"
        )
        db_session.add(contact)
        db_session.commit()
        
        # 不正なconfidence_score値でのテスト
        with pytest.raises(Exception):  # チェック制約違反
            invalid_analysis = ContactAIAnalysis(
                contact_id=contact.id,
                category="product",
                urgency=1,
                sentiment="neutral", 
                confidence_score=1.5,  # 1.0を超える不正な値
                summary="テスト要約",
                reasoning="テスト理由"
            )
            db_session.add(invalid_analysis)
            db_session.commit()

    def test_migration_script_exists(self):
        """マイグレーションスクリプトが存在することを確認"""
        migration_file = "/Users/kouta.ozawa/Git/_personal/contact-api/backend/migrations/create_ai_analysis_tables.sql"
        assert os.path.exists(migration_file), "マイグレーションスクリプトが存在しません"
        
        # ファイル内容の基本チェック
        with open(migration_file, 'r') as f:
            content = f.read()
            assert "CREATE EXTENSION IF NOT EXISTS vector" in content, \
                "pgvector拡張の有効化が含まれていません"
            assert "CREATE TABLE contact_ai_analyses" in content, \
                "contact_ai_analysesテーブル作成が含まれていません"
            assert "CREATE TABLE contact_vectors" in content, \
                "contact_vectorsテーブル作成が含まれていません"
            assert "CREATE INDEX" in content and "hnsw" in content, \
                "HNSWインデックス作成が含まれていません"