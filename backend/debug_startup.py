"""
Cloud Run 起動デバッグスクリプト

このスクリプトは起動問題のトラブルシューティング用です。
"""

import os
import sys
import traceback
from pathlib import Path

def check_environment():
    """環境変数と設定確認"""
    print("=== Environment Debug Info ===")
    print(f"Python version: {sys.version}")
    print(f"Working directory: {os.getcwd()}")
    print(f"Python path: {sys.path}")
    
    # 重要な環境変数確認
    important_vars = [
        'PORT', 'ENVIRONMENT', 'PYTHONPATH', 'PYTHONUNBUFFERED',
        'DATABASE_URL', 'FIREBASE_CREDENTIALS_PATH',
        'GEMINI_API_KEY', 'SENDGRID_API_KEY'
    ]
    
    print("\n=== Environment Variables ===")
    for var in important_vars:
        value = os.getenv(var)
        if var in ['GEMINI_API_KEY', 'SENDGRID_API_KEY'] and value:
            # APIキーは最初の数文字のみ表示
            masked_value = f"{value[:8]}..." if len(value) > 8 else "***"
            print(f"{var}: {masked_value}")
        else:
            print(f"{var}: {value}")

def check_file_structure():
    """ファイル構造確認"""
    print("\n=== File Structure ===")
    app_dir = Path("/app")
    if app_dir.exists():
        for item in app_dir.iterdir():
            if item.is_dir():
                print(f"📁 {item.name}/")
                # appディレクトリ内を少し詳細に
                if item.name == "app":
                    for subitem in item.iterdir():
                        if subitem.is_file() and subitem.suffix == ".py":
                            print(f"  📄 {subitem.name}")
                        elif subitem.is_dir():
                            print(f"  📁 {subitem.name}/")
            else:
                print(f"📄 {item.name}")

def test_imports():
    """重要なモジュールのインポートテスト"""
    print("\n=== Import Tests ===")
    
    modules_to_test = [
        'fastapi',
        'uvicorn', 
        'sqlmodel',
        'google.generativeai',
        'firebase_admin',
        'psycopg2',
        'dependency_injector',
        'app.main'
    ]
    
    for module in modules_to_test:
        try:
            __import__(module)
            print(f"✅ {module}")
        except ImportError as e:
            print(f"❌ {module}: {e}")
        except Exception as e:
            print(f"⚠️  {module}: {e}")

def test_app_creation():
    """FastAPIアプリケーション作成テスト"""
    print("\n=== App Creation Test ===")
    
    try:
        from app.main import create_main_app
        app = create_main_app()
        print("✅ FastAPI app created successfully")
        
        # ルート確認
        routes = []
        for route in app.routes:
            if hasattr(route, 'path'):
                routes.append(f"{getattr(route, 'methods', ['GET'])} {route.path}")
        
        print(f"📋 Routes found: {len(routes)}")
        for route in routes[:10]:  # 最初の10個のみ表示
            print(f"  {route}")
        
        return app
        
    except Exception as e:
        print(f"❌ App creation failed: {e}")
        traceback.print_exc()
        return None

def test_health_endpoint():
    """ヘルスチェックエンドポイントテスト"""
    print("\n=== Health Endpoint Test ===")
    
    try:
        from fastapi.testclient import TestClient
        from app.main import create_main_app
        
        app = create_main_app()
        client = TestClient(app)
        
        response = client.get("/health")
        print(f"✅ Health endpoint status: {response.status_code}")
        print(f"📄 Response: {response.json()}")
        
    except Exception as e:
        print(f"❌ Health endpoint test failed: {e}")
        traceback.print_exc()

def main():
    """メイン診断実行"""
    print("🔍 Cloud Run Startup Diagnosis")
    print("=" * 50)
    
    check_environment()
    check_file_structure()
    test_imports()
    app = test_app_creation()
    
    if app:
        test_health_endpoint()
    
    print("\n" + "=" * 50)
    print("🏁 Diagnosis complete")

if __name__ == "__main__":
    main()