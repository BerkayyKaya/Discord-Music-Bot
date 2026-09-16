# Soyut taban sınıf (BaseProvider)
from abc import ABC, abstractmethod

import discord

from utils.audio.models import Playlist, Track


class BaseProvider(ABC):
    name: str = "base"

    @abstractmethod
    def can_handle(self, query: str) -> bool:
        """
        Bu sağlayıcı bu URL'yi veya sorguyu işleyebilir mi?
        """
        pass

    @abstractmethod
    async def extract_track(self, query: str, requester: discord.Member, loop) -> Track | None:
        """
        Tek bir şarkı çıkartır.
        """
        pass

    @abstractmethod
    async def extract_playlist(self, query: str, requester: discord.Member, loop, limit: int = 25) -> Playlist | None:
        """
        Çalma listesi çıkartır.
        """
        pass

    @abstractmethod
    async def get_autoplay_track(self, last_track: Track, history: list, loop) -> Track | None:
        """Sağlayıcıya özel bir sonraki benzer şarkıyı bulur."""
        pass