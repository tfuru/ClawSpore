import os
from typing import Any
from core.tools.base import BaseTool

class CalculatorTool(BaseTool):
    @property
    def name(self) -> str:
        return 'calculator'

    @property
    def description(self) -> str:
        return '2つの数値を足し算し、その合計を返します。'

    @property
    def parameters(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'num1': {
                    'type': 'number',
                    'description': '最初の数値'
                },
                'num2': {
                    'type': 'number',
                    'description': '2番目の数値'
                }
            },
            'required': ['num1', 'num2']
        }

    async def execute(self, num1: float = None, num2: float = None, **kwargs) -> Any:
        # 引数名の揺れに対応
        if num1 is None:
            num1 = kwargs.get('a')
        if num2 is None:
            num2 = kwargs.get('b')
            
        if num1 is None or num2 is None:
            return "Error: num1 と num2 を指定してください。"
            
        try:
            result = float(num1) + float(num2)
            return f"計算結果: {num1} + {num2} = {result}"
        except Exception as e:
            return f"Error: 計算に失敗しました。{str(e)}"
