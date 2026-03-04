"""
Task 7.2 システム監視・アラート実装のテスト

TDD-REDフェーズ: 失敗するテストを先に作成
- パフォーマンス監視（API応答・AI処理・DB接続時間1分間隔）
- ビジネス指標監視（AI精度・処理失敗率・未処理滞留件数）
- セキュリティ監視（大量アクセス・認証失敗・異常パターン検知）
- Cloud Logging統合・自動アラート・エスカレーション設定
"""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, List, Any

from backend.app.monitoring.performance_monitor import (
    PerformanceMonitor,
    MetricType,
    MetricCollector,
    APIResponseTimeMonitor,
    AIProcessingTimeMonitor,
    DatabaseConnectionMonitor,
)
from backend.app.monitoring.business_metrics import (
    BusinessMetricsMonitor,
    AIAccuracyTracker,
    ProcessingFailureTracker,
    BacklogMonitor,
)
from backend.app.monitoring.security_monitor import (
    SecurityMonitor,
    AccessPatternDetector,
    AuthenticationFailureTracker,
    AnomalyDetector,
)
from backend.app.monitoring.alerting import (
    AlertManager,
    AlertSeverity,
    AlertChannel,
    EscalationPolicy,
    CloudLoggingIntegration,
)
from backend.app.monitoring.dashboards import (
    MonitoringDashboard,
    RealTimeMetrics,
    HistoricalAnalytics,
)


class TestPerformanceMonitoring:
    """パフォーマンス監視テスト"""
    
    def test_api_response_time_monitoring(self):
        """API応答時間監視テスト"""
        monitor = APIResponseTimeMonitor(
            target_percentile_95=500,  # 95%tile目標: 500ms
            alert_threshold=1000       # アラート閾値: 1000ms
        )
        
        # 複数のAPI応答時間を記録
        response_times = [100, 200, 300, 800, 1200, 150, 250]
        for response_time in response_times:
            monitor.record_response_time("/api/v1/contacts", response_time)
        
        metrics = monitor.get_metrics("/api/v1/contacts")
        
        # 統計値の検証
        assert metrics["average"] == pytest.approx(300, abs=50)
        assert metrics["p95"] > 500  # 目標を上回っている
        assert metrics["alert_triggered"] is True  # アラートが発生
        assert metrics["slow_requests_count"] == 1  # 1200msが1件
        
    def test_ai_processing_time_monitoring(self):
        """AI処理時間監視テスト"""
        monitor = AIProcessingTimeMonitor(
            target_time=20,      # 目標: 20秒
            warning_threshold=30, # 警告: 30秒
            critical_threshold=60 # 危険: 60秒
        )
        
        # AI処理時間の記録
        monitor.record_processing_time("gemini_analysis", 15)  # 正常
        monitor.record_processing_time("gemini_analysis", 35)  # 警告レベル
        monitor.record_processing_time("gemini_analysis", 65)  # 危険レベル
        
        metrics = monitor.get_metrics("gemini_analysis")
        
        assert metrics["warning_count"] == 1
        assert metrics["critical_count"] == 1
        assert metrics["sla_breach_rate"] == pytest.approx(0.67, abs=0.1)
        
    def test_database_connection_monitoring(self):
        """データベース接続監視テスト"""
        monitor = DatabaseConnectionMonitor(
            pool_size=20,
            warning_threshold=15,  # 75%使用率で警告
            critical_threshold=18  # 90%使用率で危険
        )
        
        # 接続プール使用状況をシミュレート
        monitor.record_connection_usage(16)  # 80% 使用率 -> 警告
        
        metrics = monitor.get_current_metrics()
        
        assert metrics["usage_percentage"] == 80
        assert metrics["status"] == "WARNING"
        assert metrics["available_connections"] == 4
        
    def test_real_time_metrics_collection(self):
        """リアルタイム指標収集テスト"""
        collector = MetricCollector(collection_interval=60)  # 1分間隔
        
        # メトリクス収集の開始
        collector.start_collection()
        
        # 1分間待機してメトリクス取得をシミュレート
        with patch('time.time', return_value=time.time() + 60):
            metrics = collector.collect_current_metrics()
        
        # 期待される指標が収集される
        assert "api_response_times" in metrics
        assert "ai_processing_times" in metrics
        assert "database_connections" in metrics
        assert "memory_usage" in metrics
        assert "cpu_usage" in metrics


