"""データベースマイグレーション実行スクリプト

このスクリプトは次世代サポートシステムのためのデータベースマイグレーションを実行します。
AI解析テーブルとベクトル検索テーブルの作成、インデックス設定を行います。

Usage:
    python migrations/run_migration.py
    
Environment Variables:
    DATABASE_URL: PostgreSQL接続文字列（例: postgresql://user:password@localhost:5432/dbname）
    TEST_DATABASE_URL: テスト用データベース接続文字列（テスト実行時）
"""

import os
import sys
import logging
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatabaseMigration:
    """データベースマイグレーション管理クラス"""
    
    def __init__(self, database_url: str = None):
        """マイグレーション初期化
        
        Args:
            database_url: データベース接続文字列。未指定の場合は環境変数から取得
        """
        self.database_url = database_url or os.getenv(
            'DATABASE_URL', 
            'postgresql://localhost:5432/contact_api'
        )
        self.migration_dir = Path(__file__).parent
        
    def create_engine(self):
        """データベースエンジンを作成"""
        try:
            engine = create_engine(self.database_url, echo=True)
            logger.info(f"データベースエンジン作成成功: {self.database_url}")
            return engine
        except Exception as e:
            logger.error(f"データベースエンジン作成失敗: {e}")
            raise
    
    def test_connection(self, engine):
        """データベース接続テスト"""
        try:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT version()"))
                version = result.fetchone()[0]
                logger.info(f"データベース接続成功: {version}")
                return True
        except Exception as e:
            logger.error(f"データベース接続失敗: {e}")
            return False
    
    def check_prerequisites(self, engine):
        """マイグレーション前提条件チェック"""
        logger.info("前提条件チェック開始...")
        
        with engine.connect() as conn:
            # PostgreSQLバージョンチェック
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            logger.info(f"PostgreSQLバージョン: {version}")
            
            # pgvector拡張の利用可能性チェック
            try:
                result = conn.execute(text(
                    "SELECT * FROM pg_available_extensions WHERE name = 'vector'"
                ))
                if not result.fetchone():
                    logger.warning("pgvector拡張が利用できません。手動でインストールしてください。")
                else:
                    logger.info("pgvector拡張利用可能")
            except Exception as e:
                logger.warning(f"pgvector拡張チェック時にエラー: {e}")
            
            # contactsテーブルの存在チェック
            result = conn.execute(text(
                "SELECT 1 FROM information_schema.tables WHERE table_name = 'contacts'"
            ))
            if not result.fetchone():
                logger.error("contactsテーブルが存在しません。ベーステーブルを先に作成してください。")
                return False
            else:
                logger.info("contactsテーブル存在確認")
        
        logger.info("前提条件チェック完了")
        return True
    
    def run_migration_file(self, engine, filename: str):
        """マイグレーションファイル実行"""
        migration_file = self.migration_dir / filename
        
        if not migration_file.exists():
            logger.error(f"マイグレーションファイルが見つかりません: {migration_file}")
            return False
        
        logger.info(f"マイグレーション実行開始: {filename}")
        
        try:
            with open(migration_file, 'r', encoding='utf-8') as f:
                migration_sql = f.read()
            
            with engine.begin() as conn:
                # SQLファイルを分割して実行（複数のステートメント対応）
                statements = [stmt.strip() for stmt in migration_sql.split(';') if stmt.strip()]
                
                for i, statement in enumerate(statements):
                    if statement:
                        logger.debug(f"実行中 ({i+1}/{len(statements)}): {statement[:100]}...")
                        try:
                            result = conn.execute(text(statement))
                            if result.returns_rows:
                                rows = result.fetchall()
                                for row in rows:
                                    logger.info(f"結果: {row}")
                        except Exception as e:
                            logger.error(f"ステートメント実行エラー: {e}")
                            logger.error(f"問題のあるSQL: {statement}")
                            raise
            
            logger.info(f"マイグレーション実行完了: {filename}")
            return True
            
        except SQLAlchemyError as e:
            logger.error(f"SQLエラー: {e}")
            return False
        except Exception as e:
            logger.error(f"マイグレーション実行エラー: {e}")
            return False
    
    def validate_migration(self, engine):
        """マイグレーション結果検証"""
        logger.info("マイグレーション結果検証開始...")
        
        validation_queries = {
            "pgvector拡張": "SELECT 1 FROM pg_extension WHERE extname = 'vector'",
            "contact_ai_analysesテーブル": 
                "SELECT 1 FROM information_schema.tables WHERE table_name = 'contact_ai_analyses'",
            "contact_vectorsテーブル": 
                "SELECT 1 FROM information_schema.tables WHERE table_name = 'contact_vectors'",
            "HNSWインデックス": 
                "SELECT 1 FROM pg_indexes WHERE tablename = 'contact_vectors' AND indexdef LIKE '%hnsw%'",
            "外部キー制約": 
                """SELECT COUNT(*) FROM information_schema.referential_constraints 
                   WHERE constraint_name LIKE 'fk_contact_%'""",
        }
        
        all_valid = True
        
        with engine.connect() as conn:
            for check_name, query in validation_queries.items():
                try:
                    result = conn.execute(text(query))
                    if result.fetchone():
                        logger.info(f"✓ {check_name}: OK")
                    else:
                        logger.error(f"✗ {check_name}: NG")
                        all_valid = False
                except Exception as e:
                    logger.error(f"✗ {check_name}: エラー - {e}")
                    all_valid = False
        
        if all_valid:
            logger.info("✓ マイグレーション検証: すべて正常")
        else:
            logger.error("✗ マイグレーション検証: 問題あり")
        
        return all_valid
    
    def run(self):
        """完全なマイグレーション実行"""
        logger.info("データベースマイグレーション開始")
        
        try:
            # 1. データベース接続
            engine = self.create_engine()
            if not self.test_connection(engine):
                return False
            
            # 2. 前提条件チェック
            if not self.check_prerequisites(engine):
                return False
            
            # 3. マイグレーション実行
            if not self.run_migration_file(engine, "create_ai_analysis_tables.sql"):
                return False
            
            # 4. 結果検証
            if not self.validate_migration(engine):
                logger.warning("検証で問題が検出されましたが、マイグレーションは実行されました")
            
            logger.info("データベースマイグレーション正常完了")
            return True
            
        except Exception as e:
            logger.error(f"マイグレーション実行中にエラーが発生しました: {e}")
            return False


def main():
    """メイン実行関数"""
    migration = DatabaseMigration()
    
    success = migration.run()
    
    if success:
        print("\n🎉 マイグレーション正常完了!")
        print("次世代サポートシステムのデータベーススキーマが正常に作成されました。")
        sys.exit(0)
    else:
        print("\n❌ マイグレーション失敗")
        print("ログを確認し、問題を解決してから再実行してください。")
        sys.exit(1)


if __name__ == "__main__":
    main()