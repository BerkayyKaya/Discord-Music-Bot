# Gelen linki sağlayıcılara dağıtan yönetici
from utils.audio.providers.soundcloud import SoundCloudProvider
from utils.audio.providers.youtube import YouTubeProvider


class SourceManager:
    def __init__(self):
        self.youtube = YouTubeProvider()
        self.soundcloud = SoundCloudProvider()
        self.providers = [
            self.soundcloud,
            self.youtube
        ]

    def get_provider(self, query: str):
        """URL veya sorguya göre doğru sağlayıcıyı döner."""
        for provider in self.providers:
            if provider.can_handle(query):
                return provider
        return self.youtube

    def get_provider_by_name(self, name: str):
        """Sağlayıcı ismine ('soundcloud', 'youtube') göre sınıfı döner."""
        if name == "soundcloud":
            return self.soundcloud
        return self.youtube