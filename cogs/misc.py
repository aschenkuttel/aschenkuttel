from discord.ext import commands
from discord import app_commands
import discord
import utils


class Utils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="summon", description="summons all members from the lobby into your voice channel")
    async def summon_(self, interaction):
        try:
            own_channel = interaction.user.voice.channel
        except AttributeError:
            msg = "You'll have to be in a voice channel"
            await interaction.response.send_message(embed=utils.embed(msg, error=True), ephemeral=True)
            return

        channel_id = self.bot.config.get('lobby', interaction.guild.id)
        channel = self.bot.get_channel(channel_id)

        if channel is None:
            msg = "This guild has no registered lobby"
            await interaction.response.send_message(embed=utils.embed(msg, error=True), ephemeral=True)
            return

        for member in channel.members:
            if member.bot is True:
                continue
            try:
                await member.move_to(own_channel)
            except discord.Forbidden:
                continue

        msg = f"Summoned all members from {channel.mention}"
        await interaction.response.send_message(embed=utils.embed(msg))

    @app_commands.command(name="mirror", description="displays the discord avatar of a guild member or yourself")
    @app_commands.describe(member="the member you want to get the avatar of (optional)")
    async def mirror_(self, interaction, member: discord.Member = None):
        member = member or interaction.user
        embed = discord.Embed()
        embed.set_image(url=member.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="icon", description="displays the guilds server icon")
    async def icon_(self, interaction):
        embed = discord.Embed(color=discord.Color.gold())
        embed.set_image(url=interaction.guild.icon.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="profile", description="gives some basic stats about a guild member or yourself")
    @app_commands.describe(member="the member you want to get the profile of (optional)")
    async def profile_(self, interaction, member: discord.Member = None):
        member = member or interaction.user
        creation_date = member.created_at.strftime("%d.%m.%Y")
        desc = f"**Nickname:** {member.display_name}\n" \
               f"**Highest Role:** {member.top_role}\n" \
               f"**Account created at:** {creation_date}"
        embed = discord.Embed(description=desc, color=member.colour)
        date = member.joined_at.strftime("%d.%m.%Y - %H:%M:%S")
        embed.set_footer(text=f"Member since {date}")
        embed.set_author(name=member.name, icon_url=member.avatar.url)
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Utils(bot))
