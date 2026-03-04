"""
Task 7.1 包括的エラーハンドリングのテスト

TDD-REDフェーズ: 失敗するテストを先に作成
- 入力検証エラー・AI処理エラー・DB接続エラーの分類別処理
- 段階的整合性制御（お問い合わせ受付保証・AI処理独立性）
- 外部サービス障害時のフォールバック・Circuit Breakerパターン
- リソース枯渇エラー・Rate Limiting・自動スケーリング連携
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError
from google.api_core.exceptions import GoogleAPIError, ServiceUnavailable, TooManyRequests

from backend.app.error_handling.error_handler import (
    ErrorHandler,
    ErrorCategory,
    ErrorSeverity,
    ErrorResponse,
    CircuitBreaker,
    RateLimiter,
    FallbackManager,
)
from backend.app.error_handling.exceptions import (
    ContactAPIError,
    ValidationError, 
    AIProcessingError,
    DatabaseConnectionError,
    ExternalServiceError,
    RateLimitExceededError,
    CircuitBreakerOpenError,
)
from backend.app.error_handling.recovery import (
    RecoveryManager,
    RecoveryStrategy,
    BackoffStrategy,
)


class TestErrorCategories:
    """エラーカテゴリー分類テスト"""

    def test_user_error_classification(self):
        """ユーザーエラー（4xx）の分類テスト"""
        handler = ErrorHandler()
        
        # バリデーションエラーのテスト
        validation_error = ValidationError("Invalid email format", field="email")
        response = handler.handle_error(validation_error)
        
        assert response.status_code == 422
        assert response.category == ErrorCategory.USER_ERROR
        assert response.message == "Invalid email format"
        assert response.details["field"] == "email"
        assert response.recoverable is True
        
    def test_system_error_classification(self):
        """システムエラー（5xx）の分類テスト"""
        handler = ErrorHandler()
        
        # データベース接続エラーのテスト
        db_error = DatabaseConnectionError("Connection pool exhausted")
        response = handler.handle_error(db_error)
        
        assert response.status_code == 503
        assert response.category == ErrorCategory.SYSTEM_ERROR
        assert response.severity == ErrorSeverity.HIGH
        assert response.recoverable is True
        
    def test_ai_processing_error_classification(self):
        """AI処理エラーの分類テスト"""
        handler = ErrorHandler()
        
        # AI処理エラーのテスト
        ai_error = AIProcessingError("Gemini API timeout", service="gemini")
        response = handler.handle_error(ai_error)
        
        assert response.status_code == 503
        assert response.category == ErrorCategory.EXTERNAL_SERVICE
        assert response.fallback_available is True
        
    def test_external_service_error_classification(self):
        """外部サービスエラーの分類テスト"""
        handler = ErrorHandler()
        
        # 外部サービスエラーのテスト
        service_error = ExternalServiceError("SendGrid API unavailable", service="sendgrid")
        response = handler.handle_error(service_error)
        
        assert response.status_code == 502
        assert response.category == ErrorCategory.EXTERNAL_SERVICE
        assert response.retry_after > 0


class TestStepwiseConsistencyControl:
    """段階的整合性制御テスト"""
    
    def test_contact_creation_guaranteed(self):
        """お問い合わせ受付保証テスト"""
        handler = ErrorHandler()
        
        # お問い合わせ作成は常に成功させる
        contact_data = {
            "name": "山田太郎",
            "email": "yamada@example.com",
            "subject": "商品について",
            "message": "商品の詳細を教えてください"
        }
        
        # AI処理が失敗してもお問い合わせ受付は成功する
        with patch('backend.app.services.gemini_service.GeminiService.analyze_contact', 
                  side_effect=AIProcessingError("AI service unavailable")):
            
            result = handler.handle_contact_creation_with_fallback(contact_data)
            
            # お問い合わせは作成される
            assert result["contact_created"] is True
            assert result["contact_id"] is not None
            
            # AI処理は後で実行される
            assert result["ai_analysis_status"] == "scheduled_for_retry"
            assert result["immediate_ai_analysis"] is False
    
    def test_ai_processing_independence(self):
        """AI処理独立性テスト"""
        handler = ErrorHandler()
        
        # AI処理失敗がお問い合わせ作成に影響しない
        with patch('backend.app.services.gemini_service.GeminiService.analyze_contact',
                  side_effect=TooManyRequests("API rate limit exceeded")):
            
            result = handler.handle_stepwise_processing({
                "contact_id": "test-contact-123",
                "stage": "ai_analysis"
            })
            
            # エラーは記録されるが、他の処理は続行
            assert result["stage_failed"] == "ai_analysis"
            assert result["continue_pipeline"] is True
            assert result["fallback_triggered"] is True
            

class TestCircuitBreakerPattern:
    """Circuit Breakerパターンテスト"""
    
    def test_circuit_breaker_closed_state(self):
        """Circuit Breaker閉状態テスト"""
        circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=60,
            expected_exceptions=(GoogleAPIError,)
        )
        
        # 正常時はリクエストが通る
        assert circuit_breaker.state == "CLOSED"
        assert circuit_breaker.can_execute() is True
        
    def test_circuit_breaker_open_state(self):
        """Circuit Breaker開状態テスト"""
        circuit_breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=60)
        
        # 失敗回数が閾値を超えるとOPENになる
        circuit_breaker.record_failure()
        circuit_breaker.record_failure()
        circuit_breaker.record_failure()
        
        assert circuit_breaker.state == "OPEN"
        assert circuit_breaker.can_execute() is False
        
        # OPEN状態ではCircuitBreakerOpenErrorが発生
        with pytest.raises(CircuitBreakerOpenError):
            circuit_breaker.call(lambda: "test")
    
    def test_circuit_breaker_half_open_state(self):
        """Circuit Breaker半開状態テスト"""
        circuit_breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        
        # OPENにする
        circuit_breaker.record_failure()
        circuit_breaker.record_failure()
        circuit_breaker.record_failure()
        
        # 回復タイムアウト後はHALF_OPENになる
        import time
        time.sleep(0.2)
        
        assert circuit_breaker.state == "HALF_OPEN"
        assert circuit_breaker.can_execute() is True


class TestFallbackMechanism:
    """フォールバック機構テスト"""
    
    def test_ai_analysis_fallback(self):
        """AI解析フォールバックテスト"""
        fallback_manager = FallbackManager()
        
        # Gemini APIが失敗した時のフォールバック
        with patch('backend.app.services.gemini_service.GeminiService.analyze_contact',
                  side_effect=ServiceUnavailable("Gemini API unavailable")):
            
            result = fallback_manager.execute_with_fallback(
                primary_service="gemini",
                operation="analyze_contact",
                data={"message": "テストメッセージ"}
            )
            
            # フォールバック結果が返される
            assert result["status"] == "fallback_executed"
            assert result["primary_service_failed"] is True
            assert result["fallback_method"] == "rule_based_classification"
            
    def test_notification_fallback(self):
        """通知フォールバックテスト"""
        fallback_manager = FallbackManager()
        
        # SendGrid APIが失敗した時のフォールバック
        with patch('backend.app.services.notification_service.NotificationService.send_email',
                  side_effect=ExternalServiceError("SendGrid unavailable")):
            
            result = fallback_manager.execute_with_fallback(
                primary_service="sendgrid",
                operation="send_notification",
                data={"to": "admin@example.com", "message": "Alert"}
            )
            
            # フォールバック通知が実行される
            assert result["status"] == "fallback_executed"
            assert result["fallback_method"] == "log_based_notification"


class TestRateLimiting:
    """Rate Limiting機能テスト"""
    
    def test_rate_limiter_under_limit(self):
        """レート制限以下での動作テスト"""
        rate_limiter = RateLimiter(max_requests=10, time_window=60)
        
        # 制限以下では通常実行
        for i in range(5):
            assert rate_limiter.is_allowed("test_client") is True
            
    def test_rate_limiter_exceeded(self):
        """レート制限超過テスト"""
        rate_limiter = RateLimiter(max_requests=3, time_window=60)
        
        # 制限を超える
        for i in range(3):
            rate_limiter.is_allowed("test_client")
            
        # 4回目は制限される
        assert rate_limiter.is_allowed("test_client") is False
        
        # RateLimitExceededErrorが発生
        with pytest.raises(RateLimitExceededError):
            rate_limiter.enforce("test_client")


class TestResourceExhaustionHandling:
    """リソース枯渇エラー処理テスト"""
    
    def test_memory_exhaustion_detection(self):
        """メモリ枯渇検知テスト"""
        handler = ErrorHandler()
        
        # メモリ使用量が85%を超えた場合
        with patch('psutil.virtual_memory') as mock_memory:
            mock_memory.return_value.percent = 90
            
            result = handler.check_resource_health()
            
            assert result["memory_critical"] is True
            assert result["actions_required"] == ["scale_up", "enable_backpressure"]
            
    def test_connection_pool_exhaustion(self):
        """接続プール枯渇テスト"""
        handler = ErrorHandler()
        
        # DB接続プール枯渇エラー
        pool_error = OperationalError("connection pool limit reached", None, None)
        response = handler.handle_error(DatabaseConnectionError(str(pool_error)))
        
        assert response.category == ErrorCategory.RESOURCE_EXHAUSTION
        assert response.recovery_actions == ["expand_pool", "queue_requests", "scale_horizontally"]


class TestRecoveryStrategies:
    """復旧戦略テスト"""
    
    def test_exponential_backoff_strategy(self):
        """指数バックオフ戦略テスト"""
        backoff = BackoffStrategy.exponential(base_delay=1, max_delay=30, max_attempts=3)
        
        delays = []
        for attempt in range(3):
            delay = backoff.get_delay(attempt)
            delays.append(delay)
            
        # 指数的に増加（1秒、2秒、4秒）
        assert delays[0] == 1
        assert delays[1] == 2
        assert delays[2] == 4
        
    def test_recovery_manager_retry(self):
        """復旧管理リトライテスト"""
        recovery_manager = RecoveryManager()
        
        # 3回失敗してから成功するモック
        mock_service = Mock()
        mock_service.side_effect = [
            AIProcessingError("Temporary failure"),
            AIProcessingError("Temporary failure"),
            AIProcessingError("Temporary failure"), 
            {"status": "success", "result": "analysis complete"}
        ]
        
        result = recovery_manager.execute_with_retry(
            operation=mock_service,
            strategy=BackoffStrategy.exponential(1, 30, 4),
            recoverable_exceptions=(AIProcessingError,)
        )
        
        # 最終的に成功
        assert result["status"] == "success"
        assert result["attempts"] == 4


class TestIntegrationErrorHandling:
    """統合エラーハンドリングテスト"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_error_recovery(self):
        """エンドツーエンドエラー復旧テスト"""
        handler = ErrorHandler()
        
        # 複数のエラーが連鎖した場合のテスト
        scenario = {
            "contact_data": {"name": "テスト", "email": "test@example.com"},
            "errors": [
                ("database", OperationalError("Connection lost", None, None)),
                ("gemini", TooManyRequests("API limit")),
                ("sendgrid", ExternalServiceError("Service unavailable"))
            ]
        }
        
        result = await handler.handle_complex_error_scenario(scenario)
        
        # 段階的復旧が実行される
        assert result["contact_saved"] is True  # 最優先でお問い合わせは保存
        assert result["ai_analysis"] == "scheduled_retry"  # AI処理は後で実行
        assert result["notification"] == "fallback_sent"  # 通知はフォールバックで送信
        assert result["recovery_plan_created"] is True  # 復旧プランが作成される


if __name__ == "__main__":
    pytest.main([__file__, "-v"])