FROM python:3.11-slim

# Phase 8: 完全版 - メール通知機能追加
RUN pip install fastapi==0.104.1 uvicorn==0.24.0 pydantic==2.5.0 firebase-admin==6.4.0 asyncpg==0.29.0 databases==0.8.0 google-generativeai==0.3.2 sentence-transformers==2.2.2 scikit-learn==1.3.2 numpy==1.24.3 sendgrid==6.10.0

WORKDIR /app

# v8 アプリケーションファイル（完全版）をコピー
COPY app_v8.py .

# 環境変数設定
ENV PYTHONUNBUFFERED=1

# 動的ポート対応
CMD ["sh", "-c", "python -m uvicorn app_v8:app --host 0.0.0.0 --port $PORT"]