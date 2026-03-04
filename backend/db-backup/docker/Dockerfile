FROM python:3.11-slim

# Phase 5: PostgreSQL接続追加（オプショナル）
RUN pip install fastapi==0.104.1 uvicorn==0.24.0 pydantic==2.5.0 firebase-admin==6.4.0 asyncpg==0.29.0 databases==0.8.0

WORKDIR /app

# v5 アプリケーションファイルをコピー
COPY app_v5.py .

# 環境変数設定
ENV PYTHONUNBUFFERED=1

# 動的ポート対応
CMD ["sh", "-c", "python -m uvicorn app_v5:app --host 0.0.0.0 --port $PORT"]