"""
段階的復元 v7 - ベクター検索機能追加

ベクター埋め込みと類似検索機能を追加
"""

import os
import sys
import asyncio
import json
import numpy as np
from datetime import datetime
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from enum import Enum

# Firebase関連インポート
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

# PostgreSQL関連インポート
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

# Gemini AI関連インポート
ai_available = False
try:
    import google.generativeai as genai
    ai_available = True
    print("✅ Gemini AI SDK loaded successfully")
except ImportError as e:
    print(f"⚠️ Gemini AI SDK not available: {e}")
except Exception as e:
    print(f"⚠️ Gemini AI import error: {e}")

# ベクター検索関連インポート
vector_available = False
try:
    from sentence_transformers import SentenceTransformer
    import sklearn.metrics.pairwise as sklearn_pairwise
    vector_available = True
    print("✅ Vector search libraries loaded successfully")
except ImportError as e:
    print(f"⚠️ Vector search libraries not available: {e}")
except Exception as e:
    print(f"⚠️ Vector search import error: {e}")

# 起動時環境確認
print("🚀 Starting FastAPI app v7...")
print(f"📋 Python version: {sys.version}")
print(f"📋 PORT env var: {os.getenv('PORT', 'NOT_SET')}")
print(f"📋 ENVIRONMENT: {os.getenv('ENVIRONMENT', 'NOT_SET')}")
print(f"📋 Firebase available: {firebase_available}")
print(f"📋 Database available: {database_available}")
print(f"📋 AI available: {ai_available}")
print(f"📋 Vector search available: {vector_available}")

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

# Firebase初期化
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

# データベース初期化
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

# Gemini AI初期化
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

