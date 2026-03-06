import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { User } from 'firebase/auth';
import { Toaster } from 'react-hot-toast';
import { AuthService, isFirebaseEnabled } from './services/auth';
import ContactForm from './components/ContactForm';
import AdminDashboard from './components/AdminDashboard';
import VectorSearch from './components/VectorSearch';
import AuthModal from './components/AuthModal';
import LoadingSpinner from './components/LoadingSpinner';

interface NavigationProps {
  currentUser: User | null;
  onAuthClick: () => void;
  onSignOut: () => void;
  activeTab: string;
  setActiveTab: (tab: string) => void;
}

const Navigation: React.FC<NavigationProps> = ({
  currentUser,
  onAuthClick,
  onSignOut,
  activeTab,
  setActiveTab
}) => {
  const tabs = [
    { id: 'contact', label: 'お問い合わせ', icon: '📧' },
    { id: 'search', label: '検索', icon: '🔍' },
    { id: 'admin', label: '管理', icon: '⚙️' }
  ];

  return (
    <nav className="bg-white shadow-sm border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex items-center">
            <div className="flex-shrink-0 flex items-center">
              <h1 className="text-xl font-bold text-gray-900">
                <span className="text-gradient">Contact API</span>
              </h1>
              <span className="ml-2 badge bg-blue-100 text-blue-800 text-xs">
                v8.0.0
              </span>
            </div>
            <div className="ml-10 flex space-x-8">
              {tabs.map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`py-2 px-1 border-b-2 font-medium text-sm transition-colors ${
                    activeTab === tab.id
                      ? 'border-primary-500 text-primary-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  <span className="mr-2">{tab.icon}</span>
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center space-x-4">
            {isFirebaseEnabled && (
              <>
                {currentUser ? (
                  <div className="flex items-center space-x-3">
                    <div className="flex items-center">
                      {currentUser.photoURL && (
                        <img
                          src={currentUser.photoURL}
                          alt="プロフィール"
                          className="w-8 h-8 rounded-full"
                        />
                      )}
                      <span className="ml-2 text-sm text-gray-700">
                        {currentUser.displayName || currentUser.email}
                      </span>
                    </div>
                    <button
                      onClick={onSignOut}
                      className="btn-secondary text-sm"
                    >
                      ログアウト
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={onAuthClick}
                    className="btn-primary text-sm"
                  >
                    ログイン
                  </button>
                )}
              </>
            )}
            
            {!isFirebaseEnabled && (
              <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">
                認証無効
              </span>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
};

const App: React.FC = () => {
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [activeTab, setActiveTab] = useState('contact');

  useEffect(() => {
    if (!isFirebaseEnabled) {
      setAuthLoading(false);
      return;
    }

    const unsubscribe = AuthService.onAuthStateChanged((user) => {
      setCurrentUser(user);
      setAuthLoading(false);
    });

    return unsubscribe;
  }, []);

  const handleAuthSuccess = () => {
    setShowAuthModal(false);
  };

  const handleSignOut = async () => {
    try {
      await AuthService.signOut();
      setCurrentUser(null);
    } catch (error) {
      console.error('Sign out error:', error);
    }
  };

  const renderMainContent = () => {
    switch (activeTab) {
      case 'contact':
        return (
          <div className="max-w-2xl mx-auto">
            <div className="mb-8 text-center">
              <h2 className="text-3xl font-bold text-gray-900 mb-4">
                次世代カスタマーサポート
              </h2>
              <p className="text-lg text-gray-600">
                AIによる自動分析とベクター検索で、より良いサポート体験を提供します
              </p>
              <div className="mt-4 flex justify-center space-x-4 text-sm">
                <span className="badge bg-green-100 text-green-800">🤖 AI分析</span>
                <span className="badge bg-blue-100 text-blue-800">🔍 ベクター検索</span>
                <span className="badge bg-purple-100 text-purple-800">📧 自動通知</span>
                <span className="badge bg-yellow-100 text-yellow-800">🔐 認証対応</span>
              </div>
            </div>
            <ContactForm />
          </div>
        );
      
      case 'search':
        return (
          <div className="max-w-4xl mx-auto">
            <div className="mb-8">
              <h2 className="text-2xl font-bold text-gray-900 mb-2">
                ベクター検索
              </h2>
              <p className="text-gray-600">
                過去のお問い合わせから類似内容を意味的に検索できます
              </p>
            </div>
            <VectorSearch />
          </div>
        );
      
      case 'admin':
        return (
          <div className="max-w-7xl mx-auto">
            <AdminDashboard />
          </div>
        );
      
      default:
        return <Navigate to="/" />;
    }
  };

  if (authLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <LoadingSpinner size="lg" />
          <p className="mt-4 text-gray-600">アプリケーションを初期化中...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation
        currentUser={currentUser}
        onAuthClick={() => setShowAuthModal(true)}
        onSignOut={handleSignOut}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
      />

      <main className="py-8 px-4 sm:px-6 lg:px-8">
        {renderMainContent()}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 mt-16">
        <div className="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col md:flex-row items-center justify-between">
            <div className="flex items-center space-x-4 mb-4 md:mb-0">
              <span className="text-sm text-gray-600">
                Next-Generation Customer Support System
              </span>
              <span className="text-xs text-gray-400">
                Powered by Gemini AI, PostgreSQL, Firebase
              </span>
            </div>
            <div className="flex items-center space-x-4 text-xs text-gray-400">
              <span>Phase 8 Complete</span>
              <span>•</span>
              <span>All Features Enabled</span>
              <span>•</span>
              <span>Production Ready</span>
            </div>
          </div>
        </div>
      </footer>

      {/* Auth Modal */}
      <AuthModal
        isOpen={showAuthModal}
        onClose={() => setShowAuthModal(false)}
        onAuthSuccess={handleAuthSuccess}
      />

      {/* Toast Notifications */}
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 4000,
          style: {
            background: '#363636',
            color: '#fff',
          },
          success: {
            duration: 3000,
            icon: '✅',
          },
          error: {
            duration: 5000,
            icon: '❌',
          },
        }}
      />
    </div>
  );
};

export default App;