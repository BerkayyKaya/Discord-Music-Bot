import asyncio
import warnings

import discord
from discord import app_commands
from discord.ext import commands

from utils.audio.autoplay_filter import extract_artist
from utils.audio.manager import SourceManager
from utils.audio.models import Playlist
from utils.context import InteractionContext
from utils.views import MusicPlayerView
from utils.ytdl import ffmpeg_options

warnings.filterwarnings("ignore")

"""
ctx.author: Komutu yazan kullanıcıyı verir.

ctx.guild: Komutun kullanıldığı sunucuyu verir.

ctx.channel: Komutun yazıldığı metin kanalını verir.

ctx.voice_client: Botun o sunucudaki ses bağlantısını kontrol eder.

Slash komutlarında link gibi metin parametreleri tek bir seçenek olarak gelir.
Kullanıcı /play duman belkide alışman lazım yazdığında, tüm metin link değişkenine aktarılır.

link: Kullanıcının /play komutundan sonra yazdığı şarkı adı veya bağlantıdır.
"""

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.source_manager = SourceManager()
        self.queues = {}
        self.np_messages = {}

        # OTOMATİK OYNATMA İÇİN HAFIZA
        self.autoplay = {}
        self.history = {}
        self.current_song = {}
        self.track_history = {}

    # region play commands
    async def play_next(self, ctx):
        if not ctx.voice_client or not ctx.voice_client.is_connected():
            return

        if ctx.guild.id in self.queues and len(self.queues[ctx.guild.id]) > 0:
            next_song = self.queues[ctx.guild.id].pop(0)
            await self.play_music(ctx, next_song)
        elif self.autoplay.get(ctx.guild.id, False) and ctx.guild.id in self.current_song and ctx.voice_client:
            last_song = self.current_song[ctx.guild.id]
            provider_name = last_song.get("provider", "youtube")
            provider = self.source_manager.get_provider_by_name(provider_name)

            provider_display = "SoundCloud" if provider_name == "soundcloud" else "YouTube"
            await ctx.send(f"Oynatma listesi bitti, **{provider_display} Otomatik Oynatma** devrede! Benzer şarkılar aranıyor...", delete_after=5)

            try:
                guild_history = self.history.get(ctx.guild.id, [])
                recent_tracks = self.track_history.get(ctx.guild.id, [])
                new_track = await provider.get_autoplay_track(
                    last_song,
                    guild_history,
                    self.bot.loop,
                    recent_tracks=recent_tracks,
                )

                if new_track:
                    await self.play_music(ctx, new_track)
                else:
                    await ctx.send("Uygun bir sonraki şarkı bulunamadı!", delete_after=5)
            except Exception as e:
                print(f"Otomatik oynatma hatası ({provider_name}): {e}")
        else:
            try:
                await self.np_messages[ctx.guild.id].delete()
                del self.np_messages[ctx.guild.id]
            except:
                pass
            await ctx.send("Kuyruktaki tüm şarkılar bitti, liste boş!", delete_after=5)

    async def play_music(self, ctx, song_data):
        song_url = song_data["url"]
        title = song_data["title"]
        thumbnail = song_data.get("thumbnail", None)
        requester = song_data.get("requester", "Bilinmeyen Kullanıcı")
        self.current_song[ctx.guild.id] = song_data

        if ctx.guild.id not in self.track_history:
            self.track_history[ctx.guild.id] = []

        self.track_history[ctx.guild.id].append({
            "id": str(song_data["id"]),
            "title": title,
            "artist": song_data.get("artist") or extract_artist(title),
            "provider": song_data.get("provider", "youtube"),
        })

        if len(self.track_history[ctx.guild.id]) > 20:
            self.track_history[ctx.guild.id].pop(0)

        if ctx.guild.id not in self.history:
            self.history[ctx.guild.id] = []

        self.history[ctx.guild.id].append(song_data["id"])

        if len(self.history[ctx.guild.id]) > 20:
            self.history[ctx.guild.id].pop(0)

        player = discord.FFmpegPCMAudio(song_url, **ffmpeg_options)

        def after_playing(error):
            if error:
                print(f"\n[Error] Oynatma Hatası: {error}")
            asyncio.run_coroutine_threadsafe(self.play_next(ctx), self.bot.loop)

        ctx.voice_client.play(player, after=after_playing)

        fixed_title = ("\u2800" * 12) + "🎵 Şimdi Çalıyor 🎵" + ("\u2800" * 12)
        song_title = title if len(title) <= 55 else title[:55] + "..."
        embed = discord.Embed(
            title=fixed_title,
            description=f"**{song_title}**",
            color=discord.Color.from_rgb(155, 89, 182)
        )
        embed.add_field(name="İsteyen:", value=requester, inline=True)

        if len(self.queues[ctx.guild.id]) > 0:
            next_title = self.queues[ctx.guild.id][0]["title"]
            next_song_title = next_title if len(next_title) <= 45 else next_title[:45] + "..."
            embed.add_field(name="Sonraki Şarkı:", value=next_song_title)

        if thumbnail:
            embed.set_thumbnail(url=thumbnail)

        view = MusicPlayerView(self, original_embed=embed, autoplay_state=self.autoplay.get(ctx.guild.id, False))

        if ctx.guild.id in self.np_messages:
            try:
                await self.np_messages[ctx.guild.id].delete()
            except discord.NotFound as e:
                print(f"\n[Error] Bot eski mesajını silmeye çalışırken hata: {e}")
            except Exception as e:
                print(f"\n[Error] Bilinmeyen hata: {e}")

        new_message = await ctx.send(embed=embed, view=view)
        self.np_messages[ctx.guild.id] = new_message

    @app_commands.command(name="play", description="Şarkı adı veya bağlantı ile müzik çalar ya da kuyruğa ekler.")
    @app_commands.describe(link="Şarkı adı veya YouTube/SoundCloud bağlantısı")
    @app_commands.guild_only()
    async def play(self, interaction: discord.Interaction, link: str):
        ctx = InteractionContext(interaction)
        await ctx.defer()

        if not ctx.author.voice:
            return await ctx.send("Önce bir ses kanalına gir ki ben de gelebileyim!", delete_after=5)

        voice_client = ctx.voice_client
        if not voice_client:
            try:
                voice_client = await ctx.author.voice.channel.connect()
            except Exception as e:
                print(f"\n[Error] Kanala bağlanırken hata: {e}")
                return await ctx.send("Ses kanalına bağlanırken bir hata oluştu!", delete_after=5)

        try:
            await ctx.send("Şarkı aranıyor...", delete_after=5)
            provider = self.source_manager.get_provider(link)
            song_data = await provider.extract_track(link, requester=ctx.author, loop=self.bot.loop)

            if not song_data:
                return await ctx.send("Şarkı bulunamadı!", delete_after=5)

            if ctx.guild.id not in self.queues:
                self.queues[ctx.guild.id] = []

            if not voice_client.is_playing() and not voice_client.is_paused():
                await self.play_music(ctx, song_data)
            else:
                self.queues[ctx.guild.id].append(song_data)
                await ctx.send(f"Şarkı sıraya eklendi: **{song_data['title']}** | Sıradaki yeri: {len(self.queues[ctx.guild.id])}", delete_after=5)
        except Exception as e:
            print(f"\n[Error] Oynatma sırasında hata: {e}")
            await ctx.send("Şarkı açılırken bir hata oluştu!", delete_after=5)

    @app_commands.command(name="playlist", description="YouTube veya SoundCloud oynatma listesini kuyruğa ekler.")
    @app_commands.describe(link="Oynatma listesi bağlantısı")
    @app_commands.guild_only()
    async def playlist(self, interaction: discord.Interaction, link: str):
        ctx = InteractionContext(interaction)
        await ctx.defer()

        if not ctx.author.voice:
            return await ctx.send("Önce bir ses kanalına girmelisin ki ben de gelebileyim.", delete_after=10)

        voice_client = ctx.voice_client
        if not voice_client:
            try:
                voice_client = await ctx.author.voice.channel.connect()
            except Exception as e:
                print(f"\n[Error] Ses kanalına bağlanırken hata: {e}")
                return await ctx.send("Ses kanalına bağlanırken hata oluştu!", delete_after=5)

        try:
            await ctx.send("⏳ Playlist inceleniyor, şarkılar sıraya alınıyor...", delete_after=10)
            provider = self.source_manager.get_provider(link)
            playlist_data: Playlist = await provider.extract_playlist(link, requester=ctx.author, loop=self.bot.loop, limit=25)

            if not playlist_data or not playlist_data.tracks:
                return await ctx.send("Playlist boş, gizli veya bulunamadı!", delete_after=5)

            if ctx.guild.id not in self.queues:
                self.queues[ctx.guild.id] = []

            for track in playlist_data.tracks:
                self.queues[ctx.guild.id].append(track)

            await ctx.send(f"🎧 **{playlist_data.title}** listesinden **{len(playlist_data.tracks)}** şarkı başarıyla sıraya eklendi!", delete_after=5)

            if not voice_client.is_playing() and not voice_client.is_paused():
                if len(self.queues[ctx.guild.id]) > 0:
                    next_song = self.queues[ctx.guild.id].pop(0)
                    await self.play_music(ctx, next_song)
        except Exception as e:
            print(f"\n[Error] Playlist oynatma hatası: {e}")
            await ctx.send("Playlist açılırken bir hata oluştu!", delete_after=5)

    # region helper functions
    @app_commands.command(name="pause", description="Çalan müziği duraklatır.")
    @app_commands.guild_only()
    async def pause(self, interaction: discord.Interaction):
        ctx = InteractionContext(interaction)
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("Müzik durduruldu!", delete_after=5)
        elif ctx.voice_client and ctx.voice_client.is_paused():
            await ctx.send("Müzik zaten duraklatılmış. Devam etmek için /resume kullan.", delete_after=5)
        else:
            await ctx.send("Şu an çalan bir şarkı yok.", delete_after=5)

    @app_commands.command(name="resume", description="Duraklatılan müziği devam ettirir.")
    @app_commands.guild_only()
    async def resume(self, interaction: discord.Interaction):
        ctx = InteractionContext(interaction)
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("Müzik devam ediyor!", delete_after=5)
        elif ctx.voice_client and ctx.voice_client.is_playing():
            await ctx.send("Müzik zaten çalıyor.", delete_after=5)
        else:
            await ctx.send("Şu an çalan bir şarkı yok.", delete_after=5)

    @app_commands.command(name="leave", description="Botu ses kanalından çıkarır ve kuyruğu temizler.")
    @app_commands.guild_only()
    async def leave(self, interaction: discord.Interaction):
        ctx = InteractionContext(interaction)
        if not ctx.voice_client:
            return await ctx.send("Zaten herhangi bir ses kanalında değilim!", delete_after=5)

        if ctx.guild.id in self.queues:
            self.queues[ctx.guild.id].clear()

        if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            ctx.voice_client.stop()

        if ctx.guild.id in self.current_song:
            del self.current_song[ctx.guild.id]

        self.track_history.pop(ctx.guild.id, None)

        if ctx.guild.id in self.np_messages:
            try:
                await self.np_messages[ctx.guild.id].delete()
                del self.np_messages[ctx.guild.id]
            except:
                pass

        await ctx.voice_client.disconnect()
        await ctx.send("Kanaldan ayrılıyorum!", delete_after=5)

    @app_commands.command(name="liste", description="Sıradaki şarkıların listesini gösterir.")
    @app_commands.guild_only()
    async def list(self, interaction: discord.Interaction):
        ctx = InteractionContext(interaction)
        if ctx.guild.id not in self.queues or len(self.queues[ctx.guild.id]) == 0:
            return await ctx.send("Şu an kuyruk bomboş, şarkı eklemek için `/play` komutunu kullanabilirsin.", delete_after=5)

        message = "**Gelecek Şarkıların Listesi:**\n"
        for i, song in enumerate(self.queues[ctx.guild.id], start=1):
            message += f"{i}. **{song['title']}**\n"

            if i == 10 and not len(self.queues[ctx.guild.id]) < 11:
                message += f"... ve {len(self.queues[ctx.guild.id]) - 10} şarkı daha sırada bekliyor..."
                break

        await ctx.send(message)

    @app_commands.command(name="skip", description="Çalan şarkıyı atlayıp sıradaki şarkıya geçer.")
    @app_commands.guild_only()
    async def skip(self, interaction: discord.Interaction):
        ctx = InteractionContext(interaction)
        if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
            ctx.voice_client.stop()
            await ctx.send("Şarkıyı geçiyorum, sıradaki şarkıya bakılıyor...", delete_after=5)
        else:
            await ctx.send("Şarkılar bitti!", delete_after=5)

    @app_commands.command(name="shuffle", description="Kuyruktaki şarkıları rastgele karıştırır.")
    @app_commands.guild_only()
    async def shuffle(self, interaction: discord.Interaction):
        ctx = InteractionContext(interaction)
        import random
        if ctx.guild.id not in self.queues or len(self.queues[ctx.guild.id]) <= 1:
            return await ctx.send("Kuyrukta karıştırmaya yetecek kadar şarkı yok, minimum 2 şarkı olmalıdır!", delete_after=5)

        random.shuffle(self.queues[ctx.guild.id])
        await ctx.send("🎲 Kuyruk karıştırıldı!", delete_after=5)

    @app_commands.command(name="clear", description="Kuyruktaki tüm şarkıları temizler.")
    @app_commands.guild_only()
    async def clear(self, interaction: discord.Interaction):
        ctx = InteractionContext(interaction)
        if ctx.guild.id in self.queues and self.queues[ctx.guild.id]:
            self.queues[ctx.guild.id].clear()
            await ctx.send("Kuyruk temizlendi!", delete_after=5)
        else:
            await ctx.send("Şarkılar bitti, temizlenecek bir şey yok.", delete_after=5)

    # endregion


async def setup(bot):
    await bot.add_cog(Music(bot))