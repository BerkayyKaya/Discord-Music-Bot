import discord
from discord.ext import commands
from utils.ytdl import ffmpeg_options, ytdl
import asyncio
import warnings
warnings.filterwarnings("ignore")

"""
ctx.author: Komutu yazan kullanıcıyı verir.

ctx.guild: Komutun kullanıldığı sunucuyu verir.

ctx.channel: Komutun yazıldığı metin kanalını verir.

ctx.voice_client: Botun o sunucudaki ses bağlantısını kontrol eder.

*: Bu discord.py'a özel çok kullanışlı bir özelliktir. Kullanıcı: 
!play duman belkide alışman lazım derse, bot sadece ilk kelimeyi yani "duman" kelimesini link değişkenine atar, geri kalanını atlar. 
Araya * koyduğumuzda ise bota şunu demiş oluruz: "Komuttan sonra yazılan her şeyi tek bir parça olarak al ve link değişkeninin içine koy."

link: Kullanıcının !play komutundan sonra yazdığı şeydir. link, arama, kelime, sarki vb. gibi...
"""


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}

    async def play_next(self, ctx):
        # ilgili sunucunun kuyruğunda şarkı var mı?
        if ctx.guild.id in self.queues and len(self.queues[ctx.guild.id]) > 0:
            next_song = self.queues[ctx.guild.id].pop(0) # ilgili sunucunun kuyruğundaki sıradaki şarkıyı çıkart ve çal
            await self.play_music(ctx, next_song)
        else:
            await ctx.send("Kuyruktaki tüm şarkılar bitti, liste boş!", delete_after = 5) # bir uyarı mesajı gönder ve 5 saniye sonra sil
    
    async def play_music(self, ctx, song_data):
        song_url = song_data["url"]
        title = song_data["title"]
        thumbnail = song_data.get("thumbnail", None) # thumbnail varsa çek yoksa None ata

        player = discord.FFmpegPCMAudio(song_url, **ffmpeg_options)

        def after_playing(error):
            if error:
                print(f"\n[Error] Oynatma Hatası: {error}")
            asyncio.run_coroutine_threadsafe(self.play_next(ctx), self.bot.loop)
        
        ctx.voice_client.play(player, after = after_playing)

        embed = discord.Embed(
            title = "🎵 Şimdi Çalıyor 🎵",
            description = f"**{title}**",
            color = discord.Color.from_rgb(155, 89, 182)
        )
        embed.add_field(name = "İsteyen", value = ctx.author.mention, inline = True)

        if thumbnail:
            embed.set_thumbnail(url = thumbnail)
        
        await ctx.send(embed = embed)
    
    @commands.command(name = "play", aliases = ["çal", "oynat", "şarkı", "cal"])
    async def play(self, ctx, *, link):
        # komutu kullanan kişi bir ses kanalında değilse
        if not ctx.author.voice:
            return await ctx.send("Önce bir ses kanalına gir ki ben de gelebileyim!")
        
        voice_client = ctx.voice_client
        if not voice_client:
            try:
                voice_client = await ctx.author.voice.channel.connect()
            except Exception as e:
                print(f"\n[Error] Kanala bağlanmaya çalışırken hata oluştu: {e}")
                return await ctx.send("Ses kanalına bağlanırken bir hata oluştu!")
        
        try:
            await ctx.send("Şarkı aranıyor...", delete_after = 5)
            loop = self.bot.loop

            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(link, download = False))

            if "entries" in data:
                data = data["entries"][0]

            song_data = {
                "url" : data["url"],
                "title" : data.get("title", "Bilinmeyen Şarkı"),
                "thumbnail" : data.get("thumbnail", None)
            }

            # eğer o sunucu için bir liste yoksa listeyi başlat
            if ctx.guild.id not in self.queues:
                self.queues[ctx.guild.id] = []
                
            # Eğer bot bir şey çalmıyorsa veya durdurulmamışsa şarkıyı hemen çalsın
            if not voice_client.is_playing() and not voice_client.is_paused():
                await self.play_music(ctx, song_data)
            else:
                # Eğer başka şarkı çalıyorsa sıraya eklesin
                self.queues[ctx.guild.id].append(song_data)
                await ctx.send(f"Şarkı sıraya eklendi: **{song_data['title']}** | Sıradaki yeri: {len(self.queues[ctx.guild.id])}")
        except Exception as e:
            print(f"\n[Error] Oynatma sırasında hata: {e}")
            await ctx.send("Şarkı açılırken bir hata oluştu!")
    
    @commands.command(name = "pause", aliases = ["dur", "stop", "durdur", "duraklat", "bekle"])
    async def pause(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("Müzik durduruldu!")

    @commands.command(name = "resume", aliases = ["devam", "başla", "go", "devam-et"])
    async def resume(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("Müzik devam ediyor!")

    @commands.command(name = "leave", aliases = ["git", "çık", "cık", "ayrıl", "ayril"])
    async def leave(self, ctx):
        if ctx.guild.id in self.queues:
            self.queues[ctx.guild.id].clear()
        
        if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            ctx.voice_client.stop()
            
        await ctx.voice_client.disconnect()
        await ctx.send("Kanaldan ayrılıyorum!")


async def setup(bot):
        await bot.add_cog(Music(bot))
