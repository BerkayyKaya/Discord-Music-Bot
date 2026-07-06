import discord
from discord.ext import commands
from utils.ytdl import ffmpeg_options, ytdl
import asyncio
import random
import yt_dlp
import warnings
from utils.views import MusicPlayerView
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
        # now playing messages
        self.np_messages = {}

    #region play commands
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
        requester = song_data.get("requester", "Bilinmeyen Kullanıcı")

        player = discord.FFmpegPCMAudio(song_url, **ffmpeg_options)

        def after_playing(error):
            if error:
                print(f"\n[Error] Oynatma Hatası: {error}")
            asyncio.run_coroutine_threadsafe(self.play_next(ctx), self.bot.loop)
        
        ctx.voice_client.play(player, after = after_playing)

        fixed_title = ("\u2800" * 12) + "🎵 Şimdi Çalıyor 🎵" + ("\u2800" * 12)
        song_title = title if len(title) <= 55 else title[:55] + "..."
        embed = discord.Embed(
            title = fixed_title,
            description = f"**{song_title}**",
            color = discord.Color.from_rgb(155, 89, 182)
        )
        embed.add_field(name = "İsteyen", value = requester, inline = True)

        if thumbnail:
            embed.set_thumbnail(url = thumbnail)
        
        # self = music cog
        view = MusicPlayerView(self, original_embed = embed)
        
        if ctx.guild.id in self.np_messages:
            try:
                await self.np_messages[ctx.guild.id].delete()
            except discord.NotFound as e:
                print(f"\n[Error] Bot eski mesajını silmeye çalışırken bir hata oluştu, hata: {e}\n "
                      "Kullanıcı bu mesajı kendi eliyle silmiş olabilir!")
            except Exception as e:
                print("\n[Error] Bot eski mesajını silmeye çalışırken bilinmeyen bir hata oluştu!\n "
                      f"Hata: {e}")
        
        new_message = await ctx.send(embed = embed, view = view)
        self.np_messages[ctx.guild.id] = new_message

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
                "thumbnail" : data.get("thumbnail", None),
                "requester" : ctx.author.mention
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

    @commands.command(name = "playlist", aliases = ["çalmalistesi", "calmalistesi", "pl", "listeekle", "mix"])
    async def playlist(self, ctx, *, link):
        if not ctx.author.voice:
            return await ctx.send("Önce bir ses kanalına girmelisin ki ben de gelebileyim.")

        voice_client = ctx.voice_client
        if not voice_client:
            try:
                voice_client = await ctx.author.voice.channel.connect()
            except Exception as e:
                print(f"\n[Error] Ses kanalına bağlanırken hata oluştu: {e}")
                await ctx.send("Ses kanalına bağlanırken hata oluştu!")
        
        flat_playlist_options = {
            "extract_flat" : True,
            "quiet" : True,
            "no_warnings" : True,
            "ignoreerrors" : True
        }

        ytdl_pl = yt_dlp.YoutubeDL(flat_playlist_options)
        try:
            await ctx.send("⏳ Playlist inceleniyor, rastgele 25 şarkıyı seçiyorum biraz sürebilir...", delete_after = 10)
            loop = self.bot.loop
            data = await loop.run_in_executor(None, lambda: ytdl_pl.extract_info(link, download = False))
            
            if "entries" not in data:
                return await ctx.send("Bu linkte bir playlist bulunamadı, doğru link olduğundan emin misiniz?")
            
            all_songs = [entry for entry in data["entries"] if entry is not None]

            if not all_songs:
                return await ctx.send("Playlist boş veya videolar gizli!")
            
            chosen_songs = random.sample(all_songs, min(25, len(all_songs)))

            if ctx.guild.id not in self.queues:
                self.queues[ctx.guild.id] = []
            
            added_song_count = 0

            for entry in chosen_songs:
                video_url = entry.get("url")
                if not video_url:
                    continue

                if not video_url.startswith("http"):
                    video_url = f"https://www.youtube.com/watch?v={video_url}"

                try:
                    song_info = await loop.run_in_executor(None, lambda: ytdl.extract_info(video_url, download = False))

                    song_data = {
                        "url" : song_info["url"],
                        "title" : song_info.get("title", "Bilinmeyen Şarkı"),
                        "thumbnail" : song_info.get("thumbnail", None),
                        "requester" : ctx.author.mention
                    }

                    self.queues[ctx.guild.id].append(song_data)
                    added_song_count += 1

                except Exception as e:
                    print(f"\n[Error] Şarkı eklenirken bir hata oluştu: {e}")
                
            playlist_name = data.get("title", "Bilinmeyen Playlist")
            await ctx.send(f"🎧 **{playlist_name}** listesinden rastgele seçilen **{added_song_count}** şarkı başarıyla sıraya eklendi!")

            if not voice_client.is_playing() and not voice_client.is_paused():
                if ctx.guild.id in self.queues and len(self.queues[ctx.guild.id]) > 0:
                    next_song = self.queues[ctx.guild.id].pop(0)
                    await self.play_music(ctx, next_song)
        except Exception as e:
            print(f"\n[Error] Playlist oynatma hatası: {e}")
            await ctx.send("Playlist açılırken bir hata oluştu. Linkin geçerli bir YouTube playlisti olduğundan emin ol!")
    
    #endregion

    #region helper functions (e.g pause, resume)
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
        
        if ctx.guild.id in self.np_messages:
            try:
                await self.np_messages[ctx.guild.id].delete()
                del self.np_messages[ctx.guild.id]
            except:
                pass
            
        await ctx.voice_client.disconnect()
        await ctx.send("Kanaldan ayrılıyorum!")

    @commands.command(name = "liste", aliases = ["list", "kuyruk", "şarkılar", "queue", "q"])
    async def list(self, ctx):
        if ctx.guild.id not in self.queues or len(self.queues[ctx.guild.id]) == 0:
            return await ctx.send("Şu an kuyruk bomboş, şarkı eklemek için `play` komutunu kullanabilirsin.")

        message = "**Gelecek Şarkıların Listesi:**\n"
        for i, song in enumerate(self.queues[ctx.guild.id], start = 1):
            message += f"{i}. **{song['title']}**\n"

            if i == 10 and not len(self.queues[ctx.guild.id]) < 11:
                message += f"... ve {len(self.queues[ctx.guild.id]) - 10} şarkı daha sırada bekliyor..."
                break
        
        await ctx.send(message)

    @commands.command(name = "skip", aliases = ["sonraki", "sıradaki", "geç", "gec", "siradaki", "atla"])
    async def skip(self, ctx):
        if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
            ctx.voice_client.stop()
            await ctx.send("Şarkıyı geçiyorum, sıradaki şarkıya bakılıyor...", delete_after = 5)
        else:
            await ctx.send("Şarkılar bitti!")

    @commands.command(name = "shuffle", aliases = ["karıştır", "karistir"])
    async def shuffle(self, ctx):
        if ctx.guild.id not in self.queues or len(self.queues[ctx.guild.id]) <= 1:
            return await ctx.send("Kuyrukta karıştırmaya yetecek kadar şarkı yok, minimum 2 şarkı olmalıdır!")
        
        random.shuffle(self.queues[ctx.guild.id])
        await ctx.send("🎲 Kuyruk karıştırıldı!")

    @commands.command(name = "clear", aliases = ["sıfırla", "temizle"])
    async def clear(self, ctx):
        if ctx.guild.id in self.queues and self.queues[ctx.guild.id]:
            self.queues[ctx.guild.id].clear()
            await ctx.send("Kuyruk temizlendi!")
        else:
            await ctx.send("Şarkılar bitti, temizlenecek bir şey yok.")
    
    #endregion


async def setup(bot):
        await bot.add_cog(Music(bot))
