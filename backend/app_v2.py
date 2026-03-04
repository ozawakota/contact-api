"""
段階的復元 v2 - 基本的なFastAPI設定追加

最小限から段階的に機能を追加していきます
"""

import os
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 起動時環境確認
print("🚀 Starting FastAPI app v2...")
print(f"📋 Python version: {sys.version}")
print(f"📋 PORT env var: {os.getenv('PORT', 'NOT_SET')}")
print(f"📋 ENVIRONMENT: {os.getenv('ENVIRONMENT', 'NOT_SET')}")
print(f"📋 Working directory: {os.getcwd()}")

# FastAPIアプリケーション作成
app = FastAPI(
    title="Contact API v2",
    description="Next-Generation Customer Support System - Phase 2",
    version="2.0.0"
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 開発用に緩い設定
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    """ルートエンドポイント"""
    return {
        "message": "Contact API v2 - With CORS",
        "environment": os.getenv("ENVIRONMENT", "unknown"),
        "port": os.getenv("PORT"),
        "status": "running",
        "version": "2.0.0"
    }

@app.get("/health")
def health():
    """ヘルスチェックエンドポイント"""
    return {
        "status": "healthy",
        "service": "Contact API",
        "version": "2.0.0",
        "port": os.getenv("PORT"),
        "pid": os.getpid()
    }

@app.get("/api/v1/status")
def api_status():
    """API状態確認エンドポイント"""
    return {
        "api_version": "v1",
        "status": "operational", 
        "features": {
            "cors": "enabled",
            "health_check": "enabled",
            "basic_endpoints": "enabled"
        },
        "next_phase": "database_connection"
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)