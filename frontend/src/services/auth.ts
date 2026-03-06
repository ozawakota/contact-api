import { initializeApp } from 'firebase/app';
import {
  getAuth,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut,
  onAuthStateChanged,
  GoogleAuthProvider,
  signInWithPopup,
  User
} from 'firebase/auth';

// Firebase configuration
const firebaseConfig = {
  apiKey: process.env.REACT_APP_FIREBASE_API_KEY,
  authDomain: process.env.REACT_APP_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.REACT_APP_FIREBASE_PROJECT_ID,
  storageBucket: process.env.REACT_APP_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.REACT_APP_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.REACT_APP_FIREBASE_APP_ID
};

// Initialize Firebase
let app;
let auth;

try {
  if (firebaseConfig.apiKey) {
    app = initializeApp(firebaseConfig);
    auth = getAuth(app);
    console.log('Firebase initialized successfully');
  } else {
    console.warn('Firebase configuration not found. Authentication will be disabled.');
  }
} catch (error) {
  console.error('Firebase initialization failed:', error);
}

export const isFirebaseEnabled = !!auth;

export class AuthService {
  static async signInWithEmail(email: string, password: string): Promise<User> {
    if (!auth) {
      throw new Error('Firebase is not initialized');
    }
    const result = await signInWithEmailAndPassword(auth, email, password);
    
    // Store token for API calls
    const token = await result.user.getIdToken();
    localStorage.setItem('firebase_token', token);
    
    return result.user;
  }

  static async signUpWithEmail(email: string, password: string): Promise<User> {
    if (!auth) {
      throw new Error('Firebase is not initialized');
    }
    const result = await createUserWithEmailAndPassword(auth, email, password);
    
    // Store token for API calls
    const token = await result.user.getIdToken();
    localStorage.setItem('firebase_token', token);
    
    return result.user;
  }

  static async signInWithGoogle(): Promise<User> {
    if (!auth) {
      throw new Error('Firebase is not initialized');
    }
    const provider = new GoogleAuthProvider();
    const result = await signInWithPopup(auth, provider);
    
    // Store token for API calls
    const token = await result.user.getIdToken();
    localStorage.setItem('firebase_token', token);
    
    return result.user;
  }

  static async signOut(): Promise<void> {
    if (!auth) {
      return;
    }
    await signOut(auth);
    localStorage.removeItem('firebase_token');
  }

  static getCurrentUser(): User | null {
    if (!auth) {
      return null;
    }
    return auth.currentUser;
  }

  static async getCurrentToken(): Promise<string | null> {
    if (!auth || !auth.currentUser) {
      return null;
    }
    try {
      const token = await auth.currentUser.getIdToken();
      localStorage.setItem('firebase_token', token);
      return token;
    } catch (error) {
      console.error('Error getting token:', error);
      return null;
    }
  }

  static onAuthStateChanged(callback: (user: User | null) => void): () => void {
    if (!auth) {
      // Return a no-op unsubscribe function if Firebase is not available
      return () => {};
    }
    return onAuthStateChanged(auth, callback);
  }

  static async refreshToken(): Promise<string | null> {
    if (!auth || !auth.currentUser) {
      return null;
    }
    try {
      const token = await auth.currentUser.getIdToken(true); // Force refresh
      localStorage.setItem('firebase_token', token);
      return token;
    } catch (error) {
      console.error('Error refreshing token:', error);
      return null;
    }
  }
}

export default AuthService;