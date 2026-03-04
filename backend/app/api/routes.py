"""FastAPIルーター・エンドポイント実装

お問い合わせ受付API・管理者用API群・Firebase認証・APIドキュメント機能を統合。
"""

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional, Annotated
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import (
    FastAPI, APIRouter, Depends, HTTPException, status, Request, Response,
    Header, Query, Path, Body
)
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field, validator
from sqlalchemy.orm import Session

# ローカルインポート
from models.contact import Contact
from models.contact_ai_analysis import ContactAIAnalysis


# リクエスト/レスポンスモデル
class ContactCreateRequest(BaseModel):
    """お問い合わせ作成リクエスト"""
    name: str = Field(..., min_length=1, max_length=100, description="お名前")
    email: EmailStr = Field(..., description="メールアドレス")
    subject: str = Field(..., min_length=1, max_length=200, description="件名")
    message: str = Field(..., min_length=1, max_length=10000, description="お問い合わせ内容")
    
    @validator('name', 'subject', 'message')
    def sanitize_string_fields(cls, v):
        """文字列フィールドのサニタイゼーション"""
        if isinstance(v, str):
            # 基本的なサニタイゼーション
            v = v.strip()
            # SQLインジェクション対策（基本的なエスケープ）
            dangerous_chars = ["'", '"', ';', '--', '/*', '*/', 'xp_', 'sp_']
            for char in dangerous_chars:
                v = v.replace(char, '')
        return v


class ContactResponse(BaseModel):
    """お問い合わせレスポンス"""
    success: bool = True
    contact: Optional[Dict[str, Any]] = None
    message: Optional[str] = None


class ContactStatusUpdateRequest(BaseModel):
    """コンタクトステータス更新リクエスト"""
    status: str = Field(..., description="新しいステータス")
    notes: Optional[str] = Field(None, max_length=500, description="更新メモ")


class AIAnalysisUpdateRequest(BaseModel):
    """AI分析結果更新リクエスト"""
    category: str = Field(..., description="カテゴリ")
    urgency: int = Field(..., ge=1, le=3, description="緊急度")
    sentiment: str = Field(..., description="感情")
    notes: Optional[str] = Field(None, max_length=500, description="更新メモ")


class PaginationParams(BaseModel):
    """ページネーションパラメータ"""
    page: int = Field(1, ge=1, description="ページ番号")
    per_page: int = Field(20, ge=1, le=100, description="ページあたり件数")


class ContactFilterParams(BaseModel):
    """コンタクトフィルタパラメータ"""
    status_filter: Optional[str] = Field(None, description="ステータスフィルタ")
    category_filter: Optional[str] = Field(None, description="カテゴリフィルタ")
    urgency_filter: Optional[int] = Field(None, ge=1, le=3, description="緊急度フィルタ")
    date_from: Optional[str] = Field(None, description="開始日 (YYYY-MM-DD)")
    date_to: Optional[str] = Field(None, description="終了日 (YYYY-MM-DD)")


class ExportParams(BaseModel):
    """エクスポートパラメータ"""
    start_date: str = Field(..., description="開始日 (YYYY-MM-DD)")
    end_date: str = Field(..., description="終了日 (YYYY-MM-DD)")
    format: str = Field("json", regex="^(json|csv)$", description="エクスポート形式")


# セキュリティ
security = HTTPBearer(auto_error=False)


class AuthenticationError(Exception):
    """認証エラー"""
    def __init__(self, message: str = "Authentication failed"):
        self.message = message


class AuthorizationError(Exception):
    """認可エラー"""
    def __init__(self, message: str = "Insufficient permissions"):
        self.message = message


