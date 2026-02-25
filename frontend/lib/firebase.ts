// Firebase設定とクライアント初期化
import { initializeApp, getApps, FirebaseApp } from 'firebase/app';
import { getAuth, Auth } from 'firebase/auth';
import { getFirestore, Firestore } from 'firebase/firestore';
import { getFunctions, Functions } from 'firebase/functions';

// Firebase設定
const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

// Firebase アプリの初期化（重複初期化防止）
let app: FirebaseApp;
if (getApps().length === 0) {
  app = initializeApp(firebaseConfig);
} else {
  app = getApps()[0];
}

// Firebase サービスの初期化
export const auth: Auth = getAuth(app);
export const db: Firestore = getFirestore(app);
export const functions: Functions = getFunctions(app, 'asia-northeast1'); // 東京リージョン

// 開発環境では Firebase エミュレーター使用
if (typeof window !== 'undefined' && process.env.NODE_ENV === 'development') {
  const { connectAuthEmulator } = require('firebase/auth');
  const { connectFirestoreEmulator } = require('firebase/firestore');
  const { connectFunctionsEmulator } = require('firebase/functions');
  
  // エミュレーター接続（一度だけ）
  if (!auth.config.emulator) {
    connectAuthEmulator(auth, 'http://localhost:9099');
  }
  if (!db._delegate._databaseId) {
    connectFirestoreEmulator(db, 'localhost', 8080);
  }
  if (!functions.app.options.appId) {
    connectFunctionsEmulator(functions, 'localhost', 5001);
  }
}

export default app;