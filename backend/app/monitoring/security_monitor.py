"""
セキュリティ監視実装

Task 7.2: アクセスパターン検知・認証失敗追跡・異常検知
"""

import time
import hashlib
import statistics
from typing import Dict, List, Any, Optional, Set, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, deque, Counter
from dataclasses import dataclass
from enum import Enum


class ThreatLevel(Enum):
    """脅威レベル"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class SecurityEvent:
    """セキュリティイベント"""
    timestamp: datetime
    event_type: str
    source_ip: str
    user_agent: str = ""
    endpoint: str = ""
    user_id: str = ""
    threat_level: ThreatLevel = ThreatLevel.LOW
    details: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}


class AccessPatternDetector:
    """アクセスパターン検知"""
    
    def __init__(
        self,
        rate_limit_threshold: int = 100,
        suspicious_threshold: int = 500,
        time_window: int = 60  # 1分
    ):
        self.rate_limit_threshold = rate_limit_threshold
        self.suspicious_threshold = suspicious_threshold
        self.time_window = time_window
        
        # IP別のリクエスト履歴
        self.request_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        
        # 既知の悪意のあるパターン
        self.known_attack_patterns = {
            'sql_injection': [r'union\s+select', r'drop\s+table', r'insert\s+into'],
            'xss': [r'<script', r'javascript:', r'onerror='],
            'path_traversal': [r'\.\./', r'\.\.\\', r'%2e%2e%2f'],
        }
        
    def record_request(self, client_ip: str, timestamp: datetime, **kwargs):
        """リクエストを記録"""
        request_info = {
            'timestamp': timestamp,
            'endpoint': kwargs.get('endpoint', ''),
            'user_agent': kwargs.get('user_agent', ''),
            'payload': kwargs.get('payload', '')
        }
        self.request_history[client_ip].append(request_info)
        
    def analyze_access_patterns(self, client_ip: str) -> Dict[str, Any]:
        """アクセスパターン分析"""
        if client_ip not in self.request_history:
            return {"classification": "UNKNOWN", "requests_per_minute": 0}
            
        requests = list(self.request_history[client_ip])
        if not requests:
            return {"classification": "NORMAL", "requests_per_minute": 0}
            
        # 直近1分間のリクエスト数を計算
        recent_requests = [
            r for r in requests 
            if (datetime.now() - r['timestamp']).total_seconds() <= self.time_window
        ]
        
        requests_per_minute = len(recent_requests)
        
        # 分類決定
        classification = "NORMAL"
        action_required = False
        
        if requests_per_minute > self.suspicious_threshold:
            classification = "SUSPICIOUS"
            action_required = True
        elif requests_per_minute > self.rate_limit_threshold:
            classification = "HIGH_VOLUME"
            
        # 攻撃パターンチェック
        attack_patterns_detected = self._detect_attack_patterns(requests)
        if attack_patterns_detected:
            classification = "MALICIOUS"
            action_required = True
            
        return {
            "classification": classification,
            "requests_per_minute": requests_per_minute,
            "action_required": action_required,
            "attack_patterns": attack_patterns_detected,
            "risk_score": self._calculate_risk_score(requests_per_minute, attack_patterns_detected),
            "recommendation": self._get_recommendation(classification)
        }
        
    def _detect_attack_patterns(self, requests: List[Dict[str, Any]]) -> List[str]:
        """攻撃パターン検知"""
        detected_patterns = []
        
        for request in requests:
            payload = request.get('payload', '').lower()
            endpoint = request.get('endpoint', '').lower()
            user_agent = request.get('user_agent', '').lower()
            
            # 検査対象テキスト
            search_text = f"{payload} {endpoint} {user_agent}"
            
            for pattern_name, patterns in self.known_attack_patterns.items():
                for pattern in patterns:
                    if pattern.lower() in search_text:
                        if pattern_name not in detected_patterns:
                            detected_patterns.append(pattern_name)
                            
        return detected_patterns
        
    def _calculate_risk_score(self, requests_per_minute: int, attack_patterns: List[str]) -> int:
        """リスクスコア計算（0-100）"""
        score = 0
        
        # リクエスト量によるスコア
        if requests_per_minute > self.suspicious_threshold:
            score += 50
        elif requests_per_minute > self.rate_limit_threshold:
            score += 25
            
        # 攻撃パターンによるスコア
        score += len(attack_patterns) * 20
        
        return min(100, score)
        
    def _get_recommendation(self, classification: str) -> str:
        """推奨アクション取得"""
        recommendations = {
            "NORMAL": "No action required",
            "HIGH_VOLUME": "Monitor closely, consider rate limiting",
            "SUSPICIOUS": "Implement rate limiting, investigate source",
            "MALICIOUS": "Block immediately, escalate to security team"
        }
        return recommendations.get(classification, "Monitor")


class AuthenticationFailureTracker:
    """認証失敗追跡"""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        lockout_threshold: int = 10,
        time_window: int = 300  # 5分
    ):
        self.failure_threshold = failure_threshold
        self.lockout_threshold = lockout_threshold
        self.time_window = time_window
        
        # ユーザー別の失敗履歴
        self.failure_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=50))
        self.locked_users: Set[str] = set()
        
    def record_failure(self, user_id: str, timestamp: datetime, **kwargs):
        """認証失敗を記録"""
        failure_info = {
            'timestamp': timestamp,
            'source_ip': kwargs.get('source_ip', ''),
            'user_agent': kwargs.get('user_agent', ''),
            'failure_reason': kwargs.get('failure_reason', 'invalid_credentials')
        }
        self.failure_history[user_id].append(failure_info)
        
        # ロックアウトチェック
        if self._should_lockout_user(user_id):
            self.locked_users.add(user_id)
            
    def record_success(self, user_id: str):
        """認証成功を記録（失敗カウンターリセット）"""
        if user_id in self.failure_history:
            self.failure_history[user_id].clear()
        if user_id in self.locked_users:
            self.locked_users.remove(user_id)
            
    def get_user_status(self, user_id: str) -> Dict[str, Any]:
        """ユーザーのセキュリティ状態取得"""
        if user_id not in self.failure_history:
            return {
                "locked_out": False,
                "failure_count": 0,
                "risk_level": "LOW"
            }
            
        failures = list(self.failure_history[user_id])
        
        # 直近の時間枠内の失敗数
        cutoff_time = datetime.now() - timedelta(seconds=self.time_window)
        recent_failures = [f for f in failures if f['timestamp'] > cutoff_time]
        
        failure_count = len(recent_failures)
        locked_out = user_id in self.locked_users
        
        # リスクレベル判定
        risk_level = "LOW"
        if failure_count >= self.lockout_threshold:
            risk_level = "CRITICAL"
        elif failure_count >= self.failure_threshold:
            risk_level = "HIGH"
        elif failure_count > 0:
            risk_level = "MEDIUM"
            
        return {
            "locked_out": locked_out,
            "failure_count": failure_count,
            "recent_failures": len(recent_failures),
            "risk_level": risk_level,
            "time_until_unlock": self._get_unlock_time(user_id) if locked_out else 0
        }
        
    def _should_lockout_user(self, user_id: str) -> bool:
        """ユーザーをロックアウトすべきかチェック"""
        failures = list(self.failure_history[user_id])
        cutoff_time = datetime.now() - timedelta(seconds=self.time_window)
        recent_failures = [f for f in failures if f['timestamp'] > cutoff_time]
        return len(recent_failures) >= self.lockout_threshold
        
    def _get_unlock_time(self, user_id: str) -> int:
        """ロックアウト解除までの時間（秒）"""
        if user_id not in self.failure_history:
            return 0
            
        failures = list(self.failure_history[user_id])
        if not failures:
            return 0
            
        last_failure = max(failures, key=lambda f: f['timestamp'])
        unlock_time = last_failure['timestamp'] + timedelta(seconds=self.time_window)
        remaining = (unlock_time - datetime.now()).total_seconds()
        return max(0, int(remaining))


class AnomalyDetector:
    """異常検知"""
    
    def __init__(
        self,
        baseline_window: int = 3600,  # 1時間
        sensitivity: float = 2.0      # 2σ
    ):
        self.baseline_window = baseline_window
        self.sensitivity = sensitivity
        
        # メトリクス別のデータ履歴
        self.metric_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=200))
        
    def add_data_point(self, metric_name: str, value: float):
        """データポイントを追加"""
        self.metric_history[metric_name].append({
            'value': value,
            'timestamp': datetime.now()
        })
        
    def detect_anomaly(self, metric_name: str, current_value: float) -> float:
        """異常検知（異常スコアを返す）"""
        if metric_name not in self.metric_history:
            return 0.0
            
        history = list(self.metric_history[metric_name])
        if len(history) < 10:  # 最低10データポイント必要
            return 0.0
            
        # ベースライン統計計算
        values = [h['value'] for h in history]
        mean_value = statistics.mean(values)
        
        try:
            std_value = statistics.stdev(values)
        except statistics.StatisticsError:
            std_value = 0.0
            
        if std_value == 0:
            return 0.0
            
        # Z-score計算
        z_score = abs(current_value - mean_value) / std_value
        return z_score
        
    def is_anomalous(self, metric_name: str, current_value: float) -> bool:
        """異常かどうか判定"""
        anomaly_score = self.detect_anomaly(metric_name, current_value)
        return anomaly_score > self.sensitivity
        
    def get_anomaly_report(self, metric_name: str) -> Dict[str, Any]:
        """異常検知レポート取得"""
        if metric_name not in self.metric_history:
            return {"status": "no_data"}
            
        history = list(self.metric_history[metric_name])
        if len(history) < 10:
            return {"status": "insufficient_data", "data_points": len(history)}
            
        values = [h['value'] for h in history]
        recent_values = values[-10:]  # 直近10件
        
        baseline_mean = statistics.mean(values[:-10]) if len(values) > 10 else statistics.mean(values)
        recent_mean = statistics.mean(recent_values)
        
        # トレンド分析
        trend = "stable"
        if recent_mean > baseline_mean * 1.2:
            trend = "increasing"
        elif recent_mean < baseline_mean * 0.8:
            trend = "decreasing"
            
        return {
            "status": "analyzed",
            "baseline_mean": baseline_mean,
            "recent_mean": recent_mean,
            "trend": trend,
            "data_points": len(history),
            "anomalous_points": sum(1 for v in values if self.is_anomalous(metric_name, v))
        }


class SecurityMonitor:
    """統合セキュリティ監視"""
    
    def __init__(self):
        self.access_detector = AccessPatternDetector()
        self.auth_tracker = AuthenticationFailureTracker()
        self.anomaly_detector = AnomalyDetector()
        self.security_events: deque = deque(maxlen=1000)
        
    def check_threats(self, scenario: Dict[str, Any]) -> List[Dict[str, Any]]:
        """脅威チェックとアラート生成"""
        alerts = []
        
        # 認証失敗チェック
        failed_auth = scenario.get("failed_authentications", 0)
        if failed_auth > 10:
            alerts.append({
                "type": "authentication_failures",
                "severity": "WARNING",
                "message": f"High authentication failure rate: {failed_auth}",
                "metric": "failed_authentications",
                "threshold": 10,
                "current_value": failed_auth
            })
            
        return alerts
        
    def record_security_event(
        self,
        event_type: str,
        source_ip: str,
        threat_level: ThreatLevel = ThreatLevel.LOW,
        **kwargs
    ):
        """セキュリティイベントを記録"""
        event = SecurityEvent(
            timestamp=datetime.now(),
            event_type=event_type,
            source_ip=source_ip,
            threat_level=threat_level,
            user_agent=kwargs.get('user_agent', ''),
            endpoint=kwargs.get('endpoint', ''),
            user_id=kwargs.get('user_id', ''),
            details=kwargs
        )
        self.security_events.append(event)
        
    def get_security_summary(self) -> Dict[str, Any]:
        """セキュリティサマリー取得"""
        if not self.security_events:
            return {"status": "no_events"}
            
        events = list(self.security_events)
        recent_events = [
            e for e in events 
            if (datetime.now() - e.timestamp).total_seconds() <= 3600  # 直近1時間
        ]
        
        # 脅威レベル別集計
        threat_counts = Counter(e.threat_level.value for e in recent_events)
        
        # イベント種別集計
        event_type_counts = Counter(e.event_type for e in recent_events)
        
        # 上位攻撃元IP
        top_source_ips = Counter(e.source_ip for e in recent_events).most_common(5)
        
        return {
            "total_events": len(recent_events),
            "threat_level_distribution": dict(threat_counts),
            "event_type_distribution": dict(event_type_counts),
            "top_source_ips": top_source_ips,
            "high_risk_events": len([e for e in recent_events if e.threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]]),
            "security_score": self._calculate_security_score(recent_events)
        }
        
    def _calculate_security_score(self, events: List[SecurityEvent]) -> int:
        """セキュリティスコア計算（0-100、高いほど安全）"""
        if not events:
            return 100
            
        # 脅威レベル重み
        threat_weights = {
            ThreatLevel.LOW: 1,
            ThreatLevel.MEDIUM: 3,
            ThreatLevel.HIGH: 7,
            ThreatLevel.CRITICAL: 15
        }
        
        # 重み付きリスクスコア計算
        total_risk = sum(threat_weights.get(e.threat_level, 1) for e in events)
        
        # 100点からリスクスコアを差し引き
        security_score = max(0, 100 - (total_risk // 2))
        
        return security_score