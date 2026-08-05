import asyncio
import os

from dotenv import load_dotenv

from core.bot import MusicBot


async def main():
    bot = MusicBot()
    load_dotenv()
    TOKEN = os.getenv("discord_token")
    
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())