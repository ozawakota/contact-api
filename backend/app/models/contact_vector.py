"""RAG検索用ベクトルモデル

768次元のベクトル埋め込みを使用したRAG（Retrieval-Augmented Generation）検索システムのための
ContactVectorモデルを定義します。pgvector拡張を使用してPostgreSQLでの高速ベクトル検索を実現します。
"""
from typing import Optional, Dict, Any
from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, UniqueConstraint, JSON, func
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from db.base import Base
from models.mixins.timestamps import TimestampMixin
from datetime import datetime


class ContactVector(Base, TimestampMixin):
    """RAG検索用contact_vectorsテーブルのSQLModelクラス
    
    Features:
    - pgvector型の768次元ベクトル埋め込み
    - contactsテーブルとの1:1リレーションシップ
    - HNSW インデックス対応（高速類似度検索）
    - モデルバージョンとメタデータ管理
    - カスケード削除対応
    """
    __tablename__ = "contact_vectors"
    
    # テーブル制約
    __table_args__ = (
        UniqueConstraint('contact_id', name='uq_contact_vectors_contact_id'),
    )

    # 主キー
    id = Column(Integer, primary_key=True, index=True)
    
    # 外部キー: contactsテーブルとの1:1リレーション
    contact_id = Column(
        Integer, 
        ForeignKey("contacts.id", ondelete="CASCADE"), 
        nullable=False,
        unique=True,
        index=True
    )
    
    # pgvector型embedディングフィールド（768次元）
    # Geminiモデル使用時の標準的な埋め込み次元数
    embedding = Column(Vector(768), nullable=False, comment="768次元ベクトル埋め込み")
    
    # メタデータフィールド
    model_version = Column(
        String(50), 
        nullable=False,
        comment="使用したベクトル化モデルのバージョン (例: gemini-pro-1.5)"
    )
    metadata = Column(
        JSON, 
        nullable=True,
        comment="処理に関する追加メタデータ (品質スコア、処理時間等)"
    )
    vectorized_at = Column(
        DateTime, 
        nullable=False, 
        default=func.now(),
        comment="ベクトル化処理実行時刻"
    )
    
    # リレーションシップ（contactsテーブルとの1:1関係）
    contact = relationship(
        "Contact",
        back_populates="vector",
        cascade="delete"  # Contact削除時にContactVectorも削除
    )

    def __repr__(self) -> str:
        return (
            f"<ContactVector("
            f"id={self.id}, "
            f"contact_id={self.contact_id}, "
            f"model_version='{self.model_version}', "
            f"vectorized_at='{self.vectorized_at}'"
            f")>"
        )
    
    @property
    def embedding_dimension(self) -> int:
        """ベクトル次元数を返すプロパティ"""
        return 768
    
    def to_dict(self) -> Dict[str, Any]:
        """オブジェクトを辞書形式に変換"""
        return {
            'id': self.id,
            'contact_id': self.contact_id,
            'model_version': self.model_version,
            'metadata': self.metadata,
            'vectorized_at': self.vectorized_at.isoformat() if self.vectorized_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }