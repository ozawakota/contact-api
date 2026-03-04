"""
カスタム例外クラス定義

Task 7.1: エラーカテゴリー別の例外クラス
"""

from typing import Optional, Dict, Any
from enum import Enum


class ErrorCategory(Enum):
    """エラーカテゴリー"""
    USER_ERROR = "user_error"              # 4xx ユーザーエラー
    SYSTEM_ERROR = "system_error"          # 5xx システムエラー  
    EXTERNAL_SERVICE = "external_service"   # 外部サービスエラー
    RESOURCE_EXHAUSTION = "resource_exhaustion"  # リソース枯渇
    BUSINESS_LOGIC = "business_logic"      # ビジネスロジックエラー


class ErrorSeverity(Enum):
    """エラー重要度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ContactAPIError(Exception):
    """Contact API ベース例外クラス"""
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        category: ErrorCategory = ErrorCategory.SYSTEM_ERROR,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        details: Optional[Dict[str, Any]] = None,
        recoverable: bool = True,
        retry_after: Optional[int] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.category = category
        self.severity = severity
        self.details = details or {}
        self.recoverable = recoverable
        self.retry_after = retry_after


class ValidationError(ContactAPIError):
    """入力バリデーションエラー"""
    
    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.USER_ERROR,
            severity=ErrorSeverity.LOW,
            details={"field": field} if field else {},
            recoverable=True,
            **kwargs
        )


class AIProcessingError(ContactAPIError):
    """AI処理エラー"""
    
    def __init__(
        self, 
        message: str, 
        service: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            message=message,
            category=ErrorCategory.EXTERNAL_SERVICE,
            severity=ErrorSeverity.HIGH,
            details={"service": service, "operation": operation},
            recoverable=True,
            retry_after=30,
            **kwargs
        )


class DatabaseConnectionError(ContactAPIError):
    """データベース接続エラー"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.SYSTEM_ERROR,
            severity=ErrorSeverity.HIGH,
            recoverable=True,
            retry_after=60,
            **kwargs
        )


class ExternalServiceError(ContactAPIError):
    """外部サービスエラー"""
    
    def __init__(
        self, 
        message: str, 
        service: Optional[str] = None,
        status_code: Optional[int] = None,
        **kwargs
    ):
        super().__init__(
            message=message,
            category=ErrorCategory.EXTERNAL_SERVICE,
            severity=ErrorSeverity.MEDIUM,
            details={"service": service, "status_code": status_code},
            recoverable=True,
            retry_after=30,
            **kwargs
        )


class RateLimitExceededError(ContactAPIError):
    """レート制限超過エラー"""
    
    def __init__(self, message: str, retry_after: int = 60, **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.USER_ERROR,
            severity=ErrorSeverity.MEDIUM,
            recoverable=True,
            retry_after=retry_after,
            **kwargs
        )


class CircuitBreakerOpenError(ContactAPIError):
    """Circuit Breaker開放エラー"""
    
    def __init__(self, message: str, service: str, **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.EXTERNAL_SERVICE,
            severity=ErrorSeverity.HIGH,
            details={"service": service},
            recoverable=True,
            retry_after=300,  # 5分後に再試行
            **kwargs
        )


class ResourceExhaustionError(ContactAPIError):
    """リソース枯渇エラー"""
    
    def __init__(
        self, 
        message: str, 
        resource_type: str,
        current_usage: Optional[float] = None,
        **kwargs
    ):
        super().__init__(
            message=message,
            category=ErrorCategory.RESOURCE_EXHAUSTION,
            severity=ErrorSeverity.CRITICAL,
            details={"resource_type": resource_type, "current_usage": current_usage},
            recoverable=True,
            retry_after=120,
            **kwargs
        )


class BusinessLogicError(ContactAPIError):
    """ビジネスロジックエラー"""
    
    def __init__(self, message: str, rule: Optional[str] = None, **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.BUSINESS_LOGIC,
            severity=ErrorSeverity.MEDIUM,
            details={"rule": rule} if rule else {},
            recoverable=False,
            **kwargs
        )