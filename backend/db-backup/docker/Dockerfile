FROM python:3.11-slim

# Phase 6: Gemini AI分析機能追加
RUN pip install fastapi==0.104.1 uvicorn==0.24.0 pydantic==2.5.0 firebase-admin==6.4.0 asyncpg==0.29.0 databases==0.8.0 google-generativeai==0.3.2

WORKDIR /app

# v6 アプリケーションファイルをコピー
COPY app_v6.py .

# 環境変数設定
ENV PYTHONUNBUFFERED=1

# 動的ポート対応
CMD ["sh", "-c", "python -m uvicorn app_v6:app --host 0.0.0.0 --port $PORT"]