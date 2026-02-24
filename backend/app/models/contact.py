from typing import Optional
from sqlalchemy import Column, String, Integer, Text, Boolean
from db.base import Base  # 既存のベースクラス
from models.mixins.timestamps import TimestampMixin  # 既存のタイムスタンプ用mixin

class Contact(Base, TimestampMixin):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    
    # ユーザー入力
    name = Column(String(50), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    subject = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)

    # AI解析結果 (Function Callingの戻り値を保存)
    category = Column(String(20), nullable=True)  # shipping, product, billing, other
    priority = Column(Integer, nullable=True)     # 1, 2, 3
    sentiment = Column(String(20), nullable=True) # positive, neutral, negative
    summary = Column(String(100), nullable=True)  # AIによる30文字要約
    reasoning = Column(Text, nullable=True)       # AIの判断根拠
    
    # システム管理用
    is_spam = Column(Boolean, default=False)
    processed_at = Column(DateTime, nullable=True) # 担当者が処理した時間
    status = Column(String(20), default="new")     # new, in_progress, completed