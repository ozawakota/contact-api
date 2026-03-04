"""
段階的復元 v5 - PostgreSQL接続追加（オプショナル）

データベース接続を追加しますが、失敗してもアプリは起動継続
"""

import os
import sys
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
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

# PostgreSQL関連インポート（エラーでも継続）
database_available = False
try:
    import asyncpg
    import databases
    database_available = True
    print("✅ Database libraries loaded successfully")
except ImportError as e:
    print(f"⚠️ Database libraries not available: {e}")
except Exception as e:
    print(f"⚠️ Database import error: {e}")

# 起動時環境確認
print("🚀 Starting FastAPI app v5...")
print(f"📋 Python version: {sys.version}")
print(f"📋 PORT env var: {os.getenv('PORT', 'NOT_SET')}")
print(f"📋 ENVIRONMENT: {os.getenv('ENVIRONMENT', 'NOT_SET')}")
print(f"📋 Firebase available: {firebase_available}")
print(f"📋 Database available: {database_available}")

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

# データベース初期化（失敗しても継続）
database_initialized = False
database = None
if database_available:
    try:
        # データベースURL構築
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5432")
        db_user = os.getenv("DB_USER", "postgres")
        db_password = os.getenv("DB_PASSWORD", "")
        db_name = os.getenv("DB_NAME", "contact_api")
        
        DATABASE_URL = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        
        # Cloud SQL接続のためのUnix socketサポート
        db_socket_dir = os.getenv("DB_SOCKET_DIR", "/cloudsql")
        instance_connection_name = os.getenv("INSTANCE_CONNECTION_NAME")
        
        if instance_connection_name and os.path.exists(db_socket_dir):
            DATABASE_URL = f"postgresql://{db_user}:{db_password}@/{db_name}?host={db_socket_dir}/{instance_connection_name}"
            print(f"✅ Using Cloud SQL connection: {instance_connection_name}")
        else:
            print(f"✅ Using standard PostgreSQL connection: {db_host}:{db_port}")
        
        database = databases.Database(DATABASE_URL)
        database_initialized = True
        print("✅ Database connection configured")
        
    except Exception as e:
        print(f"⚠️ Database configuration failed: {e}")
        database = None

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
    title="Contact API v5",
    description="Next-Generation Customer Support System - Phase 5 (Database)",
    version="5.0.0"
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# メモリ内データストレージ（データベース未使用時のフォールバック）
contacts_db = []

# データベース接続管理
@app.on_event("startup")
async def startup():
    if database and database_initialized:
        try:
            await database.connect()
            print("✅ Database connection established")
            
            # テーブル作成（存在しない場合）
            await create_tables()
            
        except Exception as e:
            print(f"⚠️ Database connection failed: {e}")
            print("⚠️ Falling back to in-memory storage")

@app.on_event("shutdown")
async def shutdown():
    if database and database_initialized:
        try:
            await database.disconnect()
            print("✅ Database connection closed")
        except Exception as e:
            print(f"⚠️ Database disconnect error: {e}")

async def create_tables():
    """データベーステーブル作成"""
    if not database:
        return
        
    try:
        # contactsテーブル作成
        query = """
        CREATE TABLE IF NOT EXISTS contacts (
            id VARCHAR(50) PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255) NOT NULL,
            subject VARCHAR(500) NOT NULL,
            message TEXT NOT NULL,
            status VARCHAR(50) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_authenticated BOOLEAN DEFAULT FALSE,
            user_id VARCHAR(255),
            user_email VARCHAR(255)
        )
        """
        await database.execute(query)
        print("✅ Database tables created/verified")
        
    except Exception as e:
        print(f"⚠️ Table creation failed: {e}")

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

# データベースヘルパー関数
async def save_contact_to_db(contact_data: Dict[str, Any]) -> Dict[str, Any]:
    """お問い合わせをデータベースに保存"""
    if not database or not database_initialized:
        # フォールバック：メモリ内保存
        contacts_db.append(contact_data)
        return contact_data
    
    try:
        query = """
        INSERT INTO contacts (
            id, name, email, subject, message, status, created_at, 
            user_authenticated, user_id, user_email
        ) VALUES (
            :id, :name, :email, :subject, :message, :status, :created_at,
            :user_authenticated, :user_id, :user_email
        ) RETURNING *
        """
        
        result = await database.fetch_one(query=query, values=contact_data)
        if result:
            return dict(result)
        else:
            # データベース保存失敗時のフォールバック
            contacts_db.append(contact_data)
            return contact_data
            
    except Exception as e:
        print(f"⚠️ Database save failed: {e}")
        # フォールバック：メモリ内保存
        contacts_db.append(contact_data)
        return contact_data

