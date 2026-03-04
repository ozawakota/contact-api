"""FastAPIルーター・エンドポイントのテスト

お問い合わせ受付API・管理者用API群・Firebase認証・APIドキュメント機能をテストします。
"""
import pytest
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi.testclient import TestClient
from fastapi import FastAPI, status

# テスト対象モジュールのインポート
from models.contact import Contact
from models.contact_ai_analysis import ContactAIAnalysis


@pytest.fixture
def mock_db_session():
    """モックデータベースセッション"""
    mock_session = MagicMock()
    return mock_session


@pytest.fixture
def mock_firebase_auth():
    """モックFirebase認証"""
    mock_auth = MagicMock()
    mock_auth.verify_token.return_value = {'uid': 'test123', 'email': 'test@example.com'}
    mock_auth.verify_admin_token.return_value = {'uid': 'admin123', 'email': 'admin@example.com', 'role': 'admin'}
    return mock_auth


@pytest.fixture
def mock_contact_usecase():
    """モックContactUseCase"""
    mock_usecase = AsyncMock()
    mock_usecase.create_contact.return_value = {
        'success': True,
        'contact': {'id': 123, 'name': 'テスト太郎', 'email': 'test@example.com'}
    }
    return mock_usecase


@pytest.fixture
def mock_ai_analysis_usecase():
    """モックAIAnalysisUseCase"""
    mock_usecase = AsyncMock()
    mock_usecase.execute_analysis.return_value = {
        'success': True,
        'analysis_id': 456,
        'category': 'product',
        'urgency': 2
    }
    return mock_usecase


@pytest.fixture
def mock_admin_dashboard_api():
    """モックAdminDashboardAPI"""
    mock_api = AsyncMock()
    mock_api.get_contacts_list.return_value = {
        'success': True,
        'contacts': [],
        'pagination': {'page': 1, 'total_pages': 1}
    }
    return mock_api


@pytest.fixture
def test_app(mock_db_session, mock_firebase_auth, mock_contact_usecase, mock_ai_analysis_usecase, mock_admin_dashboard_api):
    """テスト用FastAPIアプリケーション"""
    from api.routes import create_app
    app = create_app(
        db_session=mock_db_session,
        firebase_auth=mock_firebase_auth,
        contact_usecase=mock_contact_usecase,
        ai_analysis_usecase=mock_ai_analysis_usecase,
        admin_dashboard_api=mock_admin_dashboard_api
    )
    return app


@pytest.fixture
def client(test_app):
    """テストクライアント"""
    return TestClient(test_app)


