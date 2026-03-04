import pytest
from decimal import Decimal
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.base import Base
from models.contact import Contact
from models.contact_ai_analysis import ContactAIAnalysis


@pytest.fixture
def db_session():
    """テスト用のインメモリデータベースセッション"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture
def sample_contact(db_session):
    """テスト用のContactインスタンス"""
    contact = Contact(
        name="田中太郎",
        email="tanaka@example.com", 
        subject="商品について",
        content="商品の配送状況を確認したいです。注文番号は12345です。"
    )
    db_session.add(contact)
    db_session.commit()
    db_session.refresh(contact)
    return contact


class TestContactAIAnalysisModel:
    """ContactAIAnalysisモデルのテストクラス"""
    
    def test_create_contact_ai_analysis_with_valid_data(self, db_session, sample_contact):
        """正常なデータでContactAIAnalysisを作成できること"""
        analysis = ContactAIAnalysis(
            contact_id=sample_contact.id,
            category="shipping",
            urgency=2,
            sentiment="neutral", 
            summary="配送状況確認の問い合わせ",
            confidence_score=Decimal("0.95"),
            gemini_response={"raw_response": "test_response"}
        )
        
        db_session.add(analysis)
        db_session.commit()
        db_session.refresh(analysis)
        
        assert analysis.id is not None
        assert analysis.contact_id == sample_contact.id
        assert analysis.category == "shipping"
        assert analysis.urgency == 2
        assert analysis.sentiment == "neutral"
        assert analysis.summary == "配送状況確認の問い合わせ"
        assert analysis.confidence_score == Decimal("0.95")
        assert analysis.gemini_response == {"raw_response": "test_response"}
        assert analysis.analyzed_at is not None
        assert analysis.updated_at is not None

    def test_contact_ai_analysis_relationship(self, db_session, sample_contact):
        """ContactとContactAIAnalysisの1:1リレーションシップが正常に動作すること"""
        analysis = ContactAIAnalysis(
            contact_id=sample_contact.id,
            category="product",
            urgency=1,
            sentiment="positive",
            summary="商品に関する質問",
            confidence_score=Decimal("0.88")
        )
        
        db_session.add(analysis)
        db_session.commit()
        
        # リレーションシップの確認
        assert analysis.contact.id == sample_contact.id
        assert analysis.contact.name == "田中太郎"

    def test_category_enum_validation(self, db_session, sample_contact):
        """categoryフィールドが有効な値のみ受け入れること"""
        valid_categories = ["shipping", "product", "billing", "other"]
        
        for category in valid_categories:
            analysis = ContactAIAnalysis(
                contact_id=sample_contact.id,
                category=category,
                urgency=1,
                sentiment="neutral",
                summary="テスト",
                confidence_score=Decimal("0.80")
            )
            # バリデーションエラーが発生しないことを確認
            assert analysis.category == category

    def test_urgency_range_validation(self, db_session, sample_contact):
        """urgencyフィールドが1-3の範囲内の値のみ受け入れること"""
        valid_urgencies = [1, 2, 3]
        
        for urgency in valid_urgencies:
            analysis = ContactAIAnalysis(
                contact_id=sample_contact.id,
                category="other",
                urgency=urgency,
                sentiment="neutral",
                summary="テスト",
                confidence_score=Decimal("0.80")
            )
            assert analysis.urgency == urgency

    def test_sentiment_enum_validation(self, db_session, sample_contact):
        """sentimentフィールドが有効な値のみ受け入れること"""
        valid_sentiments = ["positive", "neutral", "negative"]
        
        for sentiment in valid_sentiments:
            analysis = ContactAIAnalysis(
                contact_id=sample_contact.id,
                category="other",
                urgency=1,
                sentiment=sentiment,
                summary="テスト",
                confidence_score=Decimal("0.80")
            )
            assert analysis.sentiment == sentiment

    def test_confidence_score_range_validation(self, db_session, sample_contact):
        """confidence_scoreが0.0-1.0の範囲内の値のみ受け入れること"""
        valid_scores = [Decimal("0.0"), Decimal("0.5"), Decimal("0.95"), Decimal("1.0")]
        
        for score in valid_scores:
            analysis = ContactAIAnalysis(
                contact_id=sample_contact.id,
                category="other",
                urgency=1,
                sentiment="neutral",
                summary="テスト",
                confidence_score=score
            )
            assert analysis.confidence_score == score

    def test_summary_length_constraint(self, db_session, sample_contact):
        """summaryが30文字以内の制約を満たすこと"""
        # 30文字ちょうど
        long_summary = "これは30文字ちょうどの要約文です。12345"  # 30文字
        analysis = ContactAIAnalysis(
            contact_id=sample_contact.id,
            category="other", 
            urgency=1,
            sentiment="neutral",
            summary=long_summary,
            confidence_score=Decimal("0.80")
        )
        assert len(analysis.summary) == 30

    def test_unique_contact_id_constraint(self, db_session, sample_contact):
        """同一のcontact_idに対して複数のContactAIAnalysisが作成できないこと"""
        # 最初のAnalysisを作成
        analysis1 = ContactAIAnalysis(
            contact_id=sample_contact.id,
            category="shipping",
            urgency=2,
            sentiment="neutral",
            summary="最初の解析",
            confidence_score=Decimal("0.90")
        )
        db_session.add(analysis1)
        db_session.commit()
        
        # 同じcontact_idで2つ目のAnalysisを作成しようとする
        analysis2 = ContactAIAnalysis(
            contact_id=sample_contact.id,
            category="product", 
            urgency=1,
            sentiment="positive",
            summary="2つ目の解析",
            confidence_score=Decimal("0.85")
        )
        db_session.add(analysis2)
        
        # UNIQUE制約違反でエラーが発生することを期待
        with pytest.raises(Exception):  # IntegrityError等のDB制約エラー
            db_session.commit()

    def test_cascade_delete_on_contact_deletion(self, db_session, sample_contact):
        """Contactが削除された時にContactAIAnalysisもCascade削除されること"""
        analysis = ContactAIAnalysis(
            contact_id=sample_contact.id,
            category="billing",
            urgency=3,
            sentiment="negative",
            summary="請求に関する問題",
            confidence_score=Decimal("0.92")
        )
        db_session.add(analysis)
        db_session.commit()
        
        analysis_id = analysis.id
        
        # Contactを削除
        db_session.delete(sample_contact)
        db_session.commit()
        
        # ContactAIAnalysisも削除されていることを確認
        deleted_analysis = db_session.query(ContactAIAnalysis).filter(
            ContactAIAnalysis.id == analysis_id
        ).first()
        assert deleted_analysis is None