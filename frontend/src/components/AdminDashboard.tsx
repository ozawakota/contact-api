import React, { useState, useEffect } from 'react';
import { ContactResponse, ContactListResponse, SystemStatus, HealthStatus } from '../types';
import { ApiService } from '../services/api';
import LoadingSpinner from './LoadingSpinner';
import ContactList from './ContactList';
import SystemStatusDisplay from './SystemStatusDisplay';
import AIAnalysisDisplay from './AIAnalysisDisplay';
import VectorSearch from './VectorSearch';
import SimilarContactsList from './SimilarContactsList';
import toast from 'react-hot-toast';
import { format } from 'date-fns';

interface AdminDashboardProps {
  className?: string;
}

type DashboardTab = 'overview' | 'contacts' | 'search' | 'system';

const AdminDashboard: React.FC<AdminDashboardProps> = ({ className = '' }) => {
  const [activeTab, setActiveTab] = useState<DashboardTab>('overview');
  const [contacts, setContacts] = useState<ContactResponse[]>([]);
  const [contactsLoading, setContactsLoading] = useState(true);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null);
  const [selectedContact, setSelectedContact] = useState<ContactResponse | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  // Load initial data
  useEffect(() => {
    loadDashboardData();
  }, [refreshKey]);

  const loadDashboardData = async () => {
    setContactsLoading(true);
    
    try {
      // Load contacts and system status in parallel
      const [contactsRes, systemRes, healthRes] = await Promise.all([
        ApiService.getContacts(),
        ApiService.getSystemStatus(),
        ApiService.getHealthStatus()
      ]);

      setContacts(contactsRes.contacts);
      setSystemStatus(systemRes);
      setHealthStatus(healthRes);
      
    } catch (error: any) {
      console.error('Dashboard load error:', error);
      toast.error('ダッシュボードデータの読み込みに失敗しました');
    } finally {
      setContactsLoading(false);
    }
  };

  const handleRefresh = () => {
    setRefreshKey(prev => prev + 1);
    toast.success('データを更新しました');
  };

  const handleContactSelect = async (contactId: string) => {
    try {
      const contact = await ApiService.getContact(contactId);
      setSelectedContact(contact);
      setActiveTab('contacts');
    } catch (error) {
      toast.error('お問い合わせの詳細取得に失敗しました');
    }
  };

  // Calculate dashboard statistics
  const stats = React.useMemo(() => {
    const total = contacts.length;
    const pending = contacts.filter(c => c.status === 'pending').length;
    const urgent = contacts.filter(c => 
      c.ai_analysis?.urgency === 'urgent' || c.ai_analysis?.urgency === 'high'
    ).length;
    
    const categoryBreakdown = contacts.reduce((acc, contact) => {
      const category = contact.ai_analysis?.category || 'unknown';
      acc[category] = (acc[category] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);

    const avgConfidence = contacts.length > 0 
      ? contacts
          .filter(c => c.ai_analysis?.confidence_score)
          .reduce((sum, c) => sum + (c.ai_analysis?.confidence_score || 0), 0) / contacts.length
      : 0;

    return {
      total,
      pending,
      urgent,
      categoryBreakdown,
      avgConfidence
    };
  }, [contacts]);

  const tabs = [
    { id: 'overview' as DashboardTab, label: '概要', icon: '📊' },
    { id: 'contacts' as DashboardTab, label: 'お問い合わせ', icon: '📧' },
    { id: 'search' as DashboardTab, label: '検索', icon: '🔍' },
    { id: 'system' as DashboardTab, label: 'システム', icon: '⚙️' }
  ];

  if (contactsLoading && !contacts.length) {
    return (
      <div className={`flex items-center justify-center py-12 ${className}`}>
        <div className="text-center">
          <LoadingSpinner size="lg" />
          <p className="mt-2 text-gray-600">ダッシュボードを読み込み中...</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">管理者ダッシュボード</h1>
          <p className="text-gray-600">次世代カスタマーサポートシステム</p>
        </div>
        <div className="flex space-x-3">
          <button
            onClick={handleRefresh}
            className="btn-secondary"
            disabled={contactsLoading}
          >
            {contactsLoading ? (
              <LoadingSpinner size="sm" className="mr-2" />
            ) : (
              <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            )}
            更新
          </button>
          <div className="text-sm text-gray-500">
            最終更新: {format(new Date(), 'HH:mm:ss')}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`py-2 px-1 border-b-2 font-medium text-sm ${
                activeTab === tab.id
                  ? 'border-primary-500 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <span className="mr-2">{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          {/* Statistics Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="card bg-blue-50 border-blue-200">
              <div className="flex items-center">
                <div className="p-2 bg-blue-100 rounded-lg">
                  <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
                  </svg>
                </div>
                <div className="ml-3">
                  <p className="text-sm font-medium text-gray-600">総お問い合わせ数</p>
                  <p className="text-2xl font-bold text-gray-900">{stats.total}</p>
                </div>
              </div>
            </div>

            <div className="card bg-yellow-50 border-yellow-200">
              <div className="flex items-center">
                <div className="p-2 bg-yellow-100 rounded-lg">
                  <svg className="w-6 h-6 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <div className="ml-3">
                  <p className="text-sm font-medium text-gray-600">未対応</p>
                  <p className="text-2xl font-bold text-gray-900">{stats.pending}</p>
                </div>
              </div>
            </div>

            <div className="card bg-red-50 border-red-200">
              <div className="flex items-center">
                <div className="p-2 bg-red-100 rounded-lg">
                  <svg className="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
                  </svg>
                </div>
                <div className="ml-3">
                  <p className="text-sm font-medium text-gray-600">緊急・高優先度</p>
                  <p className="text-2xl font-bold text-gray-900">{stats.urgent}</p>
                </div>
              </div>
            </div>

            <div className="card bg-green-50 border-green-200">
              <div className="flex items-center">
                <div className="p-2 bg-green-100 rounded-lg">
                  <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                  </svg>
                </div>
                <div className="ml-3">
                  <p className="text-sm font-medium text-gray-600">AI信頼度平均</p>
                  <p className="text-2xl font-bold text-gray-900">{Math.round(stats.avgConfidence * 100)}%</p>
                </div>
              </div>
            </div>
          </div>

          {/* Category Breakdown */}
          {Object.keys(stats.categoryBreakdown).length > 0 && (
            <div className="card">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">カテゴリ別お問い合わせ数</h3>
              <div className="space-y-3">
                {Object.entries(stats.categoryBreakdown).map(([category, count]) => {
                  const percentage = stats.total > 0 ? (count / stats.total * 100) : 0;
                  const categoryLabels: Record<string, string> = {
                    'general': '一般',
                    'technical': '技術',
                    'billing': '請求',
                    'support': 'サポート',
                    'complaint': '苦情',
                    'unknown': '未分類'
                  };
                  
                  return (
                    <div key={category} className="flex items-center">
                      <div className="w-24 text-sm font-medium text-gray-700">
                        {categoryLabels[category] || category}
                      </div>
                      <div className="flex-1 mx-3">
                        <div className="bg-gray-200 rounded-full h-2">
                          <div 
                            className="bg-primary-600 h-2 rounded-full transition-all duration-300"
                            style={{ width: `${percentage}%` }}
                          ></div>
                        </div>
                      </div>
                      <div className="w-12 text-sm text-gray-600 text-right">
                        {count}件
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Recent Contacts */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900">最近のお問い合わせ</h3>
              <button
                onClick={() => setActiveTab('contacts')}
                className="text-sm text-primary-600 hover:text-primary-700"
              >
                すべて表示 →
              </button>
            </div>
            <ContactList 
              contacts={contacts.slice(0, 5)} 
              compact={true}
              onContactSelect={handleContactSelect}
            />
          </div>
        </div>
      )}

      {activeTab === 'contacts' && (
        <div className="space-y-6">
          {selectedContact ? (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-semibold text-gray-900">
                  お問い合わせ詳細
                </h2>
                <button
                  onClick={() => setSelectedContact(null)}
                  className="btn-secondary"
                >
                  ← 一覧に戻る
                </button>
              </div>

              <div className="card">
                <div className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700">お問い合わせID</label>
                      <p className="mt-1 text-sm font-mono text-gray-900">{selectedContact.id}</p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700">作成日時</label>
                      <p className="mt-1 text-sm text-gray-900">
                        {format(new Date(selectedContact.created_at), 'yyyy/MM/dd HH:mm')}
                      </p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700">お名前</label>
                      <p className="mt-1 text-sm text-gray-900">{selectedContact.name}</p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700">メールアドレス</label>
                      <p className="mt-1 text-sm text-gray-900">{selectedContact.email}</p>
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700">件名</label>
                    <p className="mt-1 text-sm text-gray-900">{selectedContact.subject}</p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700">内容</label>
                    <div className="mt-1 p-3 bg-gray-50 rounded-md">
                      <p className="text-sm text-gray-900 whitespace-pre-wrap">{selectedContact.message}</p>
                    </div>
                  </div>
                </div>
              </div>

              {selectedContact.ai_analysis && (
                <AIAnalysisDisplay analysis={selectedContact.ai_analysis} />
              )}

              {selectedContact.similar_contacts && selectedContact.similar_contacts.length > 0 && (
                <SimilarContactsList 
                  contacts={selectedContact.similar_contacts}
                  showViewButton={true}
                  onViewContact={handleContactSelect}
                />
              )}
            </div>
          ) : (
            <ContactList 
              contacts={contacts} 
              onContactSelect={handleContactSelect}
              loading={contactsLoading}
            />
          )}
        </div>
      )}

      {activeTab === 'search' && (
        <VectorSearch onContactSelect={handleContactSelect} />
      )}

      {activeTab === 'system' && (
        <SystemStatusDisplay 
          systemStatus={systemStatus}
          healthStatus={healthStatus}
          onRefresh={handleRefresh}
        />
      )}
    </div>
  );
};

export default AdminDashboard;