async def get_contacts_from_db():
    """お問い合わせ一覧をデータベースから取得"""
    if not database or not database_initialized:
        # フォールバック：メモリ内データ
        return contacts_db
    
    try:
        query = "SELECT * FROM contacts ORDER BY created_at DESC"
        results = await database.fetch_all(query)
        return [dict(row) for row in results]
        
    except Exception as e:
        print(f"⚠️ Database fetch failed: {e}")
        # フォールバック：メモリ内データ
        return contacts_db

async def get_contact_from_db(contact_id: str):
    """特定のお問い合わせをデータベースから取得"""
    if not database or not database_initialized:
        # フォールバック：メモリ内検索
        for contact in contacts_db:
            if contact["id"] == contact_id:
                return contact
        return None
    
    try:
        query = "SELECT * FROM contacts WHERE id = :id"
        result = await database.fetch_one(query=query, values={"id": contact_id})
        return dict(result) if result else None
        
    except Exception as e:
        print(f"⚠️ Database fetch failed: {e}")
        # フォールバック：メモリ内検索
        for contact in contacts_db:
            if contact["id"] == contact_id:
                return contact
        return None

@app.get("/")
def read_root():
    """ルートエンドポイント"""
    return {
        "message": "Contact API v5 - With Database Integration",
        "environment": os.getenv("ENVIRONMENT", "unknown"),
        "features": ["cors", "pydantic_models", "crud_operations", "firebase_auth", "database"],
        "firebase_status": {
            "available": firebase_available,
            "initialized": firebase_initialized
        },
        "database_status": {
            "available": database_available,
            "initialized": database_initialized,
            "connected": database.is_connected if database else False
        },
        "version": "5.0.0"
    }

@app.get("/health")
def health():
    """ヘルスチェックエンドポイント"""
    return {
        "status": "healthy",
        "service": "Contact API",
        "version": "5.0.0",
        "features_enabled": {
            "pydantic": True,
            "crud_operations": True,
            "firebase_auth": firebase_initialized,
            "database": database_initialized and (database.is_connected if database else False)
        },
        "storage_mode": "database" if (database_initialized and database and database.is_connected) else "in_memory",
        "auth_mode": "optional",
        "port": os.getenv("PORT")
    }

@app.post("/api/v1/contacts", response_model=ContactResponse)
async def create_contact(
    contact: ContactRequest,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """お問い合わせ作成エンドポイント（認証・DB対応）"""
    
    # 簡単なバリデーション
    if not contact.name.strip():
        raise HTTPException(status_code=400, detail="Name is required")
    
    if not contact.email.strip():
        raise HTTPException(status_code=400, detail="Email is required")
    
    # お問い合わせ作成
    contact_count = len(contacts_db) + 1
    if database and database_initialized:
        try:
            # データベースから件数を取得
            count_query = "SELECT COUNT(*) FROM contacts"
            result = await database.fetch_val(count_query)
            contact_count = (result or 0) + 1
        except:
            pass
    
    contact_id = f"contact_{contact_count}"
    
    # 認証ユーザー情報があれば追加
    user_authenticated = current_user is not None
    user_info = {
        "user_id": None,
        "user_email": None
    }
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
    
    # データベースまたはメモリに保存
    saved_contact = await save_contact_to_db(new_contact)
    
    return ContactResponse(**saved_contact)

@app.get("/api/v1/contacts")
async def list_contacts(current_user: Optional[dict] = Depends(get_current_user)):
    """お問い合わせ一覧取得（DB対応）"""
    contacts = await get_contacts_from_db()
    
    return {
        "contacts": contacts,
        "total_count": len(contacts),
        "user_authenticated": current_user is not None,
        "storage_mode": "database" if (database_initialized and database and database.is_connected) else "in_memory",
        "status": "success"
    }

@app.get("/api/v1/contacts/{contact_id}")
async def get_contact(
    contact_id: str,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """お問い合わせ詳細取得（DB対応）"""
    contact = await get_contact_from_db(contact_id)
    
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    # 認証情報を追加
    contact["viewer_authenticated"] = current_user is not None
    return contact

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

@app.get("/api/v1/database/status")
async def database_status():
    """データベース状態確認エンドポイント"""
    connection_status = False
    if database:
        try:
            connection_status = database.is_connected
        except:
            connection_status = False
    
    return {
        "database_available": database_available,
        "database_initialized": database_initialized,
        "database_connected": connection_status,
        "storage_mode": "database" if (database_initialized and connection_status) else "in_memory",
        "contact_count": len(contacts_db) if not connection_status else None
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)