import re

def test_regex():
    # Simulated assistant response with Markdown links and tags
    content = """
[THOUGHT] ユーザーは猫の動画を求めています。
YouTubeで見つけた動画です：
1. [面白い猫の動画 2024](https://www.youtube.com/watch?v=abc)
2. [可愛い子猫の日常](https://www.youtube.com/watch?v=def)
[1] などの形式も試します。
"""
    print(f"--- Original Content ---\n{content}")
    
    # Current regex used in Agent.py
    temp_content = re.sub(r'<think>.*?(?:</think>|$)', '', content, flags=re.DOTALL)
    filtered_content = re.sub(r'\[.*?(?:\]|$)', '', temp_content, flags=re.DOTALL).strip()
    
    print(f"\n--- Filtered Content (Current) ---\n{filtered_content}")
    
    # Improved regex: Only remove specific tags or use negative lookahead
    # Here, we only want to remove internal tags like [THOUGHT], [SYSTEM], etc.
    # Or, we can just say: remove anything that starts with [ and ends with ] IF it's one of the known tags.
    known_tags = ["THOUGHT", "SYSTEM", "EXECUTION RESULT", "TOOL_RESULT", "このメッセージはシステムにより正常な状態に補正されました"]
    tag_pattern = r'\[(?:' + '|'.join(re.escape(tag) for tag in known_tags) + r').*?\]'
    improved_filtered = re.sub(tag_pattern, '', temp_content, flags=re.DOTALL).strip()
    
    print(f"\n--- Improved Filtered Content ---\n{improved_filtered}")

if __name__ == "__main__":
    test_regex()
