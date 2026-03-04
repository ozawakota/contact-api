"""
アラートシステム実装

Task 7.2: Cloud Logging統合・自動アラート・エスカレーション
"""

import json
import logging
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod


class AlertSeverity(Enum):
    """アラート重要度"""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AlertChannel(Enum):
    """アラート通知チャンネル"""
    LOG = "log"
    EMAIL = "email"
    SLACK = "slack"
    PAGER = "pager"
    SMS = "sms"


@dataclass
class Alert:
    """アラート"""
    id: str
    title: str
    message: str
    severity: AlertSeverity
    timestamp: datetime
    source: str
    labels: Dict[str, str] = field(default_factory=dict)
    resolved: bool = False
    escalated: bool = False
    channels: List[AlertChannel] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class AlertChannel(ABC):
    """アラート通知チャンネル基底クラス"""
    
    @abstractmethod
    def send_alert(self, alert: Alert) -> bool:
        """アラートを送信"""
        pass


class LogAlertChannel(AlertChannel):
    """ログアラートチャンネル"""
    
    def __init__(self, logger: logging.Logger = None):
        self.logger = logger or logging.getLogger(__name__)
        
    def send_alert(self, alert: Alert) -> bool:
        """ログにアラートを出力"""
        log_level = {
            AlertSeverity.INFO: logging.INFO,
            AlertSeverity.WARNING: logging.WARNING,
            AlertSeverity.ERROR: logging.ERROR,
            AlertSeverity.CRITICAL: logging.CRITICAL
        }.get(alert.severity, logging.INFO)
        
        self.logger.log(
            log_level,
            f"ALERT [{alert.severity.value}] {alert.title}: {alert.message}",
            extra={
                "alert_id": alert.id,
                "source": alert.source,
                "labels": alert.labels,
                "metadata": alert.metadata
            }
        )
        return True


class EmailAlertChannel(AlertChannel):
    """メールアラートチャンネル"""
    
    def __init__(self, smtp_config: Dict[str, str] = None):
        self.smtp_config = smtp_config or {}
        
    def send_alert(self, alert: Alert) -> bool:
        """メールでアラートを送信（モック実装）"""
        # 実際の実装ではSMTPライブラリを使用
        print(f"📧 EMAIL ALERT: {alert.title}")
        print(f"   Severity: {alert.severity.value}")
        print(f"   Message: {alert.message}")
        return True


class SlackAlertChannel(AlertChannel):
    """Slackアラートチャンネル"""
    
    def __init__(self, webhook_url: str = None, channel: str = "#alerts"):
        self.webhook_url = webhook_url
        self.channel = channel
        
    def send_alert(self, alert: Alert) -> bool:
        """Slackにアラートを送信（モック実装）"""
        # 実際の実装ではSlack APIを使用
        severity_emoji = {
            AlertSeverity.INFO: "ℹ️",
            AlertSeverity.WARNING: "⚠️", 
            AlertSeverity.ERROR: "❌",
            AlertSeverity.CRITICAL: "🚨"
        }.get(alert.severity, "ℹ️")
        
        print(f"{severity_emoji} SLACK ALERT in {self.channel}")
        print(f"   {alert.title}")
        print(f"   {alert.message}")
        return True


class PagerAlertChannel(AlertChannel):
    """ページャーアラートチャンネル"""
    
    def __init__(self, pager_service_config: Dict[str, str] = None):
        self.pager_service_config = pager_service_config or {}
        
    def send_alert(self, alert: Alert) -> bool:
        """ページャーでアラートを送信（モック実装）"""
        # PagerDuty、OpsGenie等のサービスを使用
        print(f"📟 PAGER ALERT: {alert.title}")
        print(f"   CRITICAL: {alert.message}")
        return True


@dataclass
class EscalationRule:
    """エスカレーションルール"""
    delay: int  # 秒
    channels: List[AlertChannel]
    conditions: Dict[str, Any] = field(default_factory=dict)


class EscalationPolicy:
    """エスカレーションポリシー"""
    
    def __init__(self, levels: List[Dict[str, Any]] = None):
        self.levels = levels or []
        self.escalation_rules = self._build_escalation_rules()
        
    def _build_escalation_rules(self) -> List[EscalationRule]:
        """エスカレーションルールを構築"""
        rules = []
        channel_mapping = {
            "email": EmailAlertChannel(),
            "slack": SlackAlertChannel(),
            "pager": PagerAlertChannel()
        }
        
        for level in self.levels:
            channels = []
            for channel_name in level.get("channels", []):
                if hasattr(AlertChannel, channel_name.upper()):
                    channels.append(getattr(AlertChannel, channel_name.upper()))
                    
            rules.append(EscalationRule(
                delay=level.get("delay", 300),
                channels=channels,
                conditions=level.get("conditions", {})
            ))
            
        return rules
        
    def get_required_actions(self, alert_time: datetime) -> List[AlertChannel]:
        """指定時刻にて必要なアクションを取得"""
        current_time = datetime.now()
        elapsed = (current_time - alert_time).total_seconds()
        
        required_channels = []
        for rule in self.escalation_rules:
            if elapsed >= rule.delay:
                required_channels.extend(rule.channels)
                
        return required_channels


