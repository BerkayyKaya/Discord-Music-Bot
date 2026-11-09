# YouTube işlemleri (Tekil, Playlist, Autoplay)
import random
import re

import yt_dlp

from utils.audio.autoplay_filter import (
    AutoplayFilter,
    Candidate,
    extract_artist,
    is_same_song,
    track_title,
)
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
        self.autoplay_filter = AutoplayFilter(max_consecutive_artist=2)

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
        title = data.get("title", "Bilinmeyen Şarkı")
        artist = extract_artist(
            title,
            uploader=data.get("channel") or data.get("uploader"),
            artist=data.get("artist") or data.get("creator"),
        )

        return Track(
            id=str(data["id"]),
            title=title,
            url=stream_url,
            webpage_url=data.get("webpage_url", f"https://www.youtube.com/watch?v={data['id']}"),
            thumbnail=data.get("thumbnail"),
            requester=requester_str,
            artist=artist,
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

                song_title = song_info.get("title", "Bilinmeyen Şarkı")
                tracks.append(Track(
                    id=str(song_info["id"]),
                    title=song_title,
                    url=stream_url,
                    webpage_url=song_info.get("webpage_url", video_url),
                    thumbnail=song_info.get("thumbnail"),
                    requester=requester_str,
                    artist=extract_artist(
                        song_title,
                        uploader=song_info.get("channel") or song_info.get("uploader"),
                        artist=song_info.get("artist") or song_info.get("creator"),
                    ),
                    provider=self.name
                ))
            except Exception:
                continue

        playlist_title = data.get("title", "YouTube Çalma Listesi")
        return Playlist(title=playlist_title, tracks=tracks)

    async def get_autoplay_track(
        self,
        last_track: Track,
        history: list,
        loop,
        recent_tracks: list | None = None,
    ) -> Track:
        """YouTube Mix (RD) radyosu üzerinden sıradaki şarkıyı bulur."""
        video_id = last_track["id"]
        radio_url = f"https://www.youtube.com/watch?v={video_id}&list=RD{video_id}"

        flat_opts = {
            "extract_flat": True,
            "playlist_items": "2-20",
            "quiet": True,
            "ignoreerrors": True
        }
        ytdl_radio = yt_dlp.YoutubeDL(flat_opts)
        data = await loop.run_in_executor(None, lambda: ytdl_radio.extract_info(radio_url, download=False))

        candidates = []
        if data and "entries" in data:
            for entry in data["entries"]:
                if not entry:
                    continue

                entry_id = str(entry.get("id") or "")
                if not entry_id or entry_id in history:
                    continue

                title = entry.get("title", "")
                candidates.append(Candidate(
                    id=entry_id,
                    title=title,
                    artist=extract_artist(
                        title,
                        uploader=entry.get("channel") or entry.get("uploader"),
                        artist=entry.get("artist") or entry.get("creator"),
                    ),
                    payload=entry,
                ))

        for candidate in self.autoplay_filter.rank(candidates, last_track, recent_tracks or []):
            song_url = f"https://www.youtube.com/watch?v={candidate.id}"
            track = await self.extract_track(song_url, requester="YouTube", loop=loop)
            if not track:
                continue

            # Flat listedeki başlık ile gerçek başlık farklı olabilir; son kontrol.
            if is_same_song(track.title, track_title(last_track)):
                continue

            return track

        return None