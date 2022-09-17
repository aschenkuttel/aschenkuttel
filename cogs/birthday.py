from dateutil.relativedelta import relativedelta
from discord.ext import commands, tasks
from datetime import datetime
from itertools import cycle
import dateparser
import discord
import random
import utils


class Birthdate:
    format = "%Y-%m-%d %H:%M:%S"
    preset = "%d.%m.%Y"

    def __init__(self, row):
        self.user_id, self.raw_date = row[1:]
        self.date = datetime.strptime(self.raw_date, self.format)
        self.member = None

    def append_year(self):
        self.date = self.date + relativedelta(years=1)

    def next_year(self, date):
        if self.year != date.year:
            return
        elif self.month < date.month:
            return True
        elif self.month == date.month and self.day < date.day:
            return True

    def __str__(self):
        return self.date.strftime(self.preset)

    def __eq__(self, other):
        return self.date == other

    @property
    def year(self):
        return self.date.year

    @property
    def month(self):
        return self.date.month

    @property
    def day(self):
        return self.date.day


class Birthday(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.emojis = ("🥰", "😎", "🥳")
        self.gifs = (
            "https://media1.tenor.com/images/4159265660b39965876a744cdc32f3c5/tenor.gif",
            "https://media1.tenor.com/images/e790abf8a07df6fe5f692754d537e7ce/tenor.gif",
            "https://media1.tenor.com/images/4edc2a068950de1b0b5cbbba7389ac79/tenor.gif",
            "https://media1.tenor.com/images/d30af3d60233e591acb0d552e96505ea/tenor.gif",
            "https://media1.tenor.com/images/ade6ea654ec8e7c6de665d9c58836455/tenor.gif"
        )
        self.birthday_loop.start()

    def cog_unload(self):
        self.birthday_loop.cancel()

    @tasks.loop(hours=1)
    async def birthday_loop(self):
        await self.bot.wait_until_unlocked()
        today = datetime.now()

        if today.hour != 12:
            return

        for guild in self.bot.guilds:
            channel_id = self.bot.config.get('bdayboard', guild.id)
            bday_channel = guild.get_channel(channel_id)

            if bday_channel is None:
                continue

            dates = await self.fetch_guild_birthdays(guild.id)

            for date in dates:
                if today.month == date.month and today.day == date.day:

                    member = guild.get_member(date.user_id)
                    if member is None:
                        continue

                    embed = discord.Embed(colour=discord.Colour.dark_gold())
                    url = random.choice(self.gifs)
                    embed.set_image(url=url)

                    new_age = today.year - date.year
                    base = "**{} has birthday today and turns {} years old** {}"

                    if new_age < 30:
                        emoji = random.choice(self.emojis)
                    else:
                        emoji = "☠"
                        base += "\nImagine being basically dead xddd"

                    description = base.format(member.mention, new_age, emoji)
                    embed.description = description

                    await bday_channel.send(embed=embed)

    async def fetch_birthday(self, ctx, suppress=False):
        query = 'SELECT * FROM birthday WHERE guild_id = $1 AND user_id = $2'
        response = await self.bot.fetchone(query, ctx.guild.id, ctx.author.id)

        if response is not None:
            return Birthdate(response)
        elif suppress is False:
            raise utils.NoBirthday()

    async def fetch_guild_birthdays(self, guild_id):
        query = 'SELECT * FROM birthday WHERE guild_id = $1'
        response = await self.bot.fetch(query, guild_id)
        return [Birthdate(row) for row in response]

    @commands.command(name="birthdays")
    async def birthdays_(self, ctx):
        """Displays the next 5 birthdays of the server"""
        dates = await self.fetch_guild_birthdays(ctx.guild.id)
        today = datetime.now()

        for date in dates:
            date.date = date.date.replace(year=today.year)

        upcoming_dates = []
        sorted_dates = sorted(dates, key=lambda d: (d.month, d.day))

        for date in cycle(sorted_dates):
            if len(upcoming_dates) == 5:
                break

            member = ctx.guild.get_member(date.user_id)
            if member is None:
                continue

            if date.next_year(today):
                date.append_year()
                continue

            line = f"`{date}` | {member.mention}"
            upcoming_dates.append(line)
            date.append_year()

        embed = discord.Embed(colour=discord.Colour.dark_gold())
        embed.title = f"Upcoming Birthdays of {ctx.guild.name}"
        embed.description = "\n".join(upcoming_dates)
        await ctx.send(embed=embed)

    @commands.command(name="birthday")
    async def birthday_(self, ctx, date_str=None):
        """Either sets/changes your birthday or
        displays your birthday if no argument is given"""
        date = await self.fetch_birthday(ctx, suppress=True)

        if date_str is None:
            if date is None:
                raise utils.NoBirthday()

            msg = f"`{date}` is your birthday?"
            await ctx.send(msg)
            return

        kwargs = {'locales': ["de-BE"], 'settings': {'PREFER_DATES_FROM': 'past'}}
        birthday_date = dateparser.parse(date_str, **kwargs)

        if birthday_date is None:
            raise utils.WrongDateFormat()

        if (datetime.now().year - birthday_date.year) < 14:
            await ctx.send("pls message <@211836670666997762>")
            return

        if date == birthday_date:
            await ctx.send("you already registered that date")
        else:
            query = 'INSERT OR REPLACE INTO birthday ' \
                    '(guild_id, user_id, date) VALUES ($1, $2, $3)'
            await self.bot.execute(query, ctx.guild.id, ctx.author.id, birthday_date)

            date_rep = birthday_date.strftime(Birthdate.preset)
            await ctx.send(f"your birthday `{date_rep}` got registered")

    @commands.command(name="insecure")
    async def insecure_(self, ctx):
        """removes your current birthday if you have one"""
        await self.fetch_birthday(ctx)

        query = 'DELETE FROM birthday WHERE guild_id = $1 AND user_id = $2'
        await self.bot.execute(query, ctx.guild.id, ctx.author.id)
        await ctx.send("birthday deleted you insecure thing")


async def setup(bot):
    await bot.add_cog(Birthday(bot))
