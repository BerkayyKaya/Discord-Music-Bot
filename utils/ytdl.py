# yt-dlp ayarları, URL çıkarma ve asenkron indirme/akış mantığı
import yt_dlp

ytdl_format_options = {
    "format": "bestaudio/best",
    "outtmpl": '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    "restrictfilenames" : True, # Dosya isimlerinde sorun çıkaracak karakterleri otomatik temizleyecek
    "noplaylist": True,
    "nocheckcertificate" : True, # Sertifika kontrolü yapmayacak
    "ignoreerrors" : False,
    "logtostderr" : False,
    "quiet": True,
    "default_search": "auto",
}

ffmpeg_options = {
    "before_options": (
        "-reconnect 1 "
        "-reconnect_streamed 1 "
        "-reconnect_at_eof 1 "
        "-reconnect_delay_max 5 "
        "-rw_timeout 15000000 "
        '-user_agent "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"'
    ),
    "options": '-vn -filter:a "volume=0.55"',
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)