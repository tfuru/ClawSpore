import subprocess
import os
from limbs.executor import executor

def test():
    # executor をインポートして SSH キー生成を保証
    print("Testing podman remote execution...")
    env = os.environ.copy()
    env["CONTAINER_HOST"] = os.getenv("PODMAN_SOCKET")
    
    cmd = ["podman", "--remote", "--identity", "/root/.ssh/id_rsa", "run", "-i", "--rm", "docker.io/library/steam-store-search-mcp-mcp-server:latest"]
    print(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    
    print("STDOUT:")
    print(result.stdout)
    print("STDERR:")
    print(result.stderr)
    print(f"Exit code: {result.returncode}")

if __name__ == "__main__":
    test()
