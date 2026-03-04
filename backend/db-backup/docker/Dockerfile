FROM python:3.11-slim

# Phase 4: Firebase認証追加（オプショナル）
RUN pip install fastapi==0.104.1 uvicorn==0.24.0 pydantic==2.5.0 firebase-admin==6.4.0

WORKDIR /app

# v4 アプリケーションファイルをコピー
COPY app_v4.py .

# 環境変数設定
ENV PYTHONUNBUFFERED=1

# 動的ポート対応
CMD ["sh", "-c", "python -m uvicorn app_v4:app --host 0.0.0.0 --port $PORT"]