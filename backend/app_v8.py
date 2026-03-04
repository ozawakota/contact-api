"""
段階的復元 v8 - メール通知機能追加（SendGrid）

完全版の次世代カスタマーサポートシステム
"""

import os
import sys
import asyncio
import json
import numpy as np
from datetime import datetime
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException, Depends, Header, BackgroundTasks
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

# SendGrid関連インポート
email_available = False
try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail
    email_available = True
    print("✅ SendGrid SDK loaded successfully")
except ImportError as e:
    print(f"⚠️ SendGrid SDK not available: {e}")
except Exception as e:
    print(f"⚠️ SendGrid import error: {e}")

# 起動時環境確認
print("🚀 Starting FastAPI app v8 (Complete Version)...")
print(f"📋 Python version: {sys.version}")
print(f"📋 PORT env var: {os.getenv('PORT', 'NOT_SET')}")
print(f"📋 ENVIRONMENT: {os.getenv('ENVIRONMENT', 'NOT_SET')}")
print(f"📋 Firebase available: {firebase_available}")
print(f"📋 Database available: {database_available}")
print(f"📋 AI available: {ai_available}")
print(f"📋 Vector search available: {vector_available}")
print(f"📋 Email available: {email_available}")

# 列挙型定義
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

class NotificationType(str, Enum):
    CONTACT_RECEIVED = "contact_received"
    URGENT_CONTACT = "urgent_contact"
    AI_ANALYSIS_COMPLETE = "ai_analysis_complete"
    DAILY_SUMMARY = "daily_summary"

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
        model_name = os.getenv("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
        embedding_model = SentenceTransformer(model_name)
        vector_initialized = True
        print(f"✅ Vector embedding model loaded: {model_name}")
    except Exception as e:
        print(f"⚠️ Vector embedding initialization failed: {e}")

# SendGrid初期化
email_initialized = False
sendgrid_client = None
if email_available:
    try:
        api_key = os.getenv("SENDGRID_API_KEY")
        if api_key:
            sendgrid_client = SendGridAPIClient(api_key)
            email_initialized = True
            print("✅ SendGrid initialized successfully")
        else:
            print("⚠️ SENDGRID_API_KEY not provided")
    except Exception as e:
        print(f"⚠️ SendGrid initialization failed: {e}")

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
    notifications_sent: Optional[List[str]] = None

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

class EmailNotificationRequest(BaseModel):
    contact_id: str
    notification_type: NotificationType
    recipients: List[str]

# FastAPIアプリケーション
app = FastAPI(
    title="Contact API v8",
    description="Next-Generation Customer Support System - Complete Version",
    version="8.0.0"
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
contact_vectors = {}

# メール送信関数
async def send_email_notification(
    contact_data: Dict[str, Any], 
    notification_type: NotificationType,
    recipients: Optional[List[str]] = None
) -> bool:
    """メール通知送信"""
    if not email_initialized or not sendgrid_client:
        print("⚠️ Email service not available")
        return False
    
    try:
        # デフォルト受信者設定
        if not recipients:
            recipients = [
                os.getenv("ADMIN_EMAIL", "admin@example.com"),
                os.getenv("SUPPORT_EMAIL", "support@example.com")
            ]
        
        from_email = os.getenv("FROM_EMAIL", "no-reply@yourcompany.com")
        
        # 通知タイプ別のメール内容
        if notification_type == NotificationType.CONTACT_RECEIVED:
            subject = f"新規お問い合わせ: {contact_data['subject']}"
            content = f"""
新しいお問い合わせが受信されました。

お問い合わせID: {contact_data['id']}
送信者: {contact_data['name']} ({contact_data['email']})
件名: {contact_data['subject']}

内容:
{contact_data['message']}

作成日時: {contact_data['created_at']}

AI分析結果:
{json.dumps(contact_data.get('ai_analysis', {}), ensure_ascii=False, indent=2) if contact_data.get('ai_analysis') else '分析なし'}

管理画面で詳細を確認してください。
"""
        
        elif notification_type == NotificationType.URGENT_CONTACT:
            subject = f"🚨 緊急お問い合わせ: {contact_data['subject']}"
            content = f"""
緊急度の高いお問い合わせが受信されました。

お問い合わせID: {contact_data['id']}
送信者: {contact_data['name']} ({contact_data['email']})
件名: {contact_data['subject']}
緊急度: {contact_data.get('ai_urgency', 'unknown').upper()}

内容:
{contact_data['message']}

このお問い合わせは優先的に対応してください。
"""
        
        elif notification_type == NotificationType.AI_ANALYSIS_COMPLETE:
            ai_analysis = contact_data.get('ai_analysis', {})
            subject = f"AI分析完了: {contact_data['subject']}"
            content = f"""
お問い合わせの AI 分析が完了しました。

お問い合わせID: {contact_data['id']}
カテゴリ: {ai_analysis.get('category', '不明')}
緊急度: {ai_analysis.get('urgency', '不明')}
信頼度: {ai_analysis.get('confidence_score', 0):.2f}
感情: {ai_analysis.get('sentiment', '不明')}

推奨アクション:
{ai_analysis.get('recommended_action', '分析結果なし')}

キートピック:
{', '.join(ai_analysis.get('key_topics', []))}
"""
        
        else:
            subject = f"システム通知: {contact_data['subject']}"
            content = f"お問い合わせ ID {contact_data['id']} に関する通知です。"
        
        # メール送信
        for recipient in recipients:
            message = Mail(
                from_email=from_email,
                to_emails=recipient,
                subject=subject,
                html_content=content.replace('\n', '<br>')
            )
            
            response = sendgrid_client.send(message)
            if response.status_code in [200, 202]:
                print(f"✅ Email sent to {recipient} (status: {response.status_code})")
            else:
                print(f"⚠️ Email send failed to {recipient} (status: {response.status_code})")
        
        return True
        
    except Exception as e:
        print(f"⚠️ Email notification failed: {e}")
        return False

# ベクター検索関数（前回と同じ）
async def generate_embedding(text: str) -> Optional[np.ndarray]:
    if not vector_initialized or not embedding_model:
        return None
    
    try:
        combined_text = text.strip()
        if not combined_text:
            return None
        
        embedding = embedding_model.encode(combined_text)
        return embedding
        
    except Exception as e:
        print(f"⚠️ Embedding generation failed: {e}")
        return None

async def find_similar_contacts(query_text: str, limit: int = 5, threshold: float = 0.7) -> List[Dict[str, Any]]:
    if not vector_initialized:
        return []
    
    try:
        query_embedding = await generate_embedding(query_text)
        if query_embedding is None:
            return []
        
        similarities = []
        
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
                            stored_embedding = np.array(json.loads(row["embedding"]))
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
                        continue
                        
            except Exception as e:
                return []
        else:
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
        
        similarities.sort(key=lambda x: x["similarity_score"], reverse=True)
        return similarities[:limit]
        
    except Exception as e:
        return []

# AI分析関数（前回と同じ）
async def analyze_contact_with_ai(contact_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
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

# データベース接続管理（テーブル作成も更新）
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
    """データベーステーブル作成（通知履歴カラム追加）"""
    if not database:
        return
        
    try:
        # contactsテーブル作成（通知履歴フィールド追加）
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
            embedding_model VARCHAR(100),
            notifications_sent JSONB,
            last_notification_at TIMESTAMP
        )
        """
        await database.execute(query)
        
        # インデックス作成
        index_query = """
        CREATE INDEX IF NOT EXISTS idx_contacts_ai_category ON contacts(ai_category);
        CREATE INDEX IF NOT EXISTS idx_contacts_ai_urgency ON contacts(ai_urgency);
        CREATE INDEX IF NOT EXISTS idx_contacts_created_at ON contacts(created_at);
        CREATE INDEX IF NOT EXISTS idx_contacts_status ON contacts(status);
        """
        await database.execute(index_query)
        
        print("✅ Database tables created/verified with notification fields")
        
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

# データベースヘルパー関数（通知履歴対応）
async def save_contact_to_db(contact_data: Dict[str, Any]) -> Dict[str, Any]:
    if not database or not database_initialized:
        contacts_db.append(contact_data)
        if contact_data.get("embedding_vector") is not None:
            contact_vectors[contact_data["id"]] = contact_data["embedding_vector"]
        return contact_data
    
    try:
        embedding_json = None
        if contact_data.get("embedding_vector") is not None:
            embedding_json = json.dumps(contact_data["embedding_vector"].tolist())
        
        notifications_json = None
        if contact_data.get("notifications_sent"):
            notifications_json = json.dumps(contact_data["notifications_sent"])
        
        query = """
        INSERT INTO contacts (
            id, name, email, subject, message, status, created_at, 
            user_authenticated, user_id, user_email,
            ai_analysis, ai_category, ai_urgency, ai_confidence_score,
            embedding, embedding_model, notifications_sent, last_notification_at
        ) VALUES (
            :id, :name, :email, :subject, :message, :status, :created_at,
            :user_authenticated, :user_id, :user_email,
            :ai_analysis, :ai_category, :ai_urgency, :ai_confidence_score,
            :embedding, :embedding_model, :notifications_sent, :last_notification_at
        ) RETURNING *
        """
        
        save_data = contact_data.copy()
        save_data["embedding"] = embedding_json
        save_data["embedding_model"] = os.getenv("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2") if embedding_json else None
        save_data["notifications_sent"] = notifications_json
        save_data["last_notification_at"] = datetime.utcnow() if notifications_json else None
        
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
        "message": "Contact API v8 - Complete Next-Generation Customer Support System",
        "environment": os.getenv("ENVIRONMENT", "unknown"),
        "features": ["cors", "pydantic_models", "crud_operations", "firebase_auth", "database", "ai_analysis", "vector_search", "email_notifications"],
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
        "email_status": {
            "available": email_available,
            "initialized": email_initialized,
            "service": "SendGrid" if email_initialized else None
        },
        "version": "8.0.0"
    }

@app.get("/health")
def health():
    """ヘルスチェックエンドポイント"""
    return {
        "status": "healthy",
        "service": "Contact API - Complete Version",
        "version": "8.0.0",
        "features_enabled": {
            "pydantic": True,
            "crud_operations": True,
            "firebase_auth": firebase_initialized,
            "database": database_initialized and (database.is_connected if database else False),
            "ai_analysis": ai_initialized,
            "vector_search": vector_initialized,
            "email_notifications": email_initialized
        },
        "storage_mode": "database" if (database_initialized and database and database.is_connected) else "in_memory",
        "auth_mode": "optional",
        "ai_mode": "gemini" if ai_initialized else "disabled",
        "vector_mode": "active" if vector_initialized else "disabled",
        "email_mode": "sendgrid" if email_initialized else "disabled",
        "port": os.getenv("PORT")
    }

@app.post("/api/v1/contacts", response_model=ContactResponse)
async def create_contact(
    contact: ContactRequest,
    background_tasks: BackgroundTasks,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """お問い合わせ作成エンドポイント（完全版：AI分析・ベクター検索・通知付き）"""
    
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
        "embedding_vector": embedding_vector,
        "notifications_sent": [],
        **user_info
    }
    
    # バックグラウンドでメール通知送信
    urgency = ai_analysis.get("urgency") if ai_analysis else "medium"
    
    # 通常の新規お問い合わせ通知
    background_tasks.add_task(
        send_email_notification,
        new_contact,
        NotificationType.CONTACT_RECEIVED
    )
    
    # 緊急度が高い場合は緊急通知も送信
    if urgency in ["high", "urgent"]:
        background_tasks.add_task(
            send_email_notification,
            new_contact,
            NotificationType.URGENT_CONTACT,
            [os.getenv("URGENT_EMAIL", os.getenv("ADMIN_EMAIL", "admin@example.com"))]
        )
        new_contact["notifications_sent"].append("urgent_notification")
    
    new_contact["notifications_sent"].append("standard_notification")
    
    saved_contact = await save_contact_to_db(new_contact)
    
    # レスポンス準備
    if "embedding_vector" in saved_contact:
        del saved_contact["embedding_vector"]
    
    saved_contact["similar_contacts"] = similar_contacts
    
    return ContactResponse(**saved_contact)

@app.post("/api/v1/notifications/send")
async def send_notification(
    notification_request: EmailNotificationRequest,
    background_tasks: BackgroundTasks,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """手動メール通知送信エンドポイント"""
    
    contact = await get_contact_from_db(notification_request.contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    background_tasks.add_task(
        send_email_notification,
        contact,
        notification_request.notification_type,
        notification_request.recipients
    )
    
    return {
        "message": "Notification queued for sending",
        "contact_id": notification_request.contact_id,
        "notification_type": notification_request.notification_type,
        "recipients": notification_request.recipients
    }

@app.get("/api/v1/email/status")
async def email_status():
    """メール機能状態確認エンドポイント"""
    return {
        "email_available": email_available,
        "email_initialized": email_initialized,
        "service": "SendGrid" if email_initialized else None,
        "from_email": os.getenv("FROM_EMAIL", "no-reply@yourcompany.com"),
        "admin_email": os.getenv("ADMIN_EMAIL", "admin@example.com"),
        "support_email": os.getenv("SUPPORT_EMAIL", "support@example.com"),
        "urgent_email": os.getenv("URGENT_EMAIL", os.getenv("ADMIN_EMAIL", "admin@example.com")),
        "notification_types": [
            "contact_received",
            "urgent_contact", 
            "ai_analysis_complete",
            "daily_summary"
        ]
    }

# 既存のエンドポイント（list_contacts、get_contact、search_similar_contacts等）
# レスポンスにnotifications_sentフィールドが含まれるように更新

@app.get("/api/v1/contacts")
async def list_contacts(current_user: Optional[dict] = Depends(get_current_user)):
    """お問い合わせ一覧取得（完全版）"""
    contacts = await get_contacts_from_db()
    
    # embedding情報は除去
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
        "email_enabled": email_initialized,
        "status": "success"
    }

@app.get("/api/v1/contacts/{contact_id}")
async def get_contact(
    contact_id: str,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """お問い合わせ詳細取得（完全版）"""
    contact = await get_contact_from_db(contact_id)
    
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    # 類似お問い合わせ検索
    if contact.get("subject") and contact.get("message"):
        combined_text = f"{contact['subject']} {contact['message']}"
        similar_contacts = await find_similar_contacts(combined_text, limit=5, threshold=0.7)
        similar_contacts = [sc for sc in similar_contacts if sc["contact_id"] != contact_id]
        contact["similar_contacts"] = similar_contacts[:3]
    
    if "embedding" in contact:
        del contact["embedding"]
    
    contact["viewer_authenticated"] = current_user is not None
    return contact

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

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)