class APIRoutes:
    """FastAPIルーター・エンドポイント実装クラス
    
    Features:
    - お問い合わせ受付API（POST /api/v1/contacts）統合
    - 管理者用API群（GET /api/v1/admin/contacts、PATCH更新等）
    - Firebase認証ガード・JWT検証・管理者権限チェック
    - APIドキュメント自動生成・Swagger UI設定
    """
    
    def __init__(
        self,
        db_session: Session,
        firebase_auth=None,
        contact_usecase=None,
        ai_analysis_usecase=None,
        admin_dashboard_api=None,
        vector_search_usecase=None,
        notification_service=None
    ):
        """APIルーター初期化
        
        Args:
            db_session: データベースセッション
            firebase_auth: Firebase認証サービス
            contact_usecase: ContactUseCase
            ai_analysis_usecase: AIAnalysisUseCase
            admin_dashboard_api: AdminDashboardAPI
            vector_search_usecase: VectorSearchUseCase
            notification_service: NotificationService
        """
        self.db_session = db_session
        self.firebase_auth = firebase_auth
        self.contact_usecase = contact_usecase
        self.ai_analysis_usecase = ai_analysis_usecase
        self.admin_dashboard_api = admin_dashboard_api
        self.vector_search_usecase = vector_search_usecase
        self.notification_service = notification_service
        self.logger = logging.getLogger(__name__)
        
        # ルーター作成
        self.public_router = APIRouter(prefix="/api/v1")
        self.admin_router = APIRouter(prefix="/api/v1/admin")
        
        # エンドポイント登録
        self._register_public_endpoints()
        self._register_admin_endpoints()
        
        self.logger.info("APIRoutes初期化完了")
    
    def _register_public_endpoints(self):
        """パブリックエンドポイント登録"""
        
        @self.public_router.post("/contacts", 
                               response_model=ContactResponse,
                               status_code=status.HTTP_201_CREATED,
                               summary="お問い合わせ作成",
                               description="新規お問い合わせを作成し、AI解析を自動実行します。")
        async def create_contact(
            request: ContactCreateRequest,
            http_request: Request
        ) -> ContactResponse:
            """お問い合わせ作成エンドポイント"""
            try:
                self.logger.info(f"お問い合わせ作成リクエスト: {request.email}")
                
                # ContactUseCaseによるお問い合わせ作成
                if not self.contact_usecase:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="ContactUseCase not configured"
                    )
                
                create_result = await self.contact_usecase.create_contact(
                    name=request.name,
                    email=request.email,
                    subject=request.subject,
                    message=request.message,
                    client_ip=http_request.client.host
                )
                
                if not create_result.get('success'):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=create_result.get('error', 'Contact creation failed')
                    )
                
                contact = create_result['contact']
                
                # AI解析を非同期で開始
                if self.ai_analysis_usecase and contact.get('id'):
                    asyncio.create_task(
                        self._trigger_ai_analysis(contact['id'])
                    )
                
                return ContactResponse(
                    success=True,
                    contact=contact,
                    message="お問い合わせを受け付けました。AI解析を開始します。"
                )
                
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"お問い合わせ作成エラー: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error"
                )
        
        @self.public_router.get("/contacts/{contact_id}",
                              response_model=ContactResponse,
                              summary="お問い合わせ詳細取得",
                              description="指定IDのお問い合わせ詳細を取得します。")
        async def get_contact(
            contact_id: int = Path(..., description="コンタクトID")
        ) -> ContactResponse:
            """お問い合わせ詳細取得エンドポイント"""
            try:
                self.logger.info(f"お問い合わせ詳細取得: contact_id={contact_id}")
                
                if not self.contact_usecase:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="ContactUseCase not configured"
                    )
                
                result = await self.contact_usecase.get_contact_by_id(contact_id)
                
                if not result.get('success'):
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Contact not found"
                    )
                
                return ContactResponse(
                    success=True,
                    contact=result['contact']
                )
                
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"お問い合わせ詳細取得エラー: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error"
                )
    
    def _register_admin_endpoints(self):
        """管理者エンドポイント登録"""
        
        @self.admin_router.get("/contacts",
                             summary="管理者：お問い合わせ一覧取得",
                             description="管理者用のお問い合わせ一覧を取得します。ページネーション・フィルタ対応。")
        async def get_admin_contacts(
            page: int = Query(1, ge=1, description="ページ番号"),
            per_page: int = Query(20, ge=1, le=100, description="ページあたり件数"),
            status_filter: Optional[str] = Query(None, description="ステータスフィルタ"),
            category_filter: Optional[str] = Query(None, description="カテゴリフィルタ"),
            urgency_filter: Optional[int] = Query(None, ge=1, le=3, description="緊急度フィルタ"),
            date_from: Optional[str] = Query(None, description="開始日"),
            date_to: Optional[str] = Query(None, description="終了日"),
            sort_by: str = Query("created_at", description="ソート項目"),
            sort_order: str = Query("desc", regex="^(asc|desc)$", description="ソート順序"),
            current_user: Dict[str, Any] = Depends(self._get_admin_user)
        ):
            """管理者お問い合わせ一覧取得"""
            try:
                if not self.admin_dashboard_api:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="AdminDashboardAPI not configured"
                    )
                
                result = await self.admin_dashboard_api.get_contacts_list(
                    page=page,
                    per_page=per_page,
                    status_filter=status_filter,
                    category_filter=category_filter,
                    urgency_filter=urgency_filter,
                    date_from=date_from,
                    date_to=date_to,
                    sort_by=sort_by,
                    sort_order=sort_order
                )
                
                return result
                
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"管理者お問い合わせ一覧取得エラー: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error"
                )
        
        @self.admin_router.get("/contacts/{contact_id}",
                             summary="管理者：お問い合わせ詳細取得",
                             description="管理者用のお問い合わせ詳細を取得します。")
        async def get_admin_contact_detail(
            contact_id: int = Path(..., description="コンタクトID"),
            current_user: Dict[str, Any] = Depends(self._get_admin_user)
        ):
            """管理者お問い合わせ詳細取得"""
            try:
                if not self.admin_dashboard_api:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="AdminDashboardAPI not configured"
                    )
                
                result = await self.admin_dashboard_api.get_contact_detail(contact_id)
                
                if not result.get('success'):
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Contact not found"
                    )
                
                return result
                
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"管理者お問い合わせ詳細取得エラー: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error"
                )
        
        @self.admin_router.patch("/contacts/{contact_id}/status",
                               summary="管理者：ステータス更新",
                               description="お問い合わせのステータスを手動更新します。")
        async def update_contact_status(
            contact_id: int = Path(..., description="コンタクトID"),
            request: ContactStatusUpdateRequest = Body(...),
            current_user: Dict[str, Any] = Depends(self._get_admin_user)
        ):
            """コンタクトステータス更新"""
            try:
                if not self.admin_dashboard_api:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="AdminDashboardAPI not configured"
                    )
                
                result = await self.admin_dashboard_api.update_contact_status(
                    contact_id=contact_id,
                    new_status=request.status,
                    admin_user_id=current_user['uid'],
                    notes=request.notes
                )
                
                if not result.get('success'):
                    error_code = result.get('error', 'update_failed')
                    if error_code == 'contact_not_found':
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail="Contact not found"
                        )
                    elif error_code == 'invalid_status':
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=result.get('message', 'Invalid status')
                        )
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=result.get('message', 'Update failed')
                        )
                
                return result
                
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"ステータス更新エラー: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error"
                )
        
        @self.admin_router.patch("/contacts/{contact_id}/ai-analysis",
                               summary="管理者：AI分析結果更新",
                               description="AI分析結果を手動で修正します。")
        async def update_ai_analysis(
            contact_id: int = Path(..., description="コンタクトID"),
            request: AIAnalysisUpdateRequest = Body(...),
            current_user: Dict[str, Any] = Depends(self._get_admin_user)
        ):
            """AI分析結果更新"""
            try:
                if not self.admin_dashboard_api:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="AdminDashboardAPI not configured"
                    )
                
                result = await self.admin_dashboard_api.update_ai_analysis_manual(
                    contact_id=contact_id,
                    new_category=request.category,
                    new_urgency=request.urgency,
                    new_sentiment=request.sentiment,
                    admin_user_id=current_user['uid'],
                    notes=request.notes
                )
                
                if not result.get('success'):
                    error_code = result.get('error', 'update_failed')
                    if error_code == 'analysis_not_found':
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail="AI analysis not found"
                        )
                    elif error_code.startswith('invalid_'):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=result.get('message', 'Invalid input')
                        )
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=result.get('message', 'Update failed')
                        )
                
                return result
                
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"AI分析結果更新エラー: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error"
                )
        
        # 分析エンドポイント
        @self.admin_router.get("/analytics/overview",
                             summary="管理者：統計概要取得",
                             description="全体統計の概要を取得します。")
        async def get_analytics_overview(
            current_user: Dict[str, Any] = Depends(self._get_admin_user)
        ):
            """統計概要取得"""
            try:
                if not self.admin_dashboard_api:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="AdminDashboardAPI not configured"
                    )
                
                result = await self.admin_dashboard_api.get_analytics_overview()
                return result
                
            except Exception as e:
                self.logger.error(f"統計概要取得エラー: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error"
                )
        
        @self.admin_router.get("/analytics/ai-performance",
                             summary="管理者：AI性能メトリクス取得",
                             description="AI分析の性能指標を取得します。")
        async def get_ai_performance_metrics(
            current_user: Dict[str, Any] = Depends(self._get_admin_user)
        ):
            """AI性能メトリクス取得"""
            try:
                if not self.admin_dashboard_api:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="AdminDashboardAPI not configured"
                    )
                
                result = await self.admin_dashboard_api.get_ai_performance_metrics()
                return result
                
            except Exception as e:
                self.logger.error(f"AI性能メトリクス取得エラー: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error"
                )
        
        @self.admin_router.get("/analytics/processing-time",
                             summary="管理者：処理時間分析取得",
                             description="処理時間の分析結果を取得します。")
        async def get_processing_time_analysis(
            current_user: Dict[str, Any] = Depends(self._get_admin_user)
        ):
            """処理時間分析取得"""
            try:
                if not self.admin_dashboard_api:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="AdminDashboardAPI not configured"
                    )
                
                result = await self.admin_dashboard_api.get_processing_time_analysis()
                return result
                
            except Exception as e:
                self.logger.error(f"処理時間分析取得エラー: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error"
                )
        
        @self.admin_router.get("/analytics/export",
                             summary="管理者：分析データエクスポート",
                             description="指定期間の分析データをエクスポートします。")
        async def export_analytics_data(
            start_date: str = Query(..., description="開始日 (YYYY-MM-DD)"),
            end_date: str = Query(..., description="終了日 (YYYY-MM-DD)"),
            format: str = Query("json", regex="^(json|csv)$", description="エクスポート形式"),
            current_user: Dict[str, Any] = Depends(self._get_admin_user)
        ):
            """分析データエクスポート"""
            try:
                if not self.admin_dashboard_api:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="AdminDashboardAPI not configured"
                    )
                
                result = await self.admin_dashboard_api.export_analytics_data(
                    date_range={'start': start_date, 'end': end_date},
                    format=format
                )
                
                return result
                
            except Exception as e:
                self.logger.error(f"データエクスポートエラー: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error"
                )
    
    async def _trigger_ai_analysis(self, contact_id: int):
        """AI解析トリガー（非同期）"""
        try:
            if not self.ai_analysis_usecase:
                self.logger.warning("AIAnalysisUseCase not configured")
                return
            
            self.logger.info(f"AI解析開始: contact_id={contact_id}")
            
            # AI解析実行
            analysis_result = await self.ai_analysis_usecase.execute_analysis({
                'contact_id': contact_id
            })
            
            if analysis_result.get('success'):
                self.logger.info(f"AI解析完了: contact_id={contact_id}")
                
                # ベクトル検索実行
                if self.vector_search_usecase:
                    await self.vector_search_usecase.process_ai_analysis_completion(
                        contact_id=contact_id,
                        ai_analysis=analysis_result.get('analysis')
                    )
            else:
                self.logger.error(f"AI解析失敗: contact_id={contact_id}, error={analysis_result.get('error')}")
                
                # 失敗通知
                if self.notification_service:
                    await self.notification_service.notify_analysis_failure(
                        contact_id=contact_id,
                        error_type=analysis_result.get('error_type', 'unknown'),
                        error_message=analysis_result.get('error', 'Analysis failed'),
                        retry_possible=analysis_result.get('retry_possible', True)
                    )
            
        except Exception as e:
            self.logger.error(f"AI解析トリガーエラー: contact_id={contact_id}, error={e}")
            
            # エラー通知
            if self.notification_service:
                await self.notification_service.notify_analysis_failure(
                    contact_id=contact_id,
                    error_type="system_error",
                    error_message=str(e),
                    retry_possible=True
                )
    
    async def _get_current_user(
        self,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
    ) -> Optional[Dict[str, Any]]:
        """現在ユーザー取得"""
        if not credentials:
            return None
        
        if not self.firebase_auth:
            # 認証サービスが設定されていない場合はスキップ
            return {'uid': 'test_user', 'email': 'test@example.com'}
        
        try:
            token = credentials.credentials
            user_info = self.firebase_auth.verify_token(token)
            return user_info
        except Exception as e:
            self.logger.warning(f"トークン検証エラー: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"}
            )
    
    async def _get_admin_user(
        self,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
    ) -> Dict[str, Any]:
        """管理者ユーザー取得（認証・認可チェック）"""
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        if not self.firebase_auth:
            # 認証サービスが設定されていない場合はテストユーザー
            return {'uid': 'admin_test', 'email': 'admin@example.com', 'role': 'admin'}
        
        try:
            token = credentials.credentials
            user_info = self.firebase_auth.verify_admin_token(token)
            
            if not user_info:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication token",
                    headers={"WWW-Authenticate": "Bearer"}
                )
            
            # 管理者権限チェック
            user_role = user_info.get('role', 'user')
            if user_role not in ['admin', 'super_admin']:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Admin role required"
                )
            
            return user_info
            
        except HTTPException:
            raise
        except Exception as e:
            self.logger.warning(f"管理者認証エラー: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed",
                headers={"WWW-Authenticate": "Bearer"}
            )


