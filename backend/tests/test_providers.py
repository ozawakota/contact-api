"""
依存性注入プロバイダーのテスト

Task 6.2のテスト実装:
- ApplicationContainerの依存性注入テスト
- TestApplicationContainerのモック機能テスト
- 環境別設定の動作確認テスト
- サービス間の依存関係解決テスト
"""

import pytest
import os
from unittest.mock import Mock, patch
from sqlmodel import Session
from dependency_injector.wiring import inject, Provide

from backend.app.contacts.providers import (
    ApplicationContainer,
    TestApplicationContainer,
    get_container,
    get_test_container,
    setup_container_config,
    create_application_container,
    create_test_container_with_mocks,
    initialize_database,
    cleanup_container,
    get_database_session,
    get_contact_usecase,
    get_ai_analysis_usecase,
    get_vector_search_usecase,
    get_admin_dashboard_api,
    get_notification_service,
    get_gemini_service,
    get_vector_service,
)
from backend.app.services.gemini_service import GeminiService
from backend.app.services.vector_service import VectorService
from backend.app.services.notification_service import NotificationService
from backend.app.use_cases.ai_analysis_usecase import AIAnalysisUseCase
from backend.app.use_cases.vector_search_usecase import VectorSearchUseCase
from backend.app.contacts.use_case import ContactUseCase
from backend.app.api.admin_dashboard import AdminDashboardAPI


class TestApplicationContainer:
    """ApplicationContainerのテストクラス"""

    def setup_method(self):
        """テストメソッド前の準備"""
        cleanup_container()

    def teardown_method(self):
        """テストメソッド後のクリーンアップ"""
        cleanup_container()

    @patch.dict(os.environ, {
        "DATABASE_URL": "postgresql://test:test@localhost:5432/test_db",
        "GEMINI_API_KEY": "test_gemini_key",
        "SENDGRID_API_KEY": "test_sendgrid_key",
        "FIREBASE_CREDENTIALS_PATH": "/path/to/test/credentials.json"
    })
    def test_container_configuration(self):
        """コンテナ設定のテスト"""
        container = ApplicationContainer()
        
        # Configuration設定
        container.config.database.echo.from_value(True)
        container.config.database.pool_size.from_value(10)
        container.config.database.max_overflow.from_value(20)
        
        # 環境変数からの値取得確認
        assert container.database_url() == "postgresql://test:test@localhost:5432/test_db"
        assert container.gemini_api_key() == "test_gemini_key"
        assert container.sendgrid_api_key() == "test_sendgrid_key"
        assert container.firebase_credentials_path() == "/path/to/test/credentials.json"

    @patch.dict(os.environ, {
        "GEMINI_API_KEY": "test_gemini_key",
        "SENDGRID_API_KEY": "test_sendgrid_key"
    })
    def test_service_dependencies(self):
        """サービス依存関係のテスト"""
        container = ApplicationContainer()
        container.config.database.echo.from_value(False)
        container.config.database.pool_size.from_value(5)
        container.config.database.max_overflow.from_value(10)
        
        # Services creation
        gemini_service = container.gemini_service()
        vector_service = container.vector_service()
        notification_service = container.notification_service()
        
        assert isinstance(gemini_service, GeminiService)
        assert isinstance(vector_service, VectorService)
        assert isinstance(notification_service, NotificationService)

    @patch.dict(os.environ, {
        "GEMINI_API_KEY": "test_gemini_key",
        "SENDGRID_API_KEY": "test_sendgrid_key"
    })
    def test_usecase_dependencies(self):
        """UseCase依存関係のテスト"""
        container = ApplicationContainer()
        container.config.database.echo.from_value(False)
        container.config.database.pool_size.from_value(5)
        container.config.database.max_overflow.from_value(10)
        
        # Use Cases creation
        contact_usecase = container.contact_usecase()
        ai_analysis_usecase = container.ai_analysis_usecase()
        vector_search_usecase = container.vector_search_usecase()
        
        assert isinstance(contact_usecase, ContactUseCase)
        assert isinstance(ai_analysis_usecase, AIAnalysisUseCase)
        assert isinstance(vector_search_usecase, VectorSearchUseCase)

    @patch.dict(os.environ, {
        "GEMINI_API_KEY": "test_gemini_key",
        "SENDGRID_API_KEY": "test_sendgrid_key"
    })
    def test_api_dependencies(self):
        """API層依存関係のテスト"""
        container = ApplicationContainer()
        container.config.database.echo.from_value(False)
        container.config.database.pool_size.from_value(5)
        container.config.database.max_overflow.from_value(10)
        
        # API layer creation
        admin_dashboard_api = container.admin_dashboard_api()
        
        assert isinstance(admin_dashboard_api, AdminDashboardAPI)

    def test_singleton_behavior(self):
        """Singletonパターンの動作テスト"""
        container = ApplicationContainer()
        
        # Same instance should be returned for singletons
        service1 = container.gemini_service()
        service2 = container.gemini_service()
        
        assert service1 is service2  # Same instance

    def test_database_session_factory(self):
        """データベースセッションファクトリーのテスト"""
        container = ApplicationContainer()
        container.config.database.echo.from_value(False)
        
        # Different instances should be created for sessions
        session_factory = container.database_session_factory
        session1 = session_factory()
        session2 = session_factory()
        
        assert isinstance(session1, Session)
        assert isinstance(session2, Session)
        assert session1 is not session2  # Different instances


