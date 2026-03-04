"""
ユーザージャーニーE2Eテスト

Task 8.2: 統合テスト・E2Eテスト実装
実際のユーザー体験をシミュレートしたエンドツーエンドテスト
"""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# テスト対象インポート
from backend.app.main import create_main_app
from backend.tests.utils.test_mocks import MockGeminiAPI, MockSendGridAPI


class TestCustomerJourneyE2E:
    """カスタマージャーニーE2Eテスト"""
    
    @pytest.fixture
    def browser_driver(self):
        """ブラウザドライバーセットアップ"""
        options = Options()
        options.add_argument("--headless")  # ヘッドレスモード
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        
        driver = webdriver.Chrome(options=options)
        driver.implicitly_wait(10)
        
        yield driver
        driver.quit()
    
    @pytest.fixture
    def test_server(self):
        """テストサーバーセットアップ"""
        # Uvicornテストサーバー起動（モック）
        return "http://localhost:8080"
    
    def test_customer_inquiry_submission_journey(self, browser_driver, test_server):
        """お客様お問い合わせ投稿ジャーニー"""
        driver = browser_driver
        
        try:
            # 1. フロントページアクセス
            driver.get(f"{test_server}/contact")
            
            # ページタイトル確認
            assert "お問い合わせ" in driver.title
            
            # 2. お問い合わせフォーム入力
            name_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "name"))
            )
            name_input.send_keys("E2Eテストユーザー")
            
            email_input = driver.find_element(By.NAME, "email")
            email_input.send_keys("e2e@example.com")
            
            subject_input = driver.find_element(By.NAME, "subject") 
            subject_input.send_keys("E2Eテストお問い合わせ")
            
            message_input = driver.find_element(By.NAME, "message")
            message_input.send_keys(
                "これはE2Eテスト用のお問い合わせです。\n"
                "商品の詳細について教えてください。\n"
                "よろしくお願いします。"
            )
            
            # 3. フォーム送信
            submit_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            submit_button.click()
            
            # 4. 送信完了確認
            success_message = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "success-message"))
            )
            assert "お問い合わせを受け付けました" in success_message.text
            
            # 5. お問い合わせ番号取得
            inquiry_number = driver.find_element(By.CLASS_NAME, "inquiry-number").text
            assert inquiry_number.startswith("INQ-")
            
            # 6. ステータス確認ページ遷移
            status_link = driver.find_element(By.LINK_TEXT, "お問い合わせ状況を確認する")
            status_link.click()
            
            # 7. ステータス表示確認
            status_display = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "inquiry-status"))
            )
            assert "受付済み" in status_display.text
            
        except Exception as e:
            # エラー時スクリーンショット
            driver.save_screenshot(f"e2e_error_{int(time.time())}.png")
            raise e
    
    def test_admin_response_workflow_journey(self, browser_driver, test_server):
        """管理者回答ワークフロージャーニー"""
        driver = browser_driver
        
        try:
            # 1. 管理画面ログイン
            driver.get(f"{test_server}/admin/login")
            
            username_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "username"))
            )
            username_input.send_keys("admin@example.com")
            
            password_input = driver.find_element(By.NAME, "password")
            password_input.send_keys("test_password")
            
            login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            login_button.click()
            
            # 2. ダッシュボード表示確認
            dashboard_title = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.H1))
            )
            assert "管理ダッシュボード" in dashboard_title.text
            
            # 3. 未回答お問い合わせ一覧
            pending_contacts_link = driver.find_element(By.LINK_TEXT, "未回答お問い合わせ")
            pending_contacts_link.click()
            
            # 4. 最新お問い合わせ選択
            first_contact = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".contact-row:first-child"))
            )
            first_contact.click()
            
            # 5. お問い合わせ詳細確認
            contact_detail = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "contact-detail"))
            )
            assert "お客様情報" in contact_detail.text
            
            # 6. AI分析結果確認
            ai_analysis = driver.find_element(By.CLASS_NAME, "ai-analysis")
            assert "カテゴリ" in ai_analysis.text
            assert "緊急度" in ai_analysis.text
            assert "推奨回答" in ai_analysis.text
            
            # 7. 回答作成
            response_textarea = driver.find_element(By.NAME, "response_message")
            response_textarea.send_keys(
                "お問い合わせいただき、ありがとうございます。\n"
                "ご質問について回答いたします。\n"
                "詳細資料を添付いたしますので、ご確認ください。"
            )
            
            # 8. 内部メモ追加
            internal_notes = driver.find_element(By.NAME, "internal_notes")
            internal_notes.send_keys("E2Eテスト - 標準回答で対応")
            
            # 9. 回答送信
            send_response_button = driver.find_element(By.ID, "send-response")
            send_response_button.click()
            
            # 10. 送信完了確認
            success_notification = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "notification-success"))
            )
            assert "回答を送信しました" in success_notification.text
            
            # 11. ステータス更新確認
            contact_status = driver.find_element(By.CLASS_NAME, "contact-status")
            assert "回答済み" in contact_status.text
            
        except Exception as e:
            driver.save_screenshot(f"admin_e2e_error_{int(time.time())}.png")
            raise e


