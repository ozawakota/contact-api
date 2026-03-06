import React, { useState } from 'react';
import { SimilarContact, VectorSearchRequest } from '../types';
import { ApiService } from '../services/api';
import LoadingSpinner from './LoadingSpinner';
import SimilarContactsList from './SimilarContactsList';
import toast from 'react-hot-toast';

interface VectorSearchProps {
  onContactSelect?: (contactId: string) => void;
  className?: string;
}

const VectorSearch: React.FC<VectorSearchProps> = ({ 
  onContactSelect,
  className = '' 
}) => {
  const [query, setQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SimilarContact[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchConfig, setSearchConfig] = useState({
    limit: 10,
    similarity_threshold: 0.7
  });
  const [hasSearched, setHasSearched] = useState(false);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!query.trim()) {
      toast.error('検索キーワードを入力してください');
      return;
    }

    setIsSearching(true);
    setHasSearched(false);

    try {
      const searchRequest: VectorSearchRequest = {
        query: query.trim(),
        limit: searchConfig.limit,
        similarity_threshold: searchConfig.similarity_threshold
      };

      const results = await ApiService.searchSimilarContacts(searchRequest);
      setSearchResults(results);
      setHasSearched(true);

      if (results.length === 0) {
        toast('該当するお問い合わせが見つかりませんでした', {
          icon: '🔍'
        });
      } else {
        toast.success(`${results.length}件の類似お問い合わせが見つかりました`);
      }

    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || '検索に失敗しました';
      toast.error(errorMessage);
      setSearchResults([]);
      setHasSearched(true);
    } finally {
      setIsSearching(false);
    }
  };

  const handleClearSearch = () => {
    setQuery('');
    setSearchResults([]);
    setHasSearched(false);
  };

  const handleConfigChange = (key: string, value: number) => {
    setSearchConfig(prev => ({
      ...prev,
      [key]: value
    }));
  };

  return (
    <div className={`space-y-6 ${className}`}>
      <div className="card">
        <h2 className="text-lg font-semibold text-gray-900 mb-6 flex items-center">
          <span className="mr-2">🔍</span>
          ベクター検索
        </h2>

        <form onSubmit={handleSearch} className="space-y-4">
          {/* Search Input */}
          <div>
            <label htmlFor="search-query" className="block text-sm font-medium text-gray-700 mb-1">
              検索キーワード
            </label>
            <div className="relative">
              <input
                type="text"
                id="search-query"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="input-field pr-10"
                placeholder="類似のお問い合わせを検索..."
                disabled={isSearching}
              />
              <div className="absolute inset-y-0 right-0 flex items-center pr-3">
                <svg 
                  className="w-4 h-4 text-gray-400" 
                  fill="none" 
                  stroke="currentColor" 
                  viewBox="0 0 24 24"
                >
                  <path 
                    strokeLinecap="round" 
                    strokeLinejoin="round" 
                    strokeWidth={2} 
                    d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" 
                  />
                </svg>
              </div>
            </div>
            <p className="mt-1 text-xs text-gray-500">
              自然言語でお問い合わせ内容を入力してください。AIが意味的に類似した過去のお問い合わせを検索します。
            </p>
          </div>

          {/* Advanced Settings */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label htmlFor="limit" className="block text-sm font-medium text-gray-700 mb-1">
                最大結果数
              </label>
              <select
                id="limit"
                value={searchConfig.limit}
                onChange={(e) => handleConfigChange('limit', parseInt(e.target.value))}
                className="input-field"
                disabled={isSearching}
              >
                <option value={5}>5件</option>
                <option value={10}>10件</option>
                <option value={20}>20件</option>
                <option value={50}>50件</option>
              </select>
            </div>

            <div>
              <label htmlFor="threshold" className="block text-sm font-medium text-gray-700 mb-1">
                類似度しきい値
              </label>
              <select
                id="threshold"
                value={searchConfig.similarity_threshold}
                onChange={(e) => handleConfigChange('similarity_threshold', parseFloat(e.target.value))}
                className="input-field"
                disabled={isSearching}
              >
                <option value={0.5}>50% (低い類似性)</option>
                <option value={0.6}>60%</option>
                <option value={0.7}>70% (推奨)</option>
                <option value={0.8}>80% (高い類似性)</option>
                <option value={0.9}>90% (非常に高い類似性)</option>
              </select>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex space-x-3">
            <button
              type="submit"
              disabled={isSearching || !query.trim()}
              className="btn-primary flex-1"
            >
              {isSearching && <LoadingSpinner size="sm" color="white" className="mr-2" />}
              {isSearching ? '検索中...' : '検索実行'}
            </button>
            
            {(hasSearched || query) && (
              <button
                type="button"
                onClick={handleClearSearch}
                className="btn-secondary"
                disabled={isSearching}
              >
                クリア
              </button>
            )}
          </div>
        </form>

        {/* Search Stats */}
        {hasSearched && (
          <div className="mt-4 p-3 bg-gray-50 rounded-lg">
            <div className="text-sm text-gray-600">
              <p className="flex items-center justify-between">
                <span>検索クエリ: <span className="font-mono text-xs bg-white px-1 rounded">{query}</span></span>
                <span>結果: {searchResults.length}件</span>
              </p>
              <p className="mt-1 text-xs">
                類似度しきい値: {Math.round(searchConfig.similarity_threshold * 100)}% • 
                最大結果数: {searchConfig.limit}件
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Search Results */}
      {hasSearched && (
        <div>
          {searchResults.length > 0 ? (
            <SimilarContactsList
              contacts={searchResults}
              showViewButton={true}
              onViewContact={onContactSelect}
            />
          ) : (
            <div className="card border-gray-200 bg-gray-50">
              <div className="text-center py-8">
                <div className="text-4xl mb-4">🔍</div>
                <h3 className="text-lg font-medium text-gray-900 mb-2">
                  該当するお問い合わせが見つかりませんでした
                </h3>
                <p className="text-gray-600 mb-4">
                  別のキーワードで検索するか、類似度しきい値を下げてみてください。
                </p>
                <button
                  onClick={handleClearSearch}
                  className="btn-secondary"
                >
                  新しい検索を実行
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Help Section */}
      <div className="card bg-blue-50 border-blue-200">
        <h3 className="text-sm font-semibold text-blue-900 mb-2 flex items-center">
          <span className="mr-1">💡</span>
          ベクター検索のヒント
        </h3>
        <ul className="text-xs text-blue-800 space-y-1">
          <li>• 具体的な問題や症状を自然言語で記述してください</li>
          <li>• 「ログインできない」「エラーが発生」「料金について」などの表現が効果的です</li>
          <li>• 類似度しきい値を下げると、より幅広い結果が得られます</li>
          <li>• 多言語対応により、日本語と英語の混在したクエリも検索可能です</li>
        </ul>
      </div>
    </div>
  );
};

export default VectorSearch;