import React from 'react';
import { AIAnalysis, CategoryType, UrgencyLevel, SentimentType } from '../types';
import { format } from 'date-fns';

interface AIAnalysisDisplayProps {
  analysis: AIAnalysis;
  className?: string;
  compact?: boolean;
}

const AIAnalysisDisplay: React.FC<AIAnalysisDisplayProps> = ({ 
  analysis, 
  className = '',
  compact = false 
}) => {
  const getCategoryInfo = (category: CategoryType) => {
    const categoryMap = {
      [CategoryType.GENERAL]: { 
        label: '一般', 
        color: 'bg-blue-100 text-blue-800',
        icon: '📝'
      },
      [CategoryType.TECHNICAL]: { 
        label: '技術', 
        color: 'bg-purple-100 text-purple-800',
        icon: '⚙️'
      },
      [CategoryType.BILLING]: { 
        label: '請求', 
        color: 'bg-green-100 text-green-800',
        icon: '💰'
      },
      [CategoryType.SUPPORT]: { 
        label: 'サポート', 
        color: 'bg-yellow-100 text-yellow-800',
        icon: '🤝'
      },
      [CategoryType.COMPLAINT]: { 
        label: '苦情', 
        color: 'bg-red-100 text-red-800',
        icon: '⚠️'
      }
    };
    return categoryMap[category] || categoryMap[CategoryType.GENERAL];
  };

  const getUrgencyInfo = (urgency: UrgencyLevel) => {
    const urgencyMap = {
      [UrgencyLevel.LOW]: { 
        label: '低', 
        color: 'bg-gray-100 text-gray-800',
        icon: '🟢',
        priority: 1
      },
      [UrgencyLevel.MEDIUM]: { 
        label: '中', 
        color: 'bg-yellow-100 text-yellow-800',
        icon: '🟡',
        priority: 2
      },
      [UrgencyLevel.HIGH]: { 
        label: '高', 
        color: 'bg-orange-100 text-orange-800',
        icon: '🟠',
        priority: 3
      },
      [UrgencyLevel.URGENT]: { 
        label: '緊急', 
        color: 'bg-red-100 text-red-800',
        icon: '🔴',
        priority: 4
      }
    };
    return urgencyMap[urgency] || urgencyMap[UrgencyLevel.MEDIUM];
  };

  const getSentimentInfo = (sentiment: SentimentType) => {
    const sentimentMap = {
      [SentimentType.POSITIVE]: { 
        label: 'ポジティブ', 
        color: 'bg-green-100 text-green-800',
        icon: '😊'
      },
      [SentimentType.NEUTRAL]: { 
        label: 'ニュートラル', 
        color: 'bg-gray-100 text-gray-800',
        icon: '😐'
      },
      [SentimentType.NEGATIVE]: { 
        label: 'ネガティブ', 
        color: 'bg-red-100 text-red-800',
        icon: '😟'
      }
    };
    return sentimentMap[sentiment] || sentimentMap[SentimentType.NEUTRAL];
  };

  const getConfidenceColor = (score: number) => {
    if (score >= 0.8) return 'text-green-600';
    if (score >= 0.6) return 'text-yellow-600';
    return 'text-red-600';
  };

  const categoryInfo = getCategoryInfo(analysis.category);
  const urgencyInfo = getUrgencyInfo(analysis.urgency);
  const sentimentInfo = getSentimentInfo(analysis.sentiment);

  if (compact) {
    return (
      <div className={`flex items-center space-x-3 ${className}`}>
        <span className={`badge ${categoryInfo.color}`}>
          {categoryInfo.icon} {categoryInfo.label}
        </span>
        <span className={`badge ${urgencyInfo.color}`}>
          {urgencyInfo.icon} {urgencyInfo.label}
        </span>
        <span className={`badge ${sentimentInfo.color}`}>
          {sentimentInfo.icon} {sentimentInfo.label}
        </span>
        <span className={`text-xs ${getConfidenceColor(analysis.confidence_score)}`}>
          信頼度: {Math.round(analysis.confidence_score * 100)}%
        </span>
      </div>
    );
  }

  return (
    <div className={`card bg-gradient-to-r from-blue-50 to-indigo-50 border-blue-200 ${className}`}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900 flex items-center">
          <span className="mr-2">🤖</span>
          AI分析結果
        </h3>
        <div className="text-sm text-gray-500">
          {format(new Date(analysis.analyzed_at), 'yyyy/MM/dd HH:mm')}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {/* Category */}
        <div className="bg-white rounded-lg p-3 border border-gray-100">
          <div className="text-xs text-gray-500 mb-1">カテゴリ</div>
          <div className={`badge ${categoryInfo.color} text-sm`}>
            {categoryInfo.icon} {categoryInfo.label}
          </div>
        </div>

        {/* Urgency */}
        <div className="bg-white rounded-lg p-3 border border-gray-100">
          <div className="text-xs text-gray-500 mb-1">緊急度</div>
          <div className={`badge ${urgencyInfo.color} text-sm`}>
            {urgencyInfo.icon} {urgencyInfo.label}
          </div>
        </div>

        {/* Sentiment */}
        <div className="bg-white rounded-lg p-3 border border-gray-100">
          <div className="text-xs text-gray-500 mb-1">感情</div>
          <div className={`badge ${sentimentInfo.color} text-sm`}>
            {sentimentInfo.icon} {sentimentInfo.label}
          </div>
        </div>

        {/* Confidence Score */}
        <div className="bg-white rounded-lg p-3 border border-gray-100">
          <div className="text-xs text-gray-500 mb-1">信頼度</div>
          <div className="flex items-center">
            <div className={`text-lg font-semibold ${getConfidenceColor(analysis.confidence_score)}`}>
              {Math.round(analysis.confidence_score * 100)}%
            </div>
            <div className="ml-2 flex-1 bg-gray-200 rounded-full h-2">
              <div 
                className={`h-2 rounded-full transition-all duration-300 ${
                  analysis.confidence_score >= 0.8 ? 'bg-green-500' :
                  analysis.confidence_score >= 0.6 ? 'bg-yellow-500' : 'bg-red-500'
                }`}
                style={{ width: `${analysis.confidence_score * 100}%` }}
              ></div>
            </div>
          </div>
        </div>
      </div>

      {/* Key Topics */}
      {analysis.key_topics && analysis.key_topics.length > 0 && (
        <div className="mb-4">
          <div className="text-sm font-medium text-gray-700 mb-2">キートピック</div>
          <div className="flex flex-wrap gap-2">
            {analysis.key_topics.map((topic, index) => (
              <span 
                key={index}
                className="badge bg-blue-100 text-blue-800 text-xs"
              >
                #{topic}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Recommended Action */}
      {analysis.recommended_action && (
        <div className="mb-4">
          <div className="text-sm font-medium text-gray-700 mb-2 flex items-center">
            <span className="mr-1">💡</span>
            推奨アクション
          </div>
          <div className="bg-white rounded-lg p-3 border border-gray-100">
            <p className="text-sm text-gray-600">{analysis.recommended_action}</p>
          </div>
        </div>
      )}

      {/* Model Info */}
      <div className="pt-4 border-t border-gray-200">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>分析モデル: {analysis.model_used}</span>
          <span>
            処理時間: {format(new Date(analysis.analyzed_at), 'HH:mm:ss')}
          </span>
        </div>
      </div>
    </div>
  );
};

export default AIAnalysisDisplay;