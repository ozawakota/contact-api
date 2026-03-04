"""管理ダッシュボードAPI実装

認証済み管理者用のREST APIエンドポイント群。
お問い合わせ履歴・AI分類結果・統計データ・分析情報のAPIを提供します。
"""

import asyncio
import logging
import time
import json
import math
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from collections import defaultdict

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func, desc, asc, and_, or_

from models.contact import Contact
from models.contact_ai_analysis import ContactAIAnalysis
from models.contact_vector import ContactVector


@dataclass
class PaginationParams:
    """ページネーションパラメータ"""
    page: int = 1
    per_page: int = 20
    max_per_page: int = 100


@dataclass
class FilterParams:
    """フィルタパラメータ"""
    status_filter: Optional[str] = None
    category_filter: Optional[str] = None
    urgency_filter: Optional[int] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


class AdminDashboardAPIError(Exception):
    """AdminDashboardAPIエラー"""
    def __init__(self, message: str, error_code: str = None, status_code: int = 500):
        super().__init__(message)
        self.error_code = error_code
        self.status_code = status_code


class AdminDashboardAPI:
    """管理ダッシュボードAPI
    
    Features:
    - 認証済み管理者用のREST APIエンドポイント群
    - お問い合わせ履歴一覧・詳細取得（ページネーション対応）
    - AI分類結果表示・手動ステータス更新機能
    - 統計データ・分析情報API（精度・処理時間・カテゴリ分布）
    """
    
    def __init__(
        self,
        db_session: Session,
        firebase_auth=None,
        enable_caching: bool = False,
        cache_ttl: int = 300
    ):
        """API初期化
        
        Args:
            db_session: データベースセッション
            firebase_auth: Firebase認証サービス
            enable_caching: キャッシュ有効化
            cache_ttl: キャッシュTTL（秒）
        """
        self.db_session = db_session
        self.firebase_auth = firebase_auth
        self.enable_caching = enable_caching
        self.cache_ttl = cache_ttl
        self.logger = logging.getLogger(__name__)
        
        # キャッシュ（簡易実装）
        self.cache = {}
        self.cache_timestamps = {}
        
        # ページネーション制限
        self.default_per_page = 20
        self.max_per_page = 100
        
        # 統計計算キャッシュ
        self.stats_cache = {}
        self.stats_cache_time = None
        self.stats_cache_ttl = 300  # 5分
        
        self.logger.info("AdminDashboardAPI初期化完了")
    
    async def get_contacts_list(
        self,
        page: int = 1,
        per_page: int = 20,
        status_filter: Optional[str] = None,
        category_filter: Optional[str] = None,
        urgency_filter: Optional[int] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        sort_by: str = 'created_at',
        sort_order: str = 'desc',
        auth_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """お問い合わせ履歴一覧取得（ページネーション対応）
        
        Args:
            page: ページ番号
            per_page: ページあたり件数
            status_filter: ステータスフィルタ
            category_filter: カテゴリフィルタ
            urgency_filter: 緊急度フィルタ
            date_from: 開始日
            date_to: 終了日
            sort_by: ソート項目
            sort_order: ソート順序
            auth_token: 認証トークン
            
        Returns:
            コンタクト一覧とページネーション情報
        """
        try:
            self.logger.info(f"コンタクト一覧取得開始: page={page}, per_page={per_page}")
            
            # 認証チェック
            if auth_token:
                auth_result = await self._verify_admin_auth(auth_token)
                if not auth_result['success']:
                    return auth_result
            
            # パラメータ検証
            validation_result = self._validate_pagination_params(page, per_page)
            if not validation_result['valid']:
                return {
                    'success': False,
                    'error': 'invalid_parameters',
                    'message': validation_result['message']
                }
            
            # ベースクエリ構築
            query = self.db_session.query(Contact)
            
            # フィルタ適用
            query = self._apply_contact_filters(
                query, status_filter, category_filter, urgency_filter, date_from, date_to
            )
            
            # ソート適用
            if sort_by == 'created_at':
                sort_column = Contact.created_at
            elif sort_by == 'updated_at':
                sort_column = Contact.updated_at
            elif sort_by == 'priority':
                sort_column = Contact.priority
            else:
                sort_column = Contact.created_at
            
            if sort_order == 'desc':
                query = query.order_by(desc(sort_column))
            else:
                query = query.order_by(asc(sort_column))
            
            # 総件数取得
            total_count = query.count()
            
            # ページネーション適用
            offset = (page - 1) * per_page
            contacts = query.offset(offset).limit(per_page).all()
            
            # レスポンス構築
            contacts_data = []
            for contact in contacts:
                # AI解析結果も含める
                ai_analysis = self.db_session.query(ContactAIAnalysis).filter_by(
                    contact_id=contact.id
                ).first()
                
                contact_data = {
                    'id': contact.id,
                    'name': contact.name,
                    'email': contact.email,
                    'subject': contact.subject,
                    'status': contact.status,
                    'priority': getattr(contact, 'priority', 1),
                    'created_at': contact.created_at.isoformat() if contact.created_at else None,
                    'ai_analysis': {
                        'category': ai_analysis.category,
                        'urgency': ai_analysis.urgency,
                        'confidence_score': ai_analysis.confidence_score
                    } if ai_analysis else None
                }
                contacts_data.append(contact_data)
            
            # ページネーション情報
            total_pages = math.ceil(total_count / per_page)
            
            result = {
                'success': True,
                'contacts': contacts_data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total_count': total_count,
                    'total_pages': total_pages,
                    'has_next': page < total_pages,
                    'has_prev': page > 1
                }
            }
            
            self.logger.info(f"コンタクト一覧取得完了: count={len(contacts_data)}")
            return result
            
        except Exception as e:
            self.logger.error(f"コンタクト一覧取得エラー: {e}")
            return {
                'success': False,
                'error': 'database_error',
                'message': str(e)
            }
    
    async def get_contact_detail(
        self,
        contact_id: int,
        auth_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """お問い合わせ詳細取得
        
        Args:
            contact_id: コンタクトID
            auth_token: 認証トークン
            
        Returns:
            コンタクト詳細情報
        """
        try:
            self.logger.info(f"コンタクト詳細取得開始: contact_id={contact_id}")
            
            # 認証チェック
            if auth_token:
                auth_result = await self._verify_admin_auth(auth_token)
                if not auth_result['success']:
                    return auth_result
            
            # コンタクト取得
            contact = self.db_session.get(Contact, contact_id)
            if not contact:
                return {
                    'success': False,
                    'error': 'contact_not_found',
                    'message': f'Contact with ID {contact_id} not found'
                }
            
            # AI解析結果取得
            ai_analysis = self.db_session.query(ContactAIAnalysis).filter_by(
                contact_id=contact_id
            ).first()
            
            # ベクトル情報取得
            vector_info = self.db_session.query(ContactVector).filter_by(
                contact_id=contact_id
            ).first()
            
            # 詳細データ構築
            contact_detail = {
                'id': contact.id,
                'name': contact.name,
                'email': contact.email,
                'subject': contact.subject,
                'message': contact.message,
                'status': contact.status,
                'priority': getattr(contact, 'priority', 1),
                'created_at': contact.created_at.isoformat() if contact.created_at else None,
                'updated_at': contact.updated_at.isoformat() if contact.updated_at else None
            }
            
            ai_analysis_detail = None
            if ai_analysis:
                ai_analysis_detail = {
                    'id': ai_analysis.id,
                    'category': ai_analysis.category,
                    'urgency': ai_analysis.urgency,
                    'sentiment': ai_analysis.sentiment,
                    'confidence_score': ai_analysis.confidence_score,
                    'summary': ai_analysis.summary,
                    'processed_at': ai_analysis.processed_at.isoformat() if ai_analysis.processed_at else None
                }
            
            vector_detail = None
            if vector_info:
                vector_detail = {
                    'id': vector_info.id,
                    'model_version': vector_info.model_version,
                    'vectorized_at': vector_info.vectorized_at.isoformat() if vector_info.vectorized_at else None,
                    'embedding_dimension': len(vector_info.embedding) if vector_info.embedding else 0
                }
            
            result = {
                'success': True,
                'contact': contact_detail,
                'ai_analysis': ai_analysis_detail,
                'vector_info': vector_detail
            }
            
            self.logger.info(f"コンタクト詳細取得完了: contact_id={contact_id}")
            return result
            
        except Exception as e:
            self.logger.error(f"コンタクト詳細取得エラー: {e}")
            return {
                'success': False,
                'error': 'database_error',
                'message': str(e)
            }
    
    async def update_contact_status(
        self,
        contact_id: int,
        new_status: str,
        admin_user_id: str,
        notes: Optional[str] = None,
        expected_version: Optional[datetime] = None,
        auth_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """コンタクトステータス手動更新
        
        Args:
            contact_id: コンタクトID
            new_status: 新しいステータス
            admin_user_id: 管理者ユーザーID
            notes: 更新メモ
            expected_version: 期待するバージョン（楽観的ロック）
            auth_token: 認証トークン
            
        Returns:
            更新結果
        """
        try:
            self.logger.info(f"ステータス更新開始: contact_id={contact_id}, status={new_status}")
            
            # 認証チェック
            if auth_token:
                auth_result = await self._verify_admin_auth(auth_token, required_role='admin')
                if not auth_result['success']:
                    return auth_result
            
            # コンタクト取得
            contact = self.db_session.get(Contact, contact_id)
            if not contact:
                return {
                    'success': False,
                    'error': 'contact_not_found'
                }
            
            # 楽観的ロックチェック
            if expected_version and contact.updated_at != expected_version:
                return {
                    'success': False,
                    'error': 'version_conflict',
                    'message': 'Contact has been updated by another user'
                }
            
            # ステータス検証
            valid_statuses = ['pending', 'analyzed', 'in_progress', 'resolved', 'closed']
            if new_status not in valid_statuses:
                return {
                    'success': False,
                    'error': 'invalid_status',
                    'message': f'Status must be one of: {valid_statuses}'
                }
            
            # ステータス更新
            old_status = contact.status
            contact.status = new_status
            contact.updated_at = datetime.now()
            
            # 更新ログ記録（簡易実装）
            update_log = {
                'contact_id': contact_id,
                'admin_user_id': admin_user_id,
                'old_status': old_status,
                'new_status': new_status,
                'notes': notes,
                'updated_at': datetime.now().isoformat()
            }
            
            self.db_session.commit()
            
            result = {
                'success': True,
                'contact_id': contact_id,
                'updated_status': new_status,
                'previous_status': old_status,
                'updated_at': contact.updated_at.isoformat(),
                'admin_user_id': admin_user_id
            }
            
            self.logger.info(f"ステータス更新完了: {old_status} → {new_status}")
            return result
            
        except SQLAlchemyError as e:
            self.db_session.rollback()
            self.logger.error(f"ステータス更新DBエラー: {e}")
            return {
                'success': False,
                'error': 'database_error',
                'message': str(e)
            }
        except Exception as e:
            self.logger.error(f"ステータス更新エラー: {e}")
            return {
                'success': False,
                'error': 'update_failed',
                'message': str(e)
            }
    
    async def update_ai_analysis_manual(
        self,
        contact_id: int,
        new_category: str,
        new_urgency: int,
        new_sentiment: str,
        admin_user_id: str,
        notes: Optional[str] = None,
        auth_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """AI分類結果手動更新
        
        Args:
            contact_id: コンタクトID
            new_category: 新しいカテゴリ
            new_urgency: 新しい緊急度
            new_sentiment: 新しい感情
            admin_user_id: 管理者ユーザーID
            notes: 更新メモ
            auth_token: 認証トークン
            
        Returns:
            更新結果
        """
        try:
            self.logger.info(f"AI解析手動更新開始: contact_id={contact_id}")
            
            # 認証チェック
            if auth_token:
                auth_result = await self._verify_admin_auth(auth_token, required_role='admin')
                if not auth_result['success']:
                    return auth_result
            
            # AI解析結果取得
            ai_analysis = self.db_session.query(ContactAIAnalysis).filter_by(
                contact_id=contact_id
            ).first()
            
            if not ai_analysis:
                return {
                    'success': False,
                    'error': 'analysis_not_found'
                }
            
            # バリデーション
            valid_categories = ['product', 'shipping', 'billing', 'support', 'other']
            valid_urgencies = [1, 2, 3]
            valid_sentiments = ['positive', 'neutral', 'negative']
            
            if new_category not in valid_categories:
                return {
                    'success': False,
                    'error': 'invalid_category',
                    'message': f'Category must be one of: {valid_categories}'
                }
            
            if new_urgency not in valid_urgencies:
                return {
                    'success': False,
                    'error': 'invalid_urgency',
                    'message': f'Urgency must be one of: {valid_urgencies}'
                }
            
            if new_sentiment not in valid_sentiments:
                return {
                    'success': False,
                    'error': 'invalid_sentiment',
                    'message': f'Sentiment must be one of: {valid_sentiments}'
                }
            
            # 更新実行
            old_data = {
                'category': ai_analysis.category,
                'urgency': ai_analysis.urgency,
                'sentiment': ai_analysis.sentiment
            }
            
            ai_analysis.category = new_category
            ai_analysis.urgency = new_urgency
            ai_analysis.sentiment = new_sentiment
            ai_analysis.updated_at = datetime.now()
            
            # 手動更新フラグ設定
            if hasattr(ai_analysis, 'manual_override'):
                ai_analysis.manual_override = True
                ai_analysis.manual_updated_by = admin_user_id
                ai_analysis.manual_updated_at = datetime.now()
            
            self.db_session.commit()
            
            result = {
                'success': True,
                'contact_id': contact_id,
                'updated_analysis': {
                    'category': new_category,
                    'urgency': new_urgency,
                    'sentiment': new_sentiment
                },
                'previous_analysis': old_data,
                'updated_at': ai_analysis.updated_at.isoformat(),
                'admin_user_id': admin_user_id
            }
            
            self.logger.info(f"AI解析手動更新完了: contact_id={contact_id}")
            return result
            
        except Exception as e:
            self.db_session.rollback()
            self.logger.error(f"AI解析手動更新エラー: {e}")
            return {
                'success': False,
                'error': 'update_failed',
                'message': str(e)
            }
    
    async def get_analytics_overview(
        self,
        auth_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """統計データ概要取得
        
        Args:
            auth_token: 認証トークン
            
        Returns:
            統計概要データ
        """
        try:
            self.logger.info("統計概要取得開始")
            
            # 認証チェック
            if auth_token:
                auth_result = await self._verify_admin_auth(auth_token)
                if not auth_result['success']:
                    return auth_result
            
            # キャッシュチェック
            cache_key = 'analytics_overview'
            cached_result = self._get_cached_result(cache_key)
            if cached_result:
                return cached_result
            
            # 総コンタクト数
            total_contacts = self.db_session.query(Contact).count()
            
            # ステータス別分布
            status_distribution = {}
            status_counts = self.db_session.query(
                Contact.status, func.count(Contact.id)
            ).group_by(Contact.status).all()
            
            for status, count in status_counts:
                status_distribution[status] = count
            
            # カテゴリ別分布（AI解析済みのみ）
            category_distribution = {}
            category_counts = self.db_session.query(
                ContactAIAnalysis.category, func.count(ContactAIAnalysis.id)
            ).group_by(ContactAIAnalysis.category).all()
            
            for category, count in category_counts:
                category_distribution[category] = count
            
            # 緊急度分布
            urgency_distribution = {}
            urgency_counts = self.db_session.query(
                ContactAIAnalysis.urgency, func.count(ContactAIAnalysis.id)
            ).group_by(ContactAIAnalysis.urgency).all()
            
            for urgency, count in urgency_counts:
                urgency_distribution[urgency] = count
            
            # 今日の新着
            today = datetime.now().date()
            today_contacts = self.db_session.query(Contact).filter(
                func.date(Contact.created_at) == today
            ).count()
            
            result = {
                'success': True,
                'analytics': {
                    'total_contacts': total_contacts,
                    'status_distribution': status_distribution,
                    'category_distribution': category_distribution,
                    'urgency_distribution': urgency_distribution,
                    'today_new_contacts': today_contacts,
                    'generated_at': datetime.now().isoformat()
                }
            }
            
            # キャッシュ保存
            self._cache_result(cache_key, result)
            
            self.logger.info("統計概要取得完了")
            return result
            
        except Exception as e:
            self.logger.error(f"統計概要取得エラー: {e}")
            return {
                'success': False,
                'error': 'analytics_error',
                'message': str(e)
            }
    
    async def get_ai_performance_metrics(
        self,
        auth_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """AI性能メトリクス取得
        
        Args:
            auth_token: 認証トークン
            
        Returns:
            AI性能データ
        """
        try:
            self.logger.info("AI性能メトリクス取得開始")
            
            # 認証チェック
            if auth_token:
                auth_result = await self._verify_admin_auth(auth_token)
                if not auth_result['success']:
                    return auth_result
            
            # AI解析データ取得
            analyses = self.db_session.query(ContactAIAnalysis).all()
            
            if not analyses:
                return {
                    'success': True,
                    'metrics': {
                        'total_analyzed': 0,
                        'average_confidence': 0.0,
                        'category_distribution': {},
                        'urgency_distribution': {},
                        'processing_statistics': {}
                    }
                }
            
            # 信頼度統計
            confidence_scores = [a.confidence_score for a in analyses if a.confidence_score]
            average_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
            
            # カテゴリ分布
            category_counts = defaultdict(int)
            for analysis in analyses:
                category_counts[analysis.category] += 1
            
            # 緊急度分布
            urgency_counts = defaultdict(int)
            for analysis in analyses:
                urgency_counts[analysis.urgency] += 1
            
            # 処理統計
            processing_stats = {
                'total_processed': len(analyses),
                'high_confidence_count': len([a for a in analyses if a.confidence_score >= 0.9]),
                'low_confidence_count': len([a for a in analyses if a.confidence_score < 0.7]),
                'urgent_cases': len([a for a in analyses if a.urgency >= 3])
            }
            
            result = {
                'success': True,
                'metrics': {
                    'total_analyzed': len(analyses),
                    'average_confidence': round(average_confidence, 3),
                    'category_distribution': dict(category_counts),
                    'urgency_distribution': dict(urgency_counts),
                    'processing_statistics': processing_stats,
                    'generated_at': datetime.now().isoformat()
                }
            }
            
            self.logger.info("AI性能メトリクス取得完了")
            return result
            
        except Exception as e:
            self.logger.error(f"AI性能メトリクス取得エラー: {e}")
            return {
                'success': False,
                'error': 'metrics_error',
                'message': str(e)
            }
    
    async def get_processing_time_analysis(
        self,
        auth_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """処理時間分析取得
        
        Args:
            auth_token: 認証トークン
            
        Returns:
            処理時間分析データ
        """
        try:
            self.logger.info("処理時間分析取得開始")
            
            # 認証チェック
            if auth_token:
                auth_result = await self._verify_admin_auth(auth_token)
                if not auth_result['success']:
                    return auth_result
            
            # 処理時間データ取得（Contact作成からAI解析完了まで）
            query = self.db_session.query(Contact, ContactAIAnalysis).join(
                ContactAIAnalysis, Contact.id == ContactAIAnalysis.contact_id
            ).filter(
                ContactAIAnalysis.processed_at.isnot(None)
            )
            
            results = query.all()
            
            if not results:
                return {
                    'success': True,
                    'analysis': {
                        'total_processed': 0,
                        'average_processing_time_ms': 0,
                        'median_processing_time_ms': 0,
                        'max_processing_time_ms': 0,
                        'within_sla_percentage': 0.0
                    }
                }
            
            # 処理時間計算
            processing_times = []
            sla_threshold_ms = 120000  # 2分 = 120秒 = 120,000ms
            
            for contact, analysis in results:
                if contact.created_at and analysis.processed_at:
                    time_diff = analysis.processed_at - contact.created_at
                    processing_time_ms = int(time_diff.total_seconds() * 1000)
                    processing_times.append(processing_time_ms)
            
            # 統計計算
            if processing_times:
                average_time = sum(processing_times) / len(processing_times)
                median_time = sorted(processing_times)[len(processing_times) // 2]
                max_time = max(processing_times)
                within_sla = len([t for t in processing_times if t <= sla_threshold_ms])
                within_sla_percentage = (within_sla / len(processing_times)) * 100
            else:
                average_time = median_time = max_time = 0
                within_sla_percentage = 0.0
            
            result = {
                'success': True,
                'analysis': {
                    'total_processed': len(processing_times),
                    'average_processing_time_ms': int(average_time),
                    'median_processing_time_ms': int(median_time),
                    'max_processing_time_ms': int(max_time),
                    'within_sla_percentage': round(within_sla_percentage, 2),
                    'sla_threshold_ms': sla_threshold_ms,
                    'generated_at': datetime.now().isoformat()
                }
            }
            
            self.logger.info("処理時間分析取得完了")
            return result
            
        except Exception as e:
            self.logger.error(f"処理時間分析取得エラー: {e}")
            return {
                'success': False,
                'error': 'analysis_error',
                'message': str(e)
            }
    
    async def get_category_analysis(
        self,
        auth_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """カテゴリ分布分析取得
        
        Args:
            auth_token: 認証トークン
            
        Returns:
            カテゴリ分析データ
        """
        try:
            self.logger.info("カテゴリ分析取得開始")
            
            # 認証チェック
            if auth_token:
                auth_result = await self._verify_admin_auth(auth_token)
                if not auth_result['success']:
                    return auth_result
            
            # カテゴリ別統計取得
            category_stats = self.db_session.query(
                ContactAIAnalysis.category,
                func.count(ContactAIAnalysis.id).label('count'),
                func.avg(ContactAIAnalysis.confidence_score).label('avg_confidence'),
                func.avg(ContactAIAnalysis.urgency).label('avg_urgency')
            ).group_by(ContactAIAnalysis.category).all()
            
            category_distribution = {}
            total_analyzed = 0
            
            for category, count, avg_conf, avg_urg in category_stats:
                category_distribution[category] = {
                    'count': count,
                    'average_confidence': round(float(avg_conf), 3) if avg_conf else 0.0,
                    'average_urgency': round(float(avg_urg), 2) if avg_urg else 0.0
                }
                total_analyzed += count
            
            # パーセンテージ計算
            for category_data in category_distribution.values():
                category_data['percentage'] = round(
                    (category_data['count'] / total_analyzed) * 100, 2
                ) if total_analyzed > 0 else 0.0
            
            result = {
                'success': True,
                'analysis': {
                    'category_distribution': category_distribution,
                    'total_analyzed': total_analyzed,
                    'generated_at': datetime.now().isoformat()
                }
            }
            
            self.logger.info("カテゴリ分析取得完了")
            return result
            
        except Exception as e:
            self.logger.error(f"カテゴリ分析取得エラー: {e}")
            return {
                'success': False,
                'error': 'analysis_error',
                'message': str(e)
            }
    
    async def bulk_update_contact_status(
        self,
        contact_ids: List[int],
        new_status: str,
        admin_user_id: str,
        notes: Optional[str] = None,
        auth_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """一括ステータス更新
        
        Args:
            contact_ids: コンタクトID一覧
            new_status: 新しいステータス
            admin_user_id: 管理者ユーザーID
            notes: 更新メモ
            auth_token: 認証トークン
            
        Returns:
            一括更新結果
        """
        try:
            self.logger.info(f"一括ステータス更新開始: count={len(contact_ids)}")
            
            # 認証チェック
            if auth_token:
                auth_result = await self._verify_admin_auth(auth_token, required_role='admin')
                if not auth_result['success']:
                    return auth_result
            
            # コンタクト取得
            contacts = self.db_session.query(Contact).filter(
                Contact.id.in_(contact_ids)
            ).all()
            
            if not contacts:
                return {
                    'success': False,
                    'error': 'contacts_not_found'
                }
            
            # 一括更新実行
            updated_count = 0
            for contact in contacts:
                contact.status = new_status
                contact.updated_at = datetime.now()
                updated_count += 1
            
            self.db_session.commit()
            
            result = {
                'success': True,
                'updated_count': updated_count,
                'total_requested': len(contact_ids),
                'new_status': new_status,
                'admin_user_id': admin_user_id,
                'updated_at': datetime.now().isoformat()
            }
            
            self.logger.info(f"一括ステータス更新完了: updated={updated_count}")
            return result
            
        except Exception as e:
            self.db_session.rollback()
            self.logger.error(f"一括ステータス更新エラー: {e}")
            return {
                'success': False,
                'error': 'bulk_update_failed',
                'message': str(e)
            }
    
    async def export_analytics_data(
        self,
        date_range: Dict[str, str],
        format: str = 'json',
        auth_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """分析データエクスポート
        
        Args:
            date_range: 日付範囲
            format: エクスポート形式
            auth_token: 認証トークン
            
        Returns:
            エクスポート結果
        """
        try:
            self.logger.info(f"データエクスポート開始: format={format}")
            
            # 認証チェック
            if auth_token:
                auth_result = await self._verify_admin_auth(auth_token)
                if not auth_result['success']:
                    return auth_result
            
            # データ取得（簡易実装）
            start_date = datetime.fromisoformat(date_range['start'])
            end_date = datetime.fromisoformat(date_range['end'])
            
            export_data = []
            analyses = self.db_session.query(ContactAIAnalysis).filter(
                and_(
                    ContactAIAnalysis.processed_at >= start_date,
                    ContactAIAnalysis.processed_at <= end_date
                )
            ).all()
            
            for analysis in analyses:
                export_data.append({
                    'contact_id': analysis.contact_id,
                    'category': analysis.category,
                    'urgency': analysis.urgency,
                    'confidence': analysis.confidence_score,
                    'sentiment': analysis.sentiment,
                    'processed_at': analysis.processed_at.isoformat() if analysis.processed_at else None
                })
            
            if format == 'json':
                result = {
                    'success': True,
                    'export_data': export_data,
                    'total_records': len(export_data),
                    'date_range': date_range,
                    'generated_at': datetime.now().isoformat()
                }
            else:
                # CSV等の他の形式は実装省略
                result = {
                    'success': True,
                    'export_url': f'/exports/analytics_{int(time.time())}.{format}',
                    'total_records': len(export_data)
                }
            
            self.logger.info(f"データエクスポート完了: records={len(export_data)}")
            return result
            
        except Exception as e:
            self.logger.error(f"データエクスポートエラー: {e}")
            return {
                'success': False,
                'error': 'export_failed',
                'message': str(e)
            }
    
    def _validate_pagination_params(self, page: int, per_page: int) -> Dict[str, Any]:
        """ページネーションパラメータ検証"""
        if page < 1:
            return {
                'valid': False,
                'message': 'Page number must be positive'
            }
        
        if per_page < 1 or per_page > self.max_per_page:
            return {
                'valid': False,
                'message': f'Per page must be between 1 and {self.max_per_page}'
            }
        
        return {'valid': True}
    
    def _apply_contact_filters(
        self,
        query,
        status_filter: Optional[str],
        category_filter: Optional[str],
        urgency_filter: Optional[int],
        date_from: Optional[str],
        date_to: Optional[str]
    ):
        """コンタクトフィルタ適用"""
        if status_filter:
            query = query.filter(Contact.status == status_filter)
        
        if date_from:
            start_date = datetime.fromisoformat(date_from)
            query = query.filter(Contact.created_at >= start_date)
        
        if date_to:
            end_date = datetime.fromisoformat(date_to)
            query = query.filter(Contact.created_at <= end_date)
        
        # AI解析結果でのフィルタ
        if category_filter or urgency_filter:
            query = query.join(ContactAIAnalysis)
            if category_filter:
                query = query.filter(ContactAIAnalysis.category == category_filter)
            if urgency_filter:
                query = query.filter(ContactAIAnalysis.urgency == urgency_filter)
        
        return query
    
    async def _verify_admin_auth(
        self,
        auth_token: str,
        required_role: str = 'admin'
    ) -> Dict[str, Any]:
        """管理者認証検証"""
        try:
            if not self.firebase_auth:
                return {'success': True}  # 認証無効時はスキップ
            
            auth_result = self.firebase_auth.verify_admin_token(auth_token)
            
            if not auth_result:
                return {
                    'success': False,
                    'error': 'authentication_failed',
                    'message': 'Invalid authentication token'
                }
            
            user_role = auth_result.get('role', 'user')
            
            if required_role == 'admin' and user_role not in ['admin', 'super_admin']:
                return {
                    'success': False,
                    'error': 'insufficient_permissions',
                    'message': 'Admin role required'
                }
            
            return {'success': True, 'user': auth_result}
            
        except Exception as e:
            self.logger.error(f"認証エラー: {e}")
            return {
                'success': False,
                'error': 'authentication_failed',
                'message': str(e)
            }
    
    def _get_cached_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """キャッシュ結果取得"""
        if not self.enable_caching:
            return None
        
        if cache_key not in self.cache:
            return None
        
        cache_time = self.cache_timestamps.get(cache_key, 0)
        if time.time() - cache_time > self.cache_ttl:
            del self.cache[cache_key]
            del self.cache_timestamps[cache_key]
            return None
        
        return self.cache[cache_key]
    
    def _cache_result(self, cache_key: str, result: Dict[str, Any]) -> None:
        """キャッシュ結果保存"""
        if not self.enable_caching:
            return
        
        self.cache[cache_key] = result
        self.cache_timestamps[cache_key] = time.time()