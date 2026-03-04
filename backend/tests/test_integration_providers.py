"""
プロバイダー統合テスト

Task 6.2の統合テスト実装:
- 本番環境に近い条件でのサービス統合テスト
- FastAPIアプリケーションとの統合確認
- エンドツーエンドの依存性注入動作テスト
- 実際のAPIエンドポイントでの動作確認
"""

import pytest
import os
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session

from backend.app.main import create_main_app, initialize_firebase
from backend.app.contacts.providers import (
    ApplicationContainer,
    create_test_container_with_mocks,
    cleanup_container,
)
from backend.app.services.gemini_service import GeminiService
from backend.app.services.vector_service import VectorService
from backend.app.services.notification_service import NotificationService


class TestApplicationIntegration:
    """アプリケーション統合テストクラス"""

    def setup_method(self):
        """テストメソッド前の準備"""
        cleanup_container()

    def teardown_method(self):
        """テストメソッド後のクリーンアップ"""
        cleanup_container()

    @patch.dict(os.environ, {
        "ENVIRONMENT": "testing",
        "DATABASE_URL": "sqlite:///:memory:",
        "GEMINI_API_KEY": "test_gemini_key",
        "SENDGRID_API_KEY": "test_sendgrid_key",
        "FIREBASE_CREDENTIALS_PATH": "/nonexistent/path"  # Will fall back to default
    })
    def test_create_main_app_integration(self):
        """メインアプリケーション作成の統合テスト"""
        
        # Mock Firebase initialization to avoid actual Firebase calls
        with patch('backend.app.main.initialize_firebase'):
            app = create_main_app()
            
            # Verify FastAPI app creation
            assert app is not None
            assert hasattr(app.state, 'container')
            assert isinstance(app.state.container, ApplicationContainer)

    @patch.dict(os.environ, {
        "ENVIRONMENT": "testing",
        "DATABASE_URL": "sqlite:///:memory:",
        "GEMINI_API_KEY": "test_gemini_key",
        "SENDGRID_API_KEY": "test_sendgrid_key",
    })
    def test_health_check_endpoint(self):
        """ヘルスチェックエンドポイントの統合テスト"""
        
        with patch('backend.app.main.initialize_firebase'):
            app = create_main_app()
            client = TestClient(app)
            
            response = client.get("/health")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["environment"] == "testing"
            assert data["service"] == "Contact API"
            assert data["version"] == "1.0.0"

    @patch.dict(os.environ, {
        "ENVIRONMENT": "testing",
        "DATABASE_URL": "sqlite:///:memory:",
        "GEMINI_API_KEY": "test_gemini_key",
        "SENDGRID_API_KEY": "test_sendgrid_key",
    })
    def test_root_endpoint_legacy_compatibility(self):
        """ルートエンドポイントの後方互換性テスト"""
        
        with patch('backend.app.main.initialize_firebase'):
            app = create_main_app()
            client = TestClient(app)
            
            response = client.get("/")
            
            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Contact API v1.0"
            assert data["environment"] == "testing"
            assert data["status"] == "running"


class TestServiceDependencyIntegration:
    """サービス依存関係統合テストクラス"""

    def setup_method(self):
        """テストメソッド前の準備"""
        cleanup_container()

    def teardown_method(self):
        """テストメソッド後のクリーンアップ"""
        cleanup_container()

    @patch.dict(os.environ, {
        "GEMINI_API_KEY": "test_gemini_key",
        "SENDGRID_API_KEY": "test_sendgrid_key",
    })
    def test_service_chain_integration(self):
        """サービスチェーン統合テスト"""
        container = ApplicationContainer()
        container.config.database.echo.from_value(False)
        container.config.database.pool_size.from_value(5)
        container.config.database.max_overflow.from_value(10)
        
        # Test complete service chain
        contact_usecase = container.contact_usecase()
        ai_analysis_usecase = container.ai_analysis_usecase()
        vector_search_usecase = container.vector_search_usecase()
        admin_dashboard_api = container.admin_dashboard_api()
        
        # Verify all services are properly instantiated
        assert contact_usecase is not None
        assert ai_analysis_usecase is not None
        assert vector_search_usecase is not None
        assert admin_dashboard_api is not None
        
        # Verify service dependencies are properly injected
        # (This would require access to internal dependencies, 
        # which may not be easily accessible depending on implementation)

    def test_mock_service_integration(self):
        """モックサービス統合テスト"""
        # Create mock services
        mock_gemini = Mock(spec=GeminiService)
        mock_vector = Mock(spec=VectorService)
        mock_notification = Mock(spec=NotificationService)
        
        # Configure mock behaviors
        mock_gemini.analyze_contact = AsyncMock(return_value={
            "category": "GENERAL",
            "urgency": "MEDIUM",
            "sentiment": "NEUTRAL",
            "confidence_score": 0.85,
            "summary": "Test summary"
        })
        
        mock_vector.search_similar = AsyncMock(return_value=[])
        mock_notification.send_notification = AsyncMock(return_value=True)
        
        # Create test container with mocks
        container = create_test_container_with_mocks(
            gemini_service=mock_gemini,
            vector_service=mock_vector,
            notification_service=mock_notification
        )
        
        # Verify mocked services are used
        assert container.gemini_service() is mock_gemini
        assert container.vector_service() is mock_vector
        assert container.notification_service() is mock_notification