class TestAPIEndpointE2E:
    """APIエンドポイントE2Eテスト"""
    
    @pytest.fixture
    def api_client(self):
        """APIクライアント"""
        from fastapi.testclient import TestClient
        app = create_main_app()
        return TestClient(app)
    
    def test_complete_api_workflow(self, api_client):
        """完全APIワークフローテスト"""
        
        # 1. お問い合わせ作成API
        contact_data = {
            "name": "APIテストユーザー",
            "email": "api@example.com",
            "subject": "APIテスト",
            "message": "APIエンドポイント完全テストです"
        }
        
        response = api_client.post("/api/v1/contacts", json=contact_data)
        assert response.status_code == 201
        
        contact_result = response.json()
        contact_id = contact_result["id"]
        assert contact_result["status"] == "pending"
        
        # 2. お問い合わせ詳細取得API
        response = api_client.get(f"/api/v1/contacts/{contact_id}")
        assert response.status_code == 200
        
        contact_detail = response.json()
        assert contact_detail["id"] == contact_id
        assert contact_detail["name"] == "APIテストユーザー"
        
        # 3. AI解析実行API（モック）
        with patch('backend.app.services.gemini_service.GeminiService.analyze_contact') as mock_analyze:
            mock_analyze.return_value = {
                "category": "technical",
                "urgency": "medium",
                "confidence_score": 0.88,
                "suggested_response": "技術サポートより回答します",
                "keywords": ["API", "テスト", "技術"],
                "sentiment_score": 0.6
            }
            
            response = api_client.post(f"/api/v1/contacts/{contact_id}/analyze")
            assert response.status_code == 200
            
            analysis_result = response.json()
            assert analysis_result["category"] == "technical"
            assert analysis_result["confidence_score"] == 0.88
        
        # 4. ベクトル検索API
        response = api_client.post(
            "/api/v1/search/similar",
            json={
                "query": "APIテストについて",
                "limit": 5,
                "threshold": 0.7
            }
        )
        assert response.status_code == 200
        
        search_result = response.json()
        assert "results" in search_result
        assert "total_count" in search_result
        
        # 5. 管理者認証API
        auth_response = api_client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@example.com",
                "password": "test_password"
            }
        )
        assert auth_response.status_code == 200
        
        auth_result = auth_response.json()
        access_token = auth_result["access_token"]
        assert access_token is not None
        
        # 6. 管理者用お問い合わせ詳細API
        headers = {"Authorization": f"Bearer {access_token}"}
        response = api_client.get(f"/api/v1/admin/contacts/{contact_id}", headers=headers)
        assert response.status_code == 200
        
        admin_detail = response.json()
        assert "analysis" in admin_detail
        assert "internal_notes" in admin_detail
        
        # 7. 回答送信API
        response_data = {
            "message": "APIテストに関する回答をお送りします",
            "internal_notes": "API E2Eテスト完了",
            "status": "resolved"
        }
        
        with patch('backend.app.services.notification_service.NotificationService.send_email') as mock_email:
            mock_email.return_value = {"status": "sent", "message_id": "api_test_123"}
            
            response = api_client.post(
                f"/api/v1/admin/contacts/{contact_id}/respond",
                json=response_data,
                headers=headers
            )
            assert response.status_code == 200
        
        # 8. 最終ステータス確認API
        response = api_client.get(f"/api/v1/contacts/{contact_id}/status")
        assert response.status_code == 200
        
        status_result = response.json()
        assert status_result["status"] == "resolved"
        assert "last_updated" in status_result
    
    def test_error_handling_workflow(self, api_client):
        """エラーハンドリングワークフロー"""
        
        # 1. 無効なお問い合わせデータ
        invalid_data = {
            "name": "",  # 空の名前
            "email": "invalid-email",  # 無効なメール
            "subject": "",  # 空の件名
            "message": ""  # 空のメッセージ
        }
        
        response = api_client.post("/api/v1/contacts", json=invalid_data)
        assert response.status_code == 422  # バリデーションエラー
        
        error_result = response.json()
        assert "detail" in error_result
        
        # 2. 存在しないお問い合わせID
        response = api_client.get("/api/v1/contacts/nonexistent-id")
        assert response.status_code == 404
        
        # 3. 認証エラー
        headers = {"Authorization": "Bearer invalid-token"}
        response = api_client.get("/api/v1/admin/contacts", headers=headers)
        assert response.status_code == 401
        
        # 4. 権限エラー
        # 一般ユーザートークンで管理者API呼び出し
        user_token = "user_token_123"  # 一般ユーザートークン（モック）
        headers = {"Authorization": f"Bearer {user_token}"}
        response = api_client.get("/api/v1/admin/dashboard", headers=headers)
        assert response.status_code in [401, 403]
        
        # 5. レート制限エラー（モック）
        with patch('backend.app.api.rate_limiter.is_rate_limited', return_value=True):
            response = api_client.post("/api/v1/contacts", json={
                "name": "テストユーザー",
                "email": "test@example.com",
                "subject": "テスト",
                "message": "レート制限テスト"
            })
            assert response.status_code == 429