class TestBusinessMetricsMonitoring:
    """ビジネス指標監視テスト"""
    
    def test_ai_accuracy_tracking(self):
        """AI精度追跡テスト"""
        tracker = AIAccuracyTracker(target_accuracy=0.95)
        
        # AI分析結果の記録（正解との比較）
        predictions = [
            {"predicted": "URGENT", "actual": "URGENT", "confidence": 0.9},      # 正解
            {"predicted": "MEDIUM", "actual": "MEDIUM", "confidence": 0.85},     # 正解
            {"predicted": "LOW", "actual": "MEDIUM", "confidence": 0.7},         # 不正解
            {"predicted": "URGENT", "actual": "URGENT", "confidence": 0.95},     # 正解
            {"predicted": "MEDIUM", "actual": "LOW", "confidence": 0.6},         # 不正解
        ]
        
        for pred in predictions:
            tracker.record_prediction(pred["predicted"], pred["actual"], pred["confidence"])
        
        metrics = tracker.get_accuracy_metrics()
        
        assert metrics["accuracy"] == 0.6  # 5件中3件正解
        assert metrics["below_target"] is True
        assert metrics["confidence_correlation"] > 0  # 信頼度と正解率の相関
        
    def test_processing_failure_tracking(self):
        """処理失敗率追跡テスト"""
        tracker = ProcessingFailureTracker(
            target_success_rate=0.99,  # 目標成功率99%
            alert_threshold=0.95       # 95%を下回ったらアラート
        )
        
        # 処理結果の記録
        results = ["success"] * 90 + ["failure"] * 10  # 90%成功率
        
        for result in results:
            tracker.record_result(result == "success")
            
        metrics = tracker.get_failure_metrics()
        
        assert metrics["success_rate"] == 0.9
        assert metrics["failure_rate"] == 0.1
        assert metrics["alert_triggered"] is True  # 95%を下回った
        
    def test_backlog_monitoring(self):
        """未処理滞留監視テスト"""
        monitor = BacklogMonitor(
            warning_threshold=50,   # 50件で警告
            critical_threshold=100  # 100件で危険
        )
        
        # 未処理件数の記録
        monitor.record_backlog_size("ai_analysis_queue", 75)
        monitor.record_backlog_size("notification_queue", 25)
        
        metrics = monitor.get_backlog_metrics()
        
        assert metrics["ai_analysis_queue"]["status"] == "WARNING"  # 75件 > 50件
        assert metrics["notification_queue"]["status"] == "OK"      # 25件 < 50件
        assert metrics["total_backlog"] == 100
        assert metrics["overall_status"] == "CRITICAL"  # 合計100件


