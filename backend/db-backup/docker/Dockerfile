FROM python:3.11-slim
WORKDIR /app

# 基準が backend フォルダなので、app/ の中にあるファイルを指定
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# app フォルダの中身（main.pyなど）をコンテナの /app にコピー
COPY app/ .

# 実行コマンド：main.py はコンテナの /app 直下にあるので "main:app" でOK
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]