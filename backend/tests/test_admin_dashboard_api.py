"""管理ダッシュボードAPIのテスト

認証済み管理者用のREST APIエンドポイント群のテスト実装。
お問い合わせ履歴・AI分類結果・統計データ・分析情報のAPI機能をテストします。
"""
import pytest
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

# テスト対象モジュールのインポート
from models.contact import Contact
from models.contact_ai_analysis import ContactAIAnalysis
from models.contact_vector import ContactVector


@pytest.fixture
def mock_db_session():
    """モックデータベースセッション"""
    mock_session = MagicMock()
    return mock_session


@pytest.fixture
def mock_firebase_auth():
    """モックFirebase認証"""
    mock_auth = MagicMock()
    mock_auth.verify_admin_token.return_value = {
        'uid': 'admin123',
        'email': 'admin@example.com',
        'role': 'admin'
    }
    return mock_auth


@pytest.fixture
def sample_contacts():
    """テスト用Contact一覧"""
    return [
        Contact(
            id=1,
            name="山田太郎",
            email="yamada@example.com",
            subject="商品の不具合について",
            message="商品に不具合があります",
            status="analyzed",
            priority=3,
            created_at=datetime.now() - timedelta(hours=1)
        ),
        Contact(
            id=2,
            name="佐藤花子",
            email="sato@example.com",
            subject="配送について",
            message="配送が遅れています",
            status="pending",
            priority=2,
            created_at=datetime.now() - timedelta(hours=2)
        ),
        Contact(
            id=3,
            name="田中次郎",
            email="tanaka@example.com",
            subject="返品について",
            message="商品を返品したいです",
            status="resolved",
            priority=1,
            created_at=datetime.now() - timedelta(hours=3)
        )
    ]


@pytest.fixture
def sample_ai_analyses():
    """テスト用AI解析結果一覧"""
    return [
        ContactAIAnalysis(
            id=1,
            contact_id=1,
            category="product",
            urgency=3,
            sentiment="negative",
            confidence_score=0.95,
            summary="商品不具合の緊急対応要求",
            processed_at=datetime.now() - timedelta(minutes=50)
        ),
        ContactAIAnalysis(
            id=2,
            contact_id=2,
            category="shipping",
            urgency=2,
            sentiment="neutral",
            confidence_score=0.87,
            summary="配送遅延の問い合わせ",
            processed_at=datetime.now() - timedelta(minutes=110)
        )
    ]