# ベクター検索初期化
vector_initialized = False
embedding_model = None
if vector_available:
    try:
        # 軽量な日本語対応埋め込みモデル
        model_name = os.getenv("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
        embedding_model = SentenceTransformer(model_name)
        vector_initialized = True
        print(f"✅ Vector embedding model loaded: {model_name}")
    except Exception as e:
        print(f"⚠️ Vector embedding initialization failed: {e}")

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
    similar_contacts: Optional[List[Dict[str, Any]]] = None

class VectorSearchRequest(BaseModel):
    query: str
    limit: int = 5
    similarity_threshold: float = 0.7

class SimilarContact(BaseModel):
    contact_id: str
    subject: str
    message: str
    similarity_score: float
    created_at: datetime

# FastAPIアプリケーション
app = FastAPI(
    title="Contact API v7",
    description="Next-Generation Customer Support System - Phase 7 (Vector Search)",
    version="7.0.0"
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
contact_vectors = {}  # contact_id -> vector

# ベクター検索関数
async def generate_embedding(text: str) -> Optional[np.ndarray]:
    """テキストのベクター埋め込みを生成"""
    if not vector_initialized or not embedding_model:
        return None
    
    try:
        # 日本語テキストの前処理
        combined_text = text.strip()
        if not combined_text:
            return None
        
        # 埋め込み生成
        embedding = embedding_model.encode(combined_text)
        return embedding
        
    except Exception as e:
        print(f"⚠️ Embedding generation failed: {e}")
        return None

async def find_similar_contacts(query_text: str, limit: int = 5, threshold: float = 0.7) -> List[Dict[str, Any]]:
    """類似するお問い合わせを検索"""
    if not vector_initialized:
        return []
    
    try:
        # クエリの埋め込み生成
        query_embedding = await generate_embedding(query_text)
        if query_embedding is None:
            return []
        
        similarities = []
        
        # データベースから埋め込み情報を取得
        if database and database_initialized:
            try:
                query = """
                SELECT id, subject, message, created_at, embedding 
                FROM contacts 
                WHERE embedding IS NOT NULL
                ORDER BY created_at DESC
                LIMIT 100
                """
                results = await database.fetch_all(query)
                
                for row in results:
                    try:
                        if row["embedding"]:
                            # JSONから埋め込みを復元
                            stored_embedding = np.array(json.loads(row["embedding"]))
                            # コサイン類似度計算
                            similarity = sklearn_pairwise.cosine_similarity(
                                [query_embedding], [stored_embedding]
                            )[0][0]
                            
                            if similarity >= threshold:
                                similarities.append({
                                    "contact_id": row["id"],
                                    "subject": row["subject"],
                                    "message": row["message"][:200] + "..." if len(row["message"]) > 200 else row["message"],
                                    "similarity_score": float(similarity),
                                    "created_at": row["created_at"]
                                })
                    except Exception as e:
                        print(f"⚠️ Error processing embedding for {row['id']}: {e}")
                        continue
                        
            except Exception as e:
                print(f"⚠️ Database vector search failed: {e}")
                return []
        else:
            # メモリ内検索
            for contact in contacts_db:
                contact_id = contact["id"]
                if contact_id in contact_vectors:
                    stored_embedding = contact_vectors[contact_id]
                    similarity = sklearn_pairwise.cosine_similarity(
                        [query_embedding], [stored_embedding]
                    )[0][0]
                    
                    if similarity >= threshold:
                        similarities.append({
                            "contact_id": contact_id,
                            "subject": contact["subject"],
                            "message": contact["message"][:200] + "..." if len(contact["message"]) > 200 else contact["message"],
                            "similarity_score": float(similarity),
                            "created_at": contact["created_at"]
                        })
        
        # 類似度でソート
        similarities.sort(key=lambda x: x["similarity_score"], reverse=True)
        return similarities[:limit]
        
    except Exception as e:
        print(f"⚠️ Vector search failed: {e}")
        return []

# AI分析関数（前回と同じ）
async def analyze_contact_with_ai(contact_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Gemini AIでお問い合わせを分析"""
    if not ai_initialized or not genai_model:
        return None
    
    try:
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
        response_text = response.text
        
        if "```json" in response_text:
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            json_text = response_text[json_start:json_end].strip()
        else:
            json_text = response_text.strip()
        
        analysis = json.loads(json_text)
        analysis["analyzed_at"] = datetime.utcnow().isoformat()
        analysis["model_used"] = "gemini-1.5-flash"
        
        return analysis
        
    except Exception as e:
        print(f"⚠️ AI analysis failed: {e}")
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
    """データベーステーブル作成（ベクター埋め込みカラム追加）"""
    if not database:
        return
        
    try:
        # contactsテーブル作成（埋め込みフィールド追加）
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
            ai_confidence_score FLOAT,
            embedding TEXT,
            embedding_model VARCHAR(100)
        )
        """
        await database.execute(query)
        
        # インデックス作成（検索性能向上）
        index_query = """
        CREATE INDEX IF NOT EXISTS idx_contacts_ai_category ON contacts(ai_category);
        CREATE INDEX IF NOT EXISTS idx_contacts_ai_urgency ON contacts(ai_urgency);
        CREATE INDEX IF NOT EXISTS idx_contacts_created_at ON contacts(created_at);
        """
        await database.execute(index_query)
        
        print("✅ Database tables created/verified with vector fields")
        
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
    """お問い合わせをデータベースに保存（ベクター埋め込み含む）"""
    if not database or not database_initialized:
        contacts_db.append(contact_data)
        # メモリ内ベクター保存
        if contact_data.get("embedding_vector") is not None:
            contact_vectors[contact_data["id"]] = contact_data["embedding_vector"]
        return contact_data
    
    try:
        # ベクター埋め込みをJSON文字列に変換
        embedding_json = None
        if contact_data.get("embedding_vector") is not None:
            embedding_json = json.dumps(contact_data["embedding_vector"].tolist())
        
        query = """
        INSERT INTO contacts (
            id, name, email, subject, message, status, created_at, 
            user_authenticated, user_id, user_email,
            ai_analysis, ai_category, ai_urgency, ai_confidence_score,
            embedding, embedding_model
        ) VALUES (
            :id, :name, :email, :subject, :message, :status, :created_at,
            :user_authenticated, :user_id, :user_email,
            :ai_analysis, :ai_category, :ai_urgency, :ai_confidence_score,
            :embedding, :embedding_model
        ) RETURNING *
        """
        
        save_data = contact_data.copy()
        save_data["embedding"] = embedding_json
        save_data["embedding_model"] = os.getenv("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2") if embedding_json else None
        
        # numpy配列を除去（データベースに保存できないため）
        if "embedding_vector" in save_data:
            del save_data["embedding_vector"]
        
        result = await database.fetch_one(query=query, values=save_data)
        if result:
            return dict(result)
        else:
            contacts_db.append(contact_data)
            return contact_data
            
    except Exception as e:
        print(f"⚠️ Database save failed: {e}")
        contacts_db.append(contact_data)
        if contact_data.get("embedding_vector") is not None:
            contact_vectors[contact_data["id"]] = contact_data["embedding_vector"]
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
        "message": "Contact API v7 - With Vector Search",
        "environment": os.getenv("ENVIRONMENT", "unknown"),
        "features": ["cors", "pydantic_models", "crud_operations", "firebase_auth", "database", "ai_analysis", "vector_search"],
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
        "vector_status": {
            "available": vector_available,
            "initialized": vector_initialized,
            "model": os.getenv("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2") if vector_initialized else None
        },
        "version": "7.0.0"
    }

@app.get("/health")
def health():
    """ヘルスチェックエンドポイント"""
    return {
        "status": "healthy",
        "service": "Contact API",
        "version": "7.0.0",
        "features_enabled": {
            "pydantic": True,
            "crud_operations": True,
            "firebase_auth": firebase_initialized,
            "database": database_initialized and (database.is_connected if database else False),
            "ai_analysis": ai_initialized,
            "vector_search": vector_initialized
        },
        "storage_mode": "database" if (database_initialized and database and database.is_connected) else "in_memory",
        "auth_mode": "optional",
        "ai_mode": "gemini" if ai_initialized else "disabled",
        "vector_mode": "active" if vector_initialized else "disabled",
        "port": os.getenv("PORT")
    }

@app.post("/api/v1/contacts", response_model=ContactResponse)
async def create_contact(
    contact: ContactRequest,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """お問い合わせ作成エンドポイント（AI分析・ベクター検索付き）"""
    
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
    
    # ベクター埋め込み生成
    combined_text = f"{contact.subject} {contact.message}"
    embedding_vector = await generate_embedding(combined_text)
    
    # 類似のお問い合わせ検索
    similar_contacts = await find_similar_contacts(combined_text, limit=3, threshold=0.8)
    
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
        "embedding_vector": embedding_vector,  # 一時的に保存（データベース保存時は除去）
        **user_info
    }
    
    saved_contact = await save_contact_to_db(new_contact)
    
    # レスポンスに類似お問い合わせ情報を追加
    if "embedding_vector" in saved_contact:
        del saved_contact["embedding_vector"]  # レスポンスから除去
    
    saved_contact["similar_contacts"] = similar_contacts
    
    return ContactResponse(**saved_contact)

@app.post("/api/v1/search", response_model=List[SimilarContact])
async def search_similar_contacts(
    search_request: VectorSearchRequest,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """ベクター検索エンドポイント"""
    
    if not search_request.query.strip():
        raise HTTPException(status_code=400, detail="Query is required")
    
    similar_contacts = await find_similar_contacts(
        search_request.query,
        limit=search_request.limit,
        threshold=search_request.similarity_threshold
    )
    
    return [SimilarContact(**contact) for contact in similar_contacts]

@app.get("/api/v1/contacts")
async def list_contacts(current_user: Optional[dict] = Depends(get_current_user)):
    """お問い合わせ一覧取得（AI分析・類似検索情報含む）"""
    contacts = await get_contacts_from_db()
    
    # embedding情報は除去（大きすぎるため）
    for contact in contacts:
        if "embedding" in contact:
            del contact["embedding"]
    
    return {
        "contacts": contacts,
        "total_count": len(contacts),
        "user_authenticated": current_user is not None,
        "storage_mode": "database" if (database_initialized and database and database.is_connected) else "in_memory",
        "ai_enabled": ai_initialized,
        "vector_search_enabled": vector_initialized,
        "status": "success"
    }

@app.get("/api/v1/contacts/{contact_id}")
async def get_contact(
    contact_id: str,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """お問い合わせ詳細取得（類似お問い合わせ検索付き）"""
    contact = await get_contact_from_db(contact_id)
    
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    # 類似お問い合わせ検索
    if contact.get("subject") and contact.get("message"):
        combined_text = f"{contact['subject']} {contact['message']}"
        similar_contacts = await find_similar_contacts(combined_text, limit=5, threshold=0.7)
        # 自分自身を除去
        similar_contacts = [sc for sc in similar_contacts if sc["contact_id"] != contact_id]
        contact["similar_contacts"] = similar_contacts[:3]  # 上位3件
    
    # embedding情報は除去
    if "embedding" in contact:
        del contact["embedding"]
    
    contact["viewer_authenticated"] = current_user is not None
    return contact

@app.get("/api/v1/vector/status")
async def vector_status():
    """ベクター検索機能状態確認エンドポイント"""
    return {
        "vector_available": vector_available,
        "vector_initialized": vector_initialized,
        "embedding_model": os.getenv("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2") if vector_initialized else None,
        "capabilities": ["text_embedding", "similarity_search", "multilingual_support"] if vector_initialized else [],
        "vector_count": len(contact_vectors) if not database else "stored_in_database"
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)