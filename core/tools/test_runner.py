import sys
import io
import unittest
import traceback
from typing import Any
from core.tools.base import BaseTool

class TestRunnerTool(BaseTool):
    """
    Pythonコード（unittestまたは単純なスクリプト）を実行し、テスト結果を確認するためのツール。
    AIが自ら作成したツールの動作確認やバグ修正を行うために使用します。
    """

    @property
    def name(self) -> str:
        return "test_runner"

    @property
    def description(self) -> str:
        return (
            "Pythonのテストコードを実行し、その結果（成功/失敗/エラー）を返します。\n"
            "unittest.TestCaseを継承したクラスを含むコード、または単純な実行コードを渡してください。\n"
            "実行結果の標準出力とエラー内容が返されるため、デバッグに役立ちます。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "test_code": {
                    "type": "string",
                    "description": "実行するPythonテストコード全体。unittest形式を推奨します。"
                }
            },
            "required": ["test_code"]
        }

    def requires_approval(self) -> bool:
        return True  # 任意のコードを実行するため承認必須

    async def execute(self, test_code: str, **kwargs) -> Any:
        # キャプチャ用のストリーム
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        # 実行用名前空間
        namespace = {}
        
        # システムの出力を一時的に乗っ取る
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = stdout_capture
        sys.stderr = stderr_capture
        
        try:
            # 1. コードの実行（クラス定義などを名前空間に読み込む）
            exec(test_code, namespace)
            
            # 2. unittest の検索と実行
            loader = unittest.TestLoader()
            # 名前空間内の TestCase を探す
            suite = loader.loadTestsFromModule(type('MockModule', (), namespace))
            
            if suite.countTestCases() > 0:
                # unittest 形式のテストが見つかった場合
                runner = unittest.TextTestRunner(stream=stdout_capture, verbosity=2)
                result = runner.run(suite)
                
                output = stdout_capture.getvalue()
                error_output = stderr_capture.getvalue()
                
                summary = (
                    f"Test Results: {'SUCCESS' if result.wasSuccessful() else 'FAILED'}\n"
                    f"Ran {result.testsRun} tests.\n"
                    f"Failures: {len(result.failures)}\n"
                    f"Errors: {len(result.errors)}\n"
                )
                
                full_details = ""
                if not result.wasSuccessful():
                    full_details += "\n--- Failure Details ---\n"
                    for test, err in result.failures + result.errors:
                        full_details += f"[{test._testMethodName}]: {err}\n"
                
                return f"{summary}\n{output}\n{error_output}\n{full_details}"
            else:
                # unittest が見つからない場合は、単純なスクリプトとして実行された結果を返す
                output = stdout_capture.getvalue()
                error_output = stderr_capture.getvalue()
                return f"No unittest cases found. Script output:\n{output}\n{error_output}"

        except Exception:
            # 構文エラーや実行時エラーのトレースバックを返す
            return f"Error during test execution:\n{traceback.format_exc()}"
        finally:
            # ストリームを戻す
            sys.stdout = old_stdout
            sys.stderr = old_stderr