class TestAdminDashboardAPI:
    """管理ダッシュボードAPIの基本機能テスト"""

    @pytest.fixture
    def admin_api(self, mock_db_session, mock_firebase_auth):
        """AdminDashboardAPIインスタンス"""
        from api.admin_dashboard import AdminDashboardAPI
        return AdminDashboardAPI(
            db_session=mock_db_session,
            firebase_auth=mock_firebase_auth
        )

    @pytest.mark.asyncio
    async def test_api_initialization(self, mock_db_session, mock_firebase_auth):
        """AdminDashboardAPI初期化テスト"""
        from api.admin_dashboard import AdminDashboardAPI
        api = AdminDashboardAPI(
            db_session=mock_db_session,
            firebase_auth=mock_firebase_auth
        )
        assert api.db_session == mock_db_session
        assert api.firebase_auth == mock_firebase_auth

    @pytest.mark.asyncio
    async def test_get_contacts_list_with_pagination(self, admin_api, sample_contacts, mock_db_session):
        """お問い合わせ履歴一覧取得（ページネーション）テスト"""
        # モッククエリ結果設定
        mock_query = MagicMock()
        mock_query.offset.return_value.limit.return_value.all.return_value = sample_contacts[:2]
        mock_query.count.return_value = len(sample_contacts)
        mock_db_session.query.return_value = mock_query
        
        result = await admin_api.get_contacts_list(
            page=1,
            per_page=2,
            status_filter=None,
            category_filter=None
        )
        
        assert result['success'] is True
        assert result['total_count'] == 3
        assert result['page'] == 1
        assert result['per_page'] == 2
        assert len(result['contacts']) == 2
        assert result['total_pages'] == 2

    @pytest.mark.asyncio
    async def test_get_contacts_list_with_filters(self, admin_api, sample_contacts, mock_db_session):
        """お問い合わせ履歴一覧取得（フィルタ）テスト"""
        # ステータスフィルタ
        filtered_contacts = [c for c in sample_contacts if c.status == "analyzed"]
        mock_query = MagicMock()
        mock_query.filter.return_value.offset.return_value.limit.return_value.all.return_value = filtered_contacts
        mock_query.filter.return_value.count.return_value = len(filtered_contacts)
        mock_db_session.query.return_value = mock_query
        
        result = await admin_api.get_contacts_list(
            page=1,
            per_page=10,
            status_filter="analyzed",
            category_filter=None
        )
        
        assert result['success'] is True
        assert len(result['contacts']) == 1
        assert result['contacts'][0]['status'] == "analyzed"

    @pytest.mark.asyncio
    async def test_get_contact_detail(self, admin_api, sample_contacts, sample_ai_analyses, mock_db_session):
        """お問い合わせ詳細取得テスト"""
        contact = sample_contacts[0]
        ai_analysis = sample_ai_analyses[0]
        
        # モック設定
        mock_db_session.get.return_value = contact
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = ai_analysis
        
        result = await admin_api.get_contact_detail(contact_id=1)
        
        assert result['success'] is True
        assert result['contact']['id'] == 1
        assert result['contact']['name'] == "山田太郎"
        assert result['ai_analysis'] is not None
        assert result['ai_analysis']['category'] == "product"
        assert result['ai_analysis']['urgency'] == 3

    @pytest.mark.asyncio
    async def test_get_contact_detail_not_found(self, admin_api, mock_db_session):
        """存在しないお問い合わせ詳細取得テスト"""
        mock_db_session.get.return_value = None
        
        result = await admin_api.get_contact_detail(contact_id=999)
        
        assert result['success'] is False
        assert result['error'] == 'contact_not_found'

    @pytest.mark.asyncio
    async def test_update_contact_status(self, admin_api, sample_contacts, mock_db_session):
        """お問い合わせステータス更新テスト"""
        contact = sample_contacts[0]
        mock_db_session.get.return_value = contact
        
        result = await admin_api.update_contact_status(
            contact_id=1,
            new_status="resolved",
            admin_user_id="admin123",
            notes="手動で解決済みに変更"
        )
        
        assert result['success'] is True
        assert result['updated_status'] == "resolved"
        assert contact.status == "resolved"
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_ai_analysis_manual(self, admin_api, sample_ai_analyses, mock_db_session):
        """AI分類結果手動更新テスト"""
        ai_analysis = sample_ai_analyses[0]
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = ai_analysis
        
        result = await admin_api.update_ai_analysis_manual(
            contact_id=1,
            new_category="billing",
            new_urgency=1,
            new_sentiment="neutral",
            admin_user_id="admin123",
            notes="手動で分類を修正"
        )
        
        assert result['success'] is True
        assert result['updated_analysis']['category'] == "billing"
        assert result['updated_analysis']['urgency'] == 1
        assert ai_analysis.category == "billing"
        assert ai_analysis.urgency == 1

    @pytest.mark.asyncio
    async def test_get_analytics_overview(self, admin_api, mock_db_session):
        """統計データ概要取得テスト"""
        # モック統計データ
        mock_db_session.query.return_value.count.return_value = 150  # total_contacts
        mock_db_session.query.return_value.filter.return_value.count.side_effect = [75, 45, 30]  # analyzed, pending, resolved
        
        result = await admin_api.get_analytics_overview()
        
        assert result['success'] is True
        assert result['analytics']['total_contacts'] == 150
        assert result['analytics']['status_distribution']['analyzed'] == 75
        assert result['analytics']['status_distribution']['pending'] == 45
        assert result['analytics']['status_distribution']['resolved'] == 30

    @pytest.mark.asyncio
    async def test_get_ai_performance_metrics(self, admin_api, mock_db_session):
        """AI性能メトリクス取得テスト"""
        # モック性能データ
        mock_analyses = [
            MagicMock(confidence_score=0.95, category="product", urgency=3, processed_at=datetime.now()),
            MagicMock(confidence_score=0.87, category="shipping", urgency=2, processed_at=datetime.now()),
            MagicMock(confidence_score=0.92, category="billing", urgency=1, processed_at=datetime.now())
        ]
        mock_db_session.query.return_value.all.return_value = mock_analyses
        
        result = await admin_api.get_ai_performance_metrics()
        
        assert result['success'] is True
        assert 'average_confidence' in result['metrics']
        assert 'category_distribution' in result['metrics']
        assert 'urgency_distribution' in result['metrics']
        assert 'processing_statistics' in result['metrics']

    @pytest.mark.asyncio
    async def test_get_processing_time_analysis(self, admin_api, mock_db_session):
        """処理時間分析取得テスト"""
        # モック処理時間データ
        mock_analyses = [
            MagicMock(processing_time_ms=1500, created_at=datetime.now(), processed_at=datetime.now()),
            MagicMock(processing_time_ms=2300, created_at=datetime.now(), processed_at=datetime.now()),
            MagicMock(processing_time_ms=1800, created_at=datetime.now(), processed_at=datetime.now())
        ]
        mock_db_session.query.return_value.all.return_value = mock_analyses
        
        result = await admin_api.get_processing_time_analysis()
        
        assert result['success'] is True
        assert 'average_processing_time_ms' in result['analysis']
        assert 'median_processing_time_ms' in result['analysis']
        assert 'max_processing_time_ms' in result['analysis']
        assert 'within_sla_percentage' in result['analysis']

    @pytest.mark.asyncio
    async def test_get_category_analysis(self, admin_api, mock_db_session):
        """カテゴリ分布分析取得テスト"""
        # モックカテゴリデータ
        mock_category_counts = [
            ("product", 45),
            ("shipping", 32),
            ("billing", 18),
            ("other", 5)
        ]
        mock_db_session.query.return_value.group_by.return_value.all.return_value = mock_category_counts
        
        result = await admin_api.get_category_analysis()
        
        assert result['success'] is True
        assert result['analysis']['category_distribution']['product'] == 45
        assert result['analysis']['category_distribution']['shipping'] == 32
        assert result['analysis']['total_analyzed'] == 100

    @pytest.mark.asyncio
    async def test_authentication_required(self, admin_api, mock_firebase_auth):
        """認証必須確認テスト"""
        # 無効トークンのシミュレート
        mock_firebase_auth.verify_admin_token.side_effect = Exception("Invalid token")
        
        result = await admin_api.get_contacts_list(
            page=1,
            per_page=10,
            auth_token="invalid_token"
        )
        
        assert result['success'] is False
        assert result['error'] == 'authentication_failed'

    @pytest.mark.asyncio
    async def test_admin_role_required(self, admin_api, mock_firebase_auth):
        """管理者権限必須確認テスト"""
        # 一般ユーザーのシミュレート
        mock_firebase_auth.verify_admin_token.return_value = {
            'uid': 'user123',
            'email': 'user@example.com',
            'role': 'user'  # 管理者ではない
        }
        
        result = await admin_api.get_contacts_list(
            page=1,
            per_page=10,
            auth_token="user_token"
        )
        
        assert result['success'] is False
        assert result['error'] == 'insufficient_permissions'


