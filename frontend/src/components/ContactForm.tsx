import React, { useState } from 'react';
import { ContactFormData, ContactFormErrors, ContactResponse } from '../types';
import { ApiService } from '../services/api';
import toast from 'react-hot-toast';
import AIAnalysisDisplay from './AIAnalysisDisplay';
import SimilarContactsList from './SimilarContactsList';
import LoadingSpinner from './LoadingSpinner';

interface ContactFormProps {
  onSuccess?: (contact: ContactResponse) => void;
  className?: string;
}

const ContactForm: React.FC<ContactFormProps> = ({ onSuccess, className = '' }) => {
  const [formData, setFormData] = useState<ContactFormData>({
    name: '',
    email: '',
    subject: '',
    message: ''
  });

  const [errors, setErrors] = useState<ContactFormErrors>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submittedContact, setSubmittedContact] = useState<ContactResponse | null>(null);

  const validateForm = (): boolean => {
    const newErrors: ContactFormErrors = {};

    // Name validation
    if (!formData.name.trim()) {
      newErrors.name = 'お名前は必須です';
    } else if (formData.name.trim().length < 2) {
      newErrors.name = 'お名前は2文字以上で入力してください';
    }

    // Email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!formData.email.trim()) {
      newErrors.email = 'メールアドレスは必須です';
    } else if (!emailRegex.test(formData.email)) {
      newErrors.email = '正しいメールアドレスを入力してください';
    }

    // Subject validation
    if (!formData.subject.trim()) {
      newErrors.subject = '件名は必須です';
    } else if (formData.subject.trim().length < 5) {
      newErrors.subject = '件名は5文字以上で入力してください';
    }

    // Message validation
    if (!formData.message.trim()) {
      newErrors.message = 'お問い合わせ内容は必須です';
    } else if (formData.message.trim().length < 10) {
      newErrors.message = 'お問い合わせ内容は10文字以上で入力してください';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleInputChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));

    // Clear specific field error when user starts typing
    if (errors[name as keyof ContactFormErrors]) {
      setErrors(prev => ({
        ...prev,
        [name]: undefined
      }));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      toast.error('入力内容を確認してください');
      return;
    }

    setIsSubmitting(true);
    setErrors({});

    try {
      console.log('送信データ:', formData);
      console.log('API URL:', process.env.REACT_APP_API_URL);
      
      const response = await ApiService.createContact(formData);
      
      console.log('APIレスポンス:', response);
      
      toast.success('お問い合わせを送信しました！', {
        duration: 5000,
        icon: '✅'
      });

      setSubmittedContact(response);
      
      // Reset form
      setFormData({
        name: '',
        email: '',
        subject: '',
        message: ''
      });

      // Call success callback if provided
      if (onSuccess) {
        onSuccess(response);
      }

    } catch (error: any) {
      console.error('API エラー詳細:', error);
      console.error('エラーレスポンス:', error.response);
      console.error('エラーメッセージ:', error.message);
      
      const errorMessage = error.response?.data?.detail || error.message || 'お問い合わせの送信に失敗しました';
      setErrors({ general: errorMessage });
      toast.error(`送信エラー: ${errorMessage}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const resetForm = () => {
    setFormData({
      name: '',
      email: '',
      subject: '',
      message: ''
    });
    setErrors({});
    setSubmittedContact(null);
  };

  // Show success view with AI analysis if contact was submitted
  if (submittedContact) {
    return (
      <div className={`space-y-6 ${className}`}>
        <div className="card border-green-200 bg-green-50">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <svg className="w-5 h-5 text-green-400" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-green-800">
                お問い合わせを受付ました
              </h3>
              <p className="mt-1 text-sm text-green-700">
                お問い合わせID: <span className="font-mono">{submittedContact.id}</span>
              </p>
            </div>
          </div>
        </div>

        {/* AI Analysis Display */}
        {submittedContact.ai_analysis && (
          <AIAnalysisDisplay analysis={submittedContact.ai_analysis} />
        )}

        {/* Similar Contacts */}
        {submittedContact.similar_contacts && submittedContact.similar_contacts.length > 0 && (
          <SimilarContactsList contacts={submittedContact.similar_contacts} />
        )}

        <div className="flex space-x-3">
          <button
            onClick={resetForm}
            className="btn-primary"
          >
            新しいお問い合わせ
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={`${className}`}>
      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="card">
          <h2 className="text-lg font-semibold text-gray-900 mb-6">
            お問い合わせフォーム
          </h2>

          {errors.general && (
            <div className="mb-4 p-4 border border-red-200 bg-red-50 rounded-md">
              <p className="text-sm text-red-600">{errors.general}</p>
            </div>
          )}

          <div className="space-y-4">
            {/* Name Field */}
            <div>
              <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-1">
                お名前 <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                id="name"
                name="name"
                value={formData.name}
                onChange={handleInputChange}
                className={`input-field ${errors.name ? 'border-red-300 focus:border-red-500 focus:ring-red-500' : ''}`}
                placeholder="山田太郎"
                disabled={isSubmitting}
              />
              {errors.name && (
                <p className="mt-1 text-sm text-red-600">{errors.name}</p>
              )}
            </div>

            {/* Email Field */}
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
                メールアドレス <span className="text-red-500">*</span>
              </label>
              <input
                type="email"
                id="email"
                name="email"
                value={formData.email}
                onChange={handleInputChange}
                className={`input-field ${errors.email ? 'border-red-300 focus:border-red-500 focus:ring-red-500' : ''}`}
                placeholder="yamada@example.com"
                disabled={isSubmitting}
              />
              {errors.email && (
                <p className="mt-1 text-sm text-red-600">{errors.email}</p>
              )}
            </div>

            {/* Subject Field */}
            <div>
              <label htmlFor="subject" className="block text-sm font-medium text-gray-700 mb-1">
                件名 <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                id="subject"
                name="subject"
                value={formData.subject}
                onChange={handleInputChange}
                className={`input-field ${errors.subject ? 'border-red-300 focus:border-red-500 focus:ring-red-500' : ''}`}
                placeholder="商品についてのお問い合わせ"
                disabled={isSubmitting}
              />
              {errors.subject && (
                <p className="mt-1 text-sm text-red-600">{errors.subject}</p>
              )}
            </div>

            {/* Message Field */}
            <div>
              <label htmlFor="message" className="block text-sm font-medium text-gray-700 mb-1">
                お問い合わせ内容 <span className="text-red-500">*</span>
              </label>
              <textarea
                id="message"
                name="message"
                rows={6}
                value={formData.message}
                onChange={handleInputChange}
                className={`input-field ${errors.message ? 'border-red-300 focus:border-red-500 focus:ring-red-500' : ''}`}
                placeholder="お問い合わせ内容を詳しくお書きください..."
                disabled={isSubmitting}
              />
              {errors.message && (
                <p className="mt-1 text-sm text-red-600">{errors.message}</p>
              )}
            </div>
          </div>

          <div className="mt-6">
            <button
              type="submit"
              disabled={isSubmitting}
              className="btn-primary w-full relative"
            >
              {isSubmitting && <LoadingSpinner className="w-4 h-4 mr-2" />}
              {isSubmitting ? '送信中...' : 'お問い合わせを送信'}
            </button>
          </div>

          <div className="mt-4 text-xs text-gray-500">
            <p>
              * 必須項目です。送信されたお問い合わせはAIによる自動分析が行われ、
              適切な担当者から迅速にご回答いたします。
            </p>
          </div>
        </div>
      </form>
    </div>
  );
};

export default ContactForm;