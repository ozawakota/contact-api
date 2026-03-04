"""VectorSearchUseCase統合実装

AI解析完了後の自動ベクトル検索起動とAIAnalysisUseCaseとの非同期連携を制御する
VectorSearchUseCaseクラス。類似事例検索・フォールバック処理・推奨情報生成を統合します。
"""

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from models.contact import Contact
from models.contact_ai_analysis import ContactAIAnalysis
from models.contact_vector import ContactVector
from services.vector_service import VectorService, VectorServiceError


@dataclass
class VectorSearchRequest:
    """ベクトル検索リクエスト"""
    contact_id: int
    limit: int = 3
    similarity_threshold: float = 0.7
    include_recommendations: bool = True
    fallback_enabled: bool = True


@dataclass
class VectorSearchResponse:
    """ベクトル検索レスポンス"""
    contact_id: int
    similar_contacts: List[Dict[str, Any]]
    recommendations: Optional[Dict[str, Any]] = None
    processing_time_ms: int = 0
    success: bool = True
    error_message: Optional[str] = None
    fallback_applied: bool = False


class VectorSearchUseCaseError(Exception):
    """VectorSearchUseCaseエラー"""
    def __init__(self, message: str, contact_id: int = None, operation: str = None):
        super().__init__(message)
        self.contact_id = contact_id
        self.operation = operation


