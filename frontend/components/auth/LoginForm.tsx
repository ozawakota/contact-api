// ログインフォームコンポーネント
'use client';

import { useState } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { FcGoogle } from 'react-icons/fc';
import { MdEmail, MdLock, MdVisibility, MdVisibilityOff } from 'react-icons/md';

interface LoginFormProps {
  onSuccess?: () => void;
  redirectTo?: string;
}

export function LoginForm({ onSuccess, redirectTo = '/admin' }: LoginFormProps) {
  const { signInWithGoogle, signInWithEmail, resetPassword, loading } = useAuth();
  
  const [loginMethod, setLoginMethod] = useState<'google' | 'email'>('google');
  const [formData, setFormData] = useState({
    email: '',
    password: '',
  });
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resetEmailSent, setResetEmailSent] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  // Google OAuth ログイン処理
  const handleGoogleLogin = async () => {
    try {
      setError(null);
      setIsLoading(true);
      await signInWithGoogle();
      onSuccess?.();
      window.location.href = redirectTo;
    } catch (error: any) {
      setError(error.message);
    } finally {
      setIsLoading(false);
    }
  };

  // メール/パスワード ログイン処理
  const handleEmailLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!formData.email || !formData.password) {
      setError('メールアドレスとパスワードを入力してください');
      return;
    }

    try {
      setError(null);
      setIsLoading(true);
      await signInWithEmail(formData.email, formData.password);
      onSuccess?.();
      window.location.href = redirectTo;
    } catch (error: any) {
      setError(error.message);
    } finally {
      setIsLoading(false);
    }
  };

  // パスワードリセット処理
  const handlePasswordReset = async () => {
    if (!formData.email) {
      setError('パスワードリセット用のメールアドレスを入力してください');
      return;
    }

    try {
      setError(null);
      await resetPassword(formData.email);
      setResetEmailSent(true);
    } catch (error: any) {
      setError(error.message);
    }
  };

  // 入力値の更新
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData(prev => ({
      ...prev,
      [e.target.name]: e.target.value
    }));
  };

  return (
    <div className="w-full max-w-md mx-auto">
      {/* ヘッダー */}
      <div className="text-center mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          Contact API 管理画面
        </h1>
        <p className="text-gray-600">
          管理者としてログインしてください
        </p>
      </div>

      {/* エラー表示 */}
      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-red-800 text-sm">{error}</p>
        </div>
      )}

      {/* リセットメール送信完了 */}
      {resetEmailSent && (
        <div className="mb-4 p-4 bg-green-50 border border-green-200 rounded-lg">
          <p className="text-green-800 text-sm">
            パスワードリセットメールを送信しました。メールをご確認ください。
          </p>
        </div>
      )}

      {/* ログイン方法選択 */}
      <div className="mb-6">
        <div className="flex border-b border-gray-200">
          <button
            type="button"
            className={`flex-1 py-2 px-4 text-sm font-medium text-center border-b-2 transition-colors ${
              loginMethod === 'google'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
            onClick={() => setLoginMethod('google')}
          >
            Google認証
          </button>
          <button
            type="button"
            className={`flex-1 py-2 px-4 text-sm font-medium text-center border-b-2 transition-colors ${
              loginMethod === 'email'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
            onClick={() => setLoginMethod('email')}
          >
            メール認証
          </button>
        </div>
      </div>

      {/* Google OAuth ログイン */}
      {loginMethod === 'google' && (
        <div className="space-y-4">
          <button
            onClick={handleGoogleLogin}
            disabled={isLoading || loading}
            className="w-full flex items-center justify-center px-4 py-3 border border-gray-300 rounded-lg shadow-sm bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isLoading ? (
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-gray-900"></div>
            ) : (
              <>
                <FcGoogle className="h-5 w-5 mr-3" />
                <span className="text-sm font-medium text-gray-900">
                  Googleアカウントでログイン
                </span>
              </>
            )}
          </button>
          
          <p className="text-xs text-gray-500 text-center">
            ※ 管理者権限を持つGoogleアカウントのみアクセス可能です
          </p>
        </div>
      )}

      {/* メール/パスワード ログイン */}
      {loginMethod === 'email' && (
        <form onSubmit={handleEmailLogin} className="space-y-4">
          {/* メールアドレス */}
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
              メールアドレス
            </label>
            <div className="relative">
              <MdEmail className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-5 w-5" />
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                required
                value={formData.email}
                onChange={handleInputChange}
                className="pl-10 w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="admin@example.com"
              />
            </div>
          </div>

          {/* パスワード */}
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
              パスワード
            </label>
            <div className="relative">
              <MdLock className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-5 w-5" />
              <input
                id="password"
                name="password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                required
                value={formData.password}
                onChange={handleInputChange}
                className="pl-10 pr-10 w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="パスワードを入力"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                {showPassword ? <MdVisibilityOff className="h-5 w-5" /> : <MdVisibility className="h-5 w-5" />}
              </button>
            </div>
          </div>

          {/* ログインボタン */}
          <button
            type="submit"
            disabled={isLoading || loading}
            className="w-full flex justify-center py-3 px-4 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isLoading ? (
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
            ) : (
              'ログイン'
            )}
          </button>

          {/* パスワードリセット */}
          <div className="text-center">
            <button
              type="button"
              onClick={handlePasswordReset}
              className="text-sm text-blue-600 hover:text-blue-500 focus:outline-none focus:underline"
            >
              パスワードをお忘れですか？
            </button>
          </div>
        </form>
      )}

      {/* フッター */}
      <div className="mt-8 pt-6 border-t border-gray-200">
        <p className="text-xs text-gray-500 text-center">
          このページは管理者専用です。<br />
          一般のお問い合わせは<a href="/" className="text-blue-600 hover:underline">こちら</a>から
        </p>
      </div>
    </div>
  );
}