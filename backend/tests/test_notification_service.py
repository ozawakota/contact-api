"""NotificationServiceのテスト

SendGrid API統合による緊急度別エスカレーション通知機能のテスト実装。
10秒以内送信・動的メール生成・Circuit Breaker・キュー再送機能をテストします。
"""
import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

# テスト対象モジュールのインポート
from models.contact import Contact
from models.contact_ai_analysis import ContactAIAnalysis


@pytest.fixture
def mock_sendgrid_client():
    """モックSendGridクライアント"""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 202
    mock_response.body = b'{"message": "success"}'
    mock_response.headers = {}
    mock_client.send.return_value = mock_response
    return mock_client


@pytest.fixture
def mock_template_engine():
    """モックテンプレートエンジン"""
    mock_engine = MagicMock()
    mock_engine.render.return_value = "<html><body>テストメール</body></html>"
    return mock_engine


@pytest.fixture
def sample_contact():
    """テスト用Contactデータ"""
    return Contact(
        id=123,
        name="山田太郎",
        email="yamada@example.com",
        subject="商品の不具合について",
        message="購入した商品に重大な不具合があります。至急対応をお願いします。",
        priority=3,
        created_at=datetime.now()
    )


@pytest.fixture
def sample_ai_analysis():
    """テスト用AI解析データ"""
    return ContactAIAnalysis(
        id=456,
        contact_id=123,
        category="product",
        urgency=3,
        sentiment="negative",
        confidence_score=0.95,
        summary="商品不具合の緊急対応要求",
        processed_at=datetime.now()
    )


@pytest.fixture
def sample_similar_cases():
    """テスト用類似事例データ"""
    return [
        {
            'contact': Contact(id=789, subject="類似商品不具合1", message="同様の不具合報告"),
            'similarity': 0.92,
            'vector_id': 789
        },
        {
            'contact': Contact(id=790, subject="類似商品不具合2", message="類似問題"),
            'similarity': 0.87,
            'vector_id': 790
        }
    ]


