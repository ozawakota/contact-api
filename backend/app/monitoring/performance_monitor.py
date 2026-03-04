"""
パフォーマンス監視実装

Task 7.2: API応答時間・AI処理時間・DB接続監視
"""

import time
import asyncio
import statistics
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum


class MetricType(Enum):
    """メトリクス種別"""
    COUNTER = "counter"
    GAUGE = "gauge" 
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class Metric:
    """メトリクス"""
    name: str
    type: MetricType
    value: float
    timestamp: datetime
    labels: Dict[str, str] = field(default_factory=dict)
    

class APIResponseTimeMonitor:
    """API応答時間監視"""
    
    def __init__(
        self, 
        target_percentile_95: int = 500,
        alert_threshold: int = 1000
    ):
        self.target_percentile_95 = target_percentile_95
        self.alert_threshold = alert_threshold
        self.response_times: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        
    def record_response_time(self, endpoint: str, response_time: float):
        """API応答時間を記録"""
        self.response_times[endpoint].append(response_time)
        
    def get_metrics(self, endpoint: str) -> Dict[str, Any]:
        """エンドポイントのメトリクスを取得"""
        if endpoint not in self.response_times:
            return {}
            
        times = list(self.response_times[endpoint])
        if not times:
            return {}
            
        # 統計値計算
        average = statistics.mean(times)
        p95 = statistics.quantiles(times, n=20)[18] if len(times) >= 20 else max(times)
        slow_requests = [t for t in times if t > self.alert_threshold]
        
        return {
            "average": average,
            "p95": p95,
            "min": min(times),
            "max": max(times),
            "slow_requests_count": len(slow_requests),
            "total_requests": len(times),
            "alert_triggered": p95 > self.target_percentile_95,
            "threshold_breaches": len(slow_requests)
        }


class AIProcessingTimeMonitor:
    """AI処理時間監視"""
    
    def __init__(
        self,
        target_time: int = 20,
        warning_threshold: int = 30,
        critical_threshold: int = 60
    ):
        self.target_time = target_time
        self.warning_threshold = warning_threshold 
        self.critical_threshold = critical_threshold
        self.processing_times: Dict[str, List[float]] = defaultdict(list)
        
    def record_processing_time(self, service: str, processing_time: float):
        """AI処理時間を記録"""
        self.processing_times[service].append(processing_time)
        
    def get_metrics(self, service: str) -> Dict[str, Any]:
        """サービスのメトリクスを取得"""
        if service not in self.processing_times:
            return {}
            
        times = self.processing_times[service]
        if not times:
            return {}
            
        warning_count = len([t for t in times if t > self.warning_threshold])
        critical_count = len([t for t in times if t > self.critical_threshold])
        sla_breaches = len([t for t in times if t > self.target_time])
        
        return {
            "average_time": statistics.mean(times),
            "warning_count": warning_count,
            "critical_count": critical_count,
            "sla_breach_count": sla_breaches,
            "sla_breach_rate": sla_breaches / len(times) if times else 0,
            "total_processed": len(times)
        }


class DatabaseConnectionMonitor:
    """データベース接続監視"""
    
    def __init__(
        self,
        pool_size: int = 20,
        warning_threshold: int = 15,
        critical_threshold: int = 18
    ):
        self.pool_size = pool_size
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self.current_usage = 0
        
    def record_connection_usage(self, active_connections: int):
        """現在の接続数を記録"""
        self.current_usage = active_connections
        
    def get_current_metrics(self) -> Dict[str, Any]:
        """現在のメトリクスを取得"""
        usage_percentage = (self.current_usage / self.pool_size) * 100
        
        if self.current_usage >= self.critical_threshold:
            status = "CRITICAL"
        elif self.current_usage >= self.warning_threshold:
            status = "WARNING"
        else:
            status = "OK"
            
        return {
            "active_connections": self.current_usage,
            "pool_size": self.pool_size,
            "available_connections": self.pool_size - self.current_usage,
            "usage_percentage": usage_percentage,
            "status": status
        }


