"""X'èeûµüÓ¹DËf(×íĞ¤Àü

Task 6.2nŸÅ:
- °µüÓ¹GeminiServiceVectorServiceNotificationService	nDI-š
- UseCasedxnX'èeûé¤Õµ¤¯ë¡
- °ƒ%-šûâÃ¯µüÓ¹ŠÿHşÜ
- âXContactUseCasehnqûø’#:-š
"""

from functools import lru_cache
from typing import Callable, Dict, Any, Optional
import os
from dependency_injector import containers, providers
from dependency_injector.wiring import Provide, inject

from sqlmodel import create_engine, Session
from fastapi import Depends

# Services
from ..services.gemini_service import GeminiService
from ..services.vector_service import VectorService
from ..services.notification_service import NotificationService

# Use Cases
from .use_case import ContactUseCase
from ..use_cases.ai_analysis_usecase import AIAnalysisUseCase
from ..use_cases.vector_search_usecase import VectorSearchUseCase

# API
from ..api.admin_dashboard import AdminDashboardAPI
from ..api.routes import APIRoutes

# Models and Config
from ..models.contact import Contact
from ..models.contact_ai_analysis import ContactAIAnalysis
from ..models.contact_vector import ContactVector
from ..config.ai_config import AIConfig


class ApplicationContainer(containers.DeclarativeContainer):
    """¢×ê±ü·çóhSnX'èe³óÆÊ"""

    # Configuration
    config = providers.Configuration()
    
    # Database
    database_url = providers.Callable(
        lambda: os.getenv(
            "DATABASE_URL", 
            "postgresql://postgres:password@localhost:5432/contact_db"
        )
    )
    
    database_engine = providers.Singleton(
        create_engine,
        config.database_url,
        echo=config.database.echo.as_(bool),
        pool_size=config.database.pool_size.as_(int),
        max_overflow=config.database.max_overflow.as_(int),
    )
    
    database_session_factory = providers.Factory(
        Session,
        database_engine,
    )

    # External Service Configuration
    gemini_api_key = providers.Callable(
        lambda: os.getenv("GEMINI_API_KEY")
    )
    
    sendgrid_api_key = providers.Callable(
        lambda: os.getenv("SENDGRID_API_KEY")
    )
    
    firebase_credentials_path = providers.Callable(
        lambda: os.getenv("FIREBASE_CREDENTIALS_PATH")
    )

    # AI Configuration
    ai_config = providers.Singleton(
        AIConfig
    )

    # Core Services
    gemini_service = providers.Singleton(
        GeminiService,
        api_key=gemini_api_key,
        config=ai_config,
    )

    vector_service = providers.Singleton(
        VectorService,
        db_session=database_session_factory,
        gemini_service=gemini_service,
    )

    notification_service = providers.Singleton(
        NotificationService,
        api_key=sendgrid_api_key,
    )

    # Use Cases
    contact_usecase = providers.Singleton(
        ContactUseCase,
        db_session=database_session_factory,
    )

    ai_analysis_usecase = providers.Singleton(
        AIAnalysisUseCase,
        db_session=database_session_factory,
        gemini_service=gemini_service,
        notification_service=notification_service,
    )

    vector_search_usecase = providers.Singleton(
        VectorSearchUseCase,
        db_session=database_session_factory,
        vector_service=vector_service,
    )

    # API Layer
    admin_dashboard_api = providers.Singleton(
        AdminDashboardAPI,
        db_session=database_session_factory,
        ai_analysis_usecase=ai_analysis_usecase,
        vector_search_usecase=vector_search_usecase,
    )

    api_routes = providers.Singleton(
        APIRoutes,
        db_session=database_session_factory,
        firebase_auth=providers.Object(None),  # Firebase auth will be injected separately
        contact_usecase=contact_usecase,
        ai_analysis_usecase=ai_analysis_usecase,
        admin_dashboard_api=admin_dashboard_api,
        vector_search_usecase=vector_search_usecase,
        notification_service=notification_service,
    )


class TestApplicationContainer(containers.DeclarativeContainer):
    """Æ¹È(nX'èe³óÆÊâÃ¯µüÓ¹şÜ	"""
    
    # Configuration for testing
    config = providers.Configuration()
    
    # Test Database (in-memory SQLite)
    database_url = providers.Callable(
        lambda: "sqlite:///:memory:"
    )
    
    database_engine = providers.Singleton(
        create_engine,
        config.database_url,
        echo=False,
    )
    
    database_session_factory = providers.Factory(
        Session,
        database_engine,
    )

    # Mock Services
    gemini_service = providers.Singleton(
        # Mock implementation will be provided during testing
        providers.Object(None)
    )

    vector_service = providers.Singleton(
        providers.Object(None)
    )

    notification_service = providers.Singleton(
        providers.Object(None)
    )

    # Test Use Cases with mocked services
    contact_usecase = providers.Singleton(
        ContactUseCase,
        db_session=database_session_factory,
    )

    ai_analysis_usecase = providers.Singleton(
        providers.Object(None)  # Will be mocked
    )

    vector_search_usecase = providers.Singleton(
        providers.Object(None)  # Will be mocked
    )

    admin_dashboard_api = providers.Singleton(
        providers.Object(None)  # Will be mocked
    )


# Global container instance
container: Optional[ApplicationContainer] = None


def get_container() -> ApplicationContainer:
    """¢×ê±ü·çó³óÆÊn·ó°ëÈó¢¯»¹"""
    global container
    if container is None:
        container = ApplicationContainer()
        # Default configuration
        container.config.database.echo.from_value(False)
        container.config.database.pool_size.from_value(10)
        container.config.database.max_overflow.from_value(20)
    return container


