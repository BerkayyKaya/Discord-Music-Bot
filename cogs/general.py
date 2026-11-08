# Ping, help, info gibi genel komutlar
import discord
from discord import app_commands
from discord.ext import commands


class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="yardim", description="Kullanılabilir tüm komutları ve işlevlerini gösterir.")
    async def yardim(self, interaction: discord.Interaction):
        command_map = {command.name: command for command in self.bot.tree.get_commands()}

        categories = (
            ("🎶 Müzik Çalma", ("play", "playlist")),
            ("⏯️ Oynatma Kontrolü", ("pause", "resume", "skip", "leave")),
            ("📜 Kuyruk Yönetimi", ("liste", "shuffle", "clear")),
            ("ℹ️ Genel", ("yardim",)),
        )

        embed = discord.Embed(
            title="🎵 Müzik Botu Komutları",
            description=(
                "Tüm komutlar `/` ön ekiyle kullanılır. Sohbete `/` yazdığında "
                "komutların listesini ve açıklamalarını Discord otomatik olarak gösterir."
            ),
            color=discord.Color.from_rgb(155, 89, 182),
        )

        for category, names in categories:
            lines = []
            for name in names:
                command = command_map.get(name)
                if command:
                    lines.append(f"**/{name}** — {command.description}")

            if lines:
                embed.add_field(name=category, value="\n".join(lines), inline=False)

        embed.set_footer(text="İpucu: /play komutu kullanıldıktan sonra şarkı kontrolleri interaktif butonlarla yapılabilir.")
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(General(bot))