class VectorSearchUseCase:
    """VectorSearchUseCase統合制御クラス
    
    Features:
    - AI解析完了後の自動ベクトル検索起動
    - 類似事例抽出・担当者向け推奨情報生成
    - 検索失敗時のフォールバック処理（閾値緩和・手動推奨）
    - AIAnalysisUseCaseとの非同期連携制御
    """
    
    def __init__(
        self,
        vector_service: VectorService,
        notification_service=None,
        db_session: Session = None,
        search_timeout: float = 30.0,
        default_similarity_threshold: float = 0.7
    ):
        """UseCase初期化
        
        Args:
            vector_service: ベクトル検索サービス
            notification_service: 通知サービス（オプション）
            db_session: データベースセッション
            search_timeout: 検索タイムアウト（秒）
            default_similarity_threshold: デフォルト類似度閾値
        """
        self.vector_service = vector_service
        self.notification_service = notification_service
        self.db_session = db_session
        self.search_timeout = search_timeout
        self.default_similarity_threshold = default_similarity_threshold
        self.logger = logging.getLogger(__name__)
        
        # フォールバック設定
        self.fallback_threshold_factor = 0.75  # 初期閾値の75%まで緩和
        self.max_fallback_attempts = 3
        
        # パフォーマンス追跡
        self.metrics = {
            'total_searches': 0,
            'successful_searches': 0,
            'fallback_applications': 0,
            'processing_times': [],
            'recommendation_generations': 0
        }
        
        self.logger.info("VectorSearchUseCase初期化完了")
    
    async def process_ai_analysis_completion(
        self,
        contact_id: int,
        ai_analysis: ContactAIAnalysis
    ) -> Dict[str, Any]:
        """AI解析完了時の自動ベクトル検索起動
        
        Args:
            contact_id: コンタクトID
            ai_analysis: AI解析結果
            
        Returns:
            処理結果辞書
            
        Raises:
            VectorSearchUseCaseError: UseCase実行エラー
        """
        start_time = datetime.now()
        self.logger.info(f"AI解析完了後処理開始: contact_id={contact_id}")
        
        try:
            # 1. Contactデータ取得
            contact = self.db_session.get(Contact, contact_id)
            if not contact:
                raise VectorSearchUseCaseError(f"Contact not found: {contact_id}")
            
            # 2. ベクトル生成・保存
            content = f"{contact.subject}\n\n{contact.message}"
            vector_result = await self.generate_and_store_vector(
                contact_id=contact_id,
                content=content,
                metadata={
                    'ai_analysis_id': ai_analysis.id,
                    'category': ai_analysis.category,
                    'urgency': ai_analysis.urgency,
                    'confidence': ai_analysis.confidence_score
                }
            )
            
            # 3. 類似コンタクト検索
            similar_contacts = await self.find_similar_contacts_with_fallback(
                contact_id=contact_id,
                similarity_threshold=self.default_similarity_threshold,
                limit=3
            )
            
            # 4. 担当者向け推奨情報生成
            recommendations = None
            if similar_contacts.get('similar_contacts'):
                recommendations = await self.generate_agent_recommendations(
                    contact_id=contact_id,
                    similar_contacts=similar_contacts['similar_contacts'],
                    ai_analysis=ai_analysis
                )
            
            # 5. 通知サービス連携（非同期）
            notification_result = None
            if self.notification_service and similar_contacts.get('similar_contacts'):
                try:
                    notification_result = await self.notification_service.notify_similar_cases_found(
                        contact_id=contact_id,
                        similar_cases=similar_contacts['similar_contacts'],
                        recommendations=recommendations
                    )
                except Exception as e:
                    self.logger.warning(f"通知送信失敗: {e}")
                    notification_result = {'error': str(e)}
            
            # 6. 処理時間計算
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            # 7. メトリクス更新
            self.metrics['total_searches'] += 1
            self.metrics['successful_searches'] += 1
            self.metrics['processing_times'].append(processing_time)
            if recommendations:
                self.metrics['recommendation_generations'] += 1
            
            result = {
                'success': True,
                'contact_id': contact_id,
                'vector_generated': vector_result is not None,
                'similar_contacts_count': len(similar_contacts.get('similar_contacts', [])),
                'recommendations_generated': recommendations is not None,
                'notification_sent': notification_result is not None,
                'processing_time_ms': int(processing_time),
                'fallback_applied': similar_contacts.get('fallback_applied', False)
            }
            
            if notification_result and 'error' in notification_result:
                result['notification_error'] = notification_result['error']
            
            self.logger.info(f"AI解析完了後処理完了: contact_id={contact_id}, time={processing_time:.1f}ms")
            return result
            
        except Exception as e:
            self.logger.error(f"AI解析完了後処理エラー: {e}")
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            raise VectorSearchUseCaseError(f"AI解析完了処理失敗: {e}", contact_id=contact_id)
    
    async def generate_and_store_vector(
        self,
        contact_id: int,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ContactVector:
        """ベクトル生成・保存
        
        Args:
            contact_id: コンタクトID
            content: ベクトル化対象コンテンツ
            metadata: 追加メタデータ
            
        Returns:
            保存されたContactVector
        """
        try:
            self.logger.info(f"ベクトル生成・保存開始: contact_id={contact_id}")
            
            # VectorServiceによるベクトル生成・保存
            vector = await self.vector_service.store_vector(
                contact_id=contact_id,
                content=content,
                metadata=metadata
            )
            
            self.logger.info(f"ベクトル生成・保存完了: vector_id={vector.id}")
            return vector
            
        except VectorServiceError as e:
            self.logger.error(f"ベクトル生成・保存エラー: {e}")
            raise VectorSearchUseCaseError(f"ベクトル処理失敗: {e}", contact_id=contact_id)
    
    async def find_similar_contacts(
        self,
        contact_id: int,
        limit: int = 3,
        similarity_threshold: float = None
    ) -> List[Dict[str, Any]]:
        """類似コンタクト検索（基本版）
        
        Args:
            contact_id: 基準コンタクトID
            limit: 最大結果数
            similarity_threshold: 類似度閾値
            
        Returns:
            類似コンタクト一覧
        """
        try:
            self.logger.info(f"類似コンタクト検索開始: contact_id={contact_id}")
            
            threshold = similarity_threshold or self.default_similarity_threshold
            
            similar_contacts = await self.vector_service.find_similar_contacts(
                contact_id=contact_id,
                limit=limit,
                similarity_threshold=threshold
            )
            
            self.logger.info(f"類似コンタクト検索完了: results={len(similar_contacts)}")
            return similar_contacts
            
        except Exception as e:
            self.logger.error(f"類似コンタクト検索エラー: {e}")
            raise VectorSearchUseCaseError(f"類似検索失敗: {e}", contact_id=contact_id)
    
    async def find_similar_contacts_with_fallback(
        self,
        contact_id: int,
        similarity_threshold: float = None,
        limit: int = 3
    ) -> Dict[str, Any]:
        """フォールバック付き類似コンタクト検索
        
        Args:
            contact_id: 基準コンタクトID  
            similarity_threshold: 類似度閾値
            limit: 最大結果数
            
        Returns:
            検索結果とフォールバック情報
        """
        try:
            self.logger.info(f"フォールバック検索開始: contact_id={contact_id}")
            
            original_threshold = similarity_threshold or self.default_similarity_threshold
            current_threshold = original_threshold
            attempt = 0
            fallback_applied = False
            
            while attempt < self.max_fallback_attempts:
                try:
                    # 類似検索実行
                    similar_contacts = await self.find_similar_contacts(
                        contact_id=contact_id,
                        limit=limit,
                        similarity_threshold=current_threshold
                    )
                    
                    if similar_contacts or attempt == self.max_fallback_attempts - 1:
                        # 結果があるか、最終試行の場合は終了
                        result = {
                            'success': True,
                            'similar_contacts': similar_contacts,
                            'original_threshold': original_threshold,
                            'final_threshold': current_threshold,
                            'fallback_applied': fallback_applied,
                            'attempts': attempt + 1
                        }
                        
                        if fallback_applied:
                            self.metrics['fallback_applications'] += 1
                            self.logger.info(f"フォールバック成功: threshold {original_threshold:.2f} → {current_threshold:.2f}")
                        
                        return result
                    
                    # 結果がない場合は閾値を緩和して再試行
                    current_threshold *= self.fallback_threshold_factor
                    fallback_applied = True
                    attempt += 1
                    
                    self.logger.info(f"フォールバック実行: attempt={attempt}, threshold={current_threshold:.2f}")
                    
                except VectorSearchUseCaseError:
                    if attempt == self.max_fallback_attempts - 1:
                        raise
                    attempt += 1
                    current_threshold *= self.fallback_threshold_factor
                    fallback_applied = True
            
            # 全ての試行が失敗した場合
            return {
                'success': False,
                'similar_contacts': [],
                'error_type': 'vector_service_error',
                'fallback_applied': True,
                'attempts': self.max_fallback_attempts
            }
            
        except Exception as e:
            self.logger.error(f"フォールバック検索エラー: {e}")
            return {
                'success': False,
                'similar_contacts': [],
                'error_type': 'unexpected_error',
                'error_message': str(e),
                'fallback_applied': False
            }
    
    async def generate_agent_recommendations(
        self,
        contact_id: int,
        similar_contacts: List[Dict[str, Any]],
        ai_analysis: Optional[ContactAIAnalysis] = None
    ) -> Dict[str, Any]:
        """担当者向け推奨情報生成
        
        Args:
            contact_id: 基準コンタクトID
            similar_contacts: 類似コンタクト一覧
            ai_analysis: AI解析結果（オプション）
            
        Returns:
            推奨情報辞書
        """
        try:
            self.logger.info(f"推奨情報生成開始: contact_id={contact_id}")
            
            if not similar_contacts:
                # 類似事例がない場合の手動推奨
                return await self._generate_manual_fallback_recommendations(ai_analysis)
            
            # 類似事例パターン分析
            case_patterns = self._analyze_similar_case_patterns(similar_contacts)
            
            # 推奨アクション生成
            recommended_actions = self._generate_recommended_actions(
                similar_contacts, ai_analysis, case_patterns
            )
            
            # レスポンステンプレート生成
            response_templates = self._generate_response_templates(
                similar_contacts, ai_analysis, case_patterns
            )
            
            # エスカレーション判定
            escalation_required = self._assess_escalation_requirement(
                similar_contacts, ai_analysis
            )
            
            recommendations = {
                'contact_id': contact_id,
                'recommendation_type': 'similarity_based',
                'similar_case_patterns': case_patterns,
                'recommended_actions': recommended_actions,
                'response_templates': response_templates,
                'escalation_required': escalation_required,
                'confidence_score': self._calculate_recommendation_confidence(similar_contacts),
                'generated_at': datetime.now().isoformat()
            }
            
            self.logger.info(f"推奨情報生成完了: actions={len(recommended_actions)}")
            return recommendations
            
        except Exception as e:
            self.logger.error(f"推奨情報生成エラー: {e}")
            return await self._generate_manual_fallback_recommendations(ai_analysis)
    
    def _analyze_similar_case_patterns(self, similar_contacts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """類似事例パターン分析
        
        Args:
            similar_contacts: 類似コンタクト一覧
            
        Returns:
            パターン分析結果
        """
        try:
            # カテゴリ分布
            categories = {}
            urgency_levels = {}
            subjects = []
            
            for item in similar_contacts:
                contact = item.get('contact')
                if contact:
                    subjects.append(contact.subject)
                    
                    # AI解析結果があれば活用
                    if hasattr(contact, 'ai_analysis') and contact.ai_analysis:
                        analysis = contact.ai_analysis
                        categories[analysis.category] = categories.get(analysis.category, 0) + 1
                        urgency_levels[analysis.urgency] = urgency_levels.get(analysis.urgency, 0) + 1
            
            # 共通キーワード抽出
            common_keywords = self._extract_common_keywords(subjects)
            
            return {
                'total_similar_cases': len(similar_contacts),
                'category_distribution': categories,
                'urgency_distribution': urgency_levels,
                'common_keywords': common_keywords,
                'average_similarity': sum(item.get('similarity', 0) for item in similar_contacts) / len(similar_contacts)
            }
            
        except Exception as e:
            self.logger.error(f"パターン分析エラー: {e}")
            return {'analysis_error': str(e)}
    
    def _generate_recommended_actions(
        self,
        similar_contacts: List[Dict[str, Any]],
        ai_analysis: Optional[ContactAIAnalysis],
        case_patterns: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """推奨アクション生成
        
        Args:
            similar_contacts: 類似コンタクト一覧
            ai_analysis: AI解析結果
            case_patterns: パターン分析結果
            
        Returns:
            推奨アクション一覧
        """
        try:
            actions = []
            
            # パターンベースの推奨
            dominant_category = max(
                case_patterns.get('category_distribution', {}).items(),
                key=lambda x: x[1],
                default=('other', 0)
            )[0]
            
            # カテゴリ別推奨アクション
            if dominant_category == 'shipping':
                actions.extend([
                    {'action': '配送状況確認', 'priority': 'high', 'estimated_time': '5分'},
                    {'action': '配送業者連絡', 'priority': 'medium', 'estimated_time': '10分'},
                    {'action': '代替配送手配', 'priority': 'low', 'estimated_time': '30分'}
                ])
            elif dominant_category == 'product':
                actions.extend([
                    {'action': '商品状況確認', 'priority': 'high', 'estimated_time': '5分'},
                    {'action': '返品・交換手続き', 'priority': 'medium', 'estimated_time': '15分'},
                    {'action': 'QA部門連携', 'priority': 'low', 'estimated_time': '60分'}
                ])
            elif dominant_category == 'billing':
                actions.extend([
                    {'action': '請求内容確認', 'priority': 'high', 'estimated_time': '10分'},
                    {'action': '返金処理検討', 'priority': 'medium', 'estimated_time': '20分'},
                    {'action': '経理部門連携', 'priority': 'low', 'estimated_time': '30分'}
                ])
            
            # 緊急度ベースの追加推奨
            if ai_analysis and ai_analysis.urgency >= 3:
                actions.insert(0, {
                    'action': '緊急対応チーム連絡',
                    'priority': 'urgent',
                    'estimated_time': '即座',
                    'escalation': True
                })
            
            return actions
            
        except Exception as e:
            self.logger.error(f"推奨アクション生成エラー: {e}")
            return [{'action': '手動対応検討', 'priority': 'medium', 'estimated_time': '30分'}]
    
    def _generate_response_templates(
        self,
        similar_contacts: List[Dict[str, Any]],
        ai_analysis: Optional[ContactAIAnalysis],
        case_patterns: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """レスポンステンプレート生成
        
        Args:
            similar_contacts: 類似コンタクト一覧
            ai_analysis: AI解析結果
            case_patterns: パターン分析結果
            
        Returns:
            レスポンステンプレート一覧
        """
        try:
            templates = []
            
            dominant_category = max(
                case_patterns.get('category_distribution', {}).items(),
                key=lambda x: x[1],
                default=('other', 0)
            )[0]
            
            # カテゴリ別テンプレート
            if dominant_category == 'shipping':
                templates.extend([
                    {
                        'title': '配送状況確認テンプレート',
                        'template': 'いつもお世話になっております。ご注文いただいた商品の配送状況についてご確認いたします。'
                    },
                    {
                        'title': '配送遅延お詫びテンプレート', 
                        'template': '配送の遅延によりご迷惑をおかけして申し訳ございません。現在の状況と今後の対応についてご説明いたします。'
                    }
                ])
            elif dominant_category == 'product':
                templates.extend([
                    {
                        'title': '商品不具合対応テンプレート',
                        'template': '商品の不具合についてご報告いただき、ありがとうございます。詳細を確認の上、適切に対応させていただきます。'
                    }
                ])
            elif dominant_category == 'billing':
                templates.extend([
                    {
                        'title': '請求内容確認テンプレート',
                        'template': 'ご請求内容についてお問い合わせいただき、ありがとうございます。詳細を確認いたします。'
                    }
                ])
            
            # 汎用テンプレート
            templates.append({
                'title': '汎用確認テンプレート',
                'template': 'お問い合わせいただき、ありがとうございます。内容を確認の上、適切に対応させていただきます。'
            })
            
            return templates
            
        except Exception as e:
            self.logger.error(f"テンプレート生成エラー: {e}")
            return [{'title': '基本テンプレート', 'template': 'お問い合わせありがとうございます。'}]
    
    def _assess_escalation_requirement(
        self,
        similar_contacts: List[Dict[str, Any]],
        ai_analysis: Optional[ContactAIAnalysis]
    ) -> Dict[str, Any]:
        """エスカレーション要否判定
        
        Args:
            similar_contacts: 類似コンタクト一覧
            ai_analysis: AI解析結果
            
        Returns:
            エスカレーション判定結果
        """
        try:
            escalation_required = False
            escalation_reasons = []
            escalation_level = 'none'
            
            # AI解析ベースの判定
            if ai_analysis:
                if ai_analysis.urgency >= 3:
                    escalation_required = True
                    escalation_reasons.append('高緊急度案件')
                    escalation_level = 'urgent'
                
                if ai_analysis.confidence_score < 0.6:
                    escalation_required = True
                    escalation_reasons.append('AI信頼度不足')
                    escalation_level = max(escalation_level, 'review_required')
            
            # 類似事例ベースの判定
            high_similarity_count = sum(
                1 for item in similar_contacts 
                if item.get('similarity', 0) > 0.9
            )
            
            if high_similarity_count == 0 and len(similar_contacts) > 0:
                escalation_reasons.append('類似事例なし')
                escalation_level = max(escalation_level, 'manual_review')
            
            return {
                'escalation_required': escalation_required,
                'escalation_level': escalation_level,
                'escalation_reasons': escalation_reasons,
                'recommended_escalation_time': '即座' if escalation_level == 'urgent' else '1時間以内'
            }
            
        except Exception as e:
            self.logger.error(f"エスカレーション判定エラー: {e}")
            return {
                'escalation_required': True,
                'escalation_level': 'error_fallback',
                'escalation_reasons': ['判定エラー']
            }
    
    def _calculate_recommendation_confidence(self, similar_contacts: List[Dict[str, Any]]) -> float:
        """推奨信頼度計算
        
        Args:
            similar_contacts: 類似コンタクト一覧
            
        Returns:
            推奨信頼度（0.0-1.0）
        """
        try:
            if not similar_contacts:
                return 0.0
            
            # 類似度の重み付き平均
            total_weight = 0.0
            weighted_sum = 0.0
            
            for i, item in enumerate(similar_contacts):
                similarity = item.get('similarity', 0.0)
                # 順位による重み（1位: 1.0, 2位: 0.7, 3位: 0.4）
                weight = max(0.1, 1.0 - i * 0.3)
                
                weighted_sum += similarity * weight
                total_weight += weight
            
            confidence = weighted_sum / total_weight if total_weight > 0 else 0.0
            
            # 類似事例数による調整
            count_factor = min(1.0, len(similar_contacts) / 3.0)
            final_confidence = confidence * count_factor
            
            return max(0.0, min(1.0, final_confidence))
            
        except Exception as e:
            self.logger.error(f"信頼度計算エラー: {e}")
            return 0.0
    
    def _extract_common_keywords(self, subjects: List[str]) -> List[str]:
        """共通キーワード抽出
        
        Args:
            subjects: 件名一覧
            
        Returns:
            共通キーワード一覧
        """
        try:
            if not subjects:
                return []
            
            # 簡易的なキーワード抽出
            all_words = []
            for subject in subjects:
                words = subject.replace('、', ' ').replace('。', ' ').split()
                all_words.extend(words)
            
            # 頻度計算
            word_counts = {}
            for word in all_words:
                if len(word) >= 2:  # 2文字以上のみ
                    word_counts[word] = word_counts.get(word, 0) + 1
            
            # 頻度上位のキーワード
            common_keywords = [
                word for word, count in sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
                if count >= 2  # 2回以上出現
            ][:5]  # 上位5個
            
            return common_keywords
            
        except Exception as e:
            self.logger.error(f"キーワード抽出エラー: {e}")
            return []
    
    async def _generate_manual_fallback_recommendations(
        self,
        ai_analysis: Optional[ContactAIAnalysis]
    ) -> Dict[str, Any]:
        """手動フォールバック推奨生成
        
        Args:
            ai_analysis: AI解析結果
            
        Returns:
            手動推奨情報
        """
        try:
            recommendations = {
                'recommendation_type': 'manual_fallback',
                'general_guidelines': [
                    '顧客の問い合わせ内容を丁寧に確認',
                    '関連部門との連携を検討',
                    '過去の類似事例を手動検索',
                    '上位者への相談を検討'
                ],
                'escalation_required': True,
                'escalation_reason': '類似事例検索失敗',
                'recommended_actions': [
                    {'action': '手動調査実施', 'priority': 'high', 'estimated_time': '30分'},
                    {'action': '上位者相談', 'priority': 'medium', 'estimated_time': '15分'}
                ],
                'confidence_score': 0.3,  # 低信頼度
                'generated_at': datetime.now().isoformat()
            }
            
            # AI解析結果がある場合の追加情報
            if ai_analysis:
                recommendations['ai_analysis'] = {
                    'category': ai_analysis.category,
                    'urgency': ai_analysis.urgency,
                    'confidence': ai_analysis.confidence_score
                }
                
                if ai_analysis.urgency >= 3:
                    recommendations['escalation_required'] = True
                    recommendations['escalation_level'] = 'urgent'
            
            return recommendations
            
        except Exception as e:
            self.logger.error(f"手動推奨生成エラー: {e}")
            return {
                'recommendation_type': 'error_fallback',
                'general_guidelines': ['上位者に相談してください'],
                'escalation_required': True
            }
    
    async def async_vector_search_trigger(self, contact_id: int) -> None:
        """非同期ベクトル検索トリガー（バックグラウンド実行用）
        
        Args:
            contact_id: コンタクトID
        """
        try:
            self.logger.info(f"非同期ベクトル検索開始: contact_id={contact_id}")
            
            # 基本検索実行
            similar_contacts = await self.find_similar_contacts_with_fallback(
                contact_id=contact_id
            )
            
            # 結果があれば推奨情報生成
            if similar_contacts.get('similar_contacts'):
                await self.generate_agent_recommendations(
                    contact_id=contact_id,
                    similar_contacts=similar_contacts['similar_contacts']
                )
            
            self.logger.info(f"非同期ベクトル検索完了: contact_id={contact_id}")
            
        except Exception as e:
            self.logger.error(f"非同期ベクトル検索エラー: {e}")
    
    async def find_similar_contacts_with_timeout(
        self,
        contact_id: int,
        timeout: float = None
    ) -> Dict[str, Any]:
        """タイムアウト付き類似コンタクト検索
        
        Args:
            contact_id: コンタクトID
            timeout: タイムアウト（秒）
            
        Returns:
            検索結果（タイムアウト情報含む）
        """
        timeout = timeout or self.search_timeout
        start_time = time.time()
        
        try:
            # タイムアウト付きで実行
            result = await asyncio.wait_for(
                self.find_similar_contacts_with_fallback(contact_id=contact_id),
                timeout=timeout
            )
            
            processing_time = (time.time() - start_time) * 1000
            result['processing_time_ms'] = int(processing_time)
            result['timeout_occurred'] = False
            
            return result
            
        except asyncio.TimeoutError:
            processing_time = (time.time() - start_time) * 1000
            self.logger.warning(f"検索タイムアウト: contact_id={contact_id}, time={processing_time:.1f}ms")
            
            return {
                'success': False,
                'timeout_occurred': True,
                'processing_time_ms': int(processing_time),
                'similar_contacts': [],
                'error_type': 'timeout'
            }
        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            return {
                'success': False,
                'timeout_occurred': False,
                'processing_time_ms': int(processing_time),
                'similar_contacts': [],
                'error_type': 'unexpected_error',
                'error_message': str(e)
            }
    
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """パフォーマンスメトリクス取得
        
        Returns:
            パフォーマンスメトリクス辞書
        """
        try:
            processing_times = self.metrics['processing_times']
            
            return {
                'total_searches': self.metrics['total_searches'],
                'successful_searches': self.metrics['successful_searches'],
                'success_rate': (
                    self.metrics['successful_searches'] / self.metrics['total_searches']
                    if self.metrics['total_searches'] > 0 else 0.0
                ),
                'fallback_applications': self.metrics['fallback_applications'],
                'fallback_rate': (
                    self.metrics['fallback_applications'] / self.metrics['total_searches']
                    if self.metrics['total_searches'] > 0 else 0.0
                ),
                'average_processing_time': (
                    sum(processing_times) / len(processing_times)
                    if processing_times else 0.0
                ),
                'max_processing_time': max(processing_times) if processing_times else 0.0,
                'recommendation_generations': self.metrics['recommendation_generations'],
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"メトリクス取得エラー: {e}")
            return {'error': str(e)}