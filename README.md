# ClawSpore - クロウスポア

自律型のAIアシスタントツール **クロウスポア**。
「自律判断」「実行」「改善」のサイクルを Podman 上で安全に回しつつ、Discord を介して人間と協調することを目指したプロジェクトです。

## プロジェクトのビジョン
人間の指示を待つだけでなく、自ら考え、環境を操作し、その結果から学習して継続的に自己改善する AI エージェントの実現を目指します。

## システムアーキテクチャ
思考を司る **Core**、外部操作を担う **MCP/CLI**、そして人間との窓口となる **Discord** の3層構造で構築します。

- **Core (Brain)**: 自律判断を担当。ローカル LLM 環境である **LM Studio** を主要な推論エンジンとして利用します。Python で実装。
- **ToolRouter (Routing)**: 推論エンジンを用いて、大量のツールの中から現在の文脈に最適なものを事前に選別。モデルの混乱を防ぎ、精度と速度を両立させます。
- **MCP/CLI (Limbs)**: 外部操作を担う「手足」。Model Context Protocol (MCP) を通じてツールを実行します。
- **Discord (Interface)**: 人間とのインタラクション。進捗報告や承認、相談を行います。

## 技術スタック
- **Language**: Python 3.11+
- **LLM**: LM Studio (Local LLM)
- **Container**: Podman (Security Isolation)
- **Messaging**: Discord
- **Architecture**: Model Context Protocol (MCP)

## セットアップ (Getting Started)
※現在開発中のため、セットアップ手順は随時更新されます。

### 前提条件
- [Podman](https://podman.io/) がインストールされていること
- [LM Studio](https://lmstudio.ai/) がインストールされ、API サーバーが起動していること

### セットアップ手順
1. **リポジトリをクローン**
2. **Discord Bot の準備**
    - [Discord Developer Portal](https://discord.com/developers/applications) にアクセスし、新しい Application を作成。
    - `Bot` セクションから `Token` を取得。
    - `Privileged Gateway Intents` 欄の **MESSAGE CONTENT INTENT** を ON に設定。
      > [!IMPORTANT]
      > これを有効にしないとメッセージの読み取りができず、起動時にエラーが発生します。
3. **環境変数の設定**
    - `.env.example` をコピーして `.env` を作成。
    - 各種 API キーやトークンを記入。
    - **[推奨] dotenvx による暗号化**
        - セキュリティ向上のため、`dotenvx` を利用して `.env` を暗号化します。
        ```bash
        # dotenvx のインストール (Mac)
        brew install dotenvx/brew/dotenvx
        
        # 暗号化の実行 (.env.keys が生成されます)
        dotenvx encrypt
        
        # 復号 (生テキストに戻す場合)
        # dotenvx decrypt
        ```
    - `DISCORD_TOKEN`: 取得したボットトークン。
    - `GEMINI_API_KEY`: (任意) ツール作成支援用の Gemini API キー。
    - `LM_STUDIO_URL`: LM Studio API のエンドポイント。

4. **コンテナのビルドと起動**
    - **暗号化を利用する場合**:
        `.env.keys` に記載された `DOTENV_PRIVATE_KEY_DOT_ENV` の値を環境変数 `DOTENV_PRIVATE_KEY` として指定して起動します。
        ```bash
        podman compose build
        DOTENV_PRIVATE_KEY="【あなたの.env.keysのキー】" podman compose up -d
        ```
    - **暗号化を利用しない場合**:
        通常通り起動します。
        ```bash
        podman compose build
        podman compose up -d
        ```

## 使い方 (Usage)

### Discord での対話
Bot が起動すると、Discord を通じて AI と対話できます。
- **メンション**: `@ClawSpore Bot [メッセージ]` で AI に話しかけます。
- **コマンド**: `!ask [メッセージ]` でも同様に質問が可能です。
- **疎通確認**: `!hello` で Bot の応答確認ができます。

### ログの確認
指定したログ用チャンネル（デフォルト: `#log`）に、起動通知やシステムログが送信されます。

## プロジェクト構成 (Structure)
主要なプロンプトは [prompts/](file:///Volumes/SSD/work/ClawSpore/prompts/README.md) にまとめられています。

```text
.
├── core/          # 自律判断・ロジック層 (思考)
│   ├── llm_client.py # 各種 LLM へ接続クライアント
│   ├── router.py     # ツール選別 (ToolRouter) 実装
│   └── main.py       # エントリーポイント
├── interface/     # 外部インターフェース層
│   └── discord_client.py # Discord Bot 実装
├── prompts/       # プロンプト定義集
├── scripts/       # メンテナンス・テスト用スクリプト
├── Dockerfile     # コンテナ定義
├── compose.yaml   # サービス定義
└── requirements.txt # Python 依存関係
```

## ロードマップ (Roadmap)
- [x] 基本的な Discord インターフェースの実装
- [x] LM Studio / Gemini 連携基盤の構築
- [x] Podman 上での安全なツール実行環境の構築
- [x] MCP および動的ツール（`create_tool`）による機能拡張
- [x] 自己改善・自律思考ループ (ReAct) の安定化
- [x] 人間との協調保護 (Human-in-the-Loop) の実装
- [x] 記憶の永続化 (Memory Persistence) の実装
- [x] **自己診断と自動修復 (Self-Healing) の実装**
- [x] 複数セッションの管理と長期記憶 (RAG) の基礎実装
- [x] セキュリティ・ガバナンスと詳細な実行権限管理 (ACL) の基礎実装
- [x] RAG の検索精度向上と長期記憶の自律的な整理（ノイズフィルタリング実装済み）
- [x] ACL の Discord 上からの動的設定機能の実装（`grant_tool`, `revoke_tool` 完了）
- [x] マルチモーダル対応（画像解析・リサイズ処理実装済み）
- [x] 外部 API 連携ツールのプリセット拡充（メンテナンス、画像解説ツール追加）
- [x] **ToolRouter によるツールの動的選別とフィルタリングの実装**

## ライセンス

