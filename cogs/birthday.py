from discord.ext import commands, tasks
from datetime import datetime
from itertools import cycle
import dateparser
import discord
import random
import utils


class Birthday(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.preset = "%d.%m.%Y"
        self.format = "%Y-%m-%d %H:%M:%S"
        self.emojis = ("🥰", "😎", "🥳")
        self.gifs = (
            "https://media1.tenor.com/images/4159265660b39965876a744cdc32f3c5/tenor.gif",
            "https://media1.tenor.com/images/e790abf8a07df6fe5f692754d537e7ce/tenor.gif",
            "https://media1.tenor.com/images/4edc2a068950de1b0b5cbbba7389ac79/tenor.gif",
            "https://media1.tenor.com/images/d30af3d60233e591acb0d552e96505ea/tenor.gif"
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

        query = 'SELECT user_id, date FROM birthday WHERE guild_id = $1'

        for guild in self.bot.guilds:
            channel_id = self.bot.config.get('bdayboard', guild.id)
            bday_channel = guild.get_channel(channel_id)

            if bday_channel is None:
                continue

            dates = await self.bot.fetch(query, guild.id)

            for user_id, date_str in dates:
                date = datetime.strptime(date_str, self.format)

                if today.month == date.month and today.day == date.day:

                    member = guild.get_member(user_id)
                    if member is None:
                        continue

                    embed = discord.Embed(colour=discord.Colour.dark_gold())
                    url = random.choice(self.gifs)
                    embed.set_image(url=url)

                    new_age = today.year - date.year
                    base = "**{} has birthday today and turns {} years old** {}"

                    if new_age < 25:
                        emoji = random.choice(self.emojis)
                    else:
                        emoji = "☠"
                        base += "\nImagine being basically dead xddd"

                    description = base.format(member.display_name, new_age, emoji)
                    embed.description = description

                    await bday_channel.send(embed=embed)

    @commands.command(name="birthdays")
    async def birthdays_(self, ctx):
        query = 'SELECT user_id, date FROM birthday WHERE guild_id = $1'
        dates = await self.bot.fetch(query, ctx.guild.id)

        dates = [(idc, datetime.strptime(d, self.format)) for idc, d in dates]
        sorted_dates = sorted(dates, key=lambda d: (d[1].month, d[1].day))
        today = datetime.now()

        next_dates = []
        for user_id, date in cycle(sorted_dates):
            if date.month < today.month or date.day < today.day:
                continue

            if len(next_dates) < 5:
                next_dates.append((user_id, date))
            else:
                break

        embed = discord.Embed()
        print(next_dates)

    @commands.command(name="birthday")
    async def birthday_(self, ctx, date_str=None):
        if date_str is None:
            query = 'DELETE FROM birthday WHERE guild_id = $1 AND user_id = $1'
            await self.bot.execute(query, ctx.guild.id, ctx.author.id)
            await ctx.send("birthday deleted you insecure thing")
            return

        kwargs = {'locales': ["de-BE"], 'settings': {'PREFER_DATES_FROM': 'past'}}
        birthday_date = dateparser.parse(date_str, **kwargs)

        if birthday_date is None:
            raise utils.WrongDateFormat()

        if (datetime.now().year - birthday_date.year) < 14:
            await ctx.send("pls message <@211836670666997762>")
            return

        query = 'SELECT date FROM birthday WHERE guild_id = $1 AND user_id = $2'
        date = await self.bot.fetchrow(query, ctx.guild.id, ctx.author.id)

        if date and date[0] == str(birthday_date):
            await ctx.send("you already registered that date")
        else:
            query = 'INSERT OR REPLACE INTO birthday ' \
                    '(guild_id, user_id, date) VALUES ($1, $2, $3)'
            await self.bot.execute(query, ctx.guild.id, ctx.author.id, birthday_date)

            date_rep = birthday_date.strftime(self.preset)
            await ctx.send(f"you're birthday `{date_rep}` got registered")


def setup(bot):
    bot.add_cog(Birthday(bot))
