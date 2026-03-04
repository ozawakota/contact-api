"""
Task 8.1 テストモック・スタブユーティリティ

TDD-RED フェーズ: モック・スタブ作成ユーティリティ
- Gemini API、SendGrid、PostgreSQL のモック
- テストデータファクトリー
- アサーションヘルパー
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
import json
import numpy as np

from sqlmodel import Session, SQLModel
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from backend.app.models.contact import Contact
from backend.app.models.contact_ai_analysis import ContactAIAnalysis
from backend.app.models.contact_vector import ContactVector
from backend.app.models.enums import CategoryType, UrgencyLevel, SentimentType


class MockGeminiAPI:
    """Gemini API モッククラス"""
    
    def __init__(self):
        self.api_key = "mock_gemini_api_key"
        self.call_count = 0
        self.responses = []
        self.errors = []
        
    def configure_response(self, response: Dict[str, Any]):
        """レスポンスを設定"""
        self.responses.append(response)
        
    def configure_error(self, error: Exception):
        """エラーレスポンスを設定"""
        self.errors.append(error)
        
    def configure_sequence(self, responses: List[Union[Dict[str, Any], Exception]]):
        """レスポンスシーケンスを設定"""
        for item in responses:
            if isinstance(item, Exception):
                self.errors.append(item)
            else:
                self.responses.append(item)
                
    async def generate_content(self, prompt: str) -> Mock:
        """コンテンツ生成モック"""
        self.call_count += 1
        
        # エラーがある場合は最初のエラーを発生
        if self.errors:
            error = self.errors.pop(0)
            raise error
            
        # レスポンスがある場合は最初のレスポンスを返す
        if self.responses:
            response = self.responses.pop(0)
            mock_response = Mock()
            mock_response.text = json.dumps(response)
            return mock_response
            
        # デフォルトレスポンス
        default_response = {
            "category": "GENERAL",
            "urgency": "MEDIUM", 
            "sentiment": "NEUTRAL",
            "confidence_score": 0.8,
            "summary": "モックされた分析結果"
        }
        
        mock_response = Mock()
        mock_response.text = json.dumps(default_response)
        return mock_response
        
    async def generate_embedding(self, text: str) -> List[float]:
        """埋め込み生成モック"""
        self.call_count += 1
        
        if self.errors:
            error = self.errors.pop(0)
            raise error
            
        # テキストに基づいて決定論的な埋め込みを生成
        np.random.seed(hash(text) % 2**32)
        return np.random.rand(768).tolist()
        
    def reset(self):
        """状態をリセット"""
        self.call_count = 0
        self.responses = []
        self.errors = []


class MockSendGridAPI:
    """SendGrid API モッククラス"""
    
    def __init__(self):
        self.api_key = "mock_sendgrid_api_key"
        self.sent_emails = []
        self.should_fail = False
        self.failure_reason = "Mock failure"
        
    def configure_failure(self, should_fail: bool = True, reason: str = "Mock failure"):
        """失敗を設定"""
        self.should_fail = should_fail
        self.failure_reason = reason
        
    async def send_email(
        self,
        to_email: str,
        subject: str, 
        html_content: str,
        from_email: str = "noreply@example.com"
    ) -> bool:
        """メール送信モック"""
        if self.should_fail:
            raise Exception(self.failure_reason)
            
        email_data = {
            "to": to_email,
            "subject": subject,
            "html_content": html_content,
            "from": from_email,
            "sent_at": datetime.now().isoformat()
        }
        
        self.sent_emails.append(email_data)
        return True
        
    async def send_template_email(
        self,
        to_email: str,
        template_id: str,
        dynamic_data: Dict[str, Any]
    ) -> bool:
        """テンプレートメール送信モック"""
        if self.should_fail:
            raise Exception(self.failure_reason)
            
        email_data = {
            "to": to_email,
            "template_id": template_id,
            "dynamic_data": dynamic_data,
            "sent_at": datetime.now().isoformat()
        }
        
        self.sent_emails.append(email_data)
        return True
        
    def get_sent_emails(self) -> List[Dict[str, Any]]:
        """送信されたメールを取得"""
        return self.sent_emails.copy()
        
    def reset(self):
        """状態をリセット"""
        self.sent_emails = []
        self.should_fail = False


class MockDatabase:
    """データベースモック"""
    
    def __init__(self):
        # インメモリSQLiteデータベースを使用
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False
        )
        self.contacts = {}
        self.ai_analyses = {}
        self.vectors = {}
        self.session_mock = Mock(spec=Session)
        self._setup_session_mock()
        
    def _setup_session_mock(self):
        """セッションモックを設定"""
        self.session_mock.add.side_effect = self._add_to_store
        self.session_mock.commit.side_effect = self._commit_changes
        self.session_mock.rollback.side_effect = self._rollback_changes
        self.session_mock.get.side_effect = self._get_by_id
        self.session_mock.query.return_value.filter.return_value.first.side_effect = self._query_first
        self.session_mock.query.return_value.filter.return_value.all.side_effect = self._query_all
        
    def _add_to_store(self, obj):
        """オブジェクトをストアに追加"""
        if isinstance(obj, Contact):
            self.contacts[obj.id] = obj
        elif isinstance(obj, ContactAIAnalysis):
            self.ai_analyses[obj.contact_id] = obj
        elif isinstance(obj, ContactVector):
            self.vectors[obj.contact_id] = obj
            
    def _commit_changes(self):
        """変更をコミット（何もしない）"""
        pass
        
    def _rollback_changes(self):
        """変更をロールバック（何もしない）"""
        pass
        
    def _get_by_id(self, model_class, obj_id):
        """IDでオブジェクトを取得"""
        if model_class == Contact:
            return self.contacts.get(obj_id)
        elif model_class == ContactAIAnalysis:
            return self.ai_analyses.get(obj_id)
        elif model_class == ContactVector:
            return self.vectors.get(obj_id)
        return None
        
    def _query_first(self):
        """クエリの最初の結果を取得"""
        # 簡易実装：最初のアイテムを返す
        if self.contacts:
            return list(self.contacts.values())[0]
        return None
        
    def _query_all(self):
        """クエリの全結果を取得"""
        return list(self.contacts.values())
        
    def add_contact(self, contact: Contact):
        """テスト用のContactを追加"""
        self.contacts[contact.id] = contact
        
    def add_analysis(self, analysis: ContactAIAnalysis):
        """テスト用のAI分析を追加"""
        self.ai_analyses[analysis.contact_id] = analysis
        
    def add_vector(self, vector: ContactVector):
        """テスト用のベクトルを追加"""
        self.vectors[vector.contact_id] = vector
        
    def get_session(self) -> Mock:
        """モックセッションを取得"""
        return self.session_mock
        
    def reset(self):
        """データをリセット"""
        self.contacts = {}
        self.ai_analyses = {}
        self.vectors = {}


class TestDataFactory:
    """テストデータファクトリー"""
    
    @staticmethod
    def create_contact(
        contact_id: str = None,
        name: str = "テスト太郎",
        email: str = "test@example.com",
        subject: str = "テスト件名",
        message: str = "テストメッセージ",
        **kwargs
    ) -> Contact:
        """テスト用のContactを作成"""
        if contact_id is None:
            contact_id = f"contact_{int(datetime.now().timestamp())}"
            
        return Contact(
            id=contact_id,
            name=name,
            email=email,
            subject=subject,
            message=message,
            created_at=kwargs.get("created_at", datetime.now()),
            status=kwargs.get("status", "received"),
            **kwargs
        )
        
    @staticmethod
    def create_urgent_contact(
        contact_id: str = None,
        name: str = "緊急太郎",
        email: str = "urgent@example.com"
    ) -> Contact:
        """緊急度の高いテスト用Contactを作成"""
        return TestDataFactory.create_contact(
            contact_id=contact_id,
            name=name,
            email=email,
            subject="緊急：システム障害",
            message="システムが使用できません。至急対応をお願いします！"
        )
        
    @staticmethod
    def create_ai_analysis(
        contact_id: str,
        category: CategoryType = CategoryType.GENERAL,
        urgency: UrgencyLevel = UrgencyLevel.MEDIUM,
        sentiment: SentimentType = SentimentType.NEUTRAL,
        confidence_score: float = 0.8,
        **kwargs
    ) -> ContactAIAnalysis:
        """テスト用のAI分析を作成"""
        return ContactAIAnalysis(
            contact_id=contact_id,
            category=category,
            urgency=urgency,
            sentiment=sentiment,
            confidence_score=confidence_score,
            summary=kwargs.get("summary", "テスト分析結果"),
            created_at=kwargs.get("created_at", datetime.now()),
            **kwargs
        )
        
    @staticmethod
    def create_vector(
        contact_id: str,
        embedding: List[float] = None,
        **kwargs
    ) -> ContactVector:
        """テスト用のベクトルを作成"""
        if embedding is None:
            embedding = np.random.rand(768).tolist()
            
        return ContactVector(
            contact_id=contact_id,
            embedding=embedding,
            model_version=kwargs.get("model_version", "test-model-v1"),
            metadata=kwargs.get("metadata", {"test": True}),
            vectorized_at=kwargs.get("vectorized_at", datetime.now())
        )
        
    @staticmethod
    def create_bulk_contacts(count: int = 10) -> List[Contact]:
        """複数のテスト用Contactを作成"""
        contacts = []
        for i in range(count):
            contact = TestDataFactory.create_contact(
                contact_id=f"bulk_contact_{i}",
                name=f"テスト太郎{i}",
                email=f"test{i}@example.com",
                subject=f"テスト件名{i}",
                message=f"テストメッセージ{i}"
            )
            contacts.append(contact)
        return contacts


class AssertionHelpers:
    """テスト用アサーションヘルパー"""
    
    @staticmethod
    def assert_contact_equals(actual: Contact, expected: Contact, ignore_fields: List[str] = None):
        """Contactが期待値と等しいかチェック"""
        if ignore_fields is None:
            ignore_fields = ['created_at', 'updated_at']
            
        for field in ['id', 'name', 'email', 'subject', 'message', 'status']:
            if field not in ignore_fields:
                assert getattr(actual, field) == getattr(expected, field), f"Field {field} mismatch"
                
    @staticmethod
    def assert_analysis_valid(analysis: Dict[str, Any]):
        """AI分析結果が有効かチェック"""
        required_fields = ['category', 'urgency', 'sentiment', 'confidence_score', 'summary']
        for field in required_fields:
            assert field in analysis, f"Required field {field} is missing"
            
        assert isinstance(analysis['category'], (CategoryType, str))
        assert isinstance(analysis['urgency'], (UrgencyLevel, str))
        assert isinstance(analysis['sentiment'], (SentimentType, str))
        assert 0.0 <= analysis['confidence_score'] <= 1.0
        assert len(analysis['summary']) > 0
        
    @staticmethod
    def assert_vector_valid(vector: List[float], expected_dimension: int = 768):
        """ベクトルが有効かチェック"""
        assert isinstance(vector, list)
        assert len(vector) == expected_dimension
        assert all(isinstance(x, (int, float)) for x in vector)
        assert not all(x == 0 for x in vector)  # ゼロベクトルでないことを確認
        
    @staticmethod
    def assert_processing_time_acceptable(processing_time: float, max_time: float = 120.0):
        """処理時間が許容範囲内かチェック"""
        assert processing_time > 0, "Processing time must be positive"
        assert processing_time <= max_time, f"Processing time {processing_time}s exceeds limit {max_time}s"
        
    @staticmethod
    def assert_error_response_valid(error_response: Dict[str, Any]):
        """エラーレスポンスが有効かチェック"""
        required_fields = ['status', 'error']
        for field in required_fields:
            assert field in error_response, f"Error response missing field {field}"
            
        assert error_response['status'] in ['failed', 'timeout', 'error']
        assert 'type' in error_response['error']
        assert 'message' in error_response['error']


# テスト用フィクスチャ定義
@pytest.fixture
def mock_gemini_api():
    """Gemini APIモック フィクスチャ"""
    mock_api = MockGeminiAPI()
    return mock_api


@pytest.fixture
def mock_sendgrid_api():
    """SendGrid APIモック フィクスチャ"""
    mock_api = MockSendGridAPI()
    return mock_api


@pytest.fixture
def mock_database():
    """データベースモック フィクスチャ"""
    mock_db = MockDatabase()
    return mock_db


@pytest.fixture
def test_contact():
    """テスト用Contact フィクスチャ"""
    return TestDataFactory.create_contact()


@pytest.fixture
def test_urgent_contact():
    """緊急度の高いテスト用Contact フィクスチャ"""
    return TestDataFactory.create_urgent_contact()


@pytest.fixture
def test_ai_analysis():
    """テスト用AI分析 フィクスチャ"""
    return TestDataFactory.create_ai_analysis("test_contact_id")


@pytest.fixture
def test_vector():
    """テスト用ベクトル フィクスチャ"""
    return TestDataFactory.create_vector("test_contact_id")


# テストスイート実行用のヘルパー関数
def run_test_with_timeout(test_func, timeout: float = 30.0):
    """タイムアウト付きでテストを実行"""
    async def wrapper():
        return await asyncio.wait_for(test_func(), timeout=timeout)
    
    return asyncio.run(wrapper())


# カバレッジレポート生成用のユーティリティ
class CoverageReporter:
    """テストカバレッジレポーター"""
    
    @staticmethod
    def generate_coverage_report(test_results: Dict[str, Any]) -> Dict[str, Any]:
        """カバレッジレポートを生成"""
        return {
            "timestamp": datetime.now().isoformat(),
            "total_tests": test_results.get("total", 0),
            "passed_tests": test_results.get("passed", 0),
            "failed_tests": test_results.get("failed", 0),
            "skipped_tests": test_results.get("skipped", 0),
            "coverage_percentage": test_results.get("coverage", 0.0),
            "quality_gate_passed": test_results.get("coverage", 0.0) >= 80.0
        }


if __name__ == "__main__":
    # テストユーティリティの動作確認
    print("Testing mock utilities...")
    
    # MockGeminiAPIのテスト
    gemini_mock = MockGeminiAPI()
    gemini_mock.configure_response({"category": "TEST", "urgency": "HIGH"})
    
    # TestDataFactoryのテスト
    test_contact = TestDataFactory.create_contact()
    print(f"Created test contact: {test_contact.name}")
    
    # AssertionHelpersのテスト
    analysis = {
        "category": CategoryType.GENERAL,
        "urgency": UrgencyLevel.MEDIUM,
        "sentiment": SentimentType.NEUTRAL,
        "confidence_score": 0.8,
        "summary": "テスト分析"
    }
    
    AssertionHelpers.assert_analysis_valid(analysis)
    print("All mock utilities working correctly!")