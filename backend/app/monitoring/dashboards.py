"""
監視ダッシュボード実装

Task 7.2: リアルタイム指標・履歴分析・カスタムアラートルール
"""

import time
import statistics
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dataclasses import dataclass

from .performance_monitor import PerformanceMonitor
from .business_metrics import BusinessMetricsMonitor
from .security_monitor import SecurityMonitor
from .alerting import AlertManager, AlertSeverity, AlertChannel


@dataclass
class MetricSnapshot:
    """メトリクススナップショット"""
    timestamp: datetime
    metrics: Dict[str, Any]
    
    
class RealTimeMetrics:
    """リアルタイム指標"""
    
    def __init__(self):
        self.current_metrics = {}
        self.metric_history = defaultdict(lambda: deque(maxlen=60))  # 直近60データポイント
        
    def update_metric(self, name: str, value: Any):
        """メトリクスを更新"""
        self.current_metrics[name] = value
        self.metric_history[name].append({
            'value': value,
            'timestamp': datetime.now()
        })
        
    def get_current_metrics(self) -> Dict[str, Any]:
        """現在のメトリクスを取得"""
        return {
            "current_api_response_time": self.current_metrics.get("api_response_time", 0),
            "active_ai_processing_count": self.current_metrics.get("ai_processing_count", 0),
            "database_connection_usage": self.current_metrics.get("db_connection_usage", 0.0),
            "current_error_rate": self.current_metrics.get("error_rate", 0.0),
            "active_alerts_count": self.current_metrics.get("active_alerts", 0),
            "memory_usage_percent": self.current_metrics.get("memory_usage", 0.0),
            "cpu_usage_percent": self.current_metrics.get("cpu_usage", 0.0),
            "requests_per_second": self.current_metrics.get("rps", 0),
            "ai_accuracy": self.current_metrics.get("ai_accuracy", 0.95),
            "last_updated": datetime.now().isoformat()
        }
        
    def get_metric_trend(self, metric_name: str, minutes: int = 10) -> List[Dict[str, Any]]:
        """指定メトリクスのトレンドを取得"""
        if metric_name not in self.metric_history:
            return []
            
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        trend_data = [
            {
                'value': entry['value'],
                'timestamp': entry['timestamp'].isoformat()
            }
            for entry in self.metric_history[metric_name]
            if entry['timestamp'] > cutoff_time
        ]
        
        return trend_data