class TestSecurityMonitoring:
    """セキュリティ監視テスト"""
    
    def test_access_pattern_detection(self):
        """アクセスパターン検知テスト"""
        detector = AccessPatternDetector(
            rate_limit_threshold=100,  # 1分間に100リクエスト
            suspicious_threshold=500   # 1分間に500リクエストで疑わしい
        )
        
        # 大量アクセスをシミュレート
        client_ip = "192.168.1.100"
        timestamp = datetime.now()
        
        for i in range(600):  # 600リクエスト送信
            detector.record_request(client_ip, timestamp + timedelta(seconds=i//10))
            
        analysis = detector.analyze_access_patterns(client_ip)
        
        assert analysis["classification"] == "SUSPICIOUS"
        assert analysis["requests_per_minute"] > 500
        assert analysis["action_required"] is True
        
    def test_authentication_failure_tracking(self):
        """認証失敗追跡テスト"""
        tracker = AuthenticationFailureTracker(
            failure_threshold=5,        # 5回失敗で警告
            lockout_threshold=10,       # 10回失敗でロックアウト
            time_window=300            # 5分間のウィンドウ
        )
        
        # 認証失敗の記録
        user_id = "suspicious_user@example.com"
        
        for i in range(12):  # 12回失敗
            tracker.record_failure(user_id, datetime.now())
            
        status = tracker.get_user_status(user_id)
        
        assert status["locked_out"] is True
        assert status["failure_count"] == 12
        assert status["risk_level"] == "HIGH"
        
    def test_anomaly_detection(self):
        """異常パターン検知テスト"""
        detector = AnomalyDetector(
            baseline_window=3600,     # 1時間のベースライン
            sensitivity=2.0           # 平均から2σ以上で異常
        )
        
        # 正常パターンの確立
        normal_requests = [10, 12, 8, 11, 9, 13, 10, 11] * 10  # 80データポイント
        for req_count in normal_requests:
            detector.add_data_point("api_requests_per_minute", req_count)
            
        # 異常データの検知
        anomaly_score = detector.detect_anomaly("api_requests_per_minute", 50)  # 通常の5倍
        
        assert anomaly_score > 2.0  # 異常判定
        assert detector.is_anomalous("api_requests_per_minute", 50) is True


class TestAlertingSystem:
    """アラートシステムテスト"""
    
    def test_alert_severity_classification(self):
        """アラート重要度分類テスト"""
        alert_manager = AlertManager()
        
        # 各重要度のアラートを作成
        info_alert = alert_manager.create_alert(
            title="System maintenance scheduled",
            severity=AlertSeverity.INFO,
            message="Scheduled maintenance in 1 hour"
        )
        
        critical_alert = alert_manager.create_alert(
            title="Database connection failed",
            severity=AlertSeverity.CRITICAL,
            message="Cannot connect to primary database"
        )
        
        assert info_alert["channels"] == [AlertChannel.LOG]  # ログのみ
        assert critical_alert["channels"] == [AlertChannel.EMAIL, AlertChannel.SLACK, AlertChannel.PAGER]
        
    def test_escalation_policy(self):
        """エスカレーションポリシーテスト"""
        escalation = EscalationPolicy(
            levels=[
                {"delay": 300, "channels": [AlertChannel.EMAIL]},       # 5分後にメール
                {"delay": 900, "channels": [AlertChannel.SLACK]},       # 15分後にSlack  
                {"delay": 1800, "channels": [AlertChannel.PAGER]},      # 30分後にページャー
            ]
        )
        
        alert_time = datetime.now()
        
        # 5分後の状態
        actions = escalation.get_required_actions(alert_time + timedelta(minutes=6))
        assert AlertChannel.EMAIL in actions
        
        # 20分後の状態  
        actions = escalation.get_required_actions(alert_time + timedelta(minutes=20))
        assert AlertChannel.SLACK in actions
        
    def test_cloud_logging_integration(self):
        """Cloud Logging統合テスト"""
        logging_integration = CloudLoggingIntegration(
            project_id="contact-api-project",
            log_name="contact-api-errors"
        )
        
        # ログエントリの送信
        log_entry = {
            "severity": "ERROR",
            "message": "AI processing failed",
            "timestamp": datetime.now().isoformat(),
            "labels": {
                "service": "gemini_service",
                "error_type": "timeout"
            }
        }
        
        with patch.object(logging_integration, 'send_log') as mock_send:
            logging_integration.send_structured_log(log_entry)
            mock_send.assert_called_once()
            
        # ログクエリの実行
        with patch.object(logging_integration, 'query_logs') as mock_query:
            mock_query.return_value = [log_entry]
            
            results = logging_integration.query_error_logs(
                start_time=datetime.now() - timedelta(hours=1),
                error_type="timeout"
            )
            
            assert len(results) == 1
            assert results[0]["error_type"] == "timeout"


class TestMonitoringDashboard:
    """監視ダッシュボードテスト"""
    
    def test_real_time_metrics_display(self):
        """リアルタイム指標表示テスト"""
        dashboard = MonitoringDashboard()
        
        # リアルタイムデータの取得
        real_time_data = dashboard.get_real_time_metrics()
        
        # 必要な指標が含まれている
        expected_metrics = [
            "current_api_response_time",
            "active_ai_processing_count", 
            "database_connection_usage",
            "current_error_rate",
            "active_alerts_count"
        ]
        
        for metric in expected_metrics:
            assert metric in real_time_data
            
    def test_historical_analytics(self):
        """履歴分析テスト"""
        analytics = HistoricalAnalytics()
        
        # 過去24時間のトレンド分析
        trends = analytics.get_24h_trends()
        
        assert "api_response_time_trend" in trends
        assert "ai_accuracy_trend" in trends
        assert "error_rate_trend" in trends
        
        # 週次パフォーマンス比較
        weekly_comparison = analytics.compare_weekly_performance()
        
        assert "current_week" in weekly_comparison
        assert "previous_week" in weekly_comparison
        assert "improvement_percentage" in weekly_comparison
        
    def test_custom_alert_rules(self):
        """カスタムアラートルールテスト"""
        dashboard = MonitoringDashboard()
        
        # カスタムルールの作成
        custom_rule = {
            "name": "High AI Processing Time",
            "condition": "ai_processing_time > 30 AND accuracy < 0.9",
            "severity": AlertSeverity.WARNING,
            "notification_channels": [AlertChannel.SLACK]
        }
        
        rule_id = dashboard.create_alert_rule(custom_rule)
        
        # ルール評価のテスト
        test_metrics = {
            "ai_processing_time": 35,
            "accuracy": 0.85
        }
        
        should_alert = dashboard.evaluate_alert_rule(rule_id, test_metrics)
        assert should_alert is True


class TestMonitoringIntegration:
    """監視システム統合テスト"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_monitoring_flow(self):
        """エンドツーエンド監視フローテスト"""
        # 全監視コンポーネントの統合テスト
        performance_monitor = PerformanceMonitor()
        business_monitor = BusinessMetricsMonitor() 
        security_monitor = SecurityMonitor()
        alert_manager = AlertManager()
        
        # 異常状況をシミュレート
        scenario = {
            "api_response_time": 2000,    # 2秒（異常に遅い）
            "ai_accuracy": 0.8,           # 80%（目標95%を下回る）
            "failed_authentications": 15, # 15回失敗
            "database_connections": 19    # 95%使用率
        }
        
        # 各監視システムで異常検知
        perf_alerts = performance_monitor.check_thresholds(scenario)
        business_alerts = business_monitor.check_metrics(scenario)
        security_alerts = security_monitor.check_threats(scenario)
        
        # アラート統合と優先順位付け
        all_alerts = perf_alerts + business_alerts + security_alerts
        prioritized_alerts = alert_manager.prioritize_alerts(all_alerts)
        
        # 最高優先度は API応答時間異常
        assert prioritized_alerts[0]["type"] == "api_performance"
        assert len(prioritized_alerts) >= 4  # 全カテゴリからアラートが発生
        
    def test_monitoring_system_resilience(self):
        """監視システム自体の耐障害性テスト"""
        monitor = PerformanceMonitor()
        
        # 監視システム自体に障害が発生した場合
        with patch('backend.app.monitoring.performance_monitor.MetricCollector.collect',
                  side_effect=Exception("Monitoring system failure")):
            
            # 監視システムが停止しても例外で落ちない
            result = monitor.safe_collect_metrics()
            
            assert result["status"] == "monitoring_degraded"
            assert result["fallback_active"] is True
            assert "error" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])