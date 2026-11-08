# Slash komutlarında eski prefix komutlarındaki ctx arayüzünü taklit eden yardımcı sınıf
import discord


class InteractionContext:
    """discord.Interaction nesnesini, cog içindeki eski ctx kullanımına uyarlar.

    Bu sayede play_next / play_music gibi arka planda da çalışan fonksiyonlar
    ``ctx.send``, ``ctx.author``, ``ctx.voice_client`` gibi alışılmış alanları
    kullanmaya devam edebilir.
    """

    def __init__(self, interaction: discord.Interaction):
        self.interaction = interaction
        self.guild = interaction.guild
        self.channel = interaction.channel
        self.author = interaction.user
        self.user = interaction.user
        self.message = None
        self._sent_any = False

    @property
    def voice_client(self):
        return self.guild.voice_client if self.guild else None

    async def defer(self, *, thinking: bool = True):
        """Uzun sürebilecek işlemlerden önce etkileşimi yanıtlar."""
        if not self.interaction.response.is_done():
            await self.interaction.response.defer(thinking=thinking)

    async def send(
        self,
        content: str | None = None,
        *,
        embed: discord.Embed | None = None,
        view: discord.ui.View | None = None,
        delete_after: float | None = None,
        ephemeral: bool = False,
    ) -> discord.Message:
        """İlk mesajı etkileşim yanıtı olarak, sonraki mesajları kanala gönderir.

        Sonraki mesajların kanala gönderilmesi, etkileşim token'ı süresi dolduktan
        sonra (uzun şarkı listelerinde) da botun mesaj göndermeye devam etmesini
        sağlar.
        """
        # Webhook/followup gönderimleri view=None değerini kabul etmez; bu yüzden
        # sadece dolu olan parametreleri gönderiyoruz.
        extra = {}
        if embed is not None:
            extra["embed"] = embed
        if view is not None:
            extra["view"] = view

        if not self._sent_any and not self.interaction.response.is_done():
            await self.interaction.response.send_message(
                content, ephemeral=ephemeral, **extra
            )
            message = await self.interaction.original_response()
        elif not self._sent_any:
            message = await self.interaction.followup.send(
                content, ephemeral=ephemeral, wait=True, **extra
            )
        elif ephemeral:
            message = await self.interaction.followup.send(
                content, ephemeral=True, wait=True, **extra
            )
        else:
            message = await self.channel.send(content, **extra)

        self._sent_any = True

        if delete_after is not None:
            await message.delete(delay=delete_after)

        return message
