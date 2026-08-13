import asyncio
import random
import warnings

import discord
import yt_dlp
from discord.ext import commands

from utils.views import MusicPlayerView
from utils.ytdl import ffmpeg_options, ytdl

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

        # OTOMATİK OYNATMA İÇİN HAFIZA
        self.autoplay = {}      # özellik aktif mi?
        self.history = {}       # aynı şarkıları çalmamak için
        self.current_song = {}  # o an çalan şarkının bilgisini tutar

    #region play commands
    async def play_next(self, ctx):

        # Bot ses kanalında mı?
        if not ctx.voice_client or not ctx.voice_client.is_connected():
            return

        # ilgili sunucunun kuyruğunda şarkı var mı?
        if ctx.guild.id in self.queues and len(self.queues[ctx.guild.id]) > 0:
            next_song = self.queues[ctx.guild.id].pop(0) # ilgili sunucunun kuyruğundaki sıradaki şarkıyı çıkart ve çal
            await self.play_music(ctx, next_song)
        elif self.autoplay.get(ctx.guild.id, False) and ctx.guild.id in self.current_song and ctx.voice_client:
            last_song = self.current_song[ctx.guild.id]
            last_id = last_song.get("id", None)

            if last_id:
                await ctx.send("Oynatma listesi bitti, **Otomatik Oynatma** devrede! Benzer şarkılar aranıyor...", delete_after = 5)

                radio_url = f"https://www.youtube.com/watch?v={last_id}&list=RD{last_id}" # youtubenin oluşturduğu mixin url adresi

                flat_options = {
                    "extract_flat": True,       # Şarkıların seslerini çözme yalnızca isimlerine bak
                    "playlist_items": "2-10",   # 10 şarkıya kadar bakabiliriz flat çıkarımda sorun olmayacaktır
                    "quiet": True,
                    "ignoreerrors": True
                }
                ytdl_flat = yt_dlp.YoutubeDL(flat_options)


                try:
                    loop = self.bot.loop
                    data = await loop.run_in_executor(None, lambda: ytdl_flat.extract_info(radio_url, download = False))

                    new_song_id = None

                    if "entries" in data:
                        for entry in data["entries"]:
                            if entry is None: continue

                            if entry['id'] not in self.history.get(ctx.guild.id, []):

                                new_song_id = entry['id']

                                break

                    if new_song_id:
                        song_url = f"https://www.youtube.com/watch?v={new_song_id}"
                        song_info = await loop.run_in_executor(None, lambda: ytdl.extract_info(song_url, download=False))

                        song_data = {
                            'url': song_info['url'],
                            'title': song_info.get('title', 'Bilinmeyen Şarkı'),
                            'thumbnail': song_info.get('thumbnail', None),
                            'requester': "YouTube",
                            'id': song_info['id']
                        }
                        await self.play_music(ctx, song_data)
                    else:
                        await ctx.send("Uygun bir şarkı bulunamadı!", delete_after = 5)
                except Exception as e:
                    print(f"Otomatik oynatma hatası: {e}")
        else:
            try:
                await self.np_messages[ctx.guild.id].delete()
                del self.np_messages[ctx.guild.id]
            except:  # noqa: E722, S110
                pass
            await ctx.send("Kuyruktaki tüm şarkılar bitti, liste boş!", delete_after = 5) # bir uyarı mesajı gönder ve 5 saniye sonra sil
    
    async def play_music(self, ctx, song_data):
        song_url = song_data["url"]
        title = song_data["title"]
        thumbnail = song_data.get("thumbnail", None) # thumbnail varsa çek yoksa None ata
        requester = song_data.get("requester", "Bilinmeyen Kullanıcı")
        self.current_song[ctx.guild.id] = song_data

        if ctx.guild.id not in self.history:
            self.history[ctx.guild.id] = []
        
        self.history[ctx.guild.id].append(song_data['id'])

        # 20 şarkıdan fazlasını tutma
        if len(self.history[ctx.guild.id]) > 20:
            self.history[ctx.guild.id].pop(0)

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
        embed.add_field(name = "İsteyen:", value = requester, inline = True)
        
        if len(self.queues[ctx.guild.id]) > 0:
            next_title = self.queues[ctx.guild.id][0]["title"]
            next_song_title = next_title if len(next_title) <= 45 else next_title[:45] + "..."
            embed.add_field(name = "Sonraki Şarkı:", value = next_song_title)

        if thumbnail:
            embed.set_thumbnail(url = thumbnail)
        
        # self = music cog
        view = MusicPlayerView(self, original_embed = embed, autoplay_state = self.autoplay.get(ctx.guild.id, False))
        
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
            return await ctx.send("Önce bir ses kanalına gir ki ben de gelebileyim!", delete_after = 5)
        
        voice_client = ctx.voice_client
        if not voice_client:
            try:
                voice_client = await ctx.author.voice.channel.connect()
            except Exception as e:
                print(f"\n[Error] Kanala bağlanmaya çalışırken hata oluştu: {e}")
                return await ctx.send("Ses kanalına bağlanırken bir hata oluştu!", delete_after = 5)
        
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
                "requester" : ctx.author.mention,
                "id" : data["id"]
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
                await ctx.send(f"Şarkı sıraya eklendi: **{song_data['title']}** | Sıradaki yeri: {len(self.queues[ctx.guild.id])}", delete_after = 5)
        except Exception as e:
            print(f"\n[Error] Oynatma sırasında hata: {e}")
            await ctx.send("Şarkı açılırken bir hata oluştu!", delete_after = 5)

    @commands.command(name = "playlist", aliases = ["çalmalistesi", "calmalistesi", "pl", "listeekle", "mix"])
    async def playlist(self, ctx, *, link):
        if not ctx.author.voice:
            return await ctx.send("Önce bir ses kanalına girmelisin ki ben de gelebileyim.", delete_after = 10)

        voice_client = ctx.voice_client
        if not voice_client:
            try:
                voice_client = await ctx.author.voice.channel.connect()
            except Exception as e:
                print(f"\n[Error] Ses kanalına bağlanırken hata oluştu: {e}")
                await ctx.send("Ses kanalına bağlanırken hata oluştu!", delete_after = 5)
        
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
                return await ctx.send("Bu linkte bir playlist bulunamadı, doğru link olduğundan emin misiniz?", delete_after = 5)
            
            all_songs = [entry for entry in data["entries"] if entry is not None]

            if not all_songs:
                return await ctx.send("Playlist boş veya videolar gizli!", delete_after = 5)
            
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
                        "requester" : ctx.author.mention,
                        "id" : song_info["id"]
                    }

                    self.queues[ctx.guild.id].append(song_data)
                    added_song_count += 1

                except Exception as e:
                    print(f"\n[Error] Şarkı eklenirken bir hata oluştu: {e}")
                
            playlist_name = data.get("title", "Bilinmeyen Playlist")
            await ctx.send(f"🎧 **{playlist_name}** listesinden rastgele seçilen **{added_song_count}** şarkı başarıyla sıraya eklendi!", delete_after = 5)

            if not voice_client.is_playing() and not voice_client.is_paused():
                if ctx.guild.id in self.queues and len(self.queues[ctx.guild.id]) > 0:
                    next_song = self.queues[ctx.guild.id].pop(0)
                    await self.play_music(ctx, next_song)
        except Exception as e:
            print(f"\n[Error] Playlist oynatma hatası: {e}")
            await ctx.send("Playlist açılırken bir hata oluştu. Linkin geçerli bir YouTube playlisti olduğundan emin ol!", delete_after = 5)
    
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

        if ctx.guild.id in self.cog.current_song:
            del self.cog.current_song[ctx.guild.id]
        
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

    async def cog_after_invoke(self, ctx):
        if ctx.message:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                print(f"\n[ERROR] {ctx.guild.name} sunucusunda komut mesajı silinemedi.")
            except discord.NotFound:
                print("\n[ERROR] Bot kullanıcının mesajını bulamadı, kullanıcı çoktan silmiş olabilir.")


async def setup(bot):
        await bot.add_cog(Music(bot))
