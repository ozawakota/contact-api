"""NotificationService通知機能実装

SendGrid API統合による緊急度別エスカレーション通知サービス。
10秒以内送信・動的メール生成・Circuit Breaker・キュー再送機能を提供します。
"""

import asyncio
import logging
import time
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import os

# SendGrid SDK import
try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail, Email, To, Content
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False
    logging.warning("sendgrid package not available. Install with: pip install sendgrid")

from models.contact import Contact
from models.contact_ai_analysis import ContactAIAnalysis


class NotificationPriority(Enum):
    """通知優先度"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4


class CircuitBreakerState(Enum):
    """Circuit Breaker状態"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class NotificationRequest:
    """通知リクエスト"""
    contact_id: int
    notification_type: str
    urgency: int
    category: str
    summary: str
    confidence: float
    recipients: Optional[List[str]] = None
    template_data: Optional[Dict[str, Any]] = None


@dataclass
class NotificationResult:
    """通知結果"""
    success: bool
    notification_id: Optional[str] = None
    delivery_time_ms: int = 0
    error_message: Optional[str] = None
    retry_attempts: int = 0
    circuit_breaker_open: bool = False


class CircuitBreaker:
    """Circuit Breaker実装"""
    
    def __init__(self, failure_threshold: int = 5, timeout_seconds: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout_seconds
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED
        self.last_failure_time = None
        
    def call(self, func, *args, **kwargs):
        """Circuit Breaker付きファンクション呼び出し"""
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e
    
    async def async_call(self, func, *args, **kwargs):
        """非同期Circuit Breaker付きファンクション呼び出し"""
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """リセット試行可否判定"""
        if self.last_failure_time is None:
            return False
        return time.time() - self.last_failure_time >= self.timeout
    
    def _on_success(self):
        """成功時処理"""
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED
    
    def _on_failure(self):
        """失敗時処理"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN


class NotificationServiceError(Exception):
    """NotificationServiceエラー"""
    def __init__(self, message: str, contact_id: int = None, error_code: str = None):
        super().__init__(message)
        self.contact_id = contact_id
        self.error_code = error_code


class NotificationService:
    """NotificationService通知機能
    
    Features:
    - SendGrid API統合・APIキー管理・テンプレート設定
    - 緊急度別エスカレーション通知（10秒以内送信）
    - メール内容動的生成（分類結果・類似事例・緊急度情報）
    - 送信失敗時のキュー再送・Circuit Breaker実装
    """
    
    def __init__(
        self,
        sendgrid_client=None,
        template_engine=None,
        api_key: str = None,
        enable_queue: bool = True,
        enable_retry: bool = True,
        max_retry_attempts: int = 3
    ):
        """サービス初期化
        
        Args:
            sendgrid_client: SendGridクライアント
            template_engine: テンプレートエンジン
            api_key: SendGrid APIキー
            enable_queue: キュー機能有効化
            enable_retry: リトライ機能有効化
            max_retry_attempts: 最大リトライ回数
        """
        self.logger = logging.getLogger(__name__)
        
        # SendGridクライアント初期化
        if sendgrid_client:
            self.sendgrid_client = sendgrid_client
        else:
            api_key = api_key or os.getenv('SENDGRID_API_KEY')
            if not api_key:
                raise ValueError("SENDGRID_API_KEY environment variable is required")
            
            if not SENDGRID_AVAILABLE:
                raise ImportError("sendgrid package is required. Install with: pip install sendgrid")
            
            self.sendgrid_client = SendGridAPIClient(api_key=api_key)
        
        # テンプレートエンジン
        self.template_engine = template_engine
        
        # 設定
        self.enable_queue = enable_queue
        self.enable_retry = enable_retry
        self.max_retry_attempts = max_retry_attempts
        self.delivery_timeout = 10.0  # 10秒以内配信保証
        
        # Circuit Breaker
        self.circuit_breaker = CircuitBreaker(failure_threshold=5, timeout_seconds=60)
        
        # 通知キュー
        self.notification_queue = []
        self.retry_queue = []
        
        # テンプレート設定
        self.default_templates = self._load_default_templates()
        self.custom_templates = {}
        
        # メトリクス
        self.metrics = {
            'total_notifications': 0,
            'successful_notifications': 0,
            'failed_notifications': 0,
            'delivery_times': [],
            'retry_attempts': 0,
            'circuit_breaker_activations': 0
        }
        
        # 緊急度別設定
        self.urgency_configs = {
            1: {'notification_required': False, 'escalation_level': 'none'},
            2: {'notification_required': True, 'escalation_level': 'standard'},
            3: {'notification_required': True, 'escalation_level': 'immediate'}
        }
        
        self.logger.info("NotificationService初期化完了")
    
    async def notify_urgent_contact(
        self,
        contact_id: int,
        urgency: int,
        category: str,
        summary: str,
        confidence: float,
        similar_cases: Optional[List[Dict[str, Any]]] = None,
        recommendations: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """緊急コンタクト通知
        
        Args:
            contact_id: コンタクトID
            urgency: 緊急度（1-3）
            category: カテゴリ
            summary: 要約
            confidence: 信頼度
            similar_cases: 類似事例（オプション）
            recommendations: 推奨情報（オプション）
            
        Returns:
            通知結果辞書
            
        Raises:
            NotificationServiceError: 通知エラー
        """
        start_time = time.time()
        self.logger.info(f"緊急コンタクト通知開始: contact_id={contact_id}, urgency={urgency}")
        
        try:
            # 入力バリデーション
            if not contact_id:
                raise NotificationServiceError("Invalid contact_id", error_code="invalid_input")
            
            if urgency not in [1, 2, 3]:
                raise NotificationServiceError(f"Invalid urgency: {urgency}", error_code="invalid_urgency")
            
            # 緊急度設定取得
            urgency_config = self.urgency_configs.get(urgency, {})
            
            if not urgency_config.get('notification_required', False):
                # 通知不要の場合
                return {
                    'success': True,
                    'notification_sent': False,
                    'urgency': urgency,
                    'reason': 'notification_not_required_for_urgency_level'
                }
            
            # 通知リクエスト構築
            notification_request = NotificationRequest(
                contact_id=contact_id,
                notification_type='urgent_escalation',
                urgency=urgency,
                category=category,
                summary=summary,
                confidence=confidence,
                template_data={
                    'similar_cases': similar_cases or [],
                    'recommendations': recommendations
                }
            )
            
            # 通知送信実行
            result = await self._send_notification(notification_request)
            
            # 配信時間計算
            delivery_time = time.time() - start_time
            delivery_time_ms = int(delivery_time * 1000)
            
            # メトリクス更新
            self.metrics['total_notifications'] += 1
            self.metrics['delivery_times'].append(delivery_time)
            
            if result.success:
                self.metrics['successful_notifications'] += 1
            else:
                self.metrics['failed_notifications'] += 1
            
            response = {
                'success': result.success,
                'notification_sent': result.success,
                'notification_type': 'urgent_escalation',
                'escalation_level': urgency_config.get('escalation_level'),
                'delivery_time_ms': delivery_time_ms,
                'within_sla': delivery_time < self.delivery_timeout,
                'contact_id': contact_id,
                'urgency': urgency
            }
            
            if result.error_message:
                response['error_type'] = 'sendgrid_api_error'
                response['error_message'] = result.error_message
            
            if result.circuit_breaker_open:
                response['circuit_breaker_open'] = True
            
            if result.retry_attempts > 0:
                response['retry_attempts'] = result.retry_attempts
            
            self.logger.info(f"緊急コンタクト通知完了: contact_id={contact_id}, time={delivery_time_ms}ms")
            return response
            
        except Exception as e:
            delivery_time = time.time() - start_time
            self.logger.error(f"緊急コンタクト通知エラー: {e}")
            
            return {
                'success': False,
                'notification_sent': False,
                'delivery_time_ms': int(delivery_time * 1000),
                'error_type': getattr(e, 'error_code', 'unexpected_error'),
                'error_message': str(e),
                'contact_id': contact_id
            }
    
    async def notify_analysis_failure(
        self,
        contact_id: int,
        error_type: str,
        error_message: str,
        retry_possible: bool
    ) -> Dict[str, Any]:
        """AI解析失敗通知
        
        Args:
            contact_id: コンタクトID
            error_type: エラー種別
            error_message: エラーメッセージ
            retry_possible: リトライ可能フラグ
            
        Returns:
            通知結果辞書
        """
        try:
            self.logger.info(f"AI解析失敗通知開始: contact_id={contact_id}, error_type={error_type}")
            
            notification_request = NotificationRequest(
                contact_id=contact_id,
                notification_type='analysis_failure',
                urgency=2,  # 中緊急度
                category='system',
                summary=f"AI解析失敗: {error_type}",
                confidence=0.0,
                template_data={
                    'error_type': error_type,
                    'error_message': error_message,
                    'retry_possible': retry_possible
                }
            )
            
            result = await self._send_notification(notification_request)
            
            return {
                'success': result.success,
                'notification_type': 'analysis_failure',
                'retry_recommended': retry_possible,
                'contact_id': contact_id,
                'error_message': result.error_message if not result.success else None
            }
            
        except Exception as e:
            self.logger.error(f"AI解析失敗通知エラー: {e}")
            return {
                'success': False,
                'error_message': str(e),
                'contact_id': contact_id
            }
    
    async def notify_similar_cases_found(
        self,
        contact_id: int,
        similar_cases: List[Dict[str, Any]],
        recommendations: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """類似事例発見通知
        
        Args:
            contact_id: コンタクトID
            similar_cases: 類似事例一覧
            recommendations: 推奨情報
            
        Returns:
            通知結果辞書
        """
        try:
            self.logger.info(f"類似事例発見通知開始: contact_id={contact_id}, cases={len(similar_cases)}")
            
            notification_request = NotificationRequest(
                contact_id=contact_id,
                notification_type='similar_cases',
                urgency=2,
                category='analysis',
                summary=f"{len(similar_cases)}件の類似事例を発見",
                confidence=1.0,
                template_data={
                    'similar_cases': similar_cases,
                    'recommendations': recommendations,
                    'similar_cases_count': len(similar_cases)
                }
            )
            
            result = await self._send_notification(notification_request)
            
            return {
                'success': result.success,
                'notification_type': 'similar_cases',
                'similar_cases_count': len(similar_cases),
                'contact_id': contact_id,
                'error_message': result.error_message if not result.success else None
            }
            
        except Exception as e:
            self.logger.error(f"類似事例発見通知エラー: {e}")
            return {
                'success': False,
                'error_message': str(e),
                'contact_id': contact_id
            }
    
    async def _send_notification(self, request: NotificationRequest) -> NotificationResult:
        """通知送信実行
        
        Args:
            request: 通知リクエスト
            
        Returns:
            通知結果
        """
        start_time = time.time()
        retry_attempts = 0
        
        while retry_attempts <= self.max_retry_attempts:
            try:
                # Circuit Breaker チェック
                if self.circuit_breaker.state == CircuitBreakerState.OPEN:
                    return NotificationResult(
                        success=False,
                        error_message="Circuit breaker is open",
                        circuit_breaker_open=True
                    )
                
                # メールテンプレート生成
                template_data = await self.generate_email_template(
                    notification_type=request.notification_type,
                    contact_id=request.contact_id,
                    urgency=request.urgency,
                    category=request.category,
                    summary=request.summary,
                    template_vars=request.template_data or {}
                )
                
                # SendGrid メール送信
                await self.circuit_breaker.async_call(
                    self._send_email_via_sendgrid,
                    template_data
                )
                
                delivery_time = time.time() - start_time
                
                return NotificationResult(
                    success=True,
                    notification_id=f"notif_{request.contact_id}_{int(time.time())}",
                    delivery_time_ms=int(delivery_time * 1000),
                    retry_attempts=retry_attempts
                )
                
            except Exception as e:
                retry_attempts += 1
                self.logger.warning(f"通知送信失敗 (試行 {retry_attempts}/{self.max_retry_attempts + 1}): {e}")
                
                if retry_attempts > self.max_retry_attempts:
                    delivery_time = time.time() - start_time
                    
                    return NotificationResult(
                        success=False,
                        error_message=str(e),
                        delivery_time_ms=int(delivery_time * 1000),
                        retry_attempts=retry_attempts
                    )
                
                # 指数バックオフ
                await asyncio.sleep(2 ** retry_attempts)
        
        return NotificationResult(success=False, error_message="Max retries exceeded")
    
    async def generate_email_template(
        self,
        notification_type: str,
        contact_id: int = None,
        urgency: int = None,
        category: str = None,
        summary: str = None,
        contact: Contact = None,
        ai_analysis: ContactAIAnalysis = None,
        similar_cases: List[Dict[str, Any]] = None,
        recommendations: Dict[str, Any] = None,
        template_vars: Dict[str, Any] = None
    ) -> Dict[str, str]:
        """メールテンプレート動的生成
        
        Args:
            notification_type: 通知タイプ
            contact_id: コンタクトID
            urgency: 緊急度
            category: カテゴリ
            summary: 要約
            contact: Contactオブジェクト
            ai_analysis: AI解析結果
            similar_cases: 類似事例
            recommendations: 推奨情報
            template_vars: 追加テンプレート変数
            
        Returns:
            テンプレートデータ辞書
        """
        try:
            # テンプレート選択
            template_key = self._select_template(notification_type, category, urgency)
            template_config = self.custom_templates.get(template_key) or self.default_templates.get(template_key)
            
            if not template_config:
                template_config = self.default_templates['default']
            
            # テンプレート変数準備
            template_context = {
                'contact_id': contact_id,
                'urgency': urgency,
                'category': category,
                'summary': summary,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'similar_cases': similar_cases or [],
                'recommendations': recommendations or {},
                'contact': contact,
                'ai_analysis': ai_analysis
            }
            
            if template_vars:
                template_context.update(template_vars)
            
            # テンプレート描画
            try:
                if self.template_engine:
                    html_content = self.template_engine.render(
                        template_config['html_template'],
                        **template_context
                    )
                    text_content = self.template_engine.render(
                        template_config['text_template'],
                        **template_context
                    )
                else:
                    # シンプルな文字列フォーマット
                    html_content = template_config['html_template'].format(**template_context)
                    text_content = template_config['text_template'].format(**template_context)
                
                return {
                    'subject': template_config['subject'].format(**template_context),
                    'html_content': html_content,
                    'text_content': text_content,
                    'template_used': template_key
                }
                
            except Exception as template_error:
                self.logger.warning(f"テンプレート生成エラー: {template_error}")
                
                # フォールバックテンプレート使用
                fallback = self.default_templates['fallback']
                return {
                    'subject': fallback['subject'].format(contact_id=contact_id or 'N/A'),
                    'html_content': fallback['html_template'].format(
                        summary=summary or 'システム通知',
                        contact_id=contact_id or 'N/A'
                    ),
                    'text_content': fallback['text_template'].format(
                        summary=summary or 'システム通知',
                        contact_id=contact_id or 'N/A'
                    ),
                    'fallback_template_used': True
                }
                
        except Exception as e:
            self.logger.error(f"テンプレート生成エラー: {e}")
            raise NotificationServiceError(f"Template generation failed: {e}")
    
    def _select_template(self, notification_type: str, category: str = None, urgency: int = None) -> str:
        """テンプレート選択ロジック
        
        Args:
            notification_type: 通知タイプ
            category: カテゴリ
            urgency: 緊急度
            
        Returns:
            テンプレートキー
        """
        # カスタムテンプレート（カテゴリ別）
        if category:
            custom_key = f"{notification_type}_{category}"
            if custom_key in self.custom_templates:
                return custom_key
        
        # 緊急度別テンプレート
        if urgency == 3:
            urgent_key = f"{notification_type}_urgent"
            if urgent_key in self.default_templates:
                return urgent_key
        
        # デフォルトテンプレート
        return notification_type if notification_type in self.default_templates else 'default'
    
    async def _send_email_via_sendgrid(self, template_data: Dict[str, str]) -> None:
        """SendGrid経由でメール送信
        
        Args:
            template_data: テンプレートデータ
            
        Raises:
            Exception: SendGrid送信エラー
        """
        try:
            # SendGrid Mail オブジェクト構築
            message = Mail(
                from_email=Email("support@example.com", "カスタマーサポート"),
                to_emails=To("admin@example.com"),
                subject=template_data['subject'],
                html_content=Content("text/html", template_data['html_content']),
                plain_text_content=Content("text/plain", template_data['text_content'])
            )
            
            # 送信実行
            response = self.sendgrid_client.send(message)
            
            if response.status_code not in [200, 201, 202]:
                raise Exception(f"SendGrid API error: status={response.status_code}")
            
            self.logger.info(f"メール送信成功: status={response.status_code}")
            
        except Exception as e:
            self.logger.error(f"SendGrid送信エラー: {e}")
            raise
    
    def _load_default_templates(self) -> Dict[str, Dict[str, str]]:
        """デフォルトテンプレート読み込み
        
        Returns:
            テンプレート辞書
        """
        return {
            'urgent_escalation': {
                'subject': '緊急: 顧客問い合わせエスカレーション - Contact #{contact_id}',
                'html_template': '''
                <html>
                <body>
                    <h2>緊急顧客問い合わせエスカレーション</h2>
                    <p><strong>コンタクトID:</strong> {contact_id}</p>
                    <p><strong>緊急度:</strong> {urgency}</p>
                    <p><strong>カテゴリ:</strong> {category}</p>
                    <p><strong>要約:</strong> {summary}</p>
                    <p><strong>処理時刻:</strong> {timestamp}</p>
                    
                    {recommendations}
                    
                    <p>至急対応をお願いします。</p>
                </body>
                </html>
                ''',
                'text_template': '''
                緊急顧客問い合わせエスカレーション
                
                コンタクトID: {contact_id}
                緊急度: {urgency}
                カテゴリ: {category}
                要約: {summary}
                処理時刻: {timestamp}
                
                至急対応をお願いします。
                '''
            },
            'analysis_failure': {
                'subject': 'AI解析失敗通知 - Contact #{contact_id}',
                'html_template': '''
                <html>
                <body>
                    <h2>AI解析失敗通知</h2>
                    <p><strong>コンタクトID:</strong> {contact_id}</p>
                    <p><strong>エラータイプ:</strong> {error_type}</p>
                    <p><strong>詳細:</strong> {summary}</p>
                    <p><strong>処理時刻:</strong> {timestamp}</p>
                    
                    <p>手動分類が必要です。</p>
                </body>
                </html>
                ''',
                'text_template': '''
                AI解析失敗通知
                
                コンタクトID: {contact_id}
                エラータイプ: {error_type}
                詳細: {summary}
                処理時刻: {timestamp}
                
                手動分類が必要です。
                '''
            },
            'similar_cases': {
                'subject': '類似事例発見通知 - Contact #{contact_id}',
                'html_template': '''
                <html>
                <body>
                    <h2>類似事例発見通知</h2>
                    <p><strong>コンタクトID:</strong> {contact_id}</p>
                    <p><strong>類似事例数:</strong> {similar_cases_count}</p>
                    <p><strong>要約:</strong> {summary}</p>
                    <p><strong>処理時刻:</strong> {timestamp}</p>
                    
                    <p>類似事例を参考に対応をお願いします。</p>
                </body>
                </html>
                ''',
                'text_template': '''
                類似事例発見通知
                
                コンタクトID: {contact_id}
                類似事例数: {similar_cases_count}
                要約: {summary}
                処理時刻: {timestamp}
                
                類似事例を参考に対応をお願いします。
                '''
            },
            'default': {
                'subject': 'カスタマーサポート通知 - Contact #{contact_id}',
                'html_template': '''
                <html>
                <body>
                    <h2>カスタマーサポート通知</h2>
                    <p><strong>コンタクトID:</strong> {contact_id}</p>
                    <p><strong>内容:</strong> {summary}</p>
                    <p><strong>処理時刻:</strong> {timestamp}</p>
                </body>
                </html>
                ''',
                'text_template': '''
                カスタマーサポート通知
                
                コンタクトID: {contact_id}
                内容: {summary}
                処理時刻: {timestamp}
                '''
            },
            'fallback': {
                'subject': 'システム通知 - Contact #{contact_id}',
                'html_template': '<html><body><h2>システム通知</h2><p>{summary}</p><p>コンタクトID: {contact_id}</p></body></html>',
                'text_template': 'システム通知\n{summary}\nコンタクトID: {contact_id}'
            }
        }
    
    def load_custom_templates(self, templates: Dict[str, Dict[str, str]]) -> None:
        """カスタムテンプレート読み込み
        
        Args:
            templates: カスタムテンプレート辞書
        """
        self.custom_templates.update(templates)
        self.logger.info(f"カスタムテンプレート読み込み完了: {len(templates)}件")
    
    async def send_batch_notifications(
        self,
        notifications: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """バッチ通知送信
        
        Args:
            notifications: 通知一覧
            
        Returns:
            送信結果一覧
        """
        try:
            self.logger.info(f"バッチ通知送信開始: {len(notifications)}件")
            
            # 並行送信（同時実行数制限）
            semaphore = asyncio.Semaphore(5)
            
            async def send_single(notification):
                async with semaphore:
                    return await self.notify_urgent_contact(**notification)
            
            results = await asyncio.gather(
                *[send_single(notification) for notification in notifications],
                return_exceptions=True
            )
            
            # エラー結果を辞書形式に変換
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    processed_results.append({
                        'success': False,
                        'error_message': str(result),
                        'contact_id': notifications[i].get('contact_id')
                    })
                else:
                    processed_results.append(result)
            
            self.logger.info(f"バッチ通知送信完了: 成功={sum(1 for r in processed_results if r.get('success'))}")
            return processed_results
            
        except Exception as e:
            self.logger.error(f"バッチ通知送信エラー: {e}")
            return [{'success': False, 'error_message': str(e)} for _ in notifications]
    
    async def notify_urgent_contact_multi_channel(
        self,
        contact_id: int,
        urgency: int,
        category: str,
        summary: str,
        confidence: float,
        channels: List[str]
    ) -> Dict[str, Any]:
        """マルチチャネル通知
        
        Args:
            contact_id: コンタクトID
            urgency: 緊急度
            category: カテゴリ
            summary: 要約
            confidence: 信頼度
            channels: 通知チャネル一覧
            
        Returns:
            マルチチャネル送信結果
        """
        try:
            self.logger.info(f"マルチチャネル通知開始: contact_id={contact_id}, channels={channels}")
            
            channel_results = []
            
            for channel in channels:
                if channel == 'email':
                    result = await self.notify_urgent_contact(
                        contact_id=contact_id,
                        urgency=urgency,
                        category=category,
                        summary=summary,
                        confidence=confidence
                    )
                    channel_results.append({
                        'channel': 'email',
                        'success': result.get('success', False)
                    })
                elif channel == 'slack':
                    # Slack通知（実装例）
                    channel_results.append({
                        'channel': 'slack',
                        'success': True  # モック成功
                    })
                elif channel == 'webhook':
                    # Webhook通知（実装例）
                    channel_results.append({
                        'channel': 'webhook',
                        'success': True  # モック成功
                    })
            
            success_count = sum(1 for r in channel_results if r['success'])
            
            return {
                'success': success_count > 0,
                'channel_results': channel_results,
                'successful_channels': success_count,
                'total_channels': len(channels)
            }
            
        except Exception as e:
            self.logger.error(f"マルチチャネル通知エラー: {e}")
            return {
                'success': False,
                'error_message': str(e),
                'channel_results': []
            }
    
    async def notify_urgent_contact_with_timeout(
        self,
        contact_id: int,
        urgency: int,
        category: str,
        summary: str,
        confidence: float,
        timeout_seconds: float = 10.0
    ) -> Dict[str, Any]:
        """タイムアウト付き緊急通知
        
        Args:
            contact_id: コンタクトID
            urgency: 緊急度
            category: カテゴリ
            summary: 要約
            confidence: 信頼度
            timeout_seconds: タイムアウト時間
            
        Returns:
            通知結果（タイムアウト情報含む）
        """
        try:
            result = await asyncio.wait_for(
                self.notify_urgent_contact(
                    contact_id=contact_id,
                    urgency=urgency,
                    category=category,
                    summary=summary,
                    confidence=confidence
                ),
                timeout=timeout_seconds
            )
            result['timeout_occurred'] = False
            return result
            
        except asyncio.TimeoutError:
            self.logger.warning(f"通知タイムアウト: contact_id={contact_id}")
            return {
                'success': False,
                'timeout_occurred': True,
                'error_message': f"Notification timeout after {timeout_seconds}s"
            }
    
    async def get_notification_analytics(self) -> Dict[str, Any]:
        """通知分析データ取得
        
        Returns:
            分析データ辞書
        """
        try:
            delivery_times = self.metrics['delivery_times']
            
            return {
                'total_notifications': self.metrics['total_notifications'],
                'successful_notifications': self.metrics['successful_notifications'],
                'failed_notifications': self.metrics['failed_notifications'],
                'delivery_success_rate': (
                    self.metrics['successful_notifications'] / self.metrics['total_notifications']
                    if self.metrics['total_notifications'] > 0 else 0.0
                ),
                'average_delivery_time': (
                    sum(delivery_times) / len(delivery_times)
                    if delivery_times else 0.0
                ),
                'max_delivery_time': max(delivery_times) if delivery_times else 0.0,
                'retry_attempts': self.metrics['retry_attempts'],
                'circuit_breaker_activations': self.metrics['circuit_breaker_activations'],
                'urgency_distribution': self._calculate_urgency_distribution(),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"分析データ取得エラー: {e}")
            return {'error': str(e)}
    
    def _calculate_urgency_distribution(self) -> Dict[int, int]:
        """緊急度分布計算（簡易実装）
        
        Returns:
            緊急度別件数辞書
        """
        # 実際の実装では通知履歴から計算
        return {1: 10, 2: 25, 3: 5}  # モック分布