"""AI解析関連のEnum定義"""
from enum import Enum


class CategoryType(Enum):
    """お問い合わせカテゴリ"""
    SHIPPING = "shipping"
    PRODUCT = "product" 
    BILLING = "billing"
    OTHER = "other"


class UrgencyLevel(Enum):
    """緊急度レベル"""
    LOW = 1
    MEDIUM = 2
    URGENT = 3


class SentimentType(Enum):
    """感情分析結果"""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"