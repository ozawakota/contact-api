"""
段階的復元 v6 - AI分析機能追加（Gemini）

Gemini AIによるお問い合わせ自動分析機能を追加
"""

import os
import sys
import asyncio
import json
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from enum import Enum

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

# Gemini AI関連インポート（エラーでも継続）
ai_available = False
try:
    import google.generativeai as genai
    ai_available = True
    print("✅ Gemini AI SDK loaded successfully")
except ImportError as e:
    print(f"⚠️ Gemini AI SDK not available: {e}")
except Exception as e:
    print(f"⚠️ Gemini AI import error: {e}")

# 起動時環境確認
print("🚀 Starting FastAPI app v6...")
print(f"📋 Python version: {sys.version}")
print(f"📋 PORT env var: {os.getenv('PORT', 'NOT_SET')}")
print(f"📋 ENVIRONMENT: {os.getenv('ENVIRONMENT', 'NOT_SET')}")
print(f"📋 Firebase available: {firebase_available}")
print(f"📋 Database available: {database_available}")
print(f"📋 AI available: {ai_available}")

# AI分析用の列挙型
class CategoryType(str, Enum):
    GENERAL = "general"
    TECHNICAL = "technical"
    BILLING = "billing"
    SUPPORT = "support"
    COMPLAINT = "complaint"

class UrgencyLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

# Firebase初期化（失敗しても継続）
firebase_initialized = False
if firebase_available:
    try:
        if not firebase_admin._apps:
            cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
            if cred_path and os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
                firebase_initialized = True
                print("✅ Firebase initialized with credentials file")
            else:
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
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5432")
        db_user = os.getenv("DB_USER", "postgres")
        db_password = os.getenv("DB_PASSWORD", "")
        db_name = os.getenv("DB_NAME", "contact_api")
        
        DATABASE_URL = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        
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

# Gemini AI初期化（失敗しても継続）
ai_initialized = False
genai_model = None
if ai_available:
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
            genai_model = genai.GenerativeModel('gemini-1.5-flash')
            ai_initialized = True
            print("✅ Gemini AI initialized successfully")
        else:
            print("⚠️ GEMINI_API_KEY not provided")
    except Exception as e:
        print(f"⚠️ Gemini AI initialization failed: {e}")

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
    ai_analysis: Optional[Dict[str, Any]] = None

class AIAnalysis(BaseModel):
    category: CategoryType
    urgency: UrgencyLevel
    confidence_score: float
    key_topics: list
    sentiment: str
    recommended_action: str

