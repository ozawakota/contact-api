FROM python:3.11-slim

# システムパッケージの更新とクリーンアップ
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 基準が backend なので、db-backup/docker/ の中にあるファイルを指定
COPY db-backup/docker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# backend フォルダの内容全体をコピーして構造を維持
COPY . .

# 環境変数設定
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 実行コマンド（app.main形式で指定）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]