def create_app(
    db_session: Session = None,
    firebase_auth=None,
    contact_usecase=None,
    ai_analysis_usecase=None,
    admin_dashboard_api=None,
    vector_search_usecase=None,
    notification_service=None,
    title: str = "Next-Gen Support System API",
    version: str = "1.0.0"
) -> FastAPI:
    """FastAPIアプリケーション作成
    
    Args:
        db_session: データベースセッション
        firebase_auth: Firebase認証サービス
        contact_usecase: ContactUseCase
        ai_analysis_usecase: AIAnalysisUseCase  
        admin_dashboard_api: AdminDashboardAPI
        vector_search_usecase: VectorSearchUseCase
        notification_service: NotificationService
        title: APIタイトル
        version: APIバージョン
        
    Returns:
        設定済みFastAPIアプリケーション
    """
    
    # アプリケーション作成
    app = FastAPI(
        title=title,
        version=version,
        description="""
        次世代カスタマーサポートシステムAPI

        ## 機能
        - **お問い合わせ受付**: 顧客からのお問い合わせを受付・AI自動分析
        - **管理者ダッシュボード**: お問い合わせ管理・統計分析・手動更新
        - **AI自動分類**: Gemini APIによる自動分類・感情分析・緊急度判定
        - **ベクトル検索**: 類似事例検索・推奨情報生成
        - **通知システム**: 緊急度別エスカレーション・管理者通知

        ## 認証
        管理者APIにはFirebase認証トークンが必要です。
        """,
        contact={
            "name": "Development Team",
            "email": "dev@example.com"
        },
        license_info={
            "name": "MIT License",
            "url": "https://opensource.org/licenses/MIT"
        }
    )
    
    # CORS設定
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "https://localhost:3000"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"]
    )
    
    # Trusted Host設定
    app.add_middleware(
        TrustedHostMiddleware, 
        allowed_hosts=["localhost", "*.localhost", "127.0.0.1"]
    )
    
    # APIルーター設定
    api_routes = APIRoutes(
        db_session=db_session,
        firebase_auth=firebase_auth,
        contact_usecase=contact_usecase,
        ai_analysis_usecase=ai_analysis_usecase,
        admin_dashboard_api=admin_dashboard_api,
        vector_search_usecase=vector_search_usecase,
        notification_service=notification_service
    )
    
    # ルーター登録
    app.include_router(api_routes.public_router, tags=["お問い合わせ"])
    app.include_router(api_routes.admin_router, tags=["管理者"])
    
    # ヘルスチェックエンドポイント
    @app.get("/health", summary="ヘルスチェック", tags=["システム"])
    async def health_check():
        """ヘルスチェック"""
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": version
        }
    
    # エラーハンドラー
    @app.exception_handler(AuthenticationError)
    async def authentication_error_handler(request: Request, exc: AuthenticationError):
        """認証エラーハンドラー"""
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": exc.message},
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    @app.exception_handler(AuthorizationError)
    async def authorization_error_handler(request: Request, exc: AuthorizationError):
        """認可エラーハンドラー"""
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": exc.message}
        )
    
    # 汎用エラーハンドラー
    @app.exception_handler(500)
    async def internal_server_error_handler(request: Request, exc):
        """内部サーバーエラーハンドラー"""
        logging.getLogger(__name__).error(f"Internal server error: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"}
        )
    
    # レスポンスタイムミドルウェア
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        """処理時間ヘッダー追加"""
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response
    
    return app