class TestNotificationService:
    """NotificationServiceの基本機能テスト"""

    @pytest.fixture
    def notification_service(self, mock_sendgrid_client, mock_template_engine):
        """NotificationServiceインスタンス"""
        from services.notification_service import NotificationService
        return NotificationService(
            sendgrid_client=mock_sendgrid_client,
            template_engine=mock_template_engine,
            api_key="test-api-key"
        )

    @pytest.mark.asyncio
    async def test_service_initialization(self, mock_sendgrid_client, mock_template_engine):
        """NotificationService初期化テスト"""
        from services.notification_service import NotificationService
        service = NotificationService(
            sendgrid_client=mock_sendgrid_client,
            template_engine=mock_template_engine,
            api_key="test-api-key"
        )
        assert service.sendgrid_client == mock_sendgrid_client
        assert service.template_engine == mock_template_engine
        assert service.circuit_breaker is not None

    @pytest.mark.asyncio
    async def test_notify_urgent_contact_basic(self, notification_service, sample_contact, sample_ai_analysis):
        """緊急コンタクト通知基本テスト"""
        result = await notification_service.notify_urgent_contact(
            contact_id=sample_contact.id,
            urgency=sample_ai_analysis.urgency,
            category=sample_ai_analysis.category,
            summary=sample_ai_analysis.summary,
            confidence=sample_ai_analysis.confidence_score
        )
        
        assert result.get('success') is True
        assert result.get('notification_type') == 'urgent_escalation'
        assert result.get('delivery_time_ms') < 10000  # 10秒以内
        notification_service.sendgrid_client.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_notify_analysis_failure(self, notification_service, sample_contact):
        """AI解析失敗通知テスト"""
        result = await notification_service.notify_analysis_failure(
            contact_id=sample_contact.id,
            error_type="GeminiAPIError",
            error_message="API rate limit exceeded",
            retry_possible=True
        )
        
        assert result.get('success') is True
        assert result.get('notification_type') == 'analysis_failure'
        assert result.get('retry_recommended') is True

    @pytest.mark.asyncio
    async def test_notify_similar_cases_found(self, notification_service, sample_contact, sample_similar_cases):
        """類似事例発見通知テスト"""
        recommendations = {
            'recommended_actions': [
                {'action': '商品確認', 'priority': 'high'},
                {'action': 'QA部門連携', 'priority': 'medium'}
            ],
            'response_templates': [
                {'title': '商品不具合対応テンプレート', 'template': 'お詫び文'}
            ]
        }
        
        result = await notification_service.notify_similar_cases_found(
            contact_id=sample_contact.id,
            similar_cases=sample_similar_cases,
            recommendations=recommendations
        )
        
        assert result.get('success') is True
        assert result.get('notification_type') == 'similar_cases'
        assert result.get('similar_cases_count') == 2

    @pytest.mark.asyncio
    async def test_urgency_level_routing(self, notification_service, sample_contact):
        """緊急度別ルーティングテスト"""
        # 低緊急度（通知なし）
        result_low = await notification_service.notify_urgent_contact(
            contact_id=sample_contact.id,
            urgency=1,
            category="billing",
            summary="一般的な請求問い合わせ",
            confidence=0.8
        )
        assert result_low.get('notification_sent') is False
        
        # 中緊急度（標準通知）
        result_medium = await notification_service.notify_urgent_contact(
            contact_id=sample_contact.id,
            urgency=2,
            category="shipping",
            summary="配送遅延問い合わせ",
            confidence=0.9
        )
        assert result_medium.get('notification_sent') is True
        assert result_medium.get('escalation_level') == 'standard'
        
        # 高緊急度（即座エスカレーション）
        result_high = await notification_service.notify_urgent_contact(
            contact_id=sample_contact.id,
            urgency=3,
            category="product",
            summary="商品安全性問題",
            confidence=0.95
        )
        assert result_high.get('notification_sent') is True
        assert result_high.get('escalation_level') == 'immediate'

    @pytest.mark.asyncio
    async def test_email_template_generation(self, notification_service, sample_contact, sample_ai_analysis):
        """メールテンプレート動的生成テスト"""
        template_data = await notification_service.generate_email_template(
            notification_type='urgent_escalation',
            contact=sample_contact,
            ai_analysis=sample_ai_analysis,
            similar_cases=[],
            recommendations=None
        )
        
        assert 'subject' in template_data
        assert 'html_content' in template_data
        assert 'text_content' in template_data
        assert sample_contact.name in template_data['html_content']
        assert sample_ai_analysis.category in template_data['html_content']
        
        notification_service.template_engine.render.assert_called_once()

    @pytest.mark.asyncio
    async def test_ten_second_delivery_guarantee(self, notification_service, sample_contact):
        """10秒以内送信保証テスト"""
        start_time = time.time()
        
        result = await notification_service.notify_urgent_contact(
            contact_id=sample_contact.id,
            urgency=3,
            category="product",
            summary="緊急事案",
            confidence=0.95
        )
        
        delivery_time = time.time() - start_time
        
        assert delivery_time < 10.0  # 10秒以内
        assert result.get('delivery_time_ms') < 10000
        assert result.get('within_sla') is True

    @pytest.mark.asyncio
    async def test_circuit_breaker_functionality(self, notification_service, mock_sendgrid_client):
        """Circuit Breaker機能テスト"""
        # 連続失敗をシミュレート
        mock_sendgrid_client.send.side_effect = Exception("SendGrid API error")
        
        # 複数回失敗を試行
        for i in range(6):  # 閾値5回を超える
            try:
                await notification_service.notify_urgent_contact(
                    contact_id=123,
                    urgency=3,
                    category="test",
                    summary="test",
                    confidence=0.9
                )
            except Exception:
                pass
        
        # Circuit Breakerが開かれていることを確認
        assert notification_service.circuit_breaker.state == 'open'
        
        # Circuit Breaker開放時の処理確認
        result = await notification_service.notify_urgent_contact(
            contact_id=123,
            urgency=3,
            category="test", 
            summary="test",
            confidence=0.9
        )
        
        assert result.get('success') is False
        assert result.get('circuit_breaker_open') is True


