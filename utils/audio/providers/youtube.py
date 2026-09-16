# YouTube işlemleri (Tekil, Playlist, Autoplay)
import random
import re

import yt_dlp

from utils.audio.base import BaseProvider
from utils.audio.models import Playlist, Track
from utils.ytdl import ytdl


class YouTubeProvider(BaseProvider):
    name = "youtube"
    YT_REGEX = r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+"

    def __init__(self):
        self.flat_ytdl = yt_dlp.YoutubeDL({
            "extract_flat": True,
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": True
        })

    def can_handle(self, query: str) -> bool:
        return bool(re.match(self.YT_REGEX, query)) or not query.startswith("http")

    async def extract_track(self, query: str, requester, loop) -> Track:
        search_query = query if query.startswith("http") else f"ytsearch:{query}"
        
        # ytdl instance'ını kullanarak bilgiyi çek
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(search_query, download=False))
        
        if not data:
            return None

        if "entries" in data:
            if not data["entries"]:
                return None
            data = data["entries"][0]

        # En kararlı ses linkini (m4a veya opus) seç
        stream_url = None
        if "formats" in data:
            # Sadece ses içeren ve URL'si doğrudan googlevideo olan formatları tara
            audio_formats = [
                f for f in data["formats"] 
                if f.get("acodec") != "none" and f.get("vcodec") == "none" and f.get("url")
            ]
            if audio_formats:
                # Genellikle son format en yüksek kaliteli ve güncel olandır
                stream_url = audio_formats[-1]["url"]

        # Bulunamazsa varsayılan URL'ye dön
        if not stream_url:
            stream_url = data.get("url")

        requester_str = requester.mention if hasattr(requester, "mention") else str(requester)

        return Track(
            id=str(data["id"]),
            title=data.get("title", "Bilinmeyen Şarkı"),
            url=stream_url,
            webpage_url=data.get("webpage_url", f"https://www.youtube.com/watch?v={data['id']}"),
            thumbnail=data.get("thumbnail"),
            requester=requester_str,
            provider=self.name
        )

    async def extract_playlist(self, query: str, requester, loop, limit: int = 25) -> Playlist:
        data = await loop.run_in_executor(None, lambda: self.flat_ytdl.extract_info(query, download=False))
        if not data or "entries" not in data or not data["entries"]:
            return None

        entries = [e for e in data["entries"] if e is not None]
        chosen = random.sample(entries, min(limit, len(entries)))
        tracks = []
        requester_str = requester.mention if hasattr(requester, "mention") else str(requester)

        for entry in chosen:
            video_url = entry.get("url")
            if not video_url:
                continue
            if not video_url.startswith("http"):
                video_url = f"https://www.youtube.com/watch?v={video_url}"

            try:
                song_info = await loop.run_in_executor(None, lambda: ytdl.extract_info(video_url, download=False))
                stream_url = song_info.get("url")
                if not stream_url and "formats" in song_info:
                    audio_formats = [f for f in song_info["formats"] if f.get("acodec") != "none" and f.get("vcodec") == "none"]
                    if audio_formats:
                        stream_url = audio_formats[-1]["url"]

                tracks.append(Track(
                    id=str(song_info["id"]),
                    title=song_info.get("title", "Bilinmeyen Şarkı"),
                    url=stream_url,
                    webpage_url=song_info.get("webpage_url", video_url),
                    thumbnail=song_info.get("thumbnail"),
                    requester=requester_str,
                    provider=self.name
                ))
            except Exception:
                continue

        playlist_title = data.get("title", "YouTube Çalma Listesi")
        return Playlist(title=playlist_title, tracks=tracks)

    async def get_autoplay_track(self, last_track: Track, history: list, loop) -> Track:
        """YouTube Mix (RD) radyosu üzerinden sıradaki şarkıyı bulur."""
        video_id = last_track["id"]
        radio_url = f"https://www.youtube.com/watch?v={video_id}&list=RD{video_id}"
        
        flat_opts = {
            "extract_flat": True,
            "playlist_items": "2-10",
            "quiet": True,
            "ignoreerrors": True
        }
        ytdl_radio = yt_dlp.YoutubeDL(flat_opts)
        data = await loop.run_in_executor(None, lambda: ytdl_radio.extract_info(radio_url, download=False))

        new_song_id = None
        if data and "entries" in data:
            for entry in data["entries"]:
                if entry and str(entry["id"]) not in history:
                    new_song_id = entry["id"]
                    break

        if new_song_id:
            song_url = f"https://www.youtube.com/watch?v={new_song_id}"
            return await self.extract_track(song_url, requester="YouTube Radyo", loop=loop)

        return None