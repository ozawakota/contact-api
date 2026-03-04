"""
段階的復元 v3 - Pydanticモデル追加

基本的なデータモデルを追加
"""

import os
import sys
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

# 起動時環境確認
print("🚀 Starting FastAPI app v3...")
print(f"📋 Python version: {sys.version}")
print(f"📋 PORT env var: {os.getenv('PORT', 'NOT_SET')}")
print(f"📋 ENVIRONMENT: {os.getenv('ENVIRONMENT', 'NOT_SET')}")

# Pydanticモデル定義
class ContactRequest(BaseModel):
    name: str
    email: str  # EmailStrは依存関係が重いので一旦str
    subject: str
    message: str

class ContactResponse(BaseModel):
    id: str
    name: str
    email: str
    subject: str
    status: str
    created_at: datetime

# FastAPIアプリケーション
app = FastAPI(
    title="Contact API v3",
    description="Next-Generation Customer Support System - Phase 3",
    version="3.0.0"
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# メモリ内データストレージ（テスト用）
contacts_db = []

@app.get("/")
def read_root():
    """ルートエンドポイント"""
    return {
        "message": "Contact API v3 - With Pydantic Models",
        "environment": os.getenv("ENVIRONMENT", "unknown"),
        "features": ["cors", "pydantic_models", "basic_crud"],
        "version": "3.0.0"
    }

@app.get("/health")
def health():
    """ヘルスチェックエンドポイント"""
    return {
        "status": "healthy",
        "service": "Contact API",
        "version": "3.0.0",
        "features_enabled": ["pydantic", "crud_operations"],
        "database": "in_memory",
        "port": os.getenv("PORT")
    }

@app.post("/api/v1/contacts", response_model=ContactResponse)
def create_contact(contact: ContactRequest):
    """お問い合わせ作成エンドポイント"""
    
    # 簡単なバリデーション
    if not contact.name.strip():
        raise HTTPException(status_code=400, detail="Name is required")
    
    if not contact.email.strip():
        raise HTTPException(status_code=400, detail="Email is required")
    
    # お問い合わせ作成
    contact_id = f"contact_{len(contacts_db) + 1}"
    
    new_contact = {
        "id": contact_id,
        "name": contact.name,
        "email": contact.email,
        "subject": contact.subject,
        "message": contact.message,
        "status": "pending",
        "created_at": datetime.utcnow()
    }
    
    contacts_db.append(new_contact)
    
    return ContactResponse(**new_contact)

@app.get("/api/v1/contacts")
def list_contacts():
    """お問い合わせ一覧取得"""
    return {
        "contacts": contacts_db,
        "total_count": len(contacts_db),
        "status": "success"
    }

@app.get("/api/v1/contacts/{contact_id}")
def get_contact(contact_id: str):
    """お問い合わせ詳細取得"""
    for contact in contacts_db:
        if contact["id"] == contact_id:
            return contact
    
    raise HTTPException(status_code=404, detail="Contact not found")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)