def get_test_container() -> TestApplicationContainer:
    """Æ¹È(³óÆÊn\"""
    test_container = TestApplicationContainer()
    test_container.config.database_url.from_value("sqlite:///:memory:")
    return test_container


# FastAPI dependency injection functions
@inject
def get_database_session(
    session_factory: Callable[[], Session] = Provide[ApplicationContainer.database_session_factory],
) -> Session:
    """Çü¿Ùü¹»Ã·çónFastAPIX'èe"""
    return session_factory()


@inject
def get_contact_usecase(
    usecase: ContactUseCase = Provide[ApplicationContainer.contact_usecase],
) -> ContactUseCase:
    """ContactUseCasenFastAPIX'èe"""
    return usecase


@inject
def get_ai_analysis_usecase(
    usecase: AIAnalysisUseCase = Provide[ApplicationContainer.ai_analysis_usecase],
) -> AIAnalysisUseCase:
    """AIAnalysisUseCasenFastAPIX'èe"""
    return usecase


@inject
def get_vector_search_usecase(
    usecase: VectorSearchUseCase = Provide[ApplicationContainer.vector_search_usecase],
) -> VectorSearchUseCase:
    """VectorSearchUseCasenFastAPIX'èe"""
    return usecase


@inject
def get_admin_dashboard_api(
    api: AdminDashboardAPI = Provide[ApplicationContainer.admin_dashboard_api],
) -> AdminDashboardAPI:
    """AdminDashboardAPInFastAPIX'èe"""
    return api


@inject
def get_notification_service(
    service: NotificationService = Provide[ApplicationContainer.notification_service],
) -> NotificationService:
    """NotificationServicenFastAPIX'èe"""
    return service


@inject
def get_gemini_service(
    service: GeminiService = Provide[ApplicationContainer.gemini_service],
) -> GeminiService:
    """GeminiServicenFastAPIX'èe"""
    return service


@inject
def get_vector_service(
    service: VectorService = Provide[ApplicationContainer.vector_service],
) -> VectorService:
    """VectorServicenFastAPIX'èe"""
    return service


def setup_container_config(env: str = "development") -> ApplicationContainer:
    """°ƒ%³óÆÊ-š
    
    Args:
        env: °ƒ ('development', 'testing', 'production')
        
    Returns:
        -šnApplicationContainer
    """
    container = get_container()
    
    if env == "development":
        container.config.database.echo.from_value(True)
        container.config.database.pool_size.from_value(5)
        container.config.database.max_overflow.from_value(10)
    elif env == "production":
        container.config.database.echo.from_value(False)
        container.config.database.pool_size.from_value(20)
        container.config.database.max_overflow.from_value(30)
    elif env == "testing":
        # Testing uses the TestApplicationContainer instead
        pass
    
    return container


def wire_container(container: ApplicationContainer, modules: list[str] = None) -> None:
    """³óÆÊnX'èeMÚ
    
    Args:
        container: MÚY‹³óÆÊ
        modules: MÚşanâ¸åüëê¹È
    """
    if modules is None:
        modules = [
            "backend.app.api.routes",
            "backend.app.api.admin_dashboard",
            "backend.app.use_cases.ai_analysis_usecase",
            "backend.app.use_cases.vector_search_usecase",
            "backend.app.contacts.use_case",
        ]
    
    container.wire(modules=modules)


# Environment-specific factory functions
def create_application_container() -> ApplicationContainer:
    """,jû‹z°ƒ(¢×ê±ü·çó³óÆÊn\"""
    env = os.getenv("ENVIRONMENT", "development")
    container = setup_container_config(env)
    wire_container(container)
    return container


def create_test_container_with_mocks(**mock_services) -> TestApplicationContainer:
    """âÃ¯µüÓ¹ØMÆ¹È³óÆÊn\
    
    Args:
        **mock_services: âÃ¯µüÓ¹nø
                        ‹: gemini_service=mock_gemini, vector_service=mock_vector
    
    Returns:
        -šnTestApplicationContainer
    """
    container = get_test_container()
    
    # Inject mock services
    for service_name, mock_service in mock_services.items():
        if hasattr(container, service_name):
            setattr(container, service_name, providers.Object(mock_service))
    
    return container


# Utility functions for application lifecycle
def initialize_database(container: ApplicationContainer) -> None:
    """Çü¿Ùü¹n
    
    Args:
        container: ¢×ê±ü·çó³óÆÊ
    """
    engine = container.database_engine()
    # Create all tables (this should be handled by migrations in production)
    from sqlmodel import SQLModel
    SQLModel.metadata.create_all(engine)


def cleanup_container() -> None:
    """³óÆÊn¯êüó¢Ã×;kÆ¹È(	"""
    global container
    if container:
        container.unwire()
        container.reset_singletons()
        container = None


# Export for easy importing
__all__ = [
    "ApplicationContainer",
    "TestApplicationContainer",
    "get_container",
    "get_test_container",
    "get_database_session",
    "get_contact_usecase",
    "get_ai_analysis_usecase",
    "get_vector_search_usecase",
    "get_admin_dashboard_api",
    "get_notification_service",
    "get_gemini_service",
    "get_vector_service",
    "setup_container_config",
    "wire_container",
    "create_application_container",
    "create_test_container_with_mocks",
    "initialize_database",
    "cleanup_container",
]