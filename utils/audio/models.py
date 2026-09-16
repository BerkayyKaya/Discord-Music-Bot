# Track ve Playlist modelleri
from dataclasses import dataclass


@dataclass
class Track:
    id: str
    title: str
    url: str               # ffmpeg akış linki
    webpage_url: str       # Orijinal web bağlantısı
    thumbnail: str | None
    requester: str
    provider: str = "youtube"


    def __getitem__(self, item):
        return getattr(self, item)

    def get(self, item, default=None):
        return getattr(self, item, default)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "webpage_url": self.webpage_url,
            "thumbnail": self.thumbnail,
            "requester": self.requester,
            "provider": self.provider
        }

@dataclass
class Playlist:
    title: str
    tracks: list[Track]