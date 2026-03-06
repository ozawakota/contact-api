"""
シンプルなContact API サーバー - フロントエンドテスト用
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid

app = FastAPI(
    title="Contact API",
    description="次世代カスタマーサポートシステム",
    version="1.0.0"
)

# CORS設定 - フロントエンドからのアクセスを許可
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React開発サーバー
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# データモデル
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
    message: str
    status: str = "pending"
    created_at: datetime
    user_authenticated: bool = False
    ai_analysis: Optional[dict] = None
    similar_contacts: Optional[List[dict]] = None
    notifications_sent: Optional[List[dict]] = None

class FirebaseStatus(BaseModel):
    available: bool = False
    initialized: bool = False

class DatabaseStatus(BaseModel):
    available: bool = True
    initialized: bool = True
    connected: bool = True

class AIStatus(BaseModel):
    available: bool = True
    initialized: bool = True
    model: Optional[str] = "demo-model"

class VectorStatus(BaseModel):
    available: bool = True
    initialized: bool = True
    model: Optional[str] = "text-search"

class EmailStatus(BaseModel):
    available: bool = False
    initialized: bool = False
    service: Optional[str] = "none"

class FeaturesEnabled(BaseModel):
    crud_operations: bool = True
    firebase_auth: bool = False
    database: bool = True
    ai_analysis: bool = True
    vector_search: bool = True
    email_notifications: bool = False

class SystemStatus(BaseModel):
    service_name: str = "Contact API"
    version: str = "1.0.0"
    status: str = "healthy"
    environment: str = "development"
    timestamp: datetime
    features: List[str] = ["お問い合わせ管理", "AI分析", "ベクター検索", "レスポンシブUI"]
    firebase_status: FirebaseStatus = FirebaseStatus()
    database_status: DatabaseStatus = DatabaseStatus()
    ai_status: AIStatus = AIStatus()
    vector_status: VectorStatus = VectorStatus()
    email_status: EmailStatus = EmailStatus()

class HealthStatus(BaseModel):
    status: str = "healthy"
    service: str = "Contact API"
    database: str = "connected"
    ai_service: str = "available"
    vector_search: str = "ready"
    email_service: str = "operational"
    auth_mode: str = "demo"
    storage_mode: str = "memory"
    ai_mode: str = "demo"
    vector_mode: str = "simple-search"
    email_mode: str = "disabled"
    port: Optional[int] = 8000
    features_enabled: FeaturesEnabled = FeaturesEnabled()

class VectorSearchRequest(BaseModel):
    query: str
    limit: int = 5

class SimilarContact(BaseModel):
    contact_id: str
    subject: str
    message: str
    created_at: datetime
    similarity_score: float

# メモリ内ストレージ（デモ用）
contacts_db: List[ContactResponse] = []

@app.get("/")
async def get_system_status() -> SystemStatus:
    """システムステータス取得"""
    return SystemStatus(timestamp=datetime.now())

@app.get("/health")
async def get_health_status() -> HealthStatus:
    """ヘルスチェック"""
    return HealthStatus()

@app.post("/api/v1/contacts")
async def create_contact(contact: ContactRequest) -> ContactResponse:
    """お問い合わせ作成"""
    # 新しいお問い合わせを作成
    new_contact = ContactResponse(
        id=str(uuid.uuid4()),
        name=contact.name,
        email=contact.email,
        subject=contact.subject,
        message=contact.message,
        status="pending",
        created_at=datetime.now(),
        user_authenticated=False,
        ai_analysis={
            "category": "general",
            "urgency": "medium",
            "sentiment": "neutral",
            "confidence_score": 0.8,
            "key_topics": ["問い合わせ"],
            "recommended_action": "24時間以内に初回回答をお送りください",
            "model_used": "demo-model",
            "analyzed_at": datetime.now().isoformat()
        },
        similar_contacts=[],
        notifications_sent=[]
    )
    
    # メモリに保存
    contacts_db.append(new_contact)
    
    return new_contact

@app.get("/api/v1/contacts")
async def get_contacts():
    """お問い合わせ一覧取得"""
    return {
        "contacts": contacts_db,
        "total": len(contacts_db),
        "page": 1,
        "page_size": len(contacts_db)
    }

@app.get("/api/v1/contacts/{contact_id}")
async def get_contact(contact_id: str) -> ContactResponse:
    """お問い合わせ詳細取得"""
    for contact in contacts_db:
        if contact.id == contact_id:
            return contact
    raise HTTPException(status_code=404, detail="Contact not found")

@app.post("/api/v1/search")
async def search_similar_contacts(search_request: VectorSearchRequest) -> List[SimilarContact]:
    """ベクター検索（デモ実装）"""
    print(f"Vector search request: {search_request}")
    
    # デモ用：シンプルなテキスト検索
    query = search_request.query.lower()
    results = []
    
    for contact in contacts_db:
        # 件名とメッセージから検索
        score = 0.0
        if query in contact.subject.lower():
            score += 0.7
        if query in contact.message.lower():
            score += 0.5
        
        # 類似度が0より大きい場合に結果に追加
        if score > 0:
            similar = SimilarContact(
                contact_id=contact.id,
                subject=contact.subject,
                message=contact.message,
                created_at=contact.created_at,
                similarity_score=min(score, 1.0)  # 最大1.0
            )
            results.append(similar)
    
    # 類似度の高い順にソートして制限数まで返す
    results.sort(key=lambda x: x.similarity_score, reverse=True)
    return results[:search_request.limit]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")