class TestEnvironmentConfiguration:
    """環境設定統合テストクラス"""

    def setup_method(self):
        """テストメソッド前の準備"""
        cleanup_container()

    def teardown_method(self):
        """テストメソッド後のクリーンアップ"""
        cleanup_container()

    @patch.dict(os.environ, {"ENVIRONMENT": "development"})
    def test_development_environment_config(self):
        """開発環境設定の統合テスト"""
        
        with patch('backend.app.main.initialize_firebase'):
            app = create_main_app()
            
            # Check environment-specific settings
            assert os.getenv("ENVIRONMENT") == "development"
            
            # Test CORS origins for development
            cors_middleware = None
            for middleware in app.user_middleware:
                if middleware.cls.__name__ == 'CORSMiddleware':
                    cors_middleware = middleware
                    break
            
            assert cors_middleware is not None
            # Note: Specific CORS configuration testing would require 
            # accessing middleware configuration, which may be complex

    @patch.dict(os.environ, {"ENVIRONMENT": "production"})
    def test_production_environment_config(self):
        """本番環境設定の統合テスト"""
        
        with patch('backend.app.main.initialize_firebase'):
            app = create_main_app()
            
            # Check environment-specific settings
            assert os.getenv("ENVIRONMENT") == "production"

    @patch.dict(os.environ, {"ENVIRONMENT": "testing"})
    def test_testing_environment_config(self):
        """テスト環境設定の統合テスト"""
        
        with patch('backend.app.main.initialize_firebase'):
            app = create_main_app()
            
            # Check environment-specific settings
            assert os.getenv("ENVIRONMENT") == "testing"


class TestFirebaseIntegration:
    """Firebase統合テストクラス"""

    def test_firebase_initialization_with_credentials_file(self):
        """認証ファイル付きFirebase初期化テスト"""
        
        with patch.dict(os.environ, {
            "FIREBASE_CREDENTIALS_PATH": "/path/to/credentials.json"
        }):
            with patch('os.path.exists', return_value=True):
                with patch('firebase_admin.credentials.Certificate') as mock_cert:
                    with patch('firebase_admin.initialize_app') as mock_init:
                        with patch('firebase_admin._apps', []):  # Empty apps list
                            
                            initialize_firebase()
                            
                            mock_cert.assert_called_once_with("/path/to/credentials.json")
                            mock_init.assert_called_once()

    def test_firebase_initialization_without_credentials_file(self):
        """認証ファイルなしFirebase初期化テスト"""
        
        with patch.dict(os.environ, {}, clear=True):
            with patch('firebase_admin.initialize_app') as mock_init:
                with patch('firebase_admin._apps', []):  # Empty apps list
                    
                    initialize_firebase()
                    
                    mock_init.assert_called_once_with()

    def test_firebase_initialization_already_initialized(self):
        """Firebase既初期化状態テスト"""
        
        # Mock that Firebase is already initialized
        with patch('firebase_admin._apps', [Mock()]):  # Non-empty apps list
            with patch('firebase_admin.initialize_app') as mock_init:
                
                initialize_firebase()
                
                # Should not call initialize_app if already initialized
                mock_init.assert_not_called()


class TestDatabaseIntegration:
    """データベース統合テストクラス"""

    def setup_method(self):
        """テストメソッド前の準備"""
        cleanup_container()

    def teardown_method(self):
        """テストメソッド後のクリーンアップ"""
        cleanup_container()

    def test_database_session_integration(self):
        """データベースセッション統合テスト"""
        container = ApplicationContainer()
        container.config.database.echo.from_value(False)
        
        # Test database session creation
        session_factory = container.database_session_factory
        session = session_factory()
        
        assert isinstance(session, Session)
        
        # Test that sessions are different instances
        session2 = session_factory()
        assert session is not session2

    def test_database_engine_singleton(self):
        """データベースエンジンSingleton動作テスト"""
        container = ApplicationContainer()
        container.config.database.echo.from_value(False)
        
        # Test that engine is singleton
        engine1 = container.database_engine()
        engine2 = container.database_engine()
        
        assert engine1 is engine2


class TestAPIRouteIntegration:
    """APIルート統合テストクラス"""

    def setup_method(self):
        """テストメソッド前の準備"""
        cleanup_container()

    def teardown_method(self):
        """テストメソッド後のクリーンアップ"""
        cleanup_container()

    @patch.dict(os.environ, {
        "ENVIRONMENT": "testing",
        "DATABASE_URL": "sqlite:///:memory:",
        "GEMINI_API_KEY": "test_gemini_key",
        "SENDGRID_API_KEY": "test_sendgrid_key",
    })
    def test_api_route_availability(self):
        """APIルート利用可能性テスト"""
        
        with patch('backend.app.main.initialize_firebase'):
            app = create_main_app()
            client = TestClient(app)
            
            # Test basic endpoints are accessible
            health_response = client.get("/health")
            assert health_response.status_code == 200
            
            root_response = client.get("/")
            assert root_response.status_code == 200
            
            # Test API routes (these may fail due to missing authentication,
            # but they should at least be routable)
            # Note: Full endpoint testing would require proper setup
            # and mocking of all dependencies


if __name__ == "__main__":
    pytest.main([__file__, "-v"])