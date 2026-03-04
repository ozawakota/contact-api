FROM python:3.11-slim

# Phase 2: 基本的な依存関係を追加
RUN pip install fastapi==0.104.1 uvicorn==0.24.0

WORKDIR /app

# v2 アプリケーションファイルをコピー
COPY app_v2.py .

# 環境変数設定
ENV PYTHONUNBUFFERED=1

# 動的ポート対応
CMD ["sh", "-c", "python -m uvicorn app_v2:app --host 0.0.0.0 --port $PORT"]