class TestAdminDashboardAPIIntegration:
    """管理ダッシュボードAPI統合テスト"""

    @pytest.fixture
    def integration_api(self, mock_db_session, mock_firebase_auth):
        """統合テスト用AdminDashboardAPIインスタンス"""
        from api.admin_dashboard import AdminDashboardAPI
        return AdminDashboardAPI(
            db_session=mock_db_session,
            firebase_auth=mock_firebase_auth,
            enable_caching=True,
            cache_ttl=300
        )

    @pytest.mark.asyncio
    async def test_full_contact_management_workflow(self, integration_api, sample_contacts, sample_ai_analyses, mock_db_session):
        """コンタクト管理フルワークフローテスト"""
        contact = sample_contacts[0]
        ai_analysis = sample_ai_analyses[0]
        
        # 1. コンタクト一覧取得
        mock_query = MagicMock()
        mock_query.offset.return_value.limit.return_value.all.return_value = [contact]
        mock_query.count.return_value = 1
        mock_db_session.query.return_value = mock_query
        
        list_result = await integration_api.get_contacts_list(page=1, per_page=10)
        assert list_result['success'] is True
        
        # 2. コンタクト詳細取得
        mock_db_session.get.return_value = contact
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = ai_analysis
        
        detail_result = await integration_api.get_contact_detail(contact_id=1)
        assert detail_result['success'] is True
        
        # 3. ステータス更新
        update_result = await integration_api.update_contact_status(
            contact_id=1,
            new_status="resolved",
            admin_user_id="admin123"
        )
        assert update_result['success'] is True

    @pytest.mark.asyncio
    async def test_analytics_dashboard_data(self, integration_api, mock_db_session):
        """分析ダッシュボードデータ統合テスト"""
        # 概要統計
        mock_db_session.query.return_value.count.return_value = 200
        mock_db_session.query.return_value.filter.return_value.count.side_effect = [120, 50, 30]
        
        overview_result = await integration_api.get_analytics_overview()
        assert overview_result['success'] is True
        
        # AI性能メトリクス
        mock_analyses = [MagicMock(confidence_score=0.9, category="product") for _ in range(10)]
        mock_db_session.query.return_value.all.return_value = mock_analyses
        
        metrics_result = await integration_api.get_ai_performance_metrics()
        assert metrics_result['success'] is True
        
        # 処理時間分析
        time_result = await integration_api.get_processing_time_analysis()
        assert time_result['success'] is True

    @pytest.mark.asyncio
    async def test_bulk_status_updates(self, integration_api, sample_contacts, mock_db_session):
        """一括ステータス更新テスト"""
        contact_ids = [1, 2, 3]
        contacts = sample_contacts
        
        mock_db_session.query.return_value.filter.return_value.all.return_value = contacts
        
        result = await integration_api.bulk_update_contact_status(
            contact_ids=contact_ids,
            new_status="reviewed",
            admin_user_id="admin123",
            notes="一括レビュー済み"
        )
        
        assert result['success'] is True
        assert result['updated_count'] == 3
        assert all(c.status == "reviewed" for c in contacts)

    @pytest.mark.asyncio
    async def test_export_analytics_data(self, integration_api, mock_db_session):
        """分析データエクスポートテスト"""
        # エクスポート用データ準備
        export_data = [
            {
                'contact_id': 1,
                'category': 'product',
                'urgency': 3,
                'confidence': 0.95,
                'processing_time': 1500
            },
            {
                'contact_id': 2,
                'category': 'shipping',
                'urgency': 2,
                'confidence': 0.87,
                'processing_time': 2300
            }
        ]
        
        result = await integration_api.export_analytics_data(
            date_range={'start': '2024-01-01', 'end': '2024-12-31'},
            format='json'
        )
        
        assert result['success'] is True
        assert 'export_url' in result or 'export_data' in result

    @pytest.mark.asyncio
    async def test_real_time_dashboard_updates(self, integration_api, mock_db_session):
        """リアルタイムダッシュボード更新テスト"""
        # WebSocket風のリアルタイム更新シミュレーション
        initial_stats = await integration_api.get_analytics_overview()
        
        # 新しいコンタクトが追加されたシミュレーション
        mock_db_session.query.return_value.count.return_value = 151  # +1
        
        updated_stats = await integration_api.get_analytics_overview()
        
        assert updated_stats['analytics']['total_contacts'] == 151
        assert updated_stats['analytics']['total_contacts'] > initial_stats['analytics']['total_contacts']


