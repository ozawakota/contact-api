"""
ビジネス指標監視実装

Task 7.2: AI精度・処理失敗率・未処理滞留件数監視
"""

import time
import statistics
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass
class PredictionResult:
    """予測結果"""
    predicted: str
    actual: str
    confidence: float
    timestamp: datetime
    correct: bool = None
    
    def __post_init__(self):
        if self.correct is None:
            self.correct = self.predicted == self.actual


class AIAccuracyTracker:
    """AI精度追跡"""
    
    def __init__(self, target_accuracy: float = 0.95):
        self.target_accuracy = target_accuracy
        self.predictions: deque = deque(maxlen=1000)  # 最新1000件を保持
        
    def record_prediction(
        self, 
        predicted: str, 
        actual: str, 
        confidence: float
    ):
        """予測結果を記録"""
        result = PredictionResult(
            predicted=predicted,
            actual=actual,
            confidence=confidence,
            timestamp=datetime.now()
        )
        self.predictions.append(result)
        
    def get_accuracy_metrics(self) -> Dict[str, Any]:
        """精度メトリクスを取得"""
        if not self.predictions:
            return {"accuracy": 0, "below_target": True}
            
        correct_predictions = sum(1 for p in self.predictions if p.correct)
        total_predictions = len(self.predictions)
        accuracy = correct_predictions / total_predictions
        
        # 信頼度と正解率の相関を計算
        confidences = [p.confidence for p in self.predictions]
        accuracies = [1.0 if p.correct else 0.0 for p in self.predictions]
        
        confidence_correlation = 0.0
        if len(confidences) > 1:
            try:
                # 簡易相関係数計算
                conf_mean = statistics.mean(confidences)
                acc_mean = statistics.mean(accuracies)
                
                numerator = sum((c - conf_mean) * (a - acc_mean) 
                               for c, a in zip(confidences, accuracies))
                conf_var = sum((c - conf_mean) ** 2 for c in confidences)
                acc_var = sum((a - acc_mean) ** 2 for a in accuracies)
                
                if conf_var > 0 and acc_var > 0:
                    confidence_correlation = numerator / (conf_var * acc_var) ** 0.5
            except (ZeroDivisionError, ValueError):
                confidence_correlation = 0.0
        
        return {
            "accuracy": accuracy,
            "target_accuracy": self.target_accuracy,
            "below_target": accuracy < self.target_accuracy,
            "correct_predictions": correct_predictions,
            "total_predictions": total_predictions,
            "confidence_correlation": confidence_correlation,
            "average_confidence": statistics.mean(confidences) if confidences else 0
        }
        
    def get_accuracy_by_category(self) -> Dict[str, float]:
        """カテゴリー別の精度を取得"""
        category_stats = defaultdict(lambda: {"correct": 0, "total": 0})
        
        for prediction in self.predictions:
            category = prediction.predicted
            category_stats[category]["total"] += 1
            if prediction.correct:
                category_stats[category]["correct"] += 1
                
        return {
            category: stats["correct"] / stats["total"] if stats["total"] > 0 else 0
            for category, stats in category_stats.items()
        }


