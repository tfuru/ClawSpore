import os
import asyncio
import aiohttp
from dotenv import load_dotenv

async def test_discord_token():
    load_dotenv()
    token = os.getenv('DISCORD_TOKEN')
    
    if not token:
        print("❌ Error: DISCORD_TOKEN が .env に設定されていません。")
        return

    print(f"🔍 トークンの検証を開始します...")
    
    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get("https://discord.com/api/v10/users/@me", headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                print(f"✅ 接続成功！")
                print(f"   Bot名: {data.get('username')}#{data.get('discriminator')}")
                print(f"   Bot ID: {data.get('id')}")
            elif resp.status == 401:
                print("❌ エラー: トークンが無効です (401 Unauthorized)。")
                print("   .env の DISCORD_TOKEN が正しいか確認してください。")
            else:
                print(f"❌ エラー: Discord API がステータスコード {resp.status} を返しました。")
                print(await resp.text())

if __name__ == "__main__":
    asyncio.run(test_discord_token())
