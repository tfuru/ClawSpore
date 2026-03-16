FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# 依存パッケージのインストール (SSH クライアント, Node.js 環境など)
RUN apt-get update && apt-get install -y \
    openssh-client \
    nodejs \
    npm \
    podman \
    curl \
    && curl -fsS https://dotenvx.sh/install.sh | sh \
    && rm -rf /var/lib/apt/lists/*

# requirements.txt をコピーしてインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードのコピー
COPY . .

# 実行
CMD ["python", "core/main.py"]
