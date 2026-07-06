# Bot mesajlarında UI görünümleri
import discord


class MusicPlayerView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout = None)
        self.cog = cog
    
    @discord.ui.button(label = "⏸️ Durdur / ▶️ Devam", style = discord.ButtonStyle.blurple)
    async def pause_resume_button(self, interaction : discord.Interaction, button : discord.ui.Button):
        voice_client = interaction.guild.voice_client
        if not voice_client:
            return await interaction.response.send_message("Bot şu an aktif değil!", ephemeral = True)

        if voice_client.is_playing():
            voice_client.pause()
            await interaction.response.send_message("Müzik duraklatıldı!", ephemeral = True)
        elif voice_client.is_paused():
            voice_client.resume()
            await interaction.response.send_message("Müzik devam ediyor!", ephemeral = True)
        else:
            await interaction.response.send_message("Şu an aktif çalan bir şey yok!", ephemeral = True)
        
    @discord.ui.button(label = "⏭️ Sonraki", style = discord.ButtonStyle.green)
    async def skip_button(self, interaction : discord.Interaction, button : discord.ui.button):
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_playing():
            return await interaction.response.send_message("Şu an atlanacak bir şarkı çalmıyor!", ephemeral = True)
        
        # voice_client durdurulduğunda after_playing tetiklenecek ve sonraki şarkıya geçecek
        voice_client.stop()
        await interaction.response.send_message("Şarkı geçildi!", ephemeral = True)