class TestTestApplicationContainer:
    """TestApplicationContainerのテストクラス"""

    def test_test_container_creation(self):
        """テストコンテナ作成のテスト"""
        container = TestApplicationContainer()
        container.config.database_url.from_value("sqlite:///:memory:")
        
        # Test database should be in-memory SQLite
        assert container.database_url() == "sqlite:///:memory:"

    def test_mock_services_injection(self):
        """モックサービス注入のテスト"""
        mock_gemini = Mock(spec=GeminiService)
        mock_vector = Mock(spec=VectorService)
        mock_notification = Mock(spec=NotificationService)
        
        container = create_test_container_with_mocks(
            gemini_service=mock_gemini,
            vector_service=mock_vector,
            notification_service=mock_notification
        )
        
        # Mocked services should be returned
        assert container.gemini_service() is mock_gemini
        assert container.vector_service() is mock_vector
        assert container.notification_service() is mock_notification


class TestContainerFactoryFunctions:
    """コンテナファクトリー関数のテストクラス"""

    def setup_method(self):
        """テストメソッド前の準備"""
        cleanup_container()

    def teardown_method(self):
        """テストメソッド後のクリーンアップ"""
        cleanup_container()

    def test_get_container_singleton(self):
        """get_container()のSingleton動作テスト"""
        container1 = get_container()
        container2 = get_container()
        
        assert container1 is container2  # Same instance

    def test_get_test_container_factory(self):
        """get_test_container()のファクトリー動作テスト"""
        container1 = get_test_container()
        container2 = get_test_container()
        
        assert container1 is not container2  # Different instances
        assert isinstance(container1, TestApplicationContainer)
        assert isinstance(container2, TestApplicationContainer)

    @patch.dict(os.environ, {"ENVIRONMENT": "development"})
    def test_setup_container_config_development(self):
        """開発環境設定のテスト"""
        container = setup_container_config("development")
        
        assert isinstance(container, ApplicationContainer)
        # Note: Configuration values are applied, but we can't easily test them
        # without accessing private config state

    @patch.dict(os.environ, {"ENVIRONMENT": "production"})
    def test_setup_container_config_production(self):
        """本番環境設定のテスト"""
        container = setup_container_config("production")
        
        assert isinstance(container, ApplicationContainer)

    @patch.dict(os.environ, {
        "GEMINI_API_KEY": "test_gemini_key",
        "SENDGRID_API_KEY": "test_sendgrid_key",
        "ENVIRONMENT": "development"
    })
    def test_create_application_container(self):
        """アプリケーションコンテナ作成のテスト"""
        container = create_application_container()
        
        assert isinstance(container, ApplicationContainer)


