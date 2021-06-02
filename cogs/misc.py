from discord.ext import commands
import asyncio
import discord
import random
import utils


class Utils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.poll_time = 10

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
    async def mirror_(self, ctx, *, member: utils.Member = None):
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
    async def profile_(self, ctx, *, member: utils.Member = None):
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

    @commands.command(name="choose")
    async def choose(self, ctx, *arguments):
        """chooses one random item out of the arguments"""
        item = random.choice(arguments or ["nothing"])
        await ctx.send(f"It's `{item}`")

    @commands.command(name="poll")
    async def poll_(self, ctx, time: int, *, arguments):
        """basic poll command, first argument has to be the time
        in minutes. The rest of the arguments should be separated by
        newlines, up to 9 choices possible"""
        lines = arguments.split("\n")

        if not 3 <= len(lines) <= 9:
            msg = "You should have between two and nine choices"
            await ctx.send(msg)
            return

        question = lines.pop(0)

        parsed_options = ""
        for index, option in enumerate(lines):
            parsed_options += f"\n`{index + 1}.` {option}"

        title = f"**Poll from {ctx.author.display_name}**"
        description = f"{title}\n{question}{parsed_options}"
        embed = discord.Embed(description=description, color=discord.Color.purple())
        embed.set_footer(text=f"Voting ends in {time} minutes")
        embed.set_thumbnail(url=ctx.author.avatar_url)
        poll = await ctx.send(embed=embed)

        for num in range(len(lines)):
            emoji = f"{num + 1}\N{COMBINING ENCLOSING KEYCAP}"
            await poll.add_reaction(emoji)

        await utils.silencer(ctx.message.delete())
        whole, remainder = divmod(time, self.poll_time)

        first_duration = self.poll_time if whole else remainder
        await asyncio.sleep(first_duration * 60)

        for n in range(1, whole):
            if n + 1 != whole:
                minutes = self.poll_time
                cur = (whole - n) * self.poll_time + remainder
            else:
                minutes = remainder
                cur = minutes

            embed.set_footer(text=f"Voting ends in {cur} minutes")
            await poll.edit(embed=embed)
            await asyncio.sleep(minutes * 60)

        re_fetched = await ctx.channel.fetch_message(poll.id)
        votes = sorted(re_fetched.reactions, key=lambda r: r.count, reverse=True)
        color = discord.Color.red()

        if [r.count for r in votes].count(1) == len(votes):
            msg = "`Nobody voted!`"

        elif votes[0].count > votes[1].count:
            color = discord.Color.green()
            winner = re_fetched.reactions.index(votes[0])
            msg = f"`{lines[winner]} won with {votes[0].count - 1} votes!`"

        else:
            msg = "`The poll resulted in a draw...`"

        result = f"{title}\n{question}\n{msg}"
        result_embed = discord.Embed(description=result, color=color)
        result_embed.set_footer(text="Finished.")
        await poll.edit(embed=result_embed)
        await utils.silencer(poll.clear_reactions())


def setup(bot):
    bot.add_cog(Utils(bot))