# FastAPIアプリケーション
app = FastAPI(
    title="Contact API v6",
    description="Next-Generation Customer Support System - Phase 6 (AI Analysis)",
    version="6.0.0"
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# メモリ内データストレージ（フォールバック）
contacts_db = []

# AI分析関数
async def analyze_contact_with_ai(contact_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Gemini AIでお問い合わせを分析"""
    if not ai_initialized or not genai_model:
        return None
    
    try:
        # プロンプト構築
        prompt = f"""
以下のお問い合わせを分析してください。JSONで回答してください。

件名: {contact_data['subject']}
内容: {contact_data['message']}
送信者: {contact_data['name']}

以下の形式でJSONを返してください：
{{
    "category": "general|technical|billing|support|complaint",
    "urgency": "low|medium|high|urgent",
    "confidence_score": 0.0-1.0,
    "key_topics": ["トピック1", "トピック2"],
    "sentiment": "positive|neutral|negative",
    "recommended_action": "推奨アクション"
}}
"""
        
        response = genai_model.generate_content(prompt)
        
        # レスポンスからJSONを抽出
        response_text = response.text
        if "```json" in response_text:
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            json_text = response_text[json_start:json_end].strip()
        else:
            json_text = response_text.strip()
        
        # JSONパース
        analysis = json.loads(json_text)
        
        # 追加情報
        analysis["analyzed_at"] = datetime.utcnow().isoformat()
        analysis["model_used"] = "gemini-1.5-flash"
        
        return analysis
        
    except Exception as e:
        print(f"⚠️ AI analysis failed: {e}")
        # フォールバック分析
        return {
            "category": "general",
            "urgency": "medium",
            "confidence_score": 0.5,
            "key_topics": ["manual_review_required"],
            "sentiment": "neutral",
            "recommended_action": "手動確認が必要です",
            "analyzed_at": datetime.utcnow().isoformat(),
            "model_used": "fallback",
            "error": str(e)
        }

# データベース接続管理
@app.on_event("startup")
async def startup():
    if database and database_initialized:
        try:
            await database.connect()
            print("✅ Database connection established")
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
    """データベーステーブル作成（AI分析カラム追加）"""
    if not database:
        return
        
    try:
        # contactsテーブル作成（AI分析フィールド追加）
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
            user_email VARCHAR(255),
            ai_analysis JSONB,
            ai_category VARCHAR(50),
            ai_urgency VARCHAR(50),
            ai_confidence_score FLOAT
        )
        """
        await database.execute(query)
        print("✅ Database tables created/verified with AI fields")
        
    except Exception as e:
        print(f"⚠️ Table creation failed: {e}")

# Firebase認証ヘルパー
async def get_current_user(authorization: str = Header(None)):
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
    """お問い合わせをデータベースに保存（AI分析含む）"""
    if not database or not database_initialized:
        contacts_db.append(contact_data)
        return contact_data
    
    try:
        query = """
        INSERT INTO contacts (
            id, name, email, subject, message, status, created_at, 
            user_authenticated, user_id, user_email,
            ai_analysis, ai_category, ai_urgency, ai_confidence_score
        ) VALUES (
            :id, :name, :email, :subject, :message, :status, :created_at,
            :user_authenticated, :user_id, :user_email,
            :ai_analysis, :ai_category, :ai_urgency, :ai_confidence_score
        ) RETURNING *
        """
        
        result = await database.fetch_one(query=query, values=contact_data)
        if result:
            return dict(result)
        else:
            contacts_db.append(contact_data)
            return contact_data
            
    except Exception as e:
        print(f"⚠️ Database save failed: {e}")
        contacts_db.append(contact_data)
        return contact_data

async def get_contacts_from_db():
    """お問い合わせ一覧をデータベースから取得"""
    if not database or not database_initialized:
        return contacts_db
    
    try:
        query = "SELECT * FROM contacts ORDER BY created_at DESC"
        results = await database.fetch_all(query)
        return [dict(row) for row in results]
    except Exception as e:
        print(f"⚠️ Database fetch failed: {e}")
        return contacts_db

async def get_contact_from_db(contact_id: str):
    """特定のお問い合わせをデータベースから取得"""
    if not database or not database_initialized:
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
        for contact in contacts_db:
            if contact["id"] == contact_id:
                return contact
        return None

@app.get("/")
def read_root():
    """ルートエンドポイント"""
    return {
        "message": "Contact API v6 - With AI Analysis (Gemini)",
        "environment": os.getenv("ENVIRONMENT", "unknown"),
        "features": ["cors", "pydantic_models", "crud_operations", "firebase_auth", "database", "ai_analysis"],
        "firebase_status": {
            "available": firebase_available,
            "initialized": firebase_initialized
        },
        "database_status": {
            "available": database_available,
            "initialized": database_initialized,
            "connected": database.is_connected if database else False
        },
        "ai_status": {
            "available": ai_available,
            "initialized": ai_initialized,
            "model": "gemini-1.5-flash" if ai_initialized else None
        },
        "version": "6.0.0"
    }

@app.get("/health")
def health():
    """ヘルスチェックエンドポイント"""
    return {
        "status": "healthy",
        "service": "Contact API",
        "version": "6.0.0",
        "features_enabled": {
            "pydantic": True,
            "crud_operations": True,
            "firebase_auth": firebase_initialized,
            "database": database_initialized and (database.is_connected if database else False),
            "ai_analysis": ai_initialized
        },
        "storage_mode": "database" if (database_initialized and database and database.is_connected) else "in_memory",
        "auth_mode": "optional",
        "ai_mode": "gemini" if ai_initialized else "disabled",
        "port": os.getenv("PORT")
    }

@app.post("/api/v1/contacts", response_model=ContactResponse)
async def create_contact(
    contact: ContactRequest,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """お問い合わせ作成エンドポイント（AI分析付き）"""
    
    if not contact.name.strip():
        raise HTTPException(status_code=400, detail="Name is required")
    
    if not contact.email.strip():
        raise HTTPException(status_code=400, detail="Email is required")
    
    # お問い合わせ基本データ作成
    contact_count = len(contacts_db) + 1
    if database and database_initialized:
        try:
            count_query = "SELECT COUNT(*) FROM contacts"
            result = await database.fetch_val(count_query)
            contact_count = (result or 0) + 1
        except:
            pass
    
    contact_id = f"contact_{contact_count}"
    
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
    
    # AI分析実行
    contact_for_analysis = {
        "name": contact.name,
        "email": contact.email,
        "subject": contact.subject,
        "message": contact.message
    }
    
    ai_analysis = await analyze_contact_with_ai(contact_for_analysis)
    
    new_contact = {
        "id": contact_id,
        "name": contact.name,
        "email": contact.email,
        "subject": contact.subject,
        "message": contact.message,
        "status": "pending",
        "created_at": datetime.utcnow(),
        "user_authenticated": user_authenticated,
        "ai_analysis": ai_analysis,
        "ai_category": ai_analysis.get("category") if ai_analysis else None,
        "ai_urgency": ai_analysis.get("urgency") if ai_analysis else None,
        "ai_confidence_score": ai_analysis.get("confidence_score") if ai_analysis else None,
        **user_info
    }
    
    saved_contact = await save_contact_to_db(new_contact)
    
    return ContactResponse(**saved_contact)

@app.get("/api/v1/contacts")
async def list_contacts(current_user: Optional[dict] = Depends(get_current_user)):
    """お問い合わせ一覧取得（AI分析情報含む）"""
    contacts = await get_contacts_from_db()
    
    return {
        "contacts": contacts,
        "total_count": len(contacts),
        "user_authenticated": current_user is not None,
        "storage_mode": "database" if (database_initialized and database and database.is_connected) else "in_memory",
        "ai_enabled": ai_initialized,
        "status": "success"
    }

@app.get("/api/v1/contacts/{contact_id}")
async def get_contact(
    contact_id: str,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """お問い合わせ詳細取得（AI分析情報含む）"""
    contact = await get_contact_from_db(contact_id)
    
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
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

@app.get("/api/v1/ai/status")
async def ai_status():
    """AI機能状態確認エンドポイント"""
    return {
        "ai_available": ai_available,
        "ai_initialized": ai_initialized,
        "model_name": "gemini-1.5-flash" if ai_initialized else None,
        "capabilities": ["category_classification", "urgency_assessment", "sentiment_analysis", "topic_extraction"] if ai_initialized else [],
        "fallback_enabled": True
    }

@app.post("/api/v1/analyze")
async def analyze_text(
    text_data: dict,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """テキスト分析エンドポイント（スタンドアロン）"""
    if not text_data.get("text"):
        raise HTTPException(status_code=400, detail="Text is required")
    
    analysis_data = {
        "subject": text_data.get("subject", ""),
        "message": text_data.get("text"),
        "name": text_data.get("name", "Anonymous")
    }
    
    analysis = await analyze_contact_with_ai(analysis_data)
    
    return {
        "analysis": analysis,
        "user_authenticated": current_user is not None,
        "timestamp": datetime.utcnow()
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)