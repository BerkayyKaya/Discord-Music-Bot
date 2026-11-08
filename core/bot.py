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
            # Komutlar slash komutu ("/") olarak çalışır; prefix komutu desteği yoktur.
            command_prefix = commands.when_mentioned,
            intents = intents,
            help_command = None,
            description = "YouTube ve SoundCloud üzerinden müzik çalan Discord botu."
        )

    async def setup_hook(self):
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py") and not filename.endswith("__"):
                await self.load_extension(f"cogs.{filename[:-3]}")
                print(f"[System] {filename[:-3]} extension added succesfully.")

        # Slash komutlarını Discord'a kaydet. guild_id tanımlıysa komutlar sadece
        # o sunucuda anında görünür; tanımlı değilse global olarak kaydedilir
        # (global komutların yayılması bir saati bulabilir).
        guild_id = os.getenv("guild_id")
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            synced = await self.tree.sync(guild=guild)
            print(f"[System] {len(synced)} slash command(s) synced to guild {guild_id}.")
        else:
            synced = await self.tree.sync()
            print(f"[System] {len(synced)} slash command(s) synced globally.")

    async def on_ready(self):
        print(f"[System] Bot logged in with the username -> '{self.user.name}'")
