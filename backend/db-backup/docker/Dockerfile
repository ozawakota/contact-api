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

# 起動スクリプトを実行可能にする
RUN chmod +x start.sh

# 環境変数設定
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# PORT環境変数を動的に使用（Cloud Run対応）
ENV PORT=8080
EXPOSE $PORT

# 実行コマンド（最適化された起動スクリプト使用）
CMD ["./start.sh"]