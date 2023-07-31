from discord.ext import commands
from discord import app_commands


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="purge", description="deletes the last x messages in the channel")
    @app_commands.describe(amount="the amount of messages to delete, defaults to 10")
    @app_commands.checks.has_permissions(administrator=True)
    async def purge_(self, interaction, amount: int = 10):
        await interaction.response.defer(ephemeral=True)
        await interaction.channel.purge(limit=amount, before=interaction.created_at)
        await interaction.followup.send(f"deleted {amount} messages")


async def setup(bot):
    await bot.add_cog(Admin(bot))