class CloudLoggingIntegration:
    """Cloud Logging統合"""
    
    def __init__(self, project_id: str, log_name: str):
        self.project_id = project_id
        self.log_name = log_name
        self.client = None  # 実際の実装ではGoogle Cloud Loggingクライアント
        
    def send_log(self, entry: Dict[str, Any]) -> bool:
        """ログエントリをCloud Loggingに送信（モック実装）"""
        # 実際の実装では google-cloud-logging を使用
        print(f"☁️ CLOUD LOGGING: {self.log_name}")
        print(f"   Project: {self.project_id}")
        print(f"   Entry: {json.dumps(entry, indent=2)}")
        return True
        
    def send_structured_log(self, log_entry: Dict[str, Any]):
        """構造化ログの送信"""
        structured_entry = {
            "timestamp": log_entry.get("timestamp", datetime.now().isoformat()),
            "severity": log_entry.get("severity", "INFO"),
            "message": log_entry["message"],
            "labels": log_entry.get("labels", {}),
            "resource": {
                "type": "gce_instance",
                "labels": {
                    "project_id": self.project_id,
                    "instance_id": "contact-api-instance"
                }
            }
        }
        self.send_log(structured_entry)
        
    def query_logs(
        self, 
        filter_expression: str = None,
        start_time: datetime = None,
        end_time: datetime = None
    ) -> List[Dict[str, Any]]:
        """ログクエリの実行（モック実装）"""
        # 実際の実装ではCloud Logging APIを使用
        return []
        
    def query_error_logs(
        self,
        start_time: datetime,
        error_type: str = None
    ) -> List[Dict[str, Any]]:
        """エラーログのクエリ"""
        # モック実装
        return [{
            "severity": "ERROR",
            "message": "AI processing failed",
            "timestamp": start_time.isoformat(),
            "labels": {
                "service": "gemini_service",
                "error_type": error_type
            }
        }] if error_type == "timeout" else []


class AlertManager:
    """アラート管理"""
    
    def __init__(self):
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        
        # 通知チャンネル設定
        self.channels = {
            AlertChannel.LOG: LogAlertChannel(),
            AlertChannel.EMAIL: EmailAlertChannel(),
            AlertChannel.SLACK: SlackAlertChannel(),
            AlertChannel.PAGER: PagerAlertChannel()
        }
        
        # 重要度別デフォルトチャンネル
        self.severity_channels = {
            AlertSeverity.INFO: [AlertChannel.LOG],
            AlertSeverity.WARNING: [AlertChannel.LOG, AlertChannel.EMAIL],
            AlertSeverity.ERROR: [AlertChannel.LOG, AlertChannel.EMAIL, AlertChannel.SLACK],
            AlertSeverity.CRITICAL: [AlertChannel.LOG, AlertChannel.EMAIL, AlertChannel.SLACK, AlertChannel.PAGER]
        }
        
    def create_alert(
        self,
        title: str,
        message: str,
        severity: AlertSeverity,
        source: str = "system",
        labels: Dict[str, str] = None,
        **metadata
    ) -> Dict[str, Any]:
        """アラートを作成"""
        alert_id = f"alert_{int(datetime.now().timestamp())}"
        
        channels = self.severity_channels.get(severity, [AlertChannel.LOG])
        
        alert = Alert(
            id=alert_id,
            title=title,
            message=message,
            severity=severity,
            timestamp=datetime.now(),
            source=source,
            labels=labels or {},
            channels=channels,
            metadata=metadata
        )
        
        self.active_alerts[alert_id] = alert
        self.alert_history.append(alert)
        
        # アラート送信
        self._send_alert(alert)
        
        return {
            "alert_id": alert_id,
            "channels": [ch.value for ch in channels],
            "timestamp": alert.timestamp.isoformat()
        }
        
    def _send_alert(self, alert: Alert):
        """アラートを各チャンネルに送信"""
        for channel_type in alert.channels:
            if channel_type in self.channels:
                try:
                    self.channels[channel_type].send_alert(alert)
                except Exception as e:
                    logging.error(f"Failed to send alert via {channel_type}: {e}")
                    
    def resolve_alert(self, alert_id: str) -> bool:
        """アラートを解決"""
        if alert_id in self.active_alerts:
            self.active_alerts[alert_id].resolved = True
            del self.active_alerts[alert_id]
            return True
        return False
        
    def escalate_alert(self, alert_id: str) -> bool:
        """アラートをエスカレーション"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            if not alert.escalated:
                alert.escalated = True
                alert.severity = AlertSeverity.CRITICAL
                self._send_alert(alert)
                return True
        return False
        
    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """アクティブなアラートを取得"""
        return [
            {
                "id": alert.id,
                "title": alert.title,
                "severity": alert.severity.value,
                "timestamp": alert.timestamp.isoformat(),
                "source": alert.source
            }
            for alert in self.active_alerts.values()
        ]
        
    def prioritize_alerts(self, alerts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """アラートを優先順位付け"""
        severity_priority = {
            "CRITICAL": 4,
            "ERROR": 3,
            "WARNING": 2,
            "INFO": 1
        }
        
        return sorted(
            alerts,
            key=lambda a: (
                severity_priority.get(a.get("severity", "INFO"), 1),
                a.get("timestamp", "")
            ),
            reverse=True
        )
        
    def get_alert_statistics(self) -> Dict[str, Any]:
        """アラート統計を取得"""
        if not self.alert_history:
            return {"total_alerts": 0}
            
        # 直近24時間のアラート
        cutoff_time = datetime.now() - timedelta(hours=24)
        recent_alerts = [
            a for a in self.alert_history
            if a.timestamp > cutoff_time
        ]
        
        # 重要度別集計
        severity_counts = {}
        for severity in AlertSeverity:
            severity_counts[severity.value] = len([
                a for a in recent_alerts
                if a.severity == severity
            ])
            
        return {
            "total_alerts": len(self.alert_history),
            "active_alerts": len(self.active_alerts),
            "recent_24h_alerts": len(recent_alerts),
            "severity_distribution": severity_counts,
            "resolution_rate": len([a for a in self.alert_history if a.resolved]) / len(self.alert_history) if self.alert_history else 0
        }