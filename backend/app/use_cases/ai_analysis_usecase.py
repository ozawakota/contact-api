"""AI解析UseCase

次世代サポートシステムのAI解析統合制御UseCaseクラス。
Contactの受付からAI分析、データベース保存、通知、ベクトル検索まで
2分以内での完全な処理フローを制御します。
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import json

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from models.contact import Contact
from models.contact_ai_analysis import ContactAIAnalysis
from models.contact_vector import ContactVector
from models.enums import CategoryType, UrgencyLevel, SentimentType
from services.gemini_service import (
    GeminiService, 
    GeminiAnalysisRequest, 
    GeminiAnalysisResponse,
    GeminiAPIError
)
from contacts._validators import EnhancedSecurityValidator, ValidationConfig


@dataclass
class AIAnalysisUseCaseRequest:
    """AI解析UseCaseリクエスト"""
    contact_id: int
    contact_content: str
    context: Optional[str] = None
    priority_override: Optional[int] = None


@dataclass
class AIAnalysisUseCaseResponse:
    """AI解析UseCaseレスポンス"""
    contact_id: int
    analysis_id: int
    category: str
    urgency: int
    sentiment: str
    summary: str
    confidence: float
    processing_time_ms: int
    success: bool
    error_message: Optional[str] = None


class AIAnalysisUseCaseError(Exception):
    """AI解析UseCaseエラー"""
    def __init__(self, message: str, contact_id: int = None, retry_possible: bool = False):
        super().__init__(message)
        self.contact_id = contact_id
        self.retry_possible = retry_possible


class AIAnalysisUseCase:
    """AI解析UseCase
    
    Features:
    - ContactからAI解析への全体フロー制御（2分以内処理）
    - GeminiService呼び出し・結果検証・データベース保存
    - エラー時の手動分類待ち状態設定・エスカレーション
    - VectorSearchUseCase・NotificationService連携
    """
    
    def __init__(
        self, 
        gemini_service: GeminiService,
        db_session: Session,
        notification_service=None,
        vector_search_service=None,
        security_validator: EnhancedSecurityValidator = None
    ):
        """UseCase初期化
        
        Args:
            gemini_service: GeminiAIサービス
            db_session: データベースセッション
            notification_service: 通知サービス（オプション）
            vector_search_service: ベクトル検索サービス（オプション）
            security_validator: セキュリティバリデーター（オプション）
        """
        self.gemini_service = gemini_service
        self.db_session = db_session
        self.notification_service = notification_service
        self.vector_search_service = vector_search_service
        self.security_validator = security_validator or EnhancedSecurityValidator()
        self.logger = logging.getLogger(__name__)
        
        # 処理時間制限
        self.processing_time_limit = timedelta(minutes=2)
        self.confidence_threshold = 0.6  # 最低信頼度閾値
        
        self.logger.info("AIAnalysisUseCase初期化完了")
    
    async def execute_analysis(self, request: AIAnalysisUseCaseRequest) -> AIAnalysisUseCaseResponse:
        """AI解析実行メイン処理
        
        Args:
            request: 解析リクエスト
            
        Returns:
            解析結果レスポンス
            
        Raises:
            AIAnalysisUseCaseError: UseCase実行エラー
        """
        start_time = datetime.now()
        self.logger.info(f"AI解析開始: contact_id={request.contact_id}")
        
        try:
            # 1. 時間制限チェック
            if datetime.now() - start_time > self.processing_time_limit:
                raise AIAnalysisUseCaseError(
                    "処理時間制限を超過しました",
                    contact_id=request.contact_id,
                    retry_possible=True
                )
            
            # 2. セキュリティバリデーション
            security_result = self.security_validator.validate_content(request.contact_content)
            if not security_result.is_safe:
                self.logger.warning(f"セキュリティ脅威検出: contact_id={request.contact_id}, threats={security_result.detected_threats}")
                # セキュリティ脅威がある場合もサニタイズ済みコンテンツで続行
                sanitized_content = security_result.sanitized_content
            else:
                sanitized_content = request.contact_content
            
            # 3. Contactレコード確認
            contact = self.db_session.get(Contact, request.contact_id)
            if not contact:
                raise AIAnalysisUseCaseError(
                    f"Contact not found: {request.contact_id}",
                    contact_id=request.contact_id,
                    retry_possible=False
                )
            
            # 4. 既存分析結果チェック
            existing_analysis = self.db_session.query(ContactAIAnalysis).filter_by(
                contact_id=request.contact_id
            ).first()
            
            if existing_analysis:
                self.logger.info(f"既存の解析結果を返却: contact_id={request.contact_id}")
                processing_time = (datetime.now() - start_time).total_seconds() * 1000
                return AIAnalysisUseCaseResponse(
                    contact_id=request.contact_id,
                    analysis_id=existing_analysis.id,
                    category=existing_analysis.category,
                    urgency=existing_analysis.urgency,
                    sentiment=existing_analysis.sentiment,
                    summary=existing_analysis.summary,
                    confidence=existing_analysis.confidence_score,
                    processing_time_ms=int(processing_time),
                    success=True
                )
            
            # 5. Gemini AI分析実行
            gemini_request = GeminiAnalysisRequest(
                content=sanitized_content,
                context=request.context,
                enable_self_refinement=True
            )
            
            gemini_response = await self.gemini_service.analyze_content(gemini_request)
            
            # 6. 信頼度チェック
            if gemini_response.confidence < self.confidence_threshold:
                self.logger.warning(
                    f"信頼度不足: contact_id={request.contact_id}, "
                    f"confidence={gemini_response.confidence}"
                )
                await self.handle_analysis_failure(
                    request.contact_id,
                    AIAnalysisUseCaseError("信頼度不足により手動分類が必要です")
                )
            
            # 7. データベース保存
            analysis = ContactAIAnalysis(
                contact_id=request.contact_id,
                category=gemini_response.category,
                urgency=gemini_response.urgency,
                sentiment=gemini_response.sentiment,
                confidence_score=gemini_response.confidence,
                summary=gemini_response.summary[:30],  # 30文字制限
                reasoning=gemini_response.reasoning,
                processed_at=datetime.now()
            )
            
            self.db_session.add(analysis)
            self.db_session.commit()
            
            self.logger.info(f"AI解析結果保存完了: analysis_id={analysis.id}")
            
            # 8. 緊急案件のエスカレーション
            if gemini_response.urgency >= 3:
                await self.escalate_urgent_contact(request.contact_id, analysis)
            
            # 9. ベクトル検索連携（非同期）
            if self.vector_search_service:
                asyncio.create_task(self._trigger_vector_search(request.contact_id, sanitized_content))
            
            # 10. 処理時間計算
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return AIAnalysisUseCaseResponse(
                contact_id=request.contact_id,
                analysis_id=analysis.id,
                category=gemini_response.category,
                urgency=gemini_response.urgency,
                sentiment=gemini_response.sentiment,
                summary=gemini_response.summary,
                confidence=gemini_response.confidence,
                processing_time_ms=int(processing_time),
                success=True
            )
            
        except GeminiAPIError as e:
            self.logger.error(f"Gemini API エラー: {e}")
            await self.handle_analysis_failure(request.contact_id, e)
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            return AIAnalysisUseCaseResponse(
                contact_id=request.contact_id,
                analysis_id=0,
                category="other",
                urgency=2,
                sentiment="neutral",
                summary="AI分析失敗",
                confidence=0.0,
                processing_time_ms=int(processing_time),
                success=False,
                error_message=str(e)
            )
            
        except SQLAlchemyError as e:
            self.logger.error(f"データベースエラー: {e}")
            self.db_session.rollback()
            await self.handle_analysis_failure(request.contact_id, e)
            raise AIAnalysisUseCaseError(
                f"データベース処理エラー: {e}",
                contact_id=request.contact_id,
                retry_possible=True
            )
            
        except Exception as e:
            self.logger.error(f"予期しないエラー: {e}")
            self.db_session.rollback()
            await self.handle_analysis_failure(request.contact_id, e)
            raise AIAnalysisUseCaseError(
                f"AI解析処理エラー: {e}",
                contact_id=request.contact_id,
                retry_possible=True
            )
    
    async def handle_analysis_failure(self, contact_id: int, error: Exception) -> None:
        """解析失敗時の処理
        
        Args:
            contact_id: コンタクトID
            error: 発生したエラー
        """
        try:
            self.logger.error(f"解析失敗処理開始: contact_id={contact_id}, error={error}")
            
            # Contact の status を手動分類待ちに設定
            contact = self.db_session.get(Contact, contact_id)
            if contact:
                contact.status = "manual_classification_required"
                self.db_session.commit()
            
            # エラー種別に応じた処理
            retry_possible = isinstance(error, (GeminiAPIError, SQLAlchemyError))
            
            # 通知サービスへのエスカレーション
            if self.notification_service:
                await self.notification_service.notify_analysis_failure(
                    contact_id=contact_id,
                    error_type=type(error).__name__,
                    error_message=str(error),
                    retry_possible=retry_possible
                )
            
            self.logger.info(f"解析失敗処理完了: contact_id={contact_id}")
            
        except Exception as e:
            self.logger.error(f"解析失敗処理でエラー: {e}")
    
    async def escalate_urgent_contact(self, contact_id: int, analysis: ContactAIAnalysis) -> bool:
        """緊急案件のエスカレーション
        
        Args:
            contact_id: コンタクトID
            analysis: AI解析結果
            
        Returns:
            エスカレーション成功フラグ
        """
        try:
            self.logger.info(f"緊急案件エスカレーション開始: contact_id={contact_id}")
            
            # Contact の priority を緊急に設定
            contact = self.db_session.get(Contact, contact_id)
            if contact:
                contact.priority = analysis.urgency
                contact.status = "urgent_escalated"
                self.db_session.commit()
            
            # 通知サービスでの緊急通知
            if self.notification_service:
                await self.notification_service.notify_urgent_contact(
                    contact_id=contact_id,
                    urgency=analysis.urgency,
                    category=analysis.category,
                    summary=analysis.summary,
                    confidence=analysis.confidence_score
                )
            
            self.logger.info(f"緊急案件エスカレーション完了: contact_id={contact_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"緊急案件エスカレーションエラー: {e}")
            return False
    
    async def _trigger_vector_search(self, contact_id: int, content: str) -> None:
        """ベクトル検索の非同期実行
        
        Args:
            contact_id: コンタクトID
            content: コンテンツ
        """
        try:
            self.logger.info(f"ベクトル検索実行開始: contact_id={contact_id}")
            
            if self.vector_search_service:
                # ベクトル埋め込み生成と保存
                await self.vector_search_service.generate_and_store_vector(
                    contact_id=contact_id,
                    content=content
                )
                
                # 類似事例検索
                similar_contacts = await self.vector_search_service.find_similar_contacts(
                    contact_id=contact_id,
                    limit=3
                )
                
                self.logger.info(
                    f"ベクトル検索完了: contact_id={contact_id}, "
                    f"similar_count={len(similar_contacts) if similar_contacts else 0}"
                )
            
        except Exception as e:
            self.logger.error(f"ベクトル検索エラー: {e}")
    
    async def get_analysis_status(self, contact_id: int) -> Dict[str, Any]:
        """AI解析状態取得
        
        Args:
            contact_id: コンタクトID
            
        Returns:
            解析状態情報
        """
        try:
            contact = self.db_session.get(Contact, contact_id)
            analysis = self.db_session.query(ContactAIAnalysis).filter_by(
                contact_id=contact_id
            ).first()
            
            return {
                "contact_id": contact_id,
                "contact_status": contact.status if contact else "not_found",
                "analysis_exists": analysis is not None,
                "analysis_id": analysis.id if analysis else None,
                "confidence": analysis.confidence_score if analysis else None,
                "processed_at": analysis.processed_at.isoformat() if analysis and analysis.processed_at else None
            }
            
        except Exception as e:
            self.logger.error(f"解析状態取得エラー: {e}")
            return {"contact_id": contact_id, "error": str(e)}
    
    async def retry_failed_analysis(self, contact_id: int) -> AIAnalysisUseCaseResponse:
        """失敗した解析の再試行
        
        Args:
            contact_id: コンタクトID
            
        Returns:
            解析結果レスポンス
        """
        try:
            # Contact情報取得
            contact = self.db_session.get(Contact, contact_id)
            if not contact:
                raise AIAnalysisUseCaseError(f"Contact not found: {contact_id}")
            
            # 再解析リクエスト構築
            retry_request = AIAnalysisUseCaseRequest(
                contact_id=contact_id,
                contact_content=f"{contact.subject}\n\n{contact.message}",
                context="解析再試行"
            )
            
            # 既存の失敗した解析結果を削除
            existing_analysis = self.db_session.query(ContactAIAnalysis).filter_by(
                contact_id=contact_id
            ).first()
            if existing_analysis:
                self.db_session.delete(existing_analysis)
                self.db_session.commit()
            
            self.logger.info(f"解析再試行実行: contact_id={contact_id}")
            return await self.execute_analysis(retry_request)
            
        except Exception as e:
            self.logger.error(f"解析再試行エラー: {e}")
            raise AIAnalysisUseCaseError(
                f"解析再試行失敗: {e}",
                contact_id=contact_id,
                retry_possible=True
            )