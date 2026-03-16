from abc import ABC, abstractmethod
from typing import Any, Dict, List

class BaseTool(ABC):
    """
    全てのツールの基底クラス。
    MCP (Model Context Protocol) のツール定義に準拠したインターフェースを提供します。
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """ツールの名前 (識別子)"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """ツールの説明 (LLM がいつ使うべきか判断するための情報)"""
        pass

    @property
    @abstractmethod
    def parameters(self) -> Dict[str, Any]:
        """引数の JSON スキーマ定義"""
        pass

    @property
    def requires_approval(self) -> bool:
        """
        実行前にユーザーの承認が必要かどうか。
        デフォルトは False (承認不要)。
        """
        return False

    @property
    def is_dangerous(self) -> bool:
        """
        システム破壊や大規模な変更を伴う「危険なツール」かどうか。
        True の場合、管理権限チェックなどが適用されます。
        """
        return False

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """ツールの実行ロジック"""
        pass

    def to_tool_def(self) -> Dict[str, Any]:
        """LLM に渡すための API 定義形式に変換"""
        # サブクラスが @property を忘れて単なるメソッド（callable）として定義した場合の救済
        name = self.name() if callable(self.name) else self.name
        description = self.description() if callable(self.description) else self.description
        params = self.parameters() if callable(self.parameters) else self.parameters
        
        # JSON Schema のルートに "type": "object" がない場合は補完する (LM Studio 等の厳格なバリデーション対策)
        if isinstance(params, dict) and "type" not in params:
            params = {
                "type": "object",
                "properties": params
            }
        elif not params:
             params = {"type": "object", "properties": {}}
        
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": params
            }
        }