class TestPerformanceE2E:
    """パフォーマンスE2Eテスト"""
    
    def test_load_testing_simulation(self, api_client):
        """負荷テストシミュレーション"""
        import concurrent.futures
        import threading
        import statistics
        
        response_times = []
        errors = []
        
        def single_request(request_id):
            """単一リクエスト実行"""
            try:
                start_time = time.time()
                
                contact_data = {
                    "name": f"負荷テストユーザー{request_id}",
                    "email": f"load{request_id}@example.com",
                    "subject": f"負荷テスト{request_id}",
                    "message": f"負荷テスト用メッセージ{request_id}"
                }
                
                response = api_client.post("/api/v1/contacts", json=contact_data)
                end_time = time.time()
                
                response_time = end_time - start_time
                response_times.append(response_time)
                
                if response.status_code != 201:
                    errors.append(f"Request {request_id}: Status {response.status_code}")
                
            except Exception as e:
                errors.append(f"Request {request_id}: Exception {str(e)}")
        
        # 50個の同時リクエストを実行
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(single_request, i) for i in range(50)]
            concurrent.futures.wait(futures)
        
        # パフォーマンス分析
        if response_times:
            avg_response_time = statistics.mean(response_times)
            median_response_time = statistics.median(response_times)
            max_response_time = max(response_times)
            min_response_time = min(response_times)
            
            print(f"\n負荷テスト結果:")
            print(f"リクエスト数: 50")
            print(f"エラー数: {len(errors)}")
            print(f"平均応答時間: {avg_response_time:.3f}秒")
            print(f"中央値応答時間: {median_response_time:.3f}秒")
            print(f"最大応答時間: {max_response_time:.3f}秒")
            print(f"最小応答時間: {min_response_time:.3f}秒")
            
            # 性能要件確認
            assert len(errors) == 0, f"エラーが発生しました: {errors[:5]}"
            assert avg_response_time < 3.0, f"平均応答時間が要件を超過: {avg_response_time}秒"
            assert max_response_time < 10.0, f"最大応答時間が要件を超過: {max_response_time}秒"
    
    @pytest.mark.asyncio
    async def test_memory_usage_monitoring(self):
        """メモリ使用量監視テスト"""
        import psutil
        import os
        
        # 現在のプロセスID取得
        current_process = psutil.Process(os.getpid())
        
        # 開始時メモリ使用量
        start_memory = current_process.memory_info().rss / 1024 / 1024  # MB
        
        # 大量データ処理シミュレーション
        large_data = []
        for i in range(1000):
            contact_data = {
                "id": f"memory_test_{i}",
                "name": f"メモリテストユーザー{i}",
                "email": f"memory{i}@example.com",
                "subject": f"メモリテスト{i}",
                "message": f"メモリテスト用大容量メッセージ{i}" * 100,  # 大きなメッセージ
                "analysis_result": {
                    "category": "general",
                    "urgency": "low", 
                    "confidence": 0.75,
                    "detailed_analysis": "詳細分析結果" * 50
                }
            }
            large_data.append(contact_data)
        
        # 処理後メモリ使用量
        end_memory = current_process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = end_memory - start_memory
        
        print(f"\nメモリ使用量テスト結果:")
        print(f"開始時メモリ: {start_memory:.2f} MB")
        print(f"終了時メモリ: {end_memory:.2f} MB")
        print(f"メモリ増加量: {memory_increase:.2f} MB")
        
        # メモリ使用量要件確認（例：1000件処理で100MB以下の増加）
        assert memory_increase < 100, f"メモリ使用量が要件を超過: {memory_increase:.2f} MB"
        
        # データクリアアップ
        large_data.clear()
        
        # ガベージコレクション強制実行
        import gc
        gc.collect()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])