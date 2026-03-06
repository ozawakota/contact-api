import React from 'react';
import { SimilarContact } from '../types';
import { format } from 'date-fns';

interface SimilarContactsListProps {
  contacts: SimilarContact[];
  className?: string;
  showViewButton?: boolean;
  onViewContact?: (contactId: string) => void;
}

const SimilarContactsList: React.FC<SimilarContactsListProps> = ({ 
  contacts, 
  className = '',
  showViewButton = false,
  onViewContact 
}) => {
  const getSimilarityColor = (score: number) => {
    if (score >= 0.9) return 'text-green-600 bg-green-50';
    if (score >= 0.8) return 'text-blue-600 bg-blue-50';
    if (score >= 0.7) return 'text-yellow-600 bg-yellow-50';
    return 'text-gray-600 bg-gray-50';
  };

  const getSimilarityLabel = (score: number) => {
    if (score >= 0.9) return '非常に類似';
    if (score >= 0.8) return '類似';
    if (score >= 0.7) return 'やや類似';
    return '低い類似性';
  };

  if (!contacts || contacts.length === 0) {
    return null;
  }

  return (
    <div className={`card bg-yellow-50 border-yellow-200 ${className}`}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900 flex items-center">
          <span className="mr-2">🔍</span>
          類似のお問い合わせ
        </h3>
        <span className="badge bg-yellow-100 text-yellow-800">
          {contacts.length}件見つかりました
        </span>
      </div>

      <div className="space-y-3">
        {contacts.map((contact, index) => (
          <div 
            key={contact.contact_id}
            className="bg-white rounded-lg p-4 border border-gray-200 hover:border-gray-300 transition-colors"
          >
            <div className="flex items-start justify-between mb-2">
              <div className="flex-1 min-w-0">
                <h4 className="text-sm font-medium text-gray-900 truncate">
                  {contact.subject}
                </h4>
                <p className="text-xs text-gray-500 mt-1">
                  ID: {contact.contact_id} • {format(new Date(contact.created_at), 'yyyy/MM/dd')}
                </p>
              </div>
              <div className="flex items-center space-x-2 ml-3">
                <div className={`px-2 py-1 rounded-full text-xs font-medium ${getSimilarityColor(contact.similarity_score)}`}>
                  {Math.round(contact.similarity_score * 100)}%
                </div>
                <span className="text-xs text-gray-500">
                  {getSimilarityLabel(contact.similarity_score)}
                </span>
              </div>
            </div>

            <div className="text-sm text-gray-600 line-clamp-2">
              {contact.message}
            </div>

            {showViewButton && onViewContact && (
              <div className="mt-3 flex justify-end">
                <button
                  onClick={() => onViewContact(contact.contact_id)}
                  className="text-xs btn-secondary"
                >
                  詳細を見る
                </button>
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="mt-4 pt-4 border-t border-yellow-200">
        <div className="text-xs text-gray-600">
          <p className="flex items-center">
            <span className="mr-1">💡</span>
            これらの類似するお問い合わせは、ベクター検索により自動的に検出されました。
            過去の回答やソリューションが参考になる可能性があります。
          </p>
        </div>
      </div>
    </div>
  );
};

export default SimilarContactsList;