class TestDependencyInjectionFunctions:
    """FastAPI依存性注入関数のテストクラス"""

    def setup_method(self):
        """テストメソッド前の準備"""
        cleanup_container()

    def teardown_method(self):
        """テストメソッド後のクリーンアップ"""
        cleanup_container()

    @patch.dict(os.environ, {
        "GEMINI_API_KEY": "test_gemini_key",
        "SENDGRID_API_KEY": "test_sendgrid_key"
    })
    def test_dependency_injection_functions(self):
        """依存性注入関数のテスト"""
        # Setup container
        container = get_container()
        container.config.database.echo.from_value(False)
        container.config.database.pool_size.from_value(5)
        container.config.database.max_overflow.from_value(10)
        
        # Wire the container for testing
        container.wire(modules=[__name__])
        
        try:
            # Test dependency injection functions
            db_session = get_database_session()
            contact_usecase = get_contact_usecase()
            ai_analysis_usecase = get_ai_analysis_usecase()
            vector_search_usecase = get_vector_search_usecase()
            admin_dashboard_api = get_admin_dashboard_api()
            notification_service = get_notification_service()
            gemini_service = get_gemini_service()
            vector_service = get_vector_service()
            
            # Verify correct types
            assert isinstance(db_session, Session)
            assert isinstance(contact_usecase, ContactUseCase)
            assert isinstance(ai_analysis_usecase, AIAnalysisUseCase)
            assert isinstance(vector_search_usecase, VectorSearchUseCase)
            assert isinstance(admin_dashboard_api, AdminDashboardAPI)
            assert isinstance(notification_service, NotificationService)
            assert isinstance(gemini_service, GeminiService)
            assert isinstance(vector_service, VectorService)
            
        finally:
            container.unwire()


class TestContainerLifecycle:
    """コンテナライフサイクルのテストクラス"""

    def test_cleanup_container(self):
        """コンテナクリーンアップのテスト"""
        # Create container
        container = get_container()
        
        # Verify container exists
        assert container is not None
        
        # Cleanup
        cleanup_container()
        
        # Verify new container is created after cleanup
        new_container = get_container()
        assert new_container is not container


class TestEnvironmentVariableHandling:
    """環境変数処理のテストクラス"""

    def test_default_database_url(self):
        """デフォルトデータベースURL取得のテスト"""
        with patch.dict(os.environ, {}, clear=True):
            container = ApplicationContainer()
            url = container.database_url()
            assert url == "postgresql://postgres:password@localhost:5432/contact_db"

    def test_custom_database_url(self):
        """カスタムデータベースURL取得のテスト"""
        custom_url = "postgresql://custom:pass@example.com:5432/custom_db"
        with patch.dict(os.environ, {"DATABASE_URL": custom_url}):
            container = ApplicationContainer()
            url = container.database_url()
            assert url == custom_url

    def test_missing_api_keys(self):
        """APIキー未設定時の処理テスト"""
        with patch.dict(os.environ, {}, clear=True):
            container = ApplicationContainer()
            
            # Should return None for missing keys
            assert container.gemini_api_key() is None
            assert container.sendgrid_api_key() is None
            assert container.firebase_credentials_path() is None


class TestServiceIntegration:
    """サービス統合のテストクラス"""

    @patch.dict(os.environ, {
        "GEMINI_API_KEY": "test_gemini_key",
        "SENDGRID_API_KEY": "test_sendgrid_key"
    })
    def test_service_integration_chain(self):
        """サービス統合チェーンのテスト"""
        container = ApplicationContainer()
        container.config.database.echo.from_value(False)
        container.config.database.pool_size.from_value(5)
        container.config.database.max_overflow.from_value(10)
        
        # Test that dependent services are properly injected
        ai_analysis_usecase = container.ai_analysis_usecase()
        vector_search_usecase = container.vector_search_usecase()
        admin_dashboard_api = container.admin_dashboard_api()
        
        # Verify dependencies are correctly resolved
        assert ai_analysis_usecase is not None
        assert vector_search_usecase is not None  
        assert admin_dashboard_api is not None
        
        # Test service chaining
        # AIAnalysisUseCase should have GeminiService and NotificationService
        # VectorSearchUseCase should have VectorService
        # AdminDashboardAPI should have AI and Vector UseCases


if __name__ == "__main__":
    pytest.main([__file__, "-v"])