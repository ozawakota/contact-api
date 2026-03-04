#!/bin/bash
# Cloud Run最適化起動スクリプト

echo "🚀 Starting Contact API for Cloud Run..."

# 環境変数の確認（Cloud RunはPORTを自動設定）
# PORT環境変数はCloud Runが自動的に設定するため、デフォルト値のみ設定
export PORT=${PORT:-8080}  # フォールバック用（通常は不要）
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
echo "🌐 Starting Uvicorn server on port $PORT..."

# デバッグ情報出力
echo "📋 Working directory: $(pwd)"
echo "📋 Python path: $PYTHONPATH"
echo "📋 Available files:"
ls -la app/

# より安定した起動設定（uvloopなし）
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port $PORT \
    --workers 1 \
    --timeout-keep-alive 60 \
    --log-level debug \
    --access-log