class MetricCollector:
    """メトリクス収集"""
    
    def __init__(self, collection_interval: int = 60):
        self.collection_interval = collection_interval
        self.is_collecting = False
        self.last_collection = None
        
    def start_collection(self):
        """メトリクス収集開始"""
        self.is_collecting = True
        self.last_collection = datetime.now()
        
    def stop_collection(self):
        """メトリクス収集停止"""
        self.is_collecting = False
        
    def collect_current_metrics(self) -> Dict[str, Any]:
        """現在のメトリクスを収集"""
        return {
            "api_response_times": self._collect_api_metrics(),
            "ai_processing_times": self._collect_ai_metrics(),
            "database_connections": self._collect_db_metrics(),
            "memory_usage": self._collect_memory_metrics(),
            "cpu_usage": self._collect_cpu_metrics(),
            "timestamp": datetime.now().isoformat()
        }
        
    def _collect_api_metrics(self) -> Dict[str, Any]:
        """API関連メトリクス収集"""
        return {
            "requests_per_minute": 42,  # モック値
            "average_response_time": 250,
            "error_rate": 0.02
        }
        
    def _collect_ai_metrics(self) -> Dict[str, Any]:
        """AI処理関連メトリクス収集"""
        return {
            "active_processing_count": 3,
            "queue_length": 12,
            "average_processing_time": 18.5
        }
        
    def _collect_db_metrics(self) -> Dict[str, Any]:
        """データベース関連メトリクス収集"""
        return {
            "active_connections": 8,
            "connection_pool_usage": 0.4,
            "query_latency": 45.2
        }
        
    def _collect_memory_metrics(self) -> Dict[str, Any]:
        """メモリ使用量メトリクス収集"""
        try:
            import psutil
            return {
                "memory_usage_percent": psutil.virtual_memory().percent,
                "memory_available_gb": psutil.virtual_memory().available / (1024**3)
            }
        except ImportError:
            return {
                "memory_usage_percent": 45.0,  # モック値
                "memory_available_gb": 4.2
            }
            
    def _collect_cpu_metrics(self) -> Dict[str, Any]:
        """CPU使用率メトリクス収集"""
        try:
            import psutil
            return {
                "cpu_usage_percent": psutil.cpu_percent(interval=1),
                "load_average": psutil.getloadavg()[0] if hasattr(psutil, 'getloadavg') else 0.5
            }
        except ImportError:
            return {
                "cpu_usage_percent": 25.0,  # モック値
                "load_average": 0.6
            }


class PerformanceMonitor:
    """統合パフォーマンス監視"""
    
    def __init__(self):
        self.api_monitor = APIResponseTimeMonitor()
        self.ai_monitor = AIProcessingTimeMonitor()
        self.db_monitor = DatabaseConnectionMonitor()
        self.metric_collector = MetricCollector()
        
    def check_thresholds(self, scenario: Dict[str, Any]) -> List[Dict[str, Any]]:
        """閾値チェックとアラート生成"""
        alerts = []
        
        # API応答時間チェック
        if scenario.get("api_response_time", 0) > 1000:
            alerts.append({
                "type": "api_performance",
                "severity": "WARNING",
                "message": f"API response time {scenario['api_response_time']}ms exceeds threshold",
                "threshold": 1000,
                "current_value": scenario["api_response_time"]
            })
            
        # AI精度チェック  
        if scenario.get("ai_accuracy", 1.0) < 0.95:
            alerts.append({
                "type": "ai_accuracy",
                "severity": "WARNING", 
                "message": f"AI accuracy {scenario['ai_accuracy']} below target",
                "threshold": 0.95,
                "current_value": scenario["ai_accuracy"]
            })
            
        # データベース接続チェック
        if scenario.get("database_connections", 0) > 18:
            alerts.append({
                "type": "database_connections",
                "severity": "CRITICAL",
                "message": f"Database connections {scenario['database_connections']} critical level",
                "threshold": 18,
                "current_value": scenario["database_connections"]
            })
            
        return alerts
        
    def safe_collect_metrics(self) -> Dict[str, Any]:
        """安全なメトリクス収集（監視システム自体の障害対応）"""
        try:
            return self.metric_collector.collect_current_metrics()
        except Exception as e:
            return {
                "status": "monitoring_degraded",
                "fallback_active": True,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }