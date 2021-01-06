from discord.ext import commands
import discord


class Utils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="summon")
    async def summon_(self, ctx):
        """summons all members from the defined
        lobby channel into your voice channel"""
        try:
            own_channel = ctx.author.voice.channel
        except AttributeError:
            msg = "You'll have to be in a voice channel"
            await ctx.send(msg)
            return

        channel_id = self.bot.config.get('lobby', ctx.guild.id)
        channel = self.bot.get_channel(channel_id)

        if channel is None:
            msg = "This guild has no registered lobby"
            await ctx.send(msg)
            return

        for member in channel.members:
            if member.bot is True:
                continue
            try:
                await member.move_to(own_channel)
            except discord.Forbidden:
                continue

        await ctx.message.delete()

    @commands.command(name="mirror")
    async def mirror_(self, ctx, member: discord.Member = None):
        """displays the discord avatar of a guild member
        or yourself if no member passed in the arguments"""
        member = member or ctx.author
        embed = discord.Embed()
        embed.set_image(url=member.avatar_url)
        await ctx.send(embed=embed)

    @commands.command(name="icon")
    async def icon_(self, ctx):
        """displays the guilds server icon"""
        embed = discord.Embed(color=discord.Color.gold())
        embed.set_image(url=ctx.guild.icon_url)
        await ctx.send(embed=embed)

    @commands.command(name="profile")
    async def profile_(self, ctx, member: discord.Member = None):
        """gives some basic stats about a guild member
        or yourself if no member passed in the arguments"""
        member = member or ctx.author
        creation_date = member.created_at.strftime("%d.%m.%Y")
        desc = f"**Nickname:** {member.display_name}\n" \
               f"**Highest Role:** {member.top_role}\n" \
               f"**Account created at:** {creation_date}"
        embed = discord.Embed(description=desc, color=member.colour)
        date = member.joined_at.strftime("%d.%m.%Y - %H:%M:%S")
        embed.set_footer(text=f"Member since {date}")
        embed.set_author(name=member.name, icon_url=member.avatar_url)
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Utils(bot))
