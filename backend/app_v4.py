"""
段階的復元 v4 - Firebase認証追加（オプショナル）

Firebase認証を追加しますが、失敗してもアプリは起動継続
"""

import os
import sys
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Firebase関連インポート（エラーでも継続）
firebase_available = False
try:
    import firebase_admin
    from firebase_admin import credentials, auth
    firebase_available = True
    print("✅ Firebase SDK loaded successfully")
except ImportError as e:
    print(f"⚠️ Firebase SDK not available: {e}")
except Exception as e:
    print(f"⚠️ Firebase import error: {e}")

# 起動時環境確認
print("🚀 Starting FastAPI app v4...")
print(f"📋 Python version: {sys.version}")
print(f"📋 PORT env var: {os.getenv('PORT', 'NOT_SET')}")
print(f"📋 ENVIRONMENT: {os.getenv('ENVIRONMENT', 'NOT_SET')}")
print(f"📋 Firebase available: {firebase_available}")

# Firebase初期化（失敗しても継続）
firebase_initialized = False
if firebase_available:
    try:
        if not firebase_admin._apps:
            # Firebase credentials pathから認証情報を読み込み
            cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
            if cred_path and os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
                firebase_initialized = True
                print("✅ Firebase initialized with credentials file")
            else:
                # Cloud Run環境では認証情報は自動設定される可能性
                try:
                    firebase_admin.initialize_app()
                    firebase_initialized = True
                    print("✅ Firebase initialized with default credentials")
                except Exception as e:
                    print(f"⚠️ Default Firebase initialization failed: {e}")
    except Exception as e:
        print(f"⚠️ Firebase initialization failed: {e}")

# Pydanticモデル定義
class ContactRequest(BaseModel):
    name: str
    email: str
    subject: str
    message: str

class ContactResponse(BaseModel):
    id: str
    name: str
    email: str
    subject: str
    status: str
    created_at: datetime
    user_authenticated: bool = False

# FastAPIアプリケーション
app = FastAPI(
    title="Contact API v4",
    description="Next-Generation Customer Support System - Phase 4 (Firebase Auth)",
    version="4.0.0"
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# メモリ内データストレージ
contacts_db = []

# Firebase認証ヘルパー（オプショナル）
async def get_current_user(authorization: str = Header(None)):
    """Firebase認証確認（オプショナル）"""
    
    if not firebase_initialized or not authorization:
        return None
    
    try:
        if authorization.startswith("Bearer "):
            token = authorization.split(" ")[1]
            decoded_token = auth.verify_id_token(token)
            return decoded_token
    except Exception as e:
        print(f"⚠️ Auth verification failed: {e}")
        return None
    
    return None

@app.get("/")
def read_root():
    """ルートエンドポイント"""
    return {
        "message": "Contact API v4 - With Firebase Auth (Optional)",
        "environment": os.getenv("ENVIRONMENT", "unknown"),
        "features": ["cors", "pydantic_models", "crud_operations", "firebase_auth"],
        "firebase_status": {
            "available": firebase_available,
            "initialized": firebase_initialized
        },
        "version": "4.0.0"
    }

@app.get("/health")
def health():
    """ヘルスチェックエンドポイント"""
    return {
        "status": "healthy",
        "service": "Contact API",
        "version": "4.0.0",
        "features_enabled": {
            "pydantic": True,
            "crud_operations": True,
            "firebase_auth": firebase_initialized
        },
        "database": "in_memory",
        "auth_mode": "optional",
        "port": os.getenv("PORT")
    }

@app.post("/api/v1/contacts", response_model=ContactResponse)
async def create_contact(
    contact: ContactRequest,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """お問い合わせ作成エンドポイント（認証オプショナル）"""
    
    # 簡単なバリデーション
    if not contact.name.strip():
        raise HTTPException(status_code=400, detail="Name is required")
    
    if not contact.email.strip():
        raise HTTPException(status_code=400, detail="Email is required")
    
    # お問い合わせ作成
    contact_id = f"contact_{len(contacts_db) + 1}"
    
    # 認証ユーザー情報があれば追加
    user_authenticated = current_user is not None
    user_info = {}
    if current_user:
        user_info = {
            "user_id": current_user.get("uid"),
            "user_email": current_user.get("email")
        }
    
    new_contact = {
        "id": contact_id,
        "name": contact.name,
        "email": contact.email,
        "subject": contact.subject,
        "message": contact.message,
        "status": "pending",
        "created_at": datetime.utcnow(),
        "user_authenticated": user_authenticated,
        **user_info
    }
    
    contacts_db.append(new_contact)
    
    return ContactResponse(**new_contact)

@app.get("/api/v1/contacts")
async def list_contacts(current_user: Optional[dict] = Depends(get_current_user)):
    """お問い合わせ一覧取得"""
    return {
        "contacts": contacts_db,
        "total_count": len(contacts_db),
        "user_authenticated": current_user is not None,
        "status": "success"
    }

@app.get("/api/v1/contacts/{contact_id}")
async def get_contact(
    contact_id: str,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """お問い合わせ詳細取得"""
    for contact in contacts_db:
        if contact["id"] == contact_id:
            # 認証情報を追加
            contact["viewer_authenticated"] = current_user is not None
            return contact
    
    raise HTTPException(status_code=404, detail="Contact not found")

@app.get("/api/v1/auth/status")
async def auth_status(current_user: Optional[dict] = Depends(get_current_user)):
    """認証状態確認エンドポイント"""
    return {
        "firebase_available": firebase_available,
        "firebase_initialized": firebase_initialized,
        "user_authenticated": current_user is not None,
        "user_info": current_user if current_user else None,
        "auth_mode": "optional"
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)