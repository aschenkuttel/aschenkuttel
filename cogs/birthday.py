from dateutil.relativedelta import relativedelta
from discord.ext import commands, tasks
from discord import app_commands
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
            "https://media1.tenor.com/images/ade6ea654ec8e7c6de665d9c58836455/tenor.gif",
            "https://media.tenor.com/RvfqrIGh_skAAAAC/umakanta.gif",
            "https://media.tenor.com/VMC8fNKdQrcAAAAd/happy-birthday-bon-anniversaire.gif",
            "https://media.tenor.com/ebZ0rVyVysYAAAAC/cake-birthday.gif"
        )
        self.birthday_loop.start()

    def cog_unload(self):
        self.birthday_loop.cancel()

    @tasks.loop(hours=1)
    async def birthday_loop(self):
        await self.bot.wait_until_unlocked()
        today = datetime.now()

        if today.hour != 10:
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

    async def fetch_birthday(self, member, suppress=False):
        query = 'SELECT * FROM birthday WHERE guild_id = $1 AND user_id = $2'
        response = await self.bot.fetchone(query, member.guild.id, member.id)

        if response is not None:
            return Birthdate(response)
        elif suppress is False:
            raise utils.NoBirthday()

    async def fetch_guild_birthdays(self, guild_id):
        query = 'SELECT * FROM birthday WHERE guild_id = $1'
        response = await self.bot.fetch(query, guild_id)
        return [Birthdate(row) for row in response]

    @app_commands.command(name="born", description="sets/changes your birthday")
    @app_commands.describe(date_str="your birthdate in `DD.MM.YYYY`")
    async def born_(self, interaction, date_str: str):
        """sets/changes your birthday"""

        date = await self.fetch_birthday(interaction.user, suppress=True)

        kwargs = {'locales': ["de-BE"], 'settings': {'PREFER_DATES_FROM': 'past'}}
        birthday_date = dateparser.parse(date_str, **kwargs)

        if birthday_date is None:
            await interaction.response.send_message("invalid date format, birthdays are in `DD.MM.YYYY`")
            return

        if (datetime.now().year - birthday_date.year) < 14:
            await interaction.response.send_message("pls message <@211836670666997762>")
            return

        if date == birthday_date:
            await interaction.response.send_message("you already registered that date")
        else:
            query = 'INSERT OR REPLACE INTO birthday ' \
                    '(guild_id, user_id, date) VALUES ($1, $2, $3)'
            await self.bot.execute(query, interaction.guild.id, interaction.user.id, birthday_date)

            date_rep = birthday_date.strftime(Birthdate.preset)
            await interaction.response.send_message(f"your birthday `{date_rep}` got registered")

    @app_commands.command(name="birthday", description="shows the birthday of a member")
    async def birthday_(self, interaction, member: discord.Member = None):
        member = member or interaction.user
        date = await self.fetch_birthday(member, suppress=True)
        no_ping = discord.AllowedMentions(users=False)

        if date is None:
            msf = f"{member.mention} has no birthday registered"
            await interaction.response.send_message(msf, allowed_mentions=no_ping)
        else:
            msg = f"{member.mention} has birthday on `{date}`"
            await interaction.response.send_message(msg, allowed_mentions=no_ping)

    @app_commands.command(name="birthdays", description="displays the next 5 birthdays of the server")
    async def birthdays_(self, interaction):
        dates = await self.fetch_guild_birthdays(interaction.guild.id)

        if not dates:
            await interaction.response.send_message("no birthdays registered in this server")
            return

        today = datetime.now()

        for date in dates:
            date.date = date.date.replace(year=today.year)

        upcoming_dates = []
        sorted_dates = sorted(dates, key=lambda d: (d.month, d.day))

        for date in cycle(sorted_dates):
            if len(upcoming_dates) == 5:
                break

            member = interaction.guild.get_member(date.user_id)
            if member is None:
                continue

            if date.next_year(today):
                date.append_year()
                continue

            line = f"`{date}` | {member.mention}"
            upcoming_dates.append(line)
            date.append_year()

        embed = discord.Embed(colour=discord.Colour.dark_gold())
        embed.title = f"Upcoming Birthdays of {interaction.guild.name}"
        embed.description = "\n".join(upcoming_dates)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="insecure", description="removes your current birthday if you have one")
    async def insecure_(self, interaction):
        await self.fetch_birthday(interaction.user)

        query = 'DELETE FROM birthday WHERE guild_id = $1 AND user_id = $2'
        await self.bot.execute(query, interaction.guild.id, interaction.user.id)
        await interaction.response.send_message("birthday deleted you insecure thing")


async def setup(bot):
    await bot.add_cog(Birthday(bot))
