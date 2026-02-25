// 認証状態管理のカスタムフック
'use client';

import { useState, useEffect, createContext, useContext, ReactNode } from 'react';
import { 
  User, 
  onAuthStateChanged, 
  signInWithPopup, 
  GoogleAuthProvider, 
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut,
  sendPasswordResetEmail,
  IdTokenResult
} from 'firebase/auth';
import { auth } from '@/lib/firebase';

// 認証コンテキストの型定義
interface AuthContextType {
  user: User | null;
  isAdmin: boolean;
  loading: boolean;
  signInWithGoogle: () => Promise<void>;
  signInWithEmail: (email: string, password: string) => Promise<void>;
  signUpWithEmail: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  resetPassword: (email: string) => Promise<void>;
  refreshToken: () => Promise<void>;
}

// 認証コンテキストの作成
const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Google OAuth プロバイダー設定
const googleProvider = new GoogleAuthProvider();
googleProvider.setCustomParameters({
  prompt: 'select_account', // 常にアカウント選択画面を表示
  hd: process.env.NEXT_PUBLIC_ADMIN_DOMAIN || undefined, // 管理者ドメイン制限
});

// 認証プロバイダーコンポーネント
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [loading, setLoading] = useState(true);

  // 認証状態の監視
  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (user) => {
      setUser(user);
      setLoading(true);

      if (user) {
        try {
          // カスタムクレームから管理者権限を確認
          const tokenResult: IdTokenResult = await user.getIdTokenResult();
          const adminClaim = tokenResult.claims.admin === true;
          
          // 開発環境では追加の管理者チェック
          if (process.env.NODE_ENV === 'development') {
            const devAdmins = process.env.NEXT_PUBLIC_DEV_ADMIN_EMAILS?.split(',') || [];
            const isDevAdmin = devAdmins.includes(user.email || '');
            setIsAdmin(adminClaim || isDevAdmin);
          } else {
            setIsAdmin(adminClaim);
          }
          
          // ログイン成功のトラッキング
          console.log('User authenticated:', {
            uid: user.uid,
            email: user.email,
            isAdmin: adminClaim,
            timestamp: new Date().toISOString()
          });
        } catch (error) {
          console.error('Token verification failed:', error);
          setIsAdmin(false);
        }
      } else {
        setIsAdmin(false);
      }
      
      setLoading(false);
    });

    return unsubscribe;
  }, []);

  // Google OAuth ログイン
  const signInWithGoogle = async (): Promise<void> => {
    try {
      setLoading(true);
      const result = await signInWithPopup(auth, googleProvider);
      
      // ログイン成功の追加処理
      console.log('Google sign-in successful:', result.user.email);
      
      // 管理者権限がない場合は警告
      const tokenResult = await result.user.getIdTokenResult();
      if (!tokenResult.claims.admin) {
        console.warn('User logged in without admin privileges:', result.user.email);
      }
    } catch (error: any) {
      console.error('Google sign-in failed:', error);
      throw new Error(error.message || 'Google認証に失敗しました');
    } finally {
      setLoading(false);
    }
  };

  // メール/パスワード ログイン
  const signInWithEmail = async (email: string, password: string): Promise<void> => {
    try {
      setLoading(true);
      await signInWithEmailAndPassword(auth, email, password);
      console.log('Email sign-in successful:', email);
    } catch (error: any) {
      console.error('Email sign-in failed:', error);
      throw new Error(error.message || 'メール認証に失敗しました');
    } finally {
      setLoading(false);
    }
  };

  // メール/パスワード サインアップ
  const signUpWithEmail = async (email: string, password: string): Promise<void> => {
    try {
      setLoading(true);
      const result = await createUserWithEmailAndPassword(auth, email, password);
      console.log('Account created successfully:', result.user.email);
      
      // 新規登録後は管理者による権限付与が必要
      console.warn('New account created - admin privileges required');
    } catch (error: any) {
      console.error('Account creation failed:', error);
      throw new Error(error.message || 'アカウント作成に失敗しました');
    } finally {
      setLoading(false);
    }
  };

  // ログアウト
  const logout = async (): Promise<void> => {
    try {
      await signOut(auth);
      console.log('User logged out successfully');
    } catch (error: any) {
      console.error('Logout failed:', error);
      throw new Error(error.message || 'ログアウトに失敗しました');
    }
  };

  // パスワードリセット
  const resetPassword = async (email: string): Promise<void> => {
    try {
      await sendPasswordResetEmail(auth, email);
      console.log('Password reset email sent to:', email);
    } catch (error: any) {
      console.error('Password reset failed:', error);
      throw new Error(error.message || 'パスワードリセットに失敗しました');
    }
  };

  // トークン更新
  const refreshToken = async (): Promise<void> => {
    if (user) {
      try {
        const tokenResult = await user.getIdTokenResult(true); // 強制更新
        const adminClaim = tokenResult.claims.admin === true;
        setIsAdmin(adminClaim);
        console.log('Token refreshed:', { admin: adminClaim });
      } catch (error) {
        console.error('Token refresh failed:', error);
      }
    }
  };

  const value: AuthContextType = {
    user,
    isAdmin,
    loading,
    signInWithGoogle,
    signInWithEmail,
    signUpWithEmail,
    logout,
    resetPassword,
    refreshToken,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

// useAuth フック
export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

// 管理者権限チェック用フック
export function useRequireAuth(requireAdmin = false) {
  const { user, isAdmin, loading } = useAuth();
  
  useEffect(() => {
    if (!loading && !user) {
      // 未認証の場合はログインページにリダイレクト
      window.location.href = '/auth/login';
    } else if (!loading && requireAdmin && !isAdmin) {
      // 管理者権限が必要だが権限がない場合
      console.error('Admin access required but user lacks admin privileges');
      window.location.href = '/auth/unauthorized';
    }
  }, [user, isAdmin, loading, requireAdmin]);

  return { user, isAdmin, loading };
}