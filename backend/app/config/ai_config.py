"""AI関連サービス設定

Gemini API、セキュリティバリデーション、その他AI機能の設定管理。
環境変数ベースの設定と本番・開発・テスト環境別の設定を提供。
"""

import os
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum


class Environment(Enum):
    """実行環境"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


@dataclass
class GeminiConfig:
    """Gemini API設定"""
    api_key: str
    model_name: str = "gemini-2.0-flash"
    max_retries: int = 3
    base_delay: float = 1.0
    timeout: float = 30.0
    temperature: float = 0.1
    max_output_tokens: int = 1000
    enable_function_calling: bool = True
    enable_self_refinement: bool = True
    self_refinement_timeout: int = 20


@dataclass
class SecurityConfig:
    """セキュリティバリデーション設定"""
    max_content_length: int = 10000
    max_field_length: int = 1000
    enable_prompt_injection_detection: bool = True
    enable_script_detection: bool = True
    enable_xml_sanitization: bool = True
    enable_security_logging: bool = True
    threat_level_threshold: int = 2  # この値以上で警告


@dataclass
class AIServiceConfig:
    """AI関連サービス統合設定"""
    gemini: GeminiConfig
    security: SecurityConfig
    environment: Environment
    debug: bool = False
    
    
class AIConfigManager:
    """AI設定管理クラス"""
    
    def __init__(self, environment: Environment = None):
        """設定管理初期化
        
        Args:
            environment: 実行環境。未指定時は環境変数から判定
        """
        self.environment = environment or self._detect_environment()
        self._load_config()
    
    def _detect_environment(self) -> Environment:
        """環境変数から実行環境を判定"""
        env_name = os.getenv("ENVIRONMENT", "development").lower()
        
        env_mapping = {
            "dev": Environment.DEVELOPMENT,
            "development": Environment.DEVELOPMENT,
            "test": Environment.TESTING,
            "testing": Environment.TESTING,
            "prod": Environment.PRODUCTION,
            "production": Environment.PRODUCTION
        }
        
        return env_mapping.get(env_name, Environment.DEVELOPMENT)
    
    def _load_config(self):
        """設定の読み込み"""
        # Gemini設定
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            if self.environment == Environment.PRODUCTION:
                raise ValueError("GEMINI_API_KEY environment variable is required in production")
            else:
                gemini_api_key = "dummy_key_for_testing"
        
        self.gemini_config = GeminiConfig(
            api_key=gemini_api_key,
            model_name=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
            max_retries=int(os.getenv("GEMINI_MAX_RETRIES", "3")),
            base_delay=float(os.getenv("GEMINI_BASE_DELAY", "1.0")),
            timeout=float(os.getenv("GEMINI_TIMEOUT", "30.0")),
            temperature=float(os.getenv("GEMINI_TEMPERATURE", "0.1")),
            max_output_tokens=int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "1000")),
            enable_function_calling=os.getenv("GEMINI_ENABLE_FUNCTION_CALLING", "true").lower() == "true",
            enable_self_refinement=os.getenv("GEMINI_ENABLE_SELF_REFINEMENT", "true").lower() == "true",
            self_refinement_timeout=int(os.getenv("GEMINI_SELF_REFINEMENT_TIMEOUT", "20"))
        )
        
        # セキュリティ設定
        self.security_config = SecurityConfig(
            max_content_length=int(os.getenv("SECURITY_MAX_CONTENT_LENGTH", "10000")),
            max_field_length=int(os.getenv("SECURITY_MAX_FIELD_LENGTH", "1000")),
            enable_prompt_injection_detection=os.getenv("SECURITY_ENABLE_PROMPT_INJECTION", "true").lower() == "true",
            enable_script_detection=os.getenv("SECURITY_ENABLE_SCRIPT_DETECTION", "true").lower() == "true",
            enable_xml_sanitization=os.getenv("SECURITY_ENABLE_XML_SANITIZATION", "true").lower() == "true",
            enable_security_logging=os.getenv("SECURITY_ENABLE_LOGGING", "true").lower() == "true",
            threat_level_threshold=int(os.getenv("SECURITY_THREAT_LEVEL_THRESHOLD", "2"))
        )
        
        # 環境別設定調整
        if self.environment == Environment.TESTING:
            self._apply_testing_overrides()
        elif self.environment == Environment.DEVELOPMENT:
            self._apply_development_overrides()
        elif self.environment == Environment.PRODUCTION:
            self._apply_production_overrides()
    
    def _apply_testing_overrides(self):
        """テスト環境用設定オーバーライド"""
        self.gemini_config.timeout = 5.0  # 短縮
        self.gemini_config.max_retries = 1  # リトライ減
        self.gemini_config.enable_self_refinement = False  # 高速化
        self.security_config.enable_security_logging = False  # ログ抑制
    
    def _apply_development_overrides(self):
        """開発環境用設定オーバーライド"""
        self.gemini_config.temperature = 0.2  # 多少のランダム性
        self.security_config.threat_level_threshold = 1  # 敏感に検知
    
    def _apply_production_overrides(self):
        """本番環境用設定オーバーライド"""
        self.gemini_config.max_retries = 5  # 堅牢性重視
        self.gemini_config.timeout = 60.0  # 余裕のあるタイムアウト
        self.security_config.threat_level_threshold = 3  # 厳格な検知
    
    def get_config(self) -> AIServiceConfig:
        """統合設定を取得"""
        return AIServiceConfig(
            gemini=self.gemini_config,
            security=self.security_config,
            environment=self.environment,
            debug=self.environment != Environment.PRODUCTION
        )
    
    def validate_config(self) -> Dict[str, Any]:
        """設定の妥当性チェック
        
        Returns:
            検証結果辞書
        """
        validation_results = {
            "valid": True,
            "warnings": [],
            "errors": []
        }
        
        # Gemini設定チェック
        if not self.gemini_config.api_key or self.gemini_config.api_key == "dummy_key_for_testing":
            if self.environment == Environment.PRODUCTION:
                validation_results["errors"].append("Production環境でGEMINI_API_KEYが無効です")
                validation_results["valid"] = False
            else:
                validation_results["warnings"].append("テスト用APIキーが使用されています")
        
        if self.gemini_config.timeout < 5.0:
            validation_results["warnings"].append("Geminiタイムアウトが短すぎる可能性があります")
        
        # セキュリティ設定チェック
        if self.security_config.max_content_length > 50000:
            validation_results["warnings"].append("コンテンツ長制限が大きすぎる可能性があります")
        
        if not self.security_config.enable_prompt_injection_detection:
            validation_results["warnings"].append("プロンプトインジェクション検知が無効です")
        
        return validation_results


# グローバル設定インスタンス
_config_manager: Optional[AIConfigManager] = None


def get_ai_config() -> AIServiceConfig:
    """AI設定を取得（シングルトン）
    
    Returns:
        AI設定
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = AIConfigManager()
    return _config_manager.get_config()


def reload_ai_config(environment: Environment = None):
    """AI設定を再読み込み
    
    Args:
        environment: 強制する環境
    """
    global _config_manager
    _config_manager = AIConfigManager(environment)


def validate_ai_config() -> Dict[str, Any]:
    """現在のAI設定を検証
    
    Returns:
        検証結果
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = AIConfigManager()
    return _config_manager.validate_config()