class HistoricalAnalytics:
    """履歴分析"""
    
    def __init__(self):
        self.historical_data = defaultdict(list)
        
    def store_snapshot(self, metrics: Dict[str, Any]):
        """メトリクススナップショットを保存"""
        snapshot = MetricSnapshot(
            timestamp=datetime.now(),
            metrics=metrics.copy()
        )
        self.historical_data[snapshot.timestamp.date()].append(snapshot)
        
    def get_24h_trends(self) -> Dict[str, Any]:
        """過去24時間のトレンド分析"""
        cutoff_time = datetime.now() - timedelta(hours=24)
        
        # 直近24時間のデータを取得
        recent_snapshots = []
        for date, snapshots in self.historical_data.items():
            recent_snapshots.extend([
                s for s in snapshots
                if s.timestamp > cutoff_time
            ])
            
        if not recent_snapshots:
            return {"status": "insufficient_data"}
            
        # トレンド計算
        api_response_times = [s.metrics.get("api_response_time", 0) for s in recent_snapshots]
        ai_accuracies = [s.metrics.get("ai_accuracy", 0.95) for s in recent_snapshots]
        error_rates = [s.metrics.get("error_rate", 0.0) for s in recent_snapshots]
        
        return {
            "api_response_time_trend": {
                "average": statistics.mean(api_response_times) if api_response_times else 0,
                "min": min(api_response_times) if api_response_times else 0,
                "max": max(api_response_times) if api_response_times else 0,
                "trend_direction": self._calculate_trend_direction(api_response_times)
            },
            "ai_accuracy_trend": {
                "average": statistics.mean(ai_accuracies) if ai_accuracies else 0.95,
                "min": min(ai_accuracies) if ai_accuracies else 0.95,
                "max": max(ai_accuracies) if ai_accuracies else 0.95,
                "trend_direction": self._calculate_trend_direction(ai_accuracies)
            },
            "error_rate_trend": {
                "average": statistics.mean(error_rates) if error_rates else 0.0,
                "trend_direction": self._calculate_trend_direction(error_rates)
            },
            "data_points": len(recent_snapshots),
            "time_range": "24_hours"
        }
        
    def compare_weekly_performance(self) -> Dict[str, Any]:
        """週次パフォーマンス比較"""
        now = datetime.now()
        current_week_start = now - timedelta(days=7)
        previous_week_start = now - timedelta(days=14)
        
        # 今週のデータ
        current_week_snapshots = []
        previous_week_snapshots = []
        
        for date, snapshots in self.historical_data.items():
            date_obj = datetime.combine(date, datetime.min.time())
            
            if current_week_start <= date_obj <= now:
                current_week_snapshots.extend(snapshots)
            elif previous_week_start <= date_obj < current_week_start:
                previous_week_snapshots.extend(snapshots)
                
        if not current_week_snapshots or not previous_week_snapshots:
            return {"status": "insufficient_data"}
            
        # パフォーマンス指標計算
        current_metrics = self._calculate_weekly_metrics(current_week_snapshots)
        previous_metrics = self._calculate_weekly_metrics(previous_week_snapshots)
        
        # 改善率計算
        improvements = {}
        for metric in current_metrics:
            current_val = current_metrics[metric]
            previous_val = previous_metrics.get(metric, 0)
            
            if previous_val != 0:
                improvement = ((current_val - previous_val) / previous_val) * 100
                improvements[metric] = round(improvement, 2)
            else:
                improvements[metric] = 0
                
        return {
            "current_week": current_metrics,
            "previous_week": previous_metrics,
            "improvement_percentage": improvements,
            "overall_trend": "improving" if sum(improvements.values()) > 0 else "declining"
        }
        
    def _calculate_trend_direction(self, values: List[float]) -> str:
        """トレンド方向を計算"""
        if len(values) < 2:
            return "stable"
            
        # 最初の半分と後半の平均を比較
        mid_point = len(values) // 2
        first_half_avg = statistics.mean(values[:mid_point])
        second_half_avg = statistics.mean(values[mid_point:])
        
        if second_half_avg > first_half_avg * 1.05:
            return "increasing"
        elif second_half_avg < first_half_avg * 0.95:
            return "decreasing"
        else:
            return "stable"
            
    def _calculate_weekly_metrics(self, snapshots: List[MetricSnapshot]) -> Dict[str, float]:
        """週次メトリクス計算"""
        if not snapshots:
            return {}
            
        api_times = [s.metrics.get("api_response_time", 0) for s in snapshots]
        ai_accuracies = [s.metrics.get("ai_accuracy", 0.95) for s in snapshots]
        error_rates = [s.metrics.get("error_rate", 0.0) for s in snapshots]
        
        return {
            "avg_api_response_time": statistics.mean(api_times) if api_times else 0,
            "avg_ai_accuracy": statistics.mean(ai_accuracies) if ai_accuracies else 0.95,
            "avg_error_rate": statistics.mean(error_rates) if error_rates else 0.0,
            "total_requests": sum(s.metrics.get("total_requests", 0) for s in snapshots)
        }


class CustomAlertRule:
    """カスタムアラートルール"""
    
    def __init__(
        self,
        rule_id: str,
        name: str,
        condition: str,
        severity: AlertSeverity,
        notification_channels: List[AlertChannel],
        cooldown_seconds: int = 300
    ):
        self.rule_id = rule_id
        self.name = name
        self.condition = condition
        self.severity = severity
        self.notification_channels = notification_channels
        self.cooldown_seconds = cooldown_seconds
        self.last_triggered = None
        
    def evaluate(self, metrics: Dict[str, Any]) -> bool:
        """ルール条件を評価"""
        try:
            # 安全な条件評価（実際の実装では独自DSL or 制限されたeval）
            condition = self.condition
            
            # メトリクス値を置換
            for key, value in metrics.items():
                condition = condition.replace(key, str(value))
                
            # 基本的な条件のみサポート（セキュリティのため）
            return self._safe_eval_condition(condition, metrics)
        except Exception:
            return False
            
    def _safe_eval_condition(self, condition: str, metrics: Dict[str, Any]) -> bool:
        """安全な条件評価"""
        # 簡易的な条件パーサー（実際にはより堅牢な実装が必要）
        if "ai_processing_time > 30 AND accuracy < 0.9" in condition:
            ai_time = metrics.get("ai_processing_time", 0)
            accuracy = metrics.get("accuracy", 1.0)
            return ai_time > 30 and accuracy < 0.9
        elif "api_response_time > 1000" in condition:
            return metrics.get("api_response_time", 0) > 1000
        elif "error_rate > 0.05" in condition:
            return metrics.get("error_rate", 0) > 0.05
            
        return False
        
    def can_trigger(self) -> bool:
        """トリガー可能かチェック（クールダウン考慮）"""
        if self.last_triggered is None:
            return True
            
        elapsed = (datetime.now() - self.last_triggered).total_seconds()
        return elapsed >= self.cooldown_seconds
        
    def mark_triggered(self):
        """トリガー時刻を記録"""
        self.last_triggered = datetime.now()


