import os
import discord
from discord.ext import commands

class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.message_content = True
        intents.voice_states = True

        super().__init__(
            command_prefix = ".",
            intents = intents,
            help_command = None
        )

    async def setup_hook(self):
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py") and not filename.endswith("__"):
                await self.load_extension(f"cogs.{filename[:-3]}")
                print(f"[System] {filename[:-3]} extension added succesfully.")

    async def on_ready(self):
        print(f"[System] Bot logged in with the username -> '{self.user.name}'")