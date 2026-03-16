# ツール実行用の最小構成イメージ
FROM alpine:latest

# 基本的なツールのインストール (必要最低限に絞る)
RUN apk add --no-cache \
    python3 \
    bash \
    curl \
    jq

# 非ルートユーザーの作成 (セキュリティのため)
RUN adduser -D worker
USER worker

# ワークスペースの作成と権限設定
RUN mkdir -p /tmp/workspace && chown worker:worker /tmp/workspace
WORKDIR /tmp/workspace

# デフォルトのコマンド (何もしない)
CMD ["sh"]
