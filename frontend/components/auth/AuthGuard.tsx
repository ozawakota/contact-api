// 認証ガード：保護されたルートのアクセス制御
'use client';

import { ReactNode, useEffect, useState } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';

interface AuthGuardProps {
  children: ReactNode;
  requireAdmin?: boolean;
  fallback?: ReactNode;
  redirectTo?: string;
}

// ローディングスピナーコンポーネント（簡易版）
function SimpleLoadingSpinner() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
        <p className="text-gray-600">認証状態を確認中...</p>
      </div>
    </div>
  );
}

// 未認証ユーザー向けメッセージ
function UnauthenticatedFallback({ redirectTo }: { redirectTo: string }) {
  useEffect(() => {
    // 3秒後に自動リダイレクト
    const timer = setTimeout(() => {
      window.location.href = redirectTo;
    }, 3000);
    
    return () => clearTimeout(timer);
  }, [redirectTo]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center max-w-md mx-auto p-6">
        <div className="mb-6">
          <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">認証が必要です</h1>
          <p className="text-gray-600 mb-6">
            このページにアクセスするには、管理者としてログインしてください。
          </p>
        </div>
        
        <div className="space-y-3">
          <a
            href={redirectTo}
            className="block w-full bg-blue-600 text-white py-2 px-4 rounded-lg hover:bg-blue-700 transition-colors"
          >
            ログインページに移動
          </a>
          <a
            href="/"
            className="block w-full border border-gray-300 text-gray-700 py-2 px-4 rounded-lg hover:bg-gray-50 transition-colors"
          >
            ホームに戻る
          </a>
        </div>
        
        <p className="text-sm text-gray-500 mt-4">
          3秒後に自動的にログインページに移動します...
        </p>
      </div>
    </div>
  );
}

// 管理者権限不足メッセージ
function UnauthorizedFallback() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center max-w-md mx-auto p-6">
        <div className="mb-6">
          <div className="w-16 h-16 bg-yellow-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">アクセス権限がありません</h1>
          <p className="text-gray-600 mb-6">
            このページにアクセスするには管理者権限が必要です。<br />
            システム管理者にお問い合わせください。
          </p>
        </div>
        
        <div className="space-y-3">
          <button
            onClick={() => window.location.href = '/auth/logout'}
            className="block w-full bg-gray-600 text-white py-2 px-4 rounded-lg hover:bg-gray-700 transition-colors"
          >
            ログアウト
          </button>
          <a
            href="/"
            className="block w-full border border-gray-300 text-gray-700 py-2 px-4 rounded-lg hover:bg-gray-50 transition-colors"
          >
            ホームに戻る
          </a>
        </div>
        
        <div className="mt-6 p-4 bg-blue-50 rounded-lg">
          <p className="text-sm text-blue-800">
            <strong>管理者の方へ：</strong><br />
            Firebase Consoleでカスタムクレーム「admin: true」を設定してください。
          </p>
        </div>
      </div>
    </div>
  );
}

// メインのAuthGuardコンポーネント
export function AuthGuard({ 
  children, 
  requireAdmin = false, 
  fallback,
  redirectTo = '/auth/login'
}: AuthGuardProps) {
  const { user, isAdmin, loading } = useAuth();
  const [isClient, setIsClient] = useState(false);

  // クライアントサイドレンダリング確認
  useEffect(() => {
    setIsClient(true);
  }, []);

  // サーバーサイドレンダリング中は何も表示しない
  if (!isClient) {
    return null;
  }

  // ローディング中
  if (loading) {
    return fallback || <SimpleLoadingSpinner />;
  }

  // 未認証ユーザー
  if (!user) {
    return <UnauthenticatedFallback redirectTo={redirectTo} />;
  }

  // 管理者権限が必要だが権限がない場合
  if (requireAdmin && !isAdmin) {
    return <UnauthorizedFallback />;
  }

  // 認証済み＋権限OK
  return <>{children}</>;
}

// 高階コンポーネント（HOC）版
export function withAuthGuard<P extends object>(
  WrappedComponent: React.ComponentType<P>,
  options: Omit<AuthGuardProps, 'children'> = {}
) {
  const AuthGuardedComponent = (props: P) => (
    <AuthGuard {...options}>
      <WrappedComponent {...props} />
    </AuthGuard>
  );

  AuthGuardedComponent.displayName = `withAuthGuard(${WrappedComponent.displayName || WrappedComponent.name})`;
  
  return AuthGuardedComponent;
}

// 認証状態に応じた条件付きレンダリング
export function ConditionalAuth({ 
  children,
  fallback,
  requireAuth = true,
  requireAdmin = false 
}: {
  children: ReactNode;
  fallback?: ReactNode;
  requireAuth?: boolean;
  requireAdmin?: boolean;
}) {
  const { user, isAdmin, loading } = useAuth();

  if (loading) {
    return fallback || <div className="animate-pulse">読み込み中...</div>;
  }

  if (requireAuth && !user) {
    return fallback || null;
  }

  if (requireAdmin && !isAdmin) {
    return fallback || null;
  }

  return <>{children}</>;
}