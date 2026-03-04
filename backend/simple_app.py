"""
超最小限FastAPIアプリ - Cloud Run起動テスト専用

依存関係を最小限に抑えた起動テスト用アプリケーション
"""

import os
import sys
from fastapi import FastAPI

# 起動時環境確認
print("🚀 Starting minimal FastAPI app...")
print(f"📋 Python version: {sys.version}")
print(f"📋 PORT env var: {os.getenv('PORT', 'NOT_SET')}")
print(f"📋 Working directory: {os.getcwd()}")

# 最小限のFastAPIアプリケーション
app = FastAPI(title="Minimal Contact API", version="0.1.0")

@app.get("/")
def read_root():
    """ルートエンドポイント"""
    port = os.getenv("PORT")
    return {
        "message": "Hello from Cloud Run!",
        "port": port,
        "port_type": type(port).__name__,
        "status": "running",
        "debug": "minimal_app_v1"
    }

@app.get("/health")
def health():
    """ヘルスチェックエンドポイント"""
    return {
        "status": "ok",
        "port": os.getenv("PORT"),
        "pid": os.getpid(),
        "app_version": "minimal_v1"
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)