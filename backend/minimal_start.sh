#!/bin/bash
# 最小限起動スクリプト - Cloud Run診断用

echo "🚀 Starting Minimal Contact API..."

# 基本環境変数
export PYTHONPATH=/app
export PYTHONUNBUFFERED=1

# PORT環境変数確認
echo "📋 PORT: ${PORT}"
echo "📋 ENVIRONMENT: ${ENVIRONMENT:-unknown}"
echo "📋 PWD: $(pwd)"

# Python動作確認
echo "🐍 Python version:"
python --version

# ファイル存在確認
echo "📂 Files check:"
ls -la minimal_main.py

# アプリケーション起動（最小限）
echo "🌐 Starting minimal FastAPI server on port ${PORT}..."
exec python -m uvicorn minimal_main:app --host 0.0.0.0 --port $PORT --log-level debug