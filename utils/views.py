# Bot mesajlarında UI görünümleri
import discord


class MusicPlayerView(discord.ui.View):
    def __init__(self, cog, original_embed, autoplay_state = False):
        super().__init__(timeout = None)
        self.cog = cog
        self.showing_queue = False
        self.original_embed = original_embed
        self.autoplay_state = autoplay_state
        self.check_methods()


    # View nesnesini kontrol etme fonksiyonu
    def check_methods(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.label and "OTO-LOOP" in child.label:
                if self.autoplay_state:
                    child.label = "♾️ OTO-LOOP: AÇIK"
                    child.style = discord.ButtonStyle.green
                else:
                    child.label = "♾️OTO-LOOP: KAPALI"
                    child.style = discord.ButtonStyle.gray
                break


    # region row 0
    @discord.ui.button(label = "⏸️Durdur/▶️Devam", style = discord.ButtonStyle.blurple)
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
        
    @discord.ui.button(label = "⏭️Sonraki", style = discord.ButtonStyle.green)
    async def skip_button(self, interaction : discord.Interaction, button : discord.ui.button):
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_playing():
            return await interaction.response.send_message("Şu an atlanacak bir şarkı çalmıyor!", ephemeral = True)
        
        # voice_client durdurulduğunda after_playing tetiklenecek ve sonraki şarkıya geçecek
        voice_client.stop()
        await interaction.response.send_message("Şarkı geçildi!", ephemeral = True)
    
    @discord.ui.button(label = "📜Listeyi Göster", style = discord.ButtonStyle.green)
    async def list_button(self, interaction : discord.Interaction, button : discord.ui.button):
        self.showing_queue = not self.showing_queue
        guild_id = interaction.guild.id
        queues = self.cog.queues

        # Liste açılacaksa
        if self.showing_queue:
            # listede şarkı yoksa
            if guild_id not in queues or len(queues[guild_id]) == 0:
                self.showing_queue = False
                return await interaction.response.send_message("Şu an listede gösterilecek şarkı yok!", ephemeral = True)
            
            # listede şarkı varsa
            queue_message = ""
            for i, song in enumerate(queues[interaction.guild.id], 1):
                title = song["title"] if (len(song["title"]) <= 40) else (song["title"][:40] + "...")
                queue_message += f"{i}. **{title.upper()}**  |  **İsteyen:** {song['requester']}\n"

                if i == 10 and len(queues[interaction.guild.id]) > 10:
                    queue_message += f"ve {len(queues[interaction.guild.id]) - 10} şarkı daha sırada bekliyor..."
                    break
            
            fixed_title = ("\u2800" * 15) + "📜 Sıradaki Şarkılar 📜" + ("\u2800" * 16)
            queue_embed = discord.Embed(
                title = fixed_title,
                description = queue_message,
                color = discord.Color.from_rgb(155, 89, 182)
            )

            button.label = "📜Listeyi Gizle"

            await interaction.response.edit_message(embed = queue_embed, view = self)
        else:
            button.label = "📜Listeyi Göster"

            await interaction.response.edit_message(embed = self.original_embed, view = self)

    @discord.ui.button(label = "🗑️Sıfırla ve Çık", style = discord.ButtonStyle.blurple)
    async def clear_button(self, interaction : discord.Interaction, button : discord.ui.Button):
        guild_id = interaction.guild.id
        
        self.cog.queues[guild_id].clear()

        if guild_id in self.cog.current_song:
            del self.cog.current_song[guild_id]

        voice_client = interaction.guild.voice_client
        if voice_client.is_playing() or voice_client.is_paused():
            voice_client.stop()

        await voice_client.disconnect()
        await interaction.response.send_message("Sırıflama başarılı, kanaldan ayrılıyorum!", ephemeral = True)
                    
        if interaction.guild.id in self.cog.np_messages:
            try:
                await self.cog.np_messages[guild_id].delete()
                del self.cog.np_messages[guild_id]
            except:
                pass
    

    # endregion

    # region row 1
    @discord.ui.button(label = "♾️ OTO-LOOP: KAPALI", style=discord.ButtonStyle.gray, row = 1)
    async def autoplay_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_id = interaction.guild.id
        
        # Durumu tersine çevir
        current_state = self.cog.autoplay.get(guild_id, False)
        new_state = not current_state
        self.cog.autoplay[guild_id] = new_state
        
        # Butonun görünümünü güncelle
        if new_state:
            button.label = "♾️ OTO-LOOP: AÇIK"
            button.style = discord.ButtonStyle.green
            await interaction.response.edit_message(view = self)
            await interaction.followup.send("♾️ Otomatik oynatma **açıldı**. Şarkılar bitince benzerleri çalınacak.", ephemeral=True)
        else:
            button.label = "♾️OTO-LOOP: KAPALI"
            button.style = discord.ButtonStyle.gray
            await interaction.response.edit_message(view = self)
            await interaction.followup.send("♾️ Otomatik oynatma **kapatıldı**.", ephemeral=True)


    # endregion