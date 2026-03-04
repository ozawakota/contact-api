"""
メインアプリケーションエントリーポイント

Task 6.2統合完了:
- ApplicationContainer依存性注入システム統合
- 環境別設定とサービス組み立て
- APIルーター統合
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import firebase_admin
from firebase_admin import credentials

from .contacts.providers import (
    create_application_container,
    initialize_database,
    wire_container,
)
from .api.routes import create_app


# Firebase Admin初期化
def initialize_firebase():
    """Firebase Admin SDKの初期化"""
    if not firebase_admin._apps:
        # Firebase credentials pathから認証情報を読み込み
        cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
        if cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
        else:
            # 開発環境用のデフォルト設定（環境変数から認証情報を取得）
            firebase_admin.initialize_app()


# Application lifespan management
@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーションライフサイクル管理"""
    # Startup
    print("🚀 Starting Contact API application...")
    
    # Initialize Firebase
    initialize_firebase()
    
    # Setup dependency injection container
    container = create_application_container()
    app.state.container = container
    
    # Initialize database
    initialize_database(container)
    
    print("✅ Application startup complete")
    
    yield
    
    # Shutdown
    print("🛑 Shutting down Contact API application...")
    container.unwire()
    print("✅ Application shutdown complete")


# Create the main FastAPI application
def create_main_app() -> FastAPI:
    """メインアプリケーションの作成"""
    
    # Get environment
    env = os.getenv("ENVIRONMENT", "development")
    
    # Create container and wire dependencies
    container = create_application_container()
    
    # Create FastAPI app with integrated services
    main_app = create_app(
        db_session=container.database_session_factory,
        firebase_auth=None,  # Firebase auth will be configured separately
        contact_usecase=container.contact_usecase(),
        ai_analysis_usecase=container.ai_analysis_usecase(),
        admin_dashboard_api=container.admin_dashboard_api(),
        vector_search_usecase=container.vector_search_usecase(),
        notification_service=container.notification_service(),
    )
    
    # Set lifespan
    main_app.router.lifespan_context = lifespan
    
    # Add CORS middleware
    main_app.add_middleware(
        CORSMiddleware,
        allow_origins=_get_cors_origins(env),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Store container in app state
    main_app.state.container = container
    
    # Add health check endpoint
    @main_app.get("/health")
    async def health_check():
        """ヘルスチェックエンドポイント"""
        return {
            "status": "healthy",
            "environment": env,
            "service": "Contact API",
            "version": "1.0.0"
        }
    
    # Legacy endpoint for backward compatibility
    @main_app.get("/")
    async def read_root():
        """ルートエンドポイント（後方互換性のため）"""
        return {
            "message": "Contact API v1.0",
            "environment": env,
            "status": "running"
        }
    
    return main_app


def _get_cors_origins(env: str) -> list[str]:
    """環境別CORS設定の取得"""
    if env == "production":
        # 本番環境では特定のドメインのみ許可
        return [
            "https://your-frontend-domain.com",
            "https://admin-dashboard.your-domain.com",
        ]
    elif env == "development":
        # 開発環境では localhost を許可
        return [
            "http://localhost:3000",
            "http://localhost:3001", 
            "http://127.0.0.1:3000",
            "http://127.0.0.1:3001",
        ]
    else:
        # テスト環境では制限なし
        return ["*"]


# Create the application instance
app = create_main_app()