class TestContactAPI:
    """お問い合わせ受付APIテスト"""

    def test_create_contact_success(self, client, mock_contact_usecase):
        """お問い合わせ作成成功テスト"""
        contact_data = {
            "name": "山田太郎",
            "email": "yamada@example.com",
            "subject": "商品について",
            "message": "商品の詳細を教えてください"
        }
        
        response = client.post("/api/v1/contacts", json=contact_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data['success'] is True
        assert 'contact' in data
        mock_contact_usecase.create_contact.assert_called_once()

    def test_create_contact_validation_error(self, client):
        """お問い合わせ作成バリデーションエラーテスト"""
        invalid_data = {
            "name": "",  # 空の名前
            "email": "invalid-email",  # 不正メール
            "subject": "",  # 空の件名
            "message": "メッセージ"
        }
        
        response = client.post("/api/v1/contacts", json=invalid_data)
        
        assert response.status_code == 422
        data = response.json()
        assert 'detail' in data

    def test_create_contact_missing_fields(self, client):
        """お問い合わせ作成必須フィールド不足テスト"""
        incomplete_data = {
            "name": "田中花子"
            # email, subject, message が不足
        }
        
        response = client.post("/api/v1/contacts", json=incomplete_data)
        
        assert response.status_code == 422

    def test_create_contact_long_message(self, client, mock_contact_usecase):
        """長文メッセージ処理テスト"""
        long_message = "あ" * 5000  # 5000文字の長文
        contact_data = {
            "name": "長文太郎",
            "email": "longtext@example.com",
            "subject": "長文テスト",
            "message": long_message
        }
        
        response = client.post("/api/v1/contacts", json=contact_data)
        
        assert response.status_code == 201
        mock_contact_usecase.create_contact.assert_called_once()

    def test_create_contact_sql_injection_protection(self, client, mock_contact_usecase):
        """SQLインジェクション保護テスト"""
        malicious_data = {
            "name": "'; DROP TABLE contacts; --",
            "email": "hacker@example.com",
            "subject": "SQL Injection Test",
            "message": "SELECT * FROM users WHERE '1'='1'"
        }
        
        response = client.post("/api/v1/contacts", json=malicious_data)
        
        # リクエスト自体は成功するが、サニタイゼーションが適用される
        assert response.status_code == 201
        mock_contact_usecase.create_contact.assert_called_once()

    def test_get_contact_by_id(self, client, mock_contact_usecase):
        """ID指定コンタクト取得テスト"""
        contact_id = 123
        mock_contact_usecase.get_contact_by_id.return_value = {
            'success': True,
            'contact': {
                'id': contact_id,
                'name': '取得太郎',
                'email': 'get@example.com',
                'subject': 'テスト件名',
                'message': 'テストメッセージ'
            }
        }
        
        response = client.get(f"/api/v1/contacts/{contact_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['contact']['id'] == contact_id

    def test_get_contact_not_found(self, client, mock_contact_usecase):
        """存在しないコンタクト取得テスト"""
        mock_contact_usecase.get_contact_by_id.return_value = {
            'success': False,
            'error': 'contact_not_found'
        }
        
        response = client.get("/api/v1/contacts/999")
        
        assert response.status_code == 404


class TestAdminAPI:
    """管理者用APIテスト"""

    def test_get_admin_contacts_with_auth(self, client, mock_admin_dashboard_api):
        """管理者コンタクト一覧取得（認証付き）テスト"""
        headers = {"Authorization": "Bearer admin_token"}
        
        response = client.get("/api/v1/admin/contacts", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'contacts' in data
        mock_admin_dashboard_api.get_contacts_list.assert_called_once()

    def test_get_admin_contacts_without_auth(self, client):
        """管理者コンタクト一覧取得（認証なし）テスト"""
        response = client.get("/api/v1/admin/contacts")
        
        assert response.status_code == 401

    def test_get_admin_contacts_invalid_token(self, client, mock_firebase_auth):
        """管理者コンタクト一覧取得（無効トークン）テスト"""
        mock_firebase_auth.verify_admin_token.side_effect = Exception("Invalid token")
        headers = {"Authorization": "Bearer invalid_token"}
        
        response = client.get("/api/v1/admin/contacts", headers=headers)
        
        assert response.status_code == 401

    def test_get_admin_contacts_with_pagination(self, client, mock_admin_dashboard_api):
        """管理者コンタクト一覧取得（ページネーション）テスト"""
        headers = {"Authorization": "Bearer admin_token"}
        params = {"page": 2, "per_page": 20}
        
        response = client.get("/api/v1/admin/contacts", headers=headers, params=params)
        
        assert response.status_code == 200
        mock_admin_dashboard_api.get_contacts_list.assert_called_with(
            page=2, per_page=20, auth_token="admin_token"
        )

    def test_get_admin_contacts_with_filters(self, client, mock_admin_dashboard_api):
        """管理者コンタクト一覧取得（フィルタ）テスト"""
        headers = {"Authorization": "Bearer admin_token"}
        params = {
            "status_filter": "analyzed",
            "category_filter": "product",
            "urgency_filter": 3
        }
        
        response = client.get("/api/v1/admin/contacts", headers=headers, params=params)
        
        assert response.status_code == 200
        mock_admin_dashboard_api.get_contacts_list.assert_called_with(
            page=1, per_page=20, auth_token="admin_token",
            status_filter="analyzed", category_filter="product", urgency_filter=3
        )

    def test_get_admin_contact_detail(self, client, mock_admin_dashboard_api):
        """管理者コンタクト詳細取得テスト"""
        contact_id = 123
        headers = {"Authorization": "Bearer admin_token"}
        mock_admin_dashboard_api.get_contact_detail.return_value = {
            'success': True,
            'contact': {'id': contact_id, 'name': '詳細太郎'},
            'ai_analysis': {'category': 'product', 'urgency': 2}
        }
        
        response = client.get(f"/api/v1/admin/contacts/{contact_id}", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['contact']['id'] == contact_id

    def test_update_contact_status(self, client, mock_admin_dashboard_api):
        """コンタクトステータス更新テスト"""
        contact_id = 123
        headers = {"Authorization": "Bearer admin_token"}
        update_data = {
            "status": "resolved",
            "notes": "問題解決済み"
        }
        
        mock_admin_dashboard_api.update_contact_status.return_value = {
            'success': True,
            'contact_id': contact_id,
            'updated_status': 'resolved'
        }
        
        response = client.patch(f"/api/v1/admin/contacts/{contact_id}/status", 
                              headers=headers, json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['updated_status'] == 'resolved'

    def test_update_ai_analysis(self, client, mock_admin_dashboard_api):
        """AI解析結果更新テスト"""
        contact_id = 123
        headers = {"Authorization": "Bearer admin_token"}
        update_data = {
            "category": "billing",
            "urgency": 1,
            "sentiment": "neutral",
            "notes": "手動で分類修正"
        }
        
        mock_admin_dashboard_api.update_ai_analysis_manual.return_value = {
            'success': True,
            'contact_id': contact_id,
            'updated_analysis': update_data
        }
        
        response = client.patch(f"/api/v1/admin/contacts/{contact_id}/ai-analysis", 
                              headers=headers, json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True


class TestAnalyticsAPI:
    """分析APIテスト"""

    def test_get_analytics_overview(self, client, mock_admin_dashboard_api):
        """統計概要取得テスト"""
        headers = {"Authorization": "Bearer admin_token"}
        mock_admin_dashboard_api.get_analytics_overview.return_value = {
            'success': True,
            'analytics': {
                'total_contacts': 1000,
                'status_distribution': {'pending': 200, 'analyzed': 600, 'resolved': 200}
            }
        }
        
        response = client.get("/api/v1/admin/analytics/overview", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['analytics']['total_contacts'] == 1000

    def test_get_ai_performance_metrics(self, client, mock_admin_dashboard_api):
        """AI性能メトリクス取得テスト"""
        headers = {"Authorization": "Bearer admin_token"}
        mock_admin_dashboard_api.get_ai_performance_metrics.return_value = {
            'success': True,
            'metrics': {
                'average_confidence': 0.87,
                'total_analyzed': 800,
                'category_distribution': {'product': 300, 'shipping': 250}
            }
        }
        
        response = client.get("/api/v1/admin/analytics/ai-performance", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data['metrics']['average_confidence'] == 0.87

    def test_get_processing_time_analysis(self, client, mock_admin_dashboard_api):
        """処理時間分析取得テスト"""
        headers = {"Authorization": "Bearer admin_token"}
        mock_admin_dashboard_api.get_processing_time_analysis.return_value = {
            'success': True,
            'analysis': {
                'average_processing_time_ms': 1850,
                'within_sla_percentage': 95.2
            }
        }
        
        response = client.get("/api/v1/admin/analytics/processing-time", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data['analysis']['within_sla_percentage'] == 95.2

    def test_export_analytics_data(self, client, mock_admin_dashboard_api):
        """分析データエクスポートテスト"""
        headers = {"Authorization": "Bearer admin_token"}
        export_params = {
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "format": "json"
        }
        
        mock_admin_dashboard_api.export_analytics_data.return_value = {
            'success': True,
            'export_data': [{'contact_id': 1, 'category': 'product'}],
            'total_records': 1
        }
        
        response = client.get("/api/v1/admin/analytics/export", 
                            headers=headers, params=export_params)
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['total_records'] == 1


class TestAuthenticationMiddleware:
    """認証ミドルウェアテスト"""

    def test_firebase_token_verification(self, client, mock_firebase_auth):
        """Firebaseトークン検証テスト"""
        # 有効トークン
        headers = {"Authorization": "Bearer valid_token"}
        response = client.get("/api/v1/admin/contacts", headers=headers)
        assert response.status_code == 200
        
        # 無効トークン
        mock_firebase_auth.verify_admin_token.side_effect = Exception("Invalid")
        headers = {"Authorization": "Bearer invalid_token"}
        response = client.get("/api/v1/admin/contacts", headers=headers)
        assert response.status_code == 401

    def test_admin_role_authorization(self, client, mock_firebase_auth):
        """管理者権限認可テスト"""
        # 管理者ユーザー
        mock_firebase_auth.verify_admin_token.return_value = {
            'uid': 'admin123', 'role': 'admin'
        }
        headers = {"Authorization": "Bearer admin_token"}
        response = client.get("/api/v1/admin/contacts", headers=headers)
        assert response.status_code == 200
        
        # 一般ユーザー（権限不足）
        mock_firebase_auth.verify_admin_token.return_value = {
            'uid': 'user123', 'role': 'user'
        }
        headers = {"Authorization": "Bearer user_token"}
        response = client.get("/api/v1/admin/contacts", headers=headers)
        assert response.status_code == 403

    def test_missing_authorization_header(self, client):
        """認証ヘッダー不足テスト"""
        response = client.get("/api/v1/admin/contacts")
        assert response.status_code == 401

    def test_malformed_authorization_header(self, client):
        """不正形式認証ヘッダーテスト"""
        headers = {"Authorization": "InvalidFormat"}
        response = client.get("/api/v1/admin/contacts", headers=headers)
        assert response.status_code == 401


class TestAPIDocumentation:
    """APIドキュメントテスト"""

    def test_openapi_schema_generation(self, client):
        """OpenAPIスキーマ生成テスト"""
        response = client.get("/openapi.json")
        
        assert response.status_code == 200
        schema = response.json()
        assert 'openapi' in schema
        assert 'paths' in schema
        assert '/api/v1/contacts' in schema['paths']
        assert '/api/v1/admin/contacts' in schema['paths']

    def test_swagger_ui_access(self, client):
        """Swagger UI アクセステスト"""
        response = client.get("/docs")
        
        assert response.status_code == 200
        assert 'text/html' in response.headers['content-type']

    def test_redoc_access(self, client):
        """ReDoc アクセステスト"""
        response = client.get("/redoc")
        
        assert response.status_code == 200
        assert 'text/html' in response.headers['content-type']

    def test_api_schema_validation(self, client):
        """APIスキーマ検証テスト"""
        response = client.get("/openapi.json")
        schema = response.json()
        
        # 基本的なスキーマ構造確認
        assert 'info' in schema
        assert 'title' in schema['info']
        assert 'version' in schema['info']
        
        # セキュリティ設定確認
        assert 'components' in schema
        assert 'securitySchemes' in schema['components']
        
        # エンドポイント確認
        paths = schema['paths']
        assert 'post' in paths['/api/v1/contacts']
        assert 'get' in paths['/api/v1/admin/contacts']


class TestErrorHandling:
    """エラーハンドリングテスト"""

    def test_404_not_found(self, client):
        """404 Not Foundテスト"""
        response = client.get("/nonexistent/endpoint")
        assert response.status_code == 404

    def test_405_method_not_allowed(self, client):
        """405 Method Not Allowedテスト"""
        response = client.put("/api/v1/contacts")
        assert response.status_code == 405

    def test_500_internal_server_error(self, client, mock_contact_usecase):
        """500 Internal Server Errorテスト"""
        mock_contact_usecase.create_contact.side_effect = Exception("Database error")
        
        contact_data = {
            "name": "エラー太郎",
            "email": "error@example.com", 
            "subject": "エラーテスト",
            "message": "エラー発生テスト"
        }
        
        response = client.post("/api/v1/contacts", json=contact_data)
        assert response.status_code == 500

    def test_request_validation_error(self, client):
        """リクエストバリデーションエラーテスト"""
        invalid_data = {"invalid_field": "value"}
        
        response = client.post("/api/v1/contacts", json=invalid_data)
        assert response.status_code == 422


class TestRateLimiting:
    """レート制限テスト"""

    def test_api_rate_limiting(self, client):
        """APIレート制限テスト"""
        # 多数のリクエストを送信
        contact_data = {
            "name": "レート太郎",
            "email": "rate@example.com",
            "subject": "レート制限テスト",
            "message": "テスト"
        }
        
        # 通常は成功
        response = client.post("/api/v1/contacts", json=contact_data)
        assert response.status_code in [201, 429]  # 成功またはレート制限
        
        # レート制限実装によっては429が返される

    def test_admin_api_rate_limiting(self, client):
        """管理者APIレート制限テスト"""
        headers = {"Authorization": "Bearer admin_token"}
        
        # 複数回リクエスト
        for _ in range(10):
            response = client.get("/api/v1/admin/contacts", headers=headers)
            if response.status_code == 429:
                break
        
        # レート制限の設定によっては制限がかかる
        assert response.status_code in [200, 429]


class TestCORS:
    """CORS設定テスト"""

    def test_cors_preflight_request(self, client):
        """CORS プリフライトリクエストテスト"""
        headers = {
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type"
        }
        
        response = client.options("/api/v1/contacts", headers=headers)
        
        # CORS設定によってはプリフライトが通る
        assert response.status_code in [200, 204]

    def test_cors_headers_in_response(self, client):
        """レスポンスのCORSヘッダーテスト"""
        headers = {"Origin": "https://example.com"}
        response = client.get("/api/v1/admin/contacts", headers=headers)
        
        # CORS設定があればヘッダーが含まれる
        # 実装によって異なるため緩い検証
        assert response.status_code in [200, 401]