class TestNotificationServiceIntegration:
    """NotificationService統合テスト"""

    @pytest.fixture
    def integration_service(self, mock_sendgrid_client, mock_template_engine):
        """統合テスト用NotificationServiceインスタンス"""
        from services.notification_service import NotificationService
        return NotificationService(
            sendgrid_client=mock_sendgrid_client,
            template_engine=mock_template_engine,
            api_key="test-api-key",
            enable_queue=True,
            enable_retry=True
        )

    @pytest.mark.asyncio
    async def test_queue_retry_mechanism(self, integration_service, sample_contact, mock_sendgrid_client):
        """キュー再送メカニズムテスト"""
        # 初回送信失敗をシミュレート
        mock_sendgrid_client.send.side_effect = [
            Exception("Network timeout"),  # 初回失敗
            Exception("Service unavailable"),  # 1回目リトライ失敗
            MagicMock(status_code=202)  # 2回目リトライ成功
        ]
        
        result = await integration_service.notify_urgent_contact(
            contact_id=sample_contact.id,
            urgency=3,
            category="product",
            summary="緊急事案",
            confidence=0.95
        )
        
        assert result.get('success') is True
        assert result.get('retry_attempts') >= 2
        assert mock_sendgrid_client.send.call_count == 3

    @pytest.mark.asyncio
    async def test_batch_notification_processing(self, integration_service):
        """バッチ通知処理テスト"""
        notifications = [
            {
                'contact_id': 1,
                'urgency': 3,
                'category': 'product',
                'summary': '緊急事案1',
                'confidence': 0.95
            },
            {
                'contact_id': 2,
                'urgency': 2,
                'category': 'shipping',
                'summary': '配送問題',
                'confidence': 0.85
            },
            {
                'contact_id': 3,
                'urgency': 3,
                'category': 'billing',
                'summary': '請求問題',
                'confidence': 0.90
            }
        ]
        
        results = await integration_service.send_batch_notifications(notifications)
        
        assert len(results) == 3
        successful_notifications = [r for r in results if r.get('success')]
        assert len(successful_notifications) >= 2  # 少なくとも2つは成功

    @pytest.mark.asyncio
    async def test_template_customization(self, integration_service, sample_contact, sample_ai_analysis):
        """テンプレートカスタマイズテスト"""
        custom_templates = {
            'urgent_escalation_product': {
                'subject': '緊急: 商品問題エスカレーション - Contact #{contact_id}',
                'html_template': '<h1>商品問題緊急通知</h1><p>{summary}</p>',
                'text_template': '商品問題緊急通知: {summary}'
            }
        }
        
        integration_service.load_custom_templates(custom_templates)
        
        result = await integration_service.notify_urgent_contact(
            contact_id=sample_contact.id,
            urgency=3,
            category="product",
            summary=sample_ai_analysis.summary,
            confidence=sample_ai_analysis.confidence_score
        )
        
        assert result.get('template_used') == 'urgent_escalation_product'
        assert result.get('success') is True

    @pytest.mark.asyncio
    async def test_notification_analytics(self, integration_service):
        """通知分析機能テスト"""
        # 複数の通知を送信
        for i in range(5):
            await integration_service.notify_urgent_contact(
                contact_id=i,
                urgency=2,
                category="test",
                summary=f"テスト通知 {i}",
                confidence=0.8
            )
        
        # 分析データ取得
        analytics = await integration_service.get_notification_analytics()
        
        assert analytics.get('total_notifications') >= 5
        assert 'delivery_success_rate' in analytics
        assert 'average_delivery_time' in analytics
        assert 'urgency_distribution' in analytics

    @pytest.mark.asyncio
    async def test_multi_channel_notification(self, integration_service, sample_contact):
        """マルチチャネル通知テスト"""
        channels = ['email', 'slack', 'webhook']
        
        result = await integration_service.notify_urgent_contact_multi_channel(
            contact_id=sample_contact.id,
            urgency=3,
            category="product",
            summary="マルチチャネルテスト",
            confidence=0.95,
            channels=channels
        )
        
        assert result.get('success') is True
        assert len(result.get('channel_results', [])) == len(channels)
        
        # 各チャネルの送信結果確認
        for channel_result in result.get('channel_results', []):
            assert 'channel' in channel_result
            assert 'success' in channel_result


