import React from 'react';
import { ContactResponse } from '../types';
import { format } from 'date-fns';
import LoadingSpinner from './LoadingSpinner';
import AIAnalysisDisplay from './AIAnalysisDisplay';

interface ContactListProps {
  contacts: ContactResponse[];
  onContactSelect?: (contactId: string) => void;
  loading?: boolean;
  compact?: boolean;
  className?: string;
}

const ContactList: React.FC<ContactListProps> = ({ 
  contacts, 
  onContactSelect,
  loading = false,
  compact = false,
  className = '' 
}) => {
  if (loading) {
    return (
      <div className={`flex items-center justify-center py-8 ${className}`}>
        <LoadingSpinner size="lg" />
        <span className="ml-2 text-gray-600">読み込み中...</span>
      </div>
    );
  }

  if (contacts.length === 0) {
    return (
      <div className={`text-center py-8 ${className}`}>
        <div className="text-4xl mb-4">📧</div>
        <h3 className="text-lg font-medium text-gray-900 mb-2">
          お問い合わせがありません
        </h3>
        <p className="text-gray-600">
          新しいお問い合わせをお待ちしています。
        </p>
      </div>
    );
  }

  const getStatusColor = (status: string) => {
    const statusMap = {
      'pending': 'bg-yellow-100 text-yellow-800',
      'in_progress': 'bg-blue-100 text-blue-800',
      'resolved': 'bg-green-100 text-green-800',
      'closed': 'bg-gray-100 text-gray-800'
    };
    return statusMap[status as keyof typeof statusMap] || 'bg-gray-100 text-gray-800';
  };

  const getStatusLabel = (status: string) => {
    const statusMap = {
      'pending': '未対応',
      'in_progress': '対応中',
      'resolved': '解決済み',
      'closed': '完了'
    };
    return statusMap[status as keyof typeof statusMap] || status;
  };

  return (
    <div className={`space-y-4 ${className}`}>
      {contacts.map((contact) => (
        <div 
          key={contact.id} 
          className={`card hover:shadow-md transition-shadow cursor-pointer ${
            onContactSelect ? 'hover:border-primary-200' : ''
          }`}
          onClick={() => onContactSelect?.(contact.id)}
        >
          <div className="flex items-start justify-between mb-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center space-x-2 mb-1">
                <span className="text-xs font-mono text-gray-500">{contact.id}</span>
                <span className={`badge ${getStatusColor(contact.status)}`}>
                  {getStatusLabel(contact.status)}
                </span>
                {contact.user_authenticated && (
                  <span className="badge bg-blue-100 text-blue-800">
                    🔐 認証済み
                  </span>
                )}
              </div>
              <h3 className={`${compact ? 'text-sm' : 'text-base'} font-medium text-gray-900 truncate`}>
                {contact.subject}
              </h3>
              <p className="text-sm text-gray-600">
                {contact.name} ({contact.email})
              </p>
            </div>
            <div className="text-right text-xs text-gray-500">
              {format(new Date(contact.created_at), 'MM/dd HH:mm')}
            </div>
          </div>

          {!compact && (
            <>
              {/* Message Preview */}
              <div className="mb-3">
                <p className="text-sm text-gray-600 line-clamp-2">
                  {contact.message}
                </p>
              </div>

              {/* AI Analysis (if available) */}
              {contact.ai_analysis && (
                <div className="mb-3">
                  <AIAnalysisDisplay 
                    analysis={contact.ai_analysis} 
                    compact={true}
                  />
                </div>
              )}

              {/* Similar Contacts Indicator */}
              {contact.similar_contacts && contact.similar_contacts.length > 0 && (
                <div className="flex items-center text-xs text-gray-500">
                  <svg className="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                  {contact.similar_contacts.length}件の類似お問い合わせ
                </div>
              )}

              {/* Notifications Sent */}
              {contact.notifications_sent && contact.notifications_sent.length > 0 && (
                <div className="flex items-center text-xs text-gray-500 mt-1">
                  <svg className="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 4.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                  </svg>
                  通知送信済み ({contact.notifications_sent.length}件)
                </div>
              )}
            </>
          )}

          {compact && contact.ai_analysis && (
            <div className="mt-2">
              <AIAnalysisDisplay 
                analysis={contact.ai_analysis} 
                compact={true}
              />
            </div>
          )}
        </div>
      ))}
    </div>
  );
};

export default ContactList;