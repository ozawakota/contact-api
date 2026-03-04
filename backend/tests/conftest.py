"""
テスト共通設定・フィクスチャ

pytest設定ファイル
全テストで共通的に使用するフィクスチャとマーク設定
"""

import pytest
import asyncio
import logging
from typing import Generator, AsyncGenerator, Dict, Any
from unittest.mock import Mock, AsyncMock, patch, MagicMock

import pytest_asyncio
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine, StaticPool

from backend.app.main import app
from backend.app.config.database import get_session
from backend.tests.utils.test_mocks import (
    MockGeminiAPI,
    MockSendGridAPI, 
    MockDatabase,
    TestDataFactory
)


# ログレベル設定
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# pytest設定
pytest_plugins = ["pytest_asyncio"]


@pytest.fixture(scope="session") 
def event_loop():
    """セッション単位のイベントループ"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
def test_db_session():
    """テスト用データベースセッション"""
    # インメモリSQLiteエンジン作成
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )
    
    # テーブル作成
    from backend.app.models.contact import Contact
    from backend.app.models.contact_ai_analysis import ContactAIAnalysis
    from backend.app.models.contact_vector import ContactVector
    
    Contact.metadata.create_all(engine)
    ContactAIAnalysis.metadata.create_all(engine)
    ContactVector.metadata.create_all(engine)
    
    with Session(engine) as session:
        yield session
        session.rollback()


@pytest.fixture
def test_client(test_db_session):
    """テスト用FastAPIクライアント"""
    
    def get_test_session():
        return test_db_session
        
    app.dependency_overrides[get_session] = get_test_session
    
    with TestClient(app) as client:
        yield client
        
    app.dependency_overrides.clear()


@pytest.fixture
def mock_gemini_service():
    """モックGeminiService"""
    mock = AsyncMock()
    mock.analyze_contact.return_value = {
        "category": "GENERAL",
        "urgency": "MEDIUM", 
        "sentiment": "NEUTRAL",
        "confidence_score": 0.85,
        "summary": "テストサマリー"
    }
    mock.generate_embedding.return_value = [0.1] * 768  # 768次元ベクトル
    return mock


@pytest.fixture
def mock_vector_service():
    """モックVectorService"""
    mock = AsyncMock()
    mock.create_embedding.return_value = {
        "contact_id": "test_id",
        "embedding": [0.1] * 768,
        "metadata": {"model_version": "test"}
    }
    mock.search_similar.return_value = [
        {
            "contact_id": "similar_1",
            "similarity": 0.9,
            "title": "類似件名1"
        },
        {
            "contact_id": "similar_2", 
            "similarity": 0.8,
            "title": "類似件名2"
        }
    ]
    return mock


@pytest.fixture
def mock_notification_service():
    """モックNotificationService"""
    mock = AsyncMock()
    mock.send_notification.return_value = {
        "message_id": "test_msg_123",
        "status": "sent",
        "sent_at": "2024-01-01T12:00:00Z"
    }
    return mock


@pytest.fixture
def sample_contact_data():
    """サンプルお問い合わせデータ"""
    return {
        "name": "山田太郎",
        "email": "yamada@example.com",
        "subject": "商品について", 
        "message": "商品の詳細を教えてください。"
    }


@pytest.fixture
def sample_ai_analysis_data():
    """サンプルAI分析データ"""
    return {
        "category": "GENERAL",
        "urgency": "MEDIUM",
        "sentiment": "NEUTRAL", 
        "confidence_score": 0.85,
        "summary": "商品に関する一般的な問い合わせ",
        "analysis_details": {
            "keywords": ["商品", "詳細"],
            "priority_factors": ["情報要求"],
            "recommended_actions": ["商品情報提供"]
        }
    }


@pytest.fixture
def test_data_factory():
    """テストデータファクトリー"""
    return TestDataFactory()


# カスタムマーク設定
def pytest_configure(config):
    """pytest設定関数"""
    config.addinivalue_line(
        "markers", 
        "unit: ユニットテストマーク"
    )
    config.addinivalue_line(
        "markers",
        "integration: 統合テストマーク"
    )
    config.addinivalue_line(
        "markers",
        "acceptance: 受入テストマーク"
    )
    config.addinivalue_line(
        "markers",
        "performance: パフォーマンステストマーク" 
    )
    config.addinivalue_line(
        "markers",
        "security: セキュリティテストマーク"
    )
    config.addinivalue_line(
        "markers",
        "slow: 時間のかかるテストマーク"
    )
    

# テスト環境変数設定
@pytest.fixture(autouse=True, scope="session")
def setup_test_environment():
    """テスト環境設定（全テスト自動実行）"""
    import os
    
    # テスト環境変数設定
    test_env = {
        "ENVIRONMENT": "test",
        "GEMINI_API_KEY": "test_gemini_key",
        "SENDGRID_API_KEY": "test_sendgrid_key",
        "DATABASE_URL": "sqlite:///:memory:",
        "ADMIN_EMAIL": "test_admin@example.com"
    }
    
    original_env = {}
    for key, value in test_env.items():
        original_env[key] = os.getenv(key)
        os.environ[key] = value
        
    yield
    
    # 環境変数復元
    for key, original_value in original_env.items():
        if original_value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = original_value


# 非同期フィクスチャサンプル
@pytest.fixture
async def async_test_setup():
    """非同期テストセットアップ"""
    # セットアップ処理
    setup_data = {"initialized": True}
    yield setup_data
    # クリーンアップ処理
    setup_data.clear()


# パラメータ化テストデータ
@pytest.fixture(params=[
    "GENERAL",
    "TECHNICAL", 
    "BILLING",
    "COMPLAINT"
])
def category_samples(request):
    """カテゴリーサンプルデータ（パラメータ化）"""
    return request.param


@pytest.fixture(params=[
    "LOW",
    "MEDIUM",
    "HIGH", 
    "CRITICAL"
])
def urgency_samples(request):
    """緊急度サンプルデータ（パラメータ化）"""
    return request.param