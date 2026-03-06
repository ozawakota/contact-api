import axios, { AxiosResponse } from 'axios';
import React from 'react';
import {
  ContactRequest,
  ContactResponse,
  ContactListResponse,
  VectorSearchRequest,
  SimilarContact,
  EmailNotificationRequest,
  SystemStatus,
  HealthStatus,
  AuthStatus,
  ApiResponse
} from '../types';

// API Configuration
const API_BASE_URL = process.env.REACT_APP_API_URL || 'https://contact-api-service-url';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('firebase_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

// API Service Class
export class ApiService {
  // System Status
  static async getSystemStatus(): Promise<SystemStatus> {
    const response: AxiosResponse<SystemStatus> = await api.get('/');
    return response.data;
  }

  static async getHealthStatus(): Promise<HealthStatus> {
    const response: AxiosResponse<HealthStatus> = await api.get('/health');
    return response.data;
  }

  static async getAuthStatus(): Promise<AuthStatus> {
    const response: AxiosResponse<AuthStatus> = await api.get('/api/v1/auth/status');
    return response.data;
  }

  // Contact Management
  static async createContact(contactData: ContactRequest): Promise<ContactResponse> {
    console.log('ApiService.createContact called with:', contactData);
    console.log('Using API base URL:', API_BASE_URL);
    
    try {
      const response: AxiosResponse<ContactResponse> = await api.post('/api/v1/contacts', contactData);
      console.log('API response received:', response);
      return response.data;
    } catch (error) {
      console.error('ApiService.createContact error:', error);
      throw error;
    }
  }

  static async getContacts(): Promise<ContactListResponse> {
    const response: AxiosResponse<ContactListResponse> = await api.get('/api/v1/contacts');
    return response.data;
  }

  static async getContact(contactId: string): Promise<ContactResponse> {
    const response: AxiosResponse<ContactResponse> = await api.get(`/api/v1/contacts/${contactId}`);
    return response.data;
  }

  // Vector Search
  static async searchSimilarContacts(searchRequest: VectorSearchRequest): Promise<SimilarContact[]> {
    const response: AxiosResponse<SimilarContact[]> = await api.post('/api/v1/search', searchRequest);
    return response.data;
  }

  // AI Analysis
  static async analyzeText(textData: { text: string; subject?: string; name?: string }) {
    const response = await api.post('/api/v1/analyze', textData);
    return response.data;
  }

  // Email Notifications
  static async sendNotification(notificationRequest: EmailNotificationRequest) {
    const response = await api.post('/api/v1/notifications/send', notificationRequest);
    return response.data;
  }

  // Feature Status Checks
  static async getDatabaseStatus() {
    const response = await api.get('/api/v1/database/status');
    return response.data;
  }

  static async getAIStatus() {
    const response = await api.get('/api/v1/ai/status');
    return response.data;
  }

  static async getVectorStatus() {
    const response = await api.get('/api/v1/vector/status');
    return response.data;
  }

  static async getEmailStatus() {
    const response = await api.get('/api/v1/email/status');
    return response.data;
  }
}

// Utility functions for API calls with error handling
export const withErrorHandling = async <T>(
  apiCall: () => Promise<T>
): Promise<ApiResponse<T>> => {
  try {
    const data = await apiCall();
    return { data, status: 200 };
  } catch (error: any) {
    const errorMessage = error.response?.data?.detail || error.message || 'An error occurred';
    const status = error.response?.status || 500;
    return { error: errorMessage, status };
  }
};

// Hook for API calls with loading and error states
export const useApiCall = <T>() => {
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const execute = async (apiCall: () => Promise<T>): Promise<T | null> => {
    setLoading(true);
    setError(null);
    
    try {
      const result = await apiCall();
      return result;
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || err.message || 'An error occurred';
      setError(errorMessage);
      return null;
    } finally {
      setLoading(false);
    }
  };

  return { execute, loading, error };
};

export default ApiService;