class ProcessingFailureTracker:
    """処理失敗率追跡"""
    
    def __init__(
        self, 
        target_success_rate: float = 0.99,
        alert_threshold: float = 0.95
    ):
        self.target_success_rate = target_success_rate
        self.alert_threshold = alert_threshold
        self.results: deque = deque(maxlen=1000)
        
    def record_result(self, success: bool):
        """処理結果を記録"""
        self.results.append({
            "success": success,
            "timestamp": datetime.now()
        })
        
    def get_failure_metrics(self) -> Dict[str, Any]:
        """失敗率メトリクスを取得"""
        if not self.results:
            return {"success_rate": 1.0, "failure_rate": 0.0}
            
        successful_results = sum(1 for r in self.results if r["success"])
        total_results = len(self.results)
        success_rate = successful_results / total_results
        failure_rate = 1.0 - success_rate
        
        return {
            "success_rate": success_rate,
            "failure_rate": failure_rate,
            "target_success_rate": self.target_success_rate,
            "alert_threshold": self.alert_threshold,
            "alert_triggered": success_rate < self.alert_threshold,
            "successful_results": successful_results,
            "total_results": total_results
        }
        
    def get_failure_trend(self, hours: int = 24) -> List[Dict[str, Any]]:
        """失敗率のトレンドを取得"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_results = [r for r in self.results if r["timestamp"] > cutoff_time]
        
        # 時間別の失敗率を計算
        hourly_stats = defaultdict(lambda: {"success": 0, "total": 0})
        
        for result in recent_results:
            hour_key = result["timestamp"].replace(minute=0, second=0, microsecond=0)
            hourly_stats[hour_key]["total"] += 1
            if result["success"]:
                hourly_stats[hour_key]["success"] += 1
                
        trend = []
        for hour, stats in sorted(hourly_stats.items()):
            success_rate = stats["success"] / stats["total"] if stats["total"] > 0 else 1.0
            trend.append({
                "hour": hour.isoformat(),
                "success_rate": success_rate,
                "failure_rate": 1.0 - success_rate,
                "total_requests": stats["total"]
            })
            
        return trend


class BacklogMonitor:
    """未処理滞留監視"""
    
    def __init__(
        self,
        warning_threshold: int = 50,
        critical_threshold: int = 100
    ):
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self.queue_sizes: Dict[str, int] = {}
        self.queue_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        
    def record_backlog_size(self, queue_name: str, size: int):
        """キュー滞留数を記録"""
        self.queue_sizes[queue_name] = size
        self.queue_history[queue_name].append({
            "size": size,
            "timestamp": datetime.now()
        })
        
    def get_backlog_metrics(self) -> Dict[str, Any]:
        """滞留メトリクスを取得"""
        queue_metrics = {}
        total_backlog = 0
        overall_status = "OK"
        
        for queue_name, size in self.queue_sizes.items():
            status = "OK"
            if size >= self.critical_threshold:
                status = "CRITICAL"
                overall_status = "CRITICAL"
            elif size >= self.warning_threshold:
                status = "WARNING"
                if overall_status == "OK":
                    overall_status = "WARNING"
                    
            queue_metrics[queue_name] = {
                "current_size": size,
                "status": status,
                "warning_threshold": self.warning_threshold,
                "critical_threshold": self.critical_threshold
            }
            
            total_backlog += size
            
        return {
            **queue_metrics,
            "total_backlog": total_backlog,
            "overall_status": overall_status,
            "queues_monitored": len(self.queue_sizes)
        }
        
    def get_backlog_trends(self, queue_name: str) -> List[Dict[str, Any]]:
        """特定キューの滞留トレンドを取得"""
        if queue_name not in self.queue_history:
            return []
            
        return [
            {
                "size": entry["size"],
                "timestamp": entry["timestamp"].isoformat()
            }
            for entry in self.queue_history[queue_name]
        ]
        
    def predict_backlog_growth(self, queue_name: str) -> Dict[str, Any]:
        """滞留増加予測"""
        if queue_name not in self.queue_history or len(self.queue_history[queue_name]) < 2:
            return {"prediction": "insufficient_data"}
            
        recent_entries = list(self.queue_history[queue_name])[-10:]  # 最新10件
        if len(recent_entries) < 2:
            return {"prediction": "insufficient_data"}
            
        # 簡易線形トレンド計算
        sizes = [entry["size"] for entry in recent_entries]
        if len(set(sizes)) == 1:  # 全て同じサイズ
            return {"prediction": "stable", "current_size": sizes[0]}
            
        # 平均変化率計算
        changes = [sizes[i] - sizes[i-1] for i in range(1, len(sizes))]
        avg_change = statistics.mean(changes)
        
        prediction_type = "stable"
        if avg_change > 2:
            prediction_type = "increasing"
        elif avg_change < -2:
            prediction_type = "decreasing"
            
        # 10分後の予測サイズ
        current_size = sizes[-1]
        predicted_size = current_size + (avg_change * 2)  # 2倍の変化を仮定
        
        return {
            "prediction": prediction_type,
            "current_size": current_size,
            "predicted_size": max(0, int(predicted_size)),
            "average_change_per_period": avg_change,
            "risk_level": "HIGH" if predicted_size > self.critical_threshold else "MEDIUM" if predicted_size > self.warning_threshold else "LOW"
        }


class BusinessMetricsMonitor:
    """ビジネス指標統合監視"""
    
    def __init__(self):
        self.ai_accuracy_tracker = AIAccuracyTracker()
        self.failure_tracker = ProcessingFailureTracker()
        self.backlog_monitor = BacklogMonitor()
        
    def check_metrics(self, scenario: Dict[str, Any]) -> List[Dict[str, Any]]:
        """ビジネス指標チェックとアラート生成"""
        alerts = []
        
        # AI精度チェック
        if scenario.get("ai_accuracy", 1.0) < 0.95:
            alerts.append({
                "type": "ai_accuracy",
                "severity": "WARNING",
                "message": f"AI accuracy {scenario['ai_accuracy']} below target 95%",
                "metric": "ai_accuracy",
                "threshold": 0.95,
                "current_value": scenario["ai_accuracy"]
            })
            
        # 認証失敗チェック
        if scenario.get("failed_authentications", 0) > 10:
            alerts.append({
                "type": "security",
                "severity": "WARNING", 
                "message": f"High authentication failures: {scenario['failed_authentications']}",
                "metric": "failed_authentications",
                "threshold": 10,
                "current_value": scenario["failed_authentications"]
            })
            
        return alerts
        
    def get_business_health_score(self) -> Dict[str, Any]:
        """ビジネスヘルススコア算出"""
        accuracy_metrics = self.ai_accuracy_tracker.get_accuracy_metrics()
        failure_metrics = self.failure_tracker.get_failure_metrics()
        backlog_metrics = self.backlog_monitor.get_backlog_metrics()
        
        # スコア計算（0-100）
        accuracy_score = accuracy_metrics["accuracy"] * 100
        reliability_score = failure_metrics["success_rate"] * 100
        
        # バックログスコア（逆数）
        total_backlog = backlog_metrics.get("total_backlog", 0)
        backlog_score = max(0, 100 - (total_backlog / 10))  # 10件につき1点減点
        
        overall_score = (accuracy_score * 0.4 + reliability_score * 0.4 + backlog_score * 0.2)
        
        health_status = "EXCELLENT"
        if overall_score < 50:
            health_status = "POOR"
        elif overall_score < 70:
            health_status = "FAIR"
        elif overall_score < 90:
            health_status = "GOOD"
            
        return {
            "overall_score": round(overall_score, 2),
            "health_status": health_status,
            "component_scores": {
                "ai_accuracy": round(accuracy_score, 2),
                "reliability": round(reliability_score, 2),
                "backlog_management": round(backlog_score, 2)
            },
            "recommendations": self._generate_recommendations(
                accuracy_score, reliability_score, backlog_score
            )
        }
        
    def _generate_recommendations(
        self, 
        accuracy_score: float,
        reliability_score: float, 
        backlog_score: float
    ) -> List[str]:
        """改善提案生成"""
        recommendations = []
        
        if accuracy_score < 90:
            recommendations.append("AI model retraining or parameter tuning needed")
        if reliability_score < 95:
            recommendations.append("Investigate and fix recurring failure patterns")
        if backlog_score < 80:
            recommendations.append("Consider scaling up processing capacity")
            
        return recommendations