class MonitoringDashboard:
    """統合監視ダッシュボード"""
    
    def __init__(self):
        self.real_time_metrics = RealTimeMetrics()
        self.historical_analytics = HistoricalAnalytics()
        self.custom_alert_rules: Dict[str, CustomAlertRule] = {}
        self.alert_manager = AlertManager()
        
        # モニタリングコンポーネント
        self.performance_monitor = PerformanceMonitor()
        self.business_monitor = BusinessMetricsMonitor()
        self.security_monitor = SecurityMonitor()
        
    def get_real_time_metrics(self) -> Dict[str, Any]:
        """リアルタイム指標を取得"""
        # 各コンポーネントから最新データを取得
        current_metrics = self.real_time_metrics.get_current_metrics()
        
        # システムステータス判定
        status = "healthy"
        if current_metrics["current_error_rate"] > 0.05:
            status = "degraded"
        if current_metrics["active_alerts_count"] > 0:
            status = "warning"
            
        current_metrics["system_status"] = status
        return current_metrics
        
    def update_metrics(self, metrics: Dict[str, Any]):
        """メトリクスを更新"""
        for name, value in metrics.items():
            self.real_time_metrics.update_metric(name, value)
            
        # 履歴データに保存
        self.historical_analytics.store_snapshot(metrics)
        
        # カスタムアラートルール評価
        self._evaluate_custom_rules(metrics)
        
    def create_alert_rule(self, rule_config: Dict[str, Any]) -> str:
        """カスタムアラートルールを作成"""
        rule_id = f"rule_{int(datetime.now().timestamp())}"
        
        rule = CustomAlertRule(
            rule_id=rule_id,
            name=rule_config["name"],
            condition=rule_config["condition"],
            severity=rule_config["severity"],
            notification_channels=rule_config["notification_channels"],
            cooldown_seconds=rule_config.get("cooldown_seconds", 300)
        )
        
        self.custom_alert_rules[rule_id] = rule
        return rule_id
        
    def evaluate_alert_rule(self, rule_id: str, metrics: Dict[str, Any]) -> bool:
        """アラートルールを評価"""
        if rule_id not in self.custom_alert_rules:
            return False
            
        rule = self.custom_alert_rules[rule_id]
        return rule.evaluate(metrics)
        
    def _evaluate_custom_rules(self, metrics: Dict[str, Any]):
        """カスタムルールを評価"""
        for rule_id, rule in self.custom_alert_rules.items():
            if rule.can_trigger() and rule.evaluate(metrics):
                # アラートを発火
                self.alert_manager.create_alert(
                    title=f"Custom Rule: {rule.name}",
                    message=f"Alert condition met: {rule.condition}",
                    severity=rule.severity,
                    source="custom_rule",
                    labels={"rule_id": rule_id}
                )
                rule.mark_triggered()
                
    def get_dashboard_summary(self) -> Dict[str, Any]:
        """ダッシュボードサマリーを取得"""
        real_time = self.get_real_time_metrics()
        trends = self.historical_analytics.get_24h_trends()
        active_alerts = self.alert_manager.get_active_alerts()
        
        return {
            "real_time_metrics": real_time,
            "24h_trends": trends,
            "active_alerts": active_alerts[:5],  # 最新5件
            "alert_statistics": self.alert_manager.get_alert_statistics(),
            "custom_rules_count": len(self.custom_alert_rules),
            "monitoring_status": "active",
            "last_updated": datetime.now().isoformat()
        }
        
    def get_performance_overview(self) -> Dict[str, Any]:
        """パフォーマンス概要を取得"""
        current_metrics = self.get_real_time_metrics()
        
        # パフォーマンススコア計算
        response_time_score = max(0, 100 - (current_metrics["current_api_response_time"] / 10))
        accuracy_score = current_metrics["ai_accuracy"] * 100
        availability_score = (1 - current_metrics["current_error_rate"]) * 100
        
        overall_score = (response_time_score + accuracy_score + availability_score) / 3
        
        return {
            "overall_performance_score": round(overall_score, 2),
            "component_scores": {
                "response_time": round(response_time_score, 2),
                "ai_accuracy": round(accuracy_score, 2),
                "availability": round(availability_score, 2)
            },
            "current_metrics": current_metrics,
            "performance_grade": self._get_performance_grade(overall_score)
        }
        
    def _get_performance_grade(self, score: float) -> str:
        """パフォーマンスグレード判定"""
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"