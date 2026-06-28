import discord
from discord.ext import commands

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}

async def setup(bot):
        await bot.add_cog(Music(bot))
