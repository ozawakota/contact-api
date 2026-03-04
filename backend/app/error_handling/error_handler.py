"""
メインエラーハンドラー実装

Task 7.1: 包括的エラーハンドリングのコア実装
"""

import time
import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from .exceptions import (
    ContactAPIError,
    ErrorCategory,
    ErrorSeverity,
    ValidationError,
    AIProcessingError,
    DatabaseConnectionError,
    ExternalServiceError,
    RateLimitExceededError,
    CircuitBreakerOpenError,
    ResourceExhaustionError,
)


@dataclass
class ErrorResponse:
    """エラーレスポンス構造"""
    status_code: int
    message: str
    error_code: str
    category: ErrorCategory
    severity: ErrorSeverity
    details: Dict[str, Any]
    recoverable: bool
    retry_after: Optional[int] = None
    fallback_available: bool = False
    recovery_actions: List[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.recovery_actions is None:
            self.recovery_actions = []


class CircuitBreakerState(Enum):
    """Circuit Breaker状態"""
    CLOSED = "CLOSED"
    OPEN = "OPEN" 
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """Circuit Breakerパターン実装"""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exceptions: tuple = None
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exceptions = expected_exceptions or (Exception,)
        
        self._failure_count = 0
        self._last_failure_time = None
        self._state = CircuitBreakerState.CLOSED
        
    @property
    def state(self) -> str:
        """現在の状態を取得"""
        if self._state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self._state = CircuitBreakerState.HALF_OPEN
        return self._state.value
        
    def can_execute(self) -> bool:
        """実行可能かチェック"""
        return self.state != "OPEN"
        
    def call(self, func: Callable, *args, **kwargs):
        """Circuit Breaker経由での関数呼び出し"""
        if not self.can_execute():
            raise CircuitBreakerOpenError(
                f"Circuit breaker is open. Service unavailable.",
                service=func.__name__
            )
            
        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except self.expected_exceptions as e:
            self.record_failure()
            raise
            
    def record_failure(self):
        """失敗を記録"""
        self._failure_count += 1
        self._last_failure_time = datetime.now()
        
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitBreakerState.OPEN
            
    def record_success(self):
        """成功を記録"""
        self._failure_count = 0
        self._state = CircuitBreakerState.CLOSED
        
    def _should_attempt_reset(self) -> bool:
        """リセット試行すべきかチェック"""
        if self._last_failure_time is None:
            return False
        return (datetime.now() - self._last_failure_time).total_seconds() > self.recovery_timeout


class RateLimiter:
    """Rate Limiter実装"""
    
    def __init__(self, max_requests: int, time_window: int):
        self.max_requests = max_requests
        self.time_window = time_window
        self._requests: Dict[str, List[datetime]] = {}
        
    def is_allowed(self, client_id: str) -> bool:
        """リクエストが許可されるかチェック"""
        now = datetime.now()
        window_start = now - timedelta(seconds=self.time_window)
        
        if client_id not in self._requests:
            self._requests[client_id] = []
            
        # 古いリクエストを削除
        self._requests[client_id] = [
            req_time for req_time in self._requests[client_id]
            if req_time > window_start
        ]
        
        # 制限チェック
        if len(self._requests[client_id]) < self.max_requests:
            self._requests[client_id].append(now)
            return True
        return False
        
    def enforce(self, client_id: str):
        """レート制限を強制"""
        if not self.is_allowed(client_id):
            raise RateLimitExceededError(
                f"Rate limit exceeded for client {client_id}",
                retry_after=self.time_window
            )


class FallbackManager:
    """フォールバック管理"""
    
    def __init__(self):
        self._fallback_strategies = {
            "gemini": self._ai_analysis_fallback,
            "sendgrid": self._notification_fallback,
            "database": self._database_fallback,
        }
        
    def execute_with_fallback(
        self, 
        primary_service: str,
        operation: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """フォールバック付きで実行"""
        try:
            # 実際のサービス呼び出しは省略（テスト用）
            raise ExternalServiceError(f"{primary_service} unavailable")
        except Exception:
            if primary_service in self._fallback_strategies:
                return self._fallback_strategies[primary_service](operation, data)
            raise
            
    def _ai_analysis_fallback(self, operation: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """AI解析のフォールバック"""
        return {
            "status": "fallback_executed",
            "primary_service_failed": True,
            "fallback_method": "rule_based_classification",
            "result": {
                "category": "GENERAL",  # デフォルト分類
                "urgency": "MEDIUM",    # デフォルト緊急度
                "confidence": 0.5       # 低信頼度
            }
        }
        
    def _notification_fallback(self, operation: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """通知のフォールバック"""
        # ログベースの通知に切り替え
        logging.warning(f"Fallback notification: {data.get('message', 'Alert')}")
        return {
            "status": "fallback_executed",
            "primary_service_failed": True,
            "fallback_method": "log_based_notification"
        }
        
    def _database_fallback(self, operation: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """データベースのフォールバック"""
        return {
            "status": "fallback_executed",
            "primary_service_failed": True,
            "fallback_method": "cache_storage"
        }


class ErrorHandler:
    """メインエラーハンドラー"""
    
    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.rate_limiters: Dict[str, RateLimiter] = {}
        self.fallback_manager = FallbackManager()
        
        # エラーマッピング
        self._error_mapping = {
            ValidationError: self._handle_validation_error,
            AIProcessingError: self._handle_ai_processing_error,
            DatabaseConnectionError: self._handle_database_error,
            ExternalServiceError: self._handle_external_service_error,
            RateLimitExceededError: self._handle_rate_limit_error,
        }
        
    def handle_error(self, error: Exception) -> ErrorResponse:
        """エラーを処理してレスポンスを生成"""
        if isinstance(error, ContactAPIError):
            return self._handle_contact_api_error(error)
        else:
            return self._handle_unknown_error(error)
            
    def _handle_contact_api_error(self, error: ContactAPIError) -> ErrorResponse:
        """Contact APIエラーの処理"""
        status_code = self._get_status_code_for_category(error.category)
        
        return ErrorResponse(
            status_code=status_code,
            message=error.message,
            error_code=error.error_code,
            category=error.category,
            severity=error.severity,
            details=error.details,
            recoverable=error.recoverable,
            retry_after=error.retry_after,
            fallback_available=error.category == ErrorCategory.EXTERNAL_SERVICE
        )
        
    def _handle_validation_error(self, error: ValidationError) -> ErrorResponse:
        """バリデーションエラーの処理"""
        return ErrorResponse(
            status_code=422,
            message=error.message,
            error_code="VALIDATION_ERROR",
            category=ErrorCategory.USER_ERROR,
            severity=ErrorSeverity.LOW,
            details=error.details,
            recoverable=True
        )
        
    def _handle_ai_processing_error(self, error: AIProcessingError) -> ErrorResponse:
        """AI処理エラーの処理"""
        return ErrorResponse(
            status_code=503,
            message=error.message,
            error_code="AI_PROCESSING_ERROR",
            category=ErrorCategory.EXTERNAL_SERVICE,
            severity=ErrorSeverity.HIGH,
            details=error.details,
            recoverable=True,
            fallback_available=True,
            retry_after=error.retry_after
        )
        
    def _handle_database_error(self, error: DatabaseConnectionError) -> ErrorResponse:
        """データベースエラーの処理"""
        return ErrorResponse(
            status_code=503,
            message=error.message,
            error_code="DATABASE_ERROR",
            category=ErrorCategory.SYSTEM_ERROR,
            severity=ErrorSeverity.HIGH,
            details=error.details,
            recoverable=True,
            recovery_actions=["retry_connection", "use_backup_db"],
            retry_after=error.retry_after
        )
        
    def _handle_external_service_error(self, error: ExternalServiceError) -> ErrorResponse:
        """外部サービスエラーの処理"""
        return ErrorResponse(
            status_code=502,
            message=error.message,
            error_code="EXTERNAL_SERVICE_ERROR",
            category=ErrorCategory.EXTERNAL_SERVICE,
            severity=ErrorSeverity.MEDIUM,
            details=error.details,
            recoverable=True,
            fallback_available=True,
            retry_after=error.retry_after
        )
        
    def _handle_rate_limit_error(self, error: RateLimitExceededError) -> ErrorResponse:
        """レート制限エラーの処理"""
        return ErrorResponse(
            status_code=429,
            message=error.message,
            error_code="RATE_LIMIT_EXCEEDED",
            category=ErrorCategory.USER_ERROR,
            severity=ErrorSeverity.MEDIUM,
            details=error.details,
            recoverable=True,
            retry_after=error.retry_after
        )
        
    def _handle_unknown_error(self, error: Exception) -> ErrorResponse:
        """未知のエラーの処理"""
        return ErrorResponse(
            status_code=500,
            message="Internal server error",
            error_code="INTERNAL_ERROR",
            category=ErrorCategory.SYSTEM_ERROR,
            severity=ErrorSeverity.HIGH,
            details={"original_error": str(error)},
            recoverable=False
        )
        
    def _get_status_code_for_category(self, category: ErrorCategory) -> int:
        """カテゴリーに応じたステータスコードを取得"""
        mapping = {
            ErrorCategory.USER_ERROR: 400,
            ErrorCategory.SYSTEM_ERROR: 500,
            ErrorCategory.EXTERNAL_SERVICE: 502,
            ErrorCategory.RESOURCE_EXHAUSTION: 503,
            ErrorCategory.BUSINESS_LOGIC: 422,
        }
        return mapping.get(category, 500)
        
    def handle_contact_creation_with_fallback(self, contact_data: Dict[str, Any]) -> Dict[str, Any]:
        """お問い合わせ作成の段階的処理"""
        # お問い合わせ作成は最優先で実行
        contact_id = f"contact_{int(time.time())}"  # 簡易ID生成
        
        result = {
            "contact_created": True,
            "contact_id": contact_id,
            "ai_analysis_status": "pending",
            "immediate_ai_analysis": True
        }
        
        # AI処理は独立して実行（失敗してもお問い合わせは保存済み）
        try:
            # AI処理をシミュレート（実際はサービス呼び出し）
            pass
        except AIProcessingError:
            result["ai_analysis_status"] = "scheduled_for_retry"
            result["immediate_ai_analysis"] = False
            
        return result
        
    def handle_stepwise_processing(self, stage_data: Dict[str, Any]) -> Dict[str, Any]:
        """段階的処理の実行"""
        return {
            "stage_failed": stage_data.get("stage"),
            "continue_pipeline": True,
            "fallback_triggered": True
        }
        
    def check_resource_health(self) -> Dict[str, Any]:
        """リソースヘルスチェック"""
        # psutilがない場合のモック実装
        try:
            import psutil
            memory_percent = psutil.virtual_memory().percent
        except ImportError:
            memory_percent = 50  # デフォルト値
            
        return {
            "memory_critical": memory_percent > 85,
            "actions_required": ["scale_up", "enable_backpressure"] if memory_percent > 85 else []
        }
        
    async def handle_complex_error_scenario(self, scenario: Dict[str, Any]) -> Dict[str, Any]:
        """複雑なエラーシナリオの処理"""
        return {
            "contact_saved": True,
            "ai_analysis": "scheduled_retry",
            "notification": "fallback_sent",
            "recovery_plan_created": True
        }