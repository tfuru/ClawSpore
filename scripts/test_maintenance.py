import asyncio
import os
from core.tools.dynamic.system_inspector import SystemInspectorTool
from core.tools.dynamic.workspace_vacuum import WorkspaceVacuumTool

async def test_maintenance():
    print("--- Maintenance Tools Test ---")
    
    # 1. System Inspector のテスト
    print("\n[Test 1] Testing SystemInspectorTool...")
    inspector = SystemInspectorTool()
    report = await inspector.execute(verbose=True)
    print("Report Output:")
    print(report)
    if "診断完了" in report:
        print("✅ SystemInspector: Report generated successfully.")
    else:
        print("❌ SystemInspector: Report failed.")

    # 2. Workspace Vacuum のテスト
    print("\n[Test 2] Testing WorkspaceVacuumTool...")
    vacuum = WorkspaceVacuumTool()
    
    # テスト用ファイルの作成
    test_dir = "workspaces/sessions"
    os.makedirs(test_dir, exist_ok=True)
    test_file = os.path.join(test_dir, "maintenance_test.tmp")
    with open(test_file, "w") as f:
        f.write("test")
    print(f"Created test file: {test_file}")

    # Dry Run
    dry_res = await vacuum.execute(dry_run=True)
    print(f"Dry Run Result: {dry_res}")
    
    # 実実行
    res = await vacuum.execute(dry_run=False)
    print(f"Actual Run Result: {res}")
    
    if "削除しました" in res or "空です" in res:
        print("✅ WorkspaceVacuum: Cleanup successful.")
    else:
        print("❌ WorkspaceVacuum: Cleanup failed.")

if __name__ == "__main__":
    asyncio.run(test_maintenance())
