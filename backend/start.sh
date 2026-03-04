#!/bin/bash
# Cloud Run最適化起動スクリプト

echo "🚀 Starting Contact API for Cloud Run..."

# 環境変数の確認とデフォルト設定
export PORT=${PORT:-8080}
export ENVIRONMENT=${ENVIRONMENT:-production}
export PYTHONPATH=/app
export PYTHONUNBUFFERED=1

echo "📋 Environment Configuration:"
echo "  PORT: $PORT"
echo "  ENVIRONMENT: $ENVIRONMENT"
echo "  PYTHONPATH: $PYTHONPATH"

# ヘルスチェックエンドポイントの事前検証
echo "🔧 Pre-startup validation..."

# Uvicornサーバー起動（Cloud Run最適化設定）
echo "🌐 Starting Uvicorn server..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port $PORT \
    --workers 1 \
    --timeout-keep-alive 30 \
    --timeout-graceful-shutdown 30 \
    --log-level info \
    --no-access-log \
    --loop uvloop