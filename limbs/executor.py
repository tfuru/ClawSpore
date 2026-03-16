import os
import docker # Podman は Docker API 互換
from dotenv import load_dotenv

load_dotenv()

class ToolExecutor:
    def __init__(self):
        # Podman Socket のパスを環境変数から取得
        self.socket_path = os.getenv("PODMAN_SOCKET")
        
        # SSH 接続の場合、docker-py は ssh://user@host:port の形式を期待し、
        # 末尾にパスがついているとエラーになることがあるため、一旦分離して試行
        if self.socket_path and self.socket_path.startswith("ssh://"):
            self._setup_ssh_key()
            # パス部分を削除した URL を作成
            original_url = self.socket_path
            import urllib.parse
            parsed = urllib.parse.urlparse(original_url)
            self.socket_path = f"ssh://{parsed.netloc}"
            print(f"ToolExecutor: Refined SSH URL for docker-py: {self.socket_path}")

        try:
            # use_ssh_client=True にすることでシステムの ssh コマンドを使用（これが一番確実）
            self.client = docker.DockerClient(base_url=self.socket_path, use_ssh_client=True)
            print(f"ToolExecutor: Connected to Podman at {self.socket_path}")
        except Exception as e:
            print(f"ToolExecutor Error: Failed to connect to Podman. {e}")
            self.client = None

    def _setup_ssh_key(self):
        """SSH 鍵をファイルに書き出し、権限を設定する"""
        key_path = os.path.expanduser("~/.ssh/id_rsa")
        os.makedirs(os.path.dirname(key_path), exist_ok=True)
        
        # 鍵の内容（本来は環境変数等から渡すべきだが、今回は定数化）
        ssh_key = os.getenv("PODMAN_SSH_KEY")
        with open(key_path, "w") as f:
            f.write(ssh_key.strip() + "\n")
        os.chmod(key_path, 0o600)
        print(f"ToolExecutor: SSH key setup at {key_path}")
        
        # SSH 設定の緩和 (初回接続時の known_hosts エラー防止)
        config_path = os.path.expanduser("~/.ssh/config")
        with open(config_path, "w") as f:
            f.write("Host *\n  StrictHostKeyChecking no\n  UserKnownHostsFile /dev/null\n")
        os.chmod(config_path, 0o600)

    async def execute_tool(self, command, network_enabled=False, session_id=None):
        """隔離されたコンテナでコマンドを実行する"""
        if not self.client:
            return "Error: Podman connection is not available."

        image_name = "clawspore-limbs:latest"
        
        # ボリュームの設定: session_id があればホストのディレクトリをマウント
        volumes = {}
        if session_id:
            # コンテナ内でのディレクトリ作成用パス
            container_workspace_dir = os.path.join(os.getcwd(), "workspaces", session_id)
            if not os.path.exists(container_workspace_dir):
                os.makedirs(container_workspace_dir, exist_ok=True)
                # Podman コンテナ内の worker ユーザーが書き込めるように全権限を付与
                os.chmod(container_workspace_dir, 0o777)
                print(f"ToolExecutor: Created workspace directory in container: {container_workspace_dir}")
            else:
                try:
                    os.chmod(container_workspace_dir, 0o777)
                except Exception:
                    pass
            
            # ホスト側のベースパス (Podman/Dockerに対するマウント元パス)
            # コンテナ内ではなく、Podmanデーモンが動いているホストマシンのパスである必要がある
            host_base_dir = os.getenv("HOST_WORKSPACE_DIR", "/Volumes/SSD/work/ClawSpore")
            host_workspace_dir = os.path.join(host_base_dir, "workspaces", session_id)
            
            # コンテナ内の書き込み可能な場所（/tmp/workspace）にマウント
            volumes[host_workspace_dir] = {'bind': '/tmp/workspace', 'mode': 'rw'}
            print(f"ToolExecutor: Mounting host workspace {host_workspace_dir} to /tmp/workspace")

        try:
            print(f"ToolExecutor: Running command in sandbox: {command}")
            # コンテナの起動と実行
            container = self.client.containers.run(
                image=image_name,
                command=command,
                remove=True, # 実行後に自動削除
                network_disabled=not network_enabled,
                mem_limit="128m",
                nano_cpus=500000000, # 0.5 CPU
                cap_drop=["ALL"], # 全ての特権を剥奪
                detach=False,
                stdout=True,
                stderr=True,
                volumes=volumes
            )
            result = container.decode('utf-8')
            return result if result.strip() else "Command executed successfully with no output."
        except Exception as e:
            print(f"ToolExecutor Error during execution: {e}")
            return f"Error: Command execution failed. {e}"

# シングルトンインスタンス
executor = ToolExecutor()
