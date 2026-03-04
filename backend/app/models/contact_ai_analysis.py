from typing import Optional
from decimal import Decimal
from sqlalchemy import Column, String, Integer, ForeignKey, DECIMAL, JSON, DateTime, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db.base import Base


class ContactAIAnalysis(Base):
    """AI解析結果を保存するモデル（再解析可能）"""
    __tablename__ = "contact_ai_analyses"
    
    # テーブル制約
    __table_args__ = (
        UniqueConstraint('contact_id', name='uq_contact_ai_analyses_contact_id'),
        CheckConstraint("category IN ('shipping', 'product', 'billing', 'other')", name='ck_category'),
        CheckConstraint("urgency IN (1, 2, 3)", name='ck_urgency'), 
        CheckConstraint("sentiment IN ('positive', 'neutral', 'negative')", name='ck_sentiment'),
        CheckConstraint("confidence_score >= 0.0 AND confidence_score <= 1.0", name='ck_confidence_score'),
        CheckConstraint("LENGTH(summary) <= 30", name='ck_summary_length')
    )

    # 主キー
    id = Column(Integer, primary_key=True, index=True)
    
    # 外部キー（ContactとのN:1リレーション）
    contact_id = Column(
        Integer, 
        ForeignKey("contacts.id", ondelete="CASCADE"), 
        nullable=False,
        unique=True,  # 1:1制約
        index=True
    )
    
    # AI解析結果フィールド
    category = Column(
        String(20), 
        nullable=False,
        comment="カテゴリ分類: shipping, product, billing, other"
    )
    
    urgency = Column(
        Integer, 
        nullable=False,
        comment="緊急度: 1=低, 2=中, 3=至急"
    )
    
    sentiment = Column(
        String(20), 
        nullable=False,
        comment="感情分析: positive, neutral, negative"
    )
    
    summary = Column(
        String(30), 
        nullable=False,
        comment="AI生成の要約（30文字以内）"
    )
    
    confidence_score = Column(
        DECIMAL(3, 2), 
        nullable=False,
        comment="AI分類の信頼度スコア（0.0-1.0）"
    )
    
    # Gemini APIの生レスポンス保存（デバッグ・監査用）
    gemini_response = Column(
        JSON,
        nullable=True,
        comment="Gemini APIからの生レスポンス（JSONB形式）"
    )
    
    # タイムスタンプ
    analyzed_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="AI解析実行日時"
    )
    
    updated_at = Column(
        DateTime(timezone=True), 
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="レコード更新日時"
    )

    # リレーションシップ（ContactとのN:1関係）
    contact = relationship(
        "Contact", 
        back_populates="ai_analysis",
        foreign_keys=[contact_id]
    )

    def __repr__(self) -> str:
        return (
            f"<ContactAIAnalysis("
            f"id={self.id}, "
            f"contact_id={self.contact_id}, "
            f"category='{self.category}', "
            f"urgency={self.urgency}, "
            f"confidence={self.confidence_score}"
            f")>"
        )