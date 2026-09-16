# SoundCloud işlemleri (Tekil, Set/Playlist)
import re

import yt_dlp

from utils.audio.base import BaseProvider
from utils.audio.models import Playlist, Track


class SoundCloudProvider(BaseProvider):
    name = "soundcloud"
    SC_REGEX = r"https?://(www\.|m\.|on\.)?soundcloud\.com/.+"

    def __init__(self):
        self.sc_opts = {
            "format": "bestaudio[protocol^=http]/bestaudio/best",
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": True,
            "noplaylist": True
        }
        self.sc_ytdl = yt_dlp.YoutubeDL(self.sc_opts)
        self.sc_flat = yt_dlp.YoutubeDL({"extract_flat": True, "quiet": True, "ignoreerrors": True})

    def can_handle(self, query: str) -> bool:
        return bool(re.match(self.SC_REGEX, query))

    def clean_title(self, title: str) -> str:
        """YouTube başlıklarındaki parazitleri temizler."""
        patterns = [
            r"\[.*?\]",                   # [Official Video], [HD] vb.
            r"\(.*?(official|video|audio|clip|visualizer|lyric).*?\)", # (Official Music Video) vb.
            r"(?i)official\s+(music\s+)?video",
            r"(?i)official\s+audio",
            r"(?i)lyric\s+video"
        ]
        cleaned = title
        for pattern in patterns:
            cleaned = re.sub(pattern, "", cleaned)
        return cleaned.strip()

    def is_similar_song(self, original_title: str, new_title: str) -> bool:
        """Aynı şarkının remix, cover veya slowed versiyonu mu kontrol eder."""
        orig_words = set(re.findall(r"\w+", original_title.lower()))
        new_words = set(re.findall(r"\w+", new_title.lower()))
        # Gereksiz ortak kelimeleri yoksay
        ignore_words = {"the", "a", "feat", "ft", "remix", "mix", "audio", "video", "official"}
        orig_words -= ignore_words
        new_words -= ignore_words
        
        if not orig_words:
            return False

        # Eğer yeni şarkının kelimelerinin %70'inden fazlası eski şarkıyla aynıysa, bu aynı şarkıdır!
        intersection = orig_words.intersection(new_words)
        return len(intersection) / len(orig_words) > 0.65

    async def extract_track(self, query: str, requester, loop) -> Track:
        search_query = query if query.startswith("http") else f"scsearch:{query}"
        data = await loop.run_in_executor(None, lambda: self.sc_ytdl.extract_info(search_query, download=False))
        if not data:
            return None
            
        if "entries" in data and data["entries"]:
            data = data["entries"][0]

        stream_url = data.get("url")
        if not stream_url and "formats" in data:
            stream_url = data["formats"][-1].get("url")

        requester_str = requester.mention if hasattr(requester, "mention") else str(requester)

        return Track(
            id=str(data.get("id")),
            title=data.get("title", "Bilinmeyen SoundCloud Şarkısı"),
            url=stream_url,
            webpage_url=data.get("webpage_url", query),
            thumbnail=data.get("thumbnail"),
            requester=requester_str,
            provider=self.name
        )

    async def extract_playlist(self, query: str, requester, loop, limit: int = 25) -> Playlist:
        data = await loop.run_in_executor(None, lambda: self.sc_flat.extract_info(query, download=False))
        if not data or "entries" not in data or not data["entries"]:
            return None

        entries = [e for e in data["entries"] if e is not None][:limit]
        tracks = []
        requester_str = requester.mention if hasattr(requester, "mention") else str(requester)

        for entry in entries:
            track_url = entry.get("url") or entry.get("webpage_url")
            if not track_url:
                continue

            try:
                info = await loop.run_in_executor(None, lambda: self.sc_ytdl.extract_info(track_url, download=False))
                stream_url = info.get("url")
                if not stream_url and "formats" in info:
                    stream_url = info["formats"][-1].get("url")

                tracks.append(Track(
                    id=str(info.get("id")),
                    title=info.get("title", "Bilinmeyen SoundCloud Şarkısı"),
                    url=stream_url,
                    webpage_url=info.get("webpage_url", track_url),
                    thumbnail=info.get("thumbnail"),
                    requester=requester_str,
                    provider=self.name
                ))
            except Exception:
                continue

        playlist_title = data.get("title", "SoundCloud Çalma Listesi")
        return Playlist(title=playlist_title, tracks=tracks)

    async def get_autoplay_track(self, last_track: Track, history: list, loop) -> Track:
        """
        YouTube'un güçlü RD Radyo algoritmasını DJ olarak kullanır,
        önerilen kaliteli şarkıyı SoundCloud üzerinden bulup çalar.
        """
        # 1. Adım: Çalan şarkıyı YouTube'da aratarak bir YouTube ID'si bul (Sadece metaveri)
        yt_search = await loop.run_in_executor(
            None, lambda: self.sc_flat.extract_info(f"ytsearch1:{last_track['title']}", download=False)
        )

        if not yt_search or "entries" not in yt_search or not yt_search["entries"]:
            return None

        yt_id = yt_search["entries"][0]["id"]

        # 2. Adım: YouTube'un RD Miksinden benzer şarkı listesini çek (extract_flat ile anında gelir)
        radio_url = f"https://www.youtube.com/watch?v={yt_id}&list=RD{yt_id}"
        radio_opts = {
            "extract_flat": True,
            "playlist_items": "2-12", # İlk 10 benzer parçayı tara
            "quiet": True,
            "ignoreerrors": True
        }
        ytdl_radio = yt_dlp.YoutubeDL(radio_opts)
        radio_data = await loop.run_in_executor(None, lambda: ytdl_radio.extract_info(radio_url, download=False))

        if not radio_data or "entries" not in radio_data:
            return None

        # 3. Adım: YouTube miksindeki şarkıları sırayla dene
        for entry in radio_data["entries"]:
            if not entry:
                continue

            raw_title = entry.get("title", "")
            cleaned_title = self.clean_title(raw_title)

            # Eğer önerilen parça zaten çalan şarkının aynısı/cover'ı ise veya geçmişte çalındıysa atla
            if self.is_similar_song(last_track["title"], cleaned_title):
                continue

            # 4. Adım: Temizlenmiş şarkı adını SoundCloud'da ara
            try:
                sc_track = await self.extract_track(cleaned_title, requester="SoundCloud", loop=loop)
                
                # Şarkı SoundCloud'da başarıyla bulunduysa ve geçmişte çalmadıysa seç!
                if sc_track and sc_track.id not in history:
                    # SoundCloud'daki bulunan sonucun da aynı parça olmadığından emin ol
                    if not self.is_similar_song(last_track["title"], sc_track.title):
                        return sc_track
            except Exception:
                # SoundCloud'da bu remix veya şarkı yoksa sonraki entry'ye geç (Fallback)
                continue

        return None