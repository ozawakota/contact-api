import React from 'react';
import { SystemStatus, HealthStatus } from '../types';
import LoadingSpinner from './LoadingSpinner';

interface SystemStatusDisplayProps {
  systemStatus: SystemStatus | null;
  healthStatus: HealthStatus | null;
  onRefresh?: () => void;
  className?: string;
}

const SystemStatusDisplay: React.FC<SystemStatusDisplayProps> = ({ 
  systemStatus, 
  healthStatus,
  onRefresh,
  className = '' 
}) => {
  const getStatusColor = (isActive: boolean, isConnected?: boolean) => {
    if (isConnected === false) return 'text-red-600 bg-red-100';
    return isActive ? 'text-green-600 bg-green-100' : 'text-gray-600 bg-gray-100';
  };

  const getStatusIcon = (isActive: boolean, isConnected?: boolean) => {
    if (isConnected === false) return '🔴';
    return isActive ? '✅' : '❌';
  };

  const getFeatureStatus = (enabled: boolean) => {
    return enabled ? '🟢 有効' : '🔴 無効';
  };

  if (!systemStatus || !healthStatus) {
    return (
      <div className={`flex items-center justify-center py-8 ${className}`}>
        <LoadingSpinner size="lg" />
        <span className="ml-2 text-gray-600">システム状態を読み込み中...</span>
      </div>
    );
  }

  return (
    <div className={`space-y-6 ${className}`}>
      {/* System Overview */}
      <div className="card">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold text-gray-900">システム状態</h2>
          {onRefresh && (
            <button onClick={onRefresh} className="btn-secondary text-sm">
              <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              更新
            </button>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
          <div className="bg-gray-50 rounded-lg p-4">
            <div className="text-sm text-gray-600 mb-1">サービス</div>
            <div className="font-medium text-gray-900">{healthStatus?.service || 'Unknown'}</div>
          </div>
          <div className="bg-gray-50 rounded-lg p-4">
            <div className="text-sm text-gray-600 mb-1">バージョン</div>
            <div className="font-medium text-gray-900">{systemStatus?.version || 'Unknown'}</div>
          </div>
          <div className="bg-gray-50 rounded-lg p-4">
            <div className="text-sm text-gray-600 mb-1">環境</div>
            <div className="font-medium text-gray-900">{systemStatus?.environment || 'Unknown'}</div>
          </div>
        </div>

        <div className="text-sm text-gray-600">
          <div className="font-medium mb-2">実装機能:</div>
          <div className="flex flex-wrap gap-2">
            {systemStatus.features && systemStatus.features.length > 0 ? (
              systemStatus.features.map((feature, index) => (
                <span key={index} className="badge bg-blue-100 text-blue-800">
                  {feature}
                </span>
              ))
            ) : (
              <span className="text-gray-500 text-xs">機能情報を取得中...</span>
            )}
          </div>
        </div>
      </div>

      {/* Service Status */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Firebase Status */}
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <span className="mr-2">🔐</span>
            Firebase認証
          </h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">ライブラリ利用可能</span>
              <span className={`badge ${getStatusColor(systemStatus?.firebase_status?.available ?? false)}`}>
                {getStatusIcon(systemStatus?.firebase_status?.available ?? false)} 
                {systemStatus?.firebase_status?.available ? '利用可能' : '利用不可'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">初期化状態</span>
              <span className={`badge ${getStatusColor(systemStatus?.firebase_status?.initialized ?? false)}`}>
                {getStatusIcon(systemStatus?.firebase_status?.initialized ?? false)}
                {systemStatus?.firebase_status?.initialized ? '初期化済み' : '未初期化'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">認証モード</span>
              <span className="text-sm text-gray-900">{healthStatus?.auth_mode || 'Unknown'}</span>
            </div>
          </div>
        </div>

        {/* Database Status */}
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <span className="mr-2">🗄️</span>
            データベース
          </h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">ライブラリ利用可能</span>
              <span className={`badge ${getStatusColor(systemStatus.database_status.available)}`}>
                {getStatusIcon(systemStatus.database_status.available)}
                {systemStatus.database_status.available ? '利用可能' : '利用不可'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">接続状態</span>
              <span className={`badge ${getStatusColor(systemStatus.database_status.initialized, systemStatus.database_status.connected)}`}>
                {getStatusIcon(systemStatus.database_status.initialized, systemStatus.database_status.connected)}
                {systemStatus.database_status.connected ? '接続中' : '未接続'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">ストレージモード</span>
              <span className="text-sm text-gray-900">{healthStatus.storage_mode}</span>
            </div>
          </div>
        </div>

        {/* AI Status */}
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <span className="mr-2">🤖</span>
            AI分析機能
          </h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">ライブラリ利用可能</span>
              <span className={`badge ${getStatusColor(systemStatus.ai_status.available)}`}>
                {getStatusIcon(systemStatus.ai_status.available)}
                {systemStatus.ai_status.available ? '利用可能' : '利用不可'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">初期化状態</span>
              <span className={`badge ${getStatusColor(systemStatus.ai_status.initialized)}`}>
                {getStatusIcon(systemStatus.ai_status.initialized)}
                {systemStatus.ai_status.initialized ? '初期化済み' : '未初期化'}
              </span>
            </div>
            {systemStatus.ai_status.model && (
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">モデル</span>
                <span className="text-sm text-gray-900 font-mono">{systemStatus.ai_status.model}</span>
              </div>
            )}
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">AIモード</span>
              <span className="text-sm text-gray-900">{healthStatus.ai_mode}</span>
            </div>
          </div>
        </div>

        {/* Vector Search Status */}
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <span className="mr-2">🔍</span>
            ベクター検索
          </h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">ライブラリ利用可能</span>
              <span className={`badge ${getStatusColor(systemStatus.vector_status.available)}`}>
                {getStatusIcon(systemStatus.vector_status.available)}
                {systemStatus.vector_status.available ? '利用可能' : '利用不可'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">初期化状態</span>
              <span className={`badge ${getStatusColor(systemStatus.vector_status.initialized)}`}>
                {getStatusIcon(systemStatus.vector_status.initialized)}
                {systemStatus.vector_status.initialized ? '初期化済み' : '未初期化'}
              </span>
            </div>
            {systemStatus.vector_status.model && (
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">埋め込みモデル</span>
                <span className="text-xs text-gray-900 font-mono">{systemStatus.vector_status.model}</span>
              </div>
            )}
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">ベクターモード</span>
              <span className="text-sm text-gray-900">{healthStatus.vector_mode}</span>
            </div>
          </div>
        </div>

        {/* Email Status */}
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <span className="mr-2">📧</span>
            メール通知
          </h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">ライブラリ利用可能</span>
              <span className={`badge ${getStatusColor(systemStatus.email_status.available)}`}>
                {getStatusIcon(systemStatus.email_status.available)}
                {systemStatus.email_status.available ? '利用可能' : '利用不可'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">初期化状態</span>
              <span className={`badge ${getStatusColor(systemStatus.email_status.initialized)}`}>
                {getStatusIcon(systemStatus.email_status.initialized)}
                {systemStatus.email_status.initialized ? '初期化済み' : '未初期化'}
              </span>
            </div>
            {systemStatus.email_status.service && (
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">サービス</span>
                <span className="text-sm text-gray-900">{systemStatus.email_status.service}</span>
              </div>
            )}
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">メールモード</span>
              <span className="text-sm text-gray-900">{healthStatus.email_mode}</span>
            </div>
          </div>
        </div>

        {/* Health Status */}
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <span className="mr-2">💚</span>
            機能有効状態
          </h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">CRUD操作</span>
              <span className="text-sm">{getFeatureStatus(healthStatus.features_enabled.crud_operations)}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">Firebase認証</span>
              <span className="text-sm">{getFeatureStatus(healthStatus.features_enabled.firebase_auth)}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">データベース</span>
              <span className="text-sm">{getFeatureStatus(healthStatus.features_enabled.database)}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">AI分析</span>
              <span className="text-sm">{getFeatureStatus(healthStatus.features_enabled.ai_analysis)}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">ベクター検索</span>
              <span className="text-sm">{getFeatureStatus(healthStatus.features_enabled.vector_search)}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">メール通知</span>
              <span className="text-sm">{getFeatureStatus(healthStatus.features_enabled.email_notifications)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Overall Status */}
      <div className="card bg-green-50 border-green-200">
        <div className="flex items-center">
          <div className="p-2 bg-green-100 rounded-lg">
            <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div className="ml-3">
            <h3 className="text-lg font-medium text-green-800">システム正常稼働中</h3>
            <p className="text-sm text-green-700">
              すべてのコアサービスが正常に動作しています。
              {healthStatus.port && ` ポート: ${healthStatus.port}`}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SystemStatusDisplay;