class TestAdminDashboardAPIError:
    """管理ダッシュボードAPIエラーハンドリングテスト"""

    @pytest.fixture
    def error_api(self, mock_db_session, mock_firebase_auth):
        """エラーテスト用AdminDashboardAPIインスタンス"""
        from api.admin_dashboard import AdminDashboardAPI
        return AdminDashboardAPI(
            db_session=mock_db_session,
            firebase_auth=mock_firebase_auth
        )

    @pytest.mark.asyncio
    async def test_database_connection_error(self, error_api, mock_db_session):
        """データベース接続エラーテスト"""
        mock_db_session.query.side_effect = Exception("Database connection failed")
        
        result = await error_api.get_contacts_list(page=1, per_page=10)
        
        assert result['success'] is False
        assert result['error'] == 'database_error'

    @pytest.mark.asyncio
    async def test_invalid_pagination_parameters(self, error_api):
        """不正なページネーションパラメータテスト"""
        # 負のページ番号
        result1 = await error_api.get_contacts_list(page=-1, per_page=10)
        assert result1['success'] is False
        assert result1['error'] == 'invalid_parameters'
        
        # 過大なper_page
        result2 = await error_api.get_contacts_list(page=1, per_page=1000)
        assert result2['success'] is False
        assert result2['error'] == 'invalid_parameters'

    @pytest.mark.asyncio
    async def test_unauthorized_status_update(self, error_api, mock_firebase_auth, mock_db_session):
        """権限なしステータス更新テスト"""
        # 読み取り専用ユーザー
        mock_firebase_auth.verify_admin_token.return_value = {
            'uid': 'readonly123',
            'role': 'readonly'
        }
        
        result = await error_api.update_contact_status(
            contact_id=1,
            new_status="resolved",
            admin_user_id="readonly123"
        )
        
        assert result['success'] is False
        assert result['error'] == 'insufficient_permissions'

    @pytest.mark.asyncio
    async def test_concurrent_update_conflict(self, error_api, sample_contacts, mock_db_session):
        """同時更新競合テスト"""
        contact = sample_contacts[0]
        contact.updated_at = datetime.now() + timedelta(seconds=1)  # 他で更新済み
        mock_db_session.get.return_value = contact
        
        result = await error_api.update_contact_status(
            contact_id=1,
            new_status="resolved",
            admin_user_id="admin123",
            expected_version=datetime.now()  # 古いバージョン
        )
        
        assert result['success'] is False
        assert result['error'] == 'version_conflict'


