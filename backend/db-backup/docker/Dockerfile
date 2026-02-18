FROM python:3.11-slim
WORKDIR /app

# 基準が backend なので、db-backup/docker/ の中にあるファイルを指定
COPY db-backup/docker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# backend フォルダの中の app/ (main.pyがある場所) を /app にコピー
COPY app/ .

# 実行コマンド
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]