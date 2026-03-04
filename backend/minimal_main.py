"""
最小限のFastAPIアプリケーション - Cloud Run起動テスト用

このファイルは起動問題のトラブルシューティング用です。
最小限の機能のみでCloud Runでの起動を確認します。
"""

import os
from fastapi import FastAPI

# 最小限のFastAPIアプリケーション
app = FastAPI(
    title="Contact API - Minimal",
    description="Minimal FastAPI for Cloud Run startup test",
    version="1.0.0"
)

@app.get("/")
async def root():
    """ルートエンドポイント"""
    return {
        "message": "Contact API - Minimal Mode",
        "status": "running",
        "port": os.getenv("PORT", "unknown"),
        "environment": os.getenv("ENVIRONMENT", "unknown")
    }

@app.get("/health")
async def health():
    """ヘルスチェックエンドポイント"""
    return {
        "status": "healthy",
        "service": "Contact API Minimal",
        "version": "1.0.0",
        "port": os.getenv("PORT"),
        "pid": os.getpid()
    }

@app.get("/debug")
async def debug():
    """デバッグ情報エンドポイント"""
    return {
        "environment_variables": {
            "PORT": os.getenv("PORT"),
            "ENVIRONMENT": os.getenv("ENVIRONMENT"),
            "PYTHONPATH": os.getenv("PYTHONPATH"),
            "PYTHONUNBUFFERED": os.getenv("PYTHONUNBUFFERED"),
        },
        "working_directory": os.getcwd(),
        "process_id": os.getpid(),
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)