class TestAdminDashboardAPIPerformance:
    """管理ダッシュボードAPIパフォーマンステスト"""

    @pytest.mark.asyncio
    async def test_large_dataset_pagination(self, mock_db_session, mock_firebase_auth):
        """大量データのページネーションテスト"""
        from api.admin_dashboard import AdminDashboardAPI
        api = AdminDashboardAPI(
            db_session=mock_db_session,
            firebase_auth=mock_firebase_auth
        )
        
        # 10,000件のシミュレーション
        mock_query = MagicMock()
        mock_query.offset.return_value.limit.return_value.all.return_value = []  # 空リスト
        mock_query.count.return_value = 10000
        mock_db_session.query.return_value = mock_query
        
        result = await api.get_contacts_list(page=100, per_page=50)
        
        assert result['success'] is True
        assert result['total_count'] == 10000
        assert result['total_pages'] == 200

    @pytest.mark.asyncio
    async def test_analytics_computation_performance(self, mock_db_session, mock_firebase_auth):
        """分析計算パフォーマンステスト"""
        from api.admin_dashboard import AdminDashboardAPI
        import time
        
        api = AdminDashboardAPI(
            db_session=mock_db_session,
            firebase_auth=mock_firebase_auth
        )
        
        # 大量データの分析シミュレーション
        mock_analyses = [MagicMock(confidence_score=0.9, category="product") for _ in range(1000)]
        mock_db_session.query.return_value.all.return_value = mock_analyses
        
        start_time = time.time()
        result = await api.get_ai_performance_metrics()
        processing_time = time.time() - start_time
        
        assert result['success'] is True
        assert processing_time < 5.0  # 5秒以内

    @pytest.mark.asyncio
    async def test_concurrent_api_requests(self, mock_db_session, mock_firebase_auth):
        """同時API リクエスト処理テスト"""
        from api.admin_dashboard import AdminDashboardAPI
        import asyncio
        
        api = AdminDashboardAPI(
            db_session=mock_db_session,
            firebase_auth=mock_firebase_auth
        )
        
        # モック設定
        mock_query = MagicMock()
        mock_query.offset.return_value.limit.return_value.all.return_value = []
        mock_query.count.return_value = 100
        mock_db_session.query.return_value = mock_query
        
        # 10個の同時リクエスト
        tasks = [
            api.get_contacts_list(page=i, per_page=10)
            for i in range(1, 11)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 全て正常に処理されることを確認
        successful_results = [r for r in results if not isinstance(r, Exception) and r.get('success')]
        assert len(successful_results) == 10