// API Response Types
export interface ContactRequest {
  name: string;
  email: string;
  subject: string;
  message: string;
}

export interface ContactResponse {
  id: string;
  name: string;
  email: string;
  subject: string;
  message: string;
  status: string;
  created_at: string;
  user_authenticated: boolean;
  ai_analysis?: AIAnalysis;
  similar_contacts?: SimilarContact[];
  notifications_sent?: string[];
}

export interface AIAnalysis {
  category: CategoryType;
  urgency: UrgencyLevel;
  confidence_score: number;
  key_topics: string[];
  sentiment: SentimentType;
  recommended_action: string;
  analyzed_at: string;
  model_used: string;
}

export interface SimilarContact {
  contact_id: string;
  subject: string;
  message: string;
  similarity_score: number;
  created_at: string;
}

export interface VectorSearchRequest {
  query: string;
  limit?: number;
  similarity_threshold?: number;
}

export interface EmailNotificationRequest {
  contact_id: string;
  notification_type: NotificationType;
  recipients: string[];
}

// Enums
export enum CategoryType {
  GENERAL = 'general',
  TECHNICAL = 'technical',
  BILLING = 'billing',
  SUPPORT = 'support',
  COMPLAINT = 'complaint'
}

export enum UrgencyLevel {
  LOW = 'low',
  MEDIUM = 'medium',
  HIGH = 'high',
  URGENT = 'urgent'
}

export enum SentimentType {
  POSITIVE = 'positive',
  NEUTRAL = 'neutral',
  NEGATIVE = 'negative'
}

export enum NotificationType {
  CONTACT_RECEIVED = 'contact_received',
  URGENT_CONTACT = 'urgent_contact',
  AI_ANALYSIS_COMPLETE = 'ai_analysis_complete',
  DAILY_SUMMARY = 'daily_summary'
}

// System Status Types
export interface SystemStatus {
  message: string;
  environment: string;
  features: string[];
  firebase_status: {
    available: boolean;
    initialized: boolean;
  };
  database_status: {
    available: boolean;
    initialized: boolean;
    connected: boolean;
  };
  ai_status: {
    available: boolean;
    initialized: boolean;
    model?: string;
  };
  vector_status: {
    available: boolean;
    initialized: boolean;
    model?: string;
  };
  email_status: {
    available: boolean;
    initialized: boolean;
    service?: string;
  };
  version: string;
}

export interface HealthStatus {
  status: string;
  service: string;
  version: string;
  features_enabled: {
    pydantic: boolean;
    crud_operations: boolean;
    firebase_auth: boolean;
    database: boolean;
    ai_analysis: boolean;
    vector_search: boolean;
    email_notifications: boolean;
  };
  storage_mode: string;
  auth_mode: string;
  ai_mode: string;
  vector_mode: string;
  email_mode: string;
  port?: string;
}

// Authentication Types
export interface User {
  uid: string;
  email: string;
  displayName?: string;
  photoURL?: string;
  emailVerified: boolean;
}

export interface AuthStatus {
  firebase_available: boolean;
  firebase_initialized: boolean;
  user_authenticated: boolean;
  user_info?: User;
  auth_mode: string;
}

// UI State Types
export interface LoadingState {
  isLoading: boolean;
  message?: string;
}

export interface ErrorState {
  hasError: boolean;
  message?: string;
  details?: string;
}

// API Response Wrappers
export interface ApiResponse<T> {
  data?: T;
  error?: string;
  status: number;
}

export interface ContactListResponse {
  contacts: ContactResponse[];
  total_count: number;
  user_authenticated: boolean;
  storage_mode: string;
  ai_enabled: boolean;
  vector_search_enabled: boolean;
  email_enabled: boolean;
  status: string;
}

// Form Types
export interface ContactFormData {
  name: string;
  email: string;
  subject: string;
  message: string;
}

export interface ContactFormErrors {
  name?: string;
  email?: string;
  subject?: string;
  message?: string;
  general?: string;
}

// Search Types
export interface SearchFilters {
  category?: CategoryType;
  urgency?: UrgencyLevel;
  sentiment?: SentimentType;
  dateFrom?: string;
  dateTo?: string;
  searchQuery?: string;
}

// Dashboard Types
export interface DashboardStats {
  total_contacts: number;
  pending_contacts: number;
  urgent_contacts: number;
  ai_analysis_accuracy: number;
  average_response_time: number;
  category_breakdown: Record<CategoryType, number>;
  urgency_breakdown: Record<UrgencyLevel, number>;
  daily_trends: Array<{
    date: string;
    contacts: number;
    urgent: number;
  }>;
}