class TestNotificationServiceErrorHandling:
    """NotificationServiceエラーハンドリングテスト"""

    @pytest.fixture
    def error_test_service(self, mock_sendgrid_client, mock_template_engine):
        """エラーテスト用NotificationServiceインスタンス"""
        from services.notification_service import NotificationService
        return NotificationService(
            sendgrid_client=mock_sendgrid_client,
            template_engine=mock_template_engine,
            api_key="test-api-key"
        )

    @pytest.mark.asyncio
    async def test_sendgrid_api_error_handling(self, error_test_service, mock_sendgrid_client, sample_contact):
        """SendGrid APIエラーハンドリングテスト"""
        mock_sendgrid_client.send.side_effect = Exception("SendGrid API rate limit")
        
        result = await error_test_service.notify_urgent_contact(
            contact_id=sample_contact.id,
            urgency=3,
            category="product",
            summary="テスト",
            confidence=0.9
        )
        
        assert result.get('success') is False
        assert result.get('error_type') == 'sendgrid_api_error'
        assert 'rate limit' in result.get('error_message', '')

    @pytest.mark.asyncio
    async def test_template_generation_error(self, error_test_service, mock_template_engine, sample_contact):
        """テンプレート生成エラーテスト"""
        mock_template_engine.render.side_effect = Exception("Template error")
        
        result = await error_test_service.notify_urgent_contact(
            contact_id=sample_contact.id,
            urgency=3,
            category="product",
            summary="テスト",
            confidence=0.9
        )
        
        # フォールバックテンプレートが使用されることを確認
        assert result.get('success') is True
        assert result.get('fallback_template_used') is True

    @pytest.mark.asyncio
    async def test_network_timeout_handling(self, error_test_service, mock_sendgrid_client):
        """ネットワークタイムアウト処理テスト"""
        async def slow_send(*args, **kwargs):
            await asyncio.sleep(15)  # 15秒待機（タイムアウト）
            return MagicMock(status_code=202)
        
        mock_sendgrid_client.send.side_effect = slow_send
        
        result = await error_test_service.notify_urgent_contact_with_timeout(
            contact_id=123,
            urgency=3,
            category="test",
            summary="タイムアウトテスト",
            confidence=0.9,
            timeout_seconds=10
        )
        
        assert result.get('success') is False
        assert result.get('timeout_occurred') is True

    @pytest.mark.asyncio
    async def test_invalid_data_handling(self, error_test_service):
        """不正データ処理テスト"""
        # 不正なcontact_id
        result1 = await error_test_service.notify_urgent_contact(
            contact_id=None,
            urgency=3,
            category="test",
            summary="テスト",
            confidence=0.9
        )
        assert result1.get('success') is False
        assert result1.get('error_type') == 'invalid_input'
        
        # 不正なurgency値
        result2 = await error_test_service.notify_urgent_contact(
            contact_id=123,
            urgency=10,  # 無効な緊急度
            category="test",
            summary="テスト",
            confidence=0.9
        )
        assert result2.get('success') is False
        assert result2.get('error_type') == 'invalid_urgency'


class TestNotificationServicePerformance:
    """NotificationServiceパフォーマンステスト"""

    @pytest.mark.asyncio
    async def test_concurrent_notifications(self, mock_sendgrid_client, mock_template_engine):
        """同時通知処理テスト"""
        from services.notification_service import NotificationService
        service = NotificationService(
            sendgrid_client=mock_sendgrid_client,
            template_engine=mock_template_engine,
            api_key="test-api-key"
        )
        
        # 10件の同時通知
        tasks = [
            service.notify_urgent_contact(
                contact_id=i,
                urgency=2,
                category="test",
                summary=f"同時通知テスト {i}",
                confidence=0.8
            )
            for i in range(10)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 全て正常に処理されることを確認
        successful_results = [r for r in results if not isinstance(r, Exception) and r.get('success')]
        assert len(successful_results) >= 8  # 80%以上の成功率

    @pytest.mark.asyncio
    async def test_delivery_time_performance(self, mock_sendgrid_client, mock_template_engine):
        """配信時間パフォーマンステスト"""
        from services.notification_service import NotificationService
        service = NotificationService(
            sendgrid_client=mock_sendgrid_client,
            template_engine=mock_template_engine,
            api_key="test-api-key"
        )
        
        delivery_times = []
        
        for i in range(20):
            start_time = time.time()
            
            result = await service.notify_urgent_contact(
                contact_id=i,
                urgency=3,
                category="performance_test",
                summary="配信時間テスト",
                confidence=0.9
            )
            
            delivery_time = time.time() - start_time
            delivery_times.append(delivery_time)
            
            assert delivery_time < 10.0  # 10秒以内
        
        # 平均配信時間が5秒以内であることを確認
        average_delivery_time = sum(delivery_times) / len(delivery_times)
        assert average_delivery_time < 5.0