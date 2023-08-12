from discord.ext import commands, tasks
from discord import app_commands
from discord import ui
from datetime import datetime
from dateutil.relativedelta import relativedelta
import dateparser
import traceback
import asyncio
import logging
import discord
import json

logger = logging.getLogger('self')


class WatchParty:
    def __init__(self, bot, args):
        self.bot = bot
        (
            self.id,
            self.name,
            self.guild_id,
            self.channel_id,
            self.author_id,
            raw_participants,
            timestamp,
            self.recurring
        ) = args

        self.participants = json.loads(raw_participants)
        self.next_date = datetime.fromtimestamp(timestamp) if timestamp else None

    def __eq__(self, other):
        return self.id == other.id

    def date_str(self, cursive=False):
        if self.next_date is None:
            return "nothing scheduled"
        else:
            time_rep = self.next_date.strftime("`%d.%m.%Y` at `%H:%M`")

            if self.recurring:
                if self.recurring != 0 and self.recurring % 7 == 0:
                    week_days = int(self.recurring / 7)
                    time_rep += f" every `{week_days} week{'s' if week_days > 1 else ''}`"
                else:
                    time_rep += f" every `{self.recurring} days`"

            if cursive:
                return f"*{time_rep.replace('`', '')}*"
            else:
                return time_rep

    async def create_next_date(self):
        if self.next_date is None:
            return

        if self.recurring == 0:
            self.next_date = None

        else:
            # next_date = self.next_date + relativedelta(days=self.recurring)
            self.next_date += relativedelta(days=self.recurring)

        await self.bot.execute(
            "UPDATE watch_parties SET next_date = $1 WHERE id = $2",
            self.next_date.timestamp(),
            self.id
        )

        new_date = self.next_date.strftime("%d.%m.%Y %H:%M") if self.next_date else "*nothing scheduled*"
        logger.debug(f"watch_party {self.id}: next date set to {new_date}")

    async def insert(self):
        cursor = await self.bot.db.execute(
            "INSERT INTO watch_parties (name, guild_id, channel_id, author_id, participants, next_date, recurring) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7)", (
                self.name,
                self.guild_id,
                self.channel_id,
                self.author_id,
                json.dumps(self.participants, separators=(',', ':')),
                self.next_date,
                self.recurring
            ))

        self.id = cursor.lastrowid
        await self.bot.db.commit()

    async def delete(self):
        query = "DELETE FROM watch_parties WHERE id = $1"
        await self.bot.execute(query, self.id)

    async def add_participant(self, user_id):
        if user_id in self.participants:
            return False

        self.participants.append(user_id)
        query = "UPDATE watch_parties SET participants = $1 WHERE id = $2"
        await self.bot.execute(query, json.dumps(self.participants), self.id)
        return True

    async def remove_participant(self, user_id):
        if user_id not in self.participants:
            return False

        self.participants.remove(user_id)
        query = "UPDATE watch_parties SET participants = $1 WHERE id = $2"
        await self.bot.execute(query, json.dumps(self.participants), self.id)
        return True

    async def send(self):
        msg = f"**Watch Party:** {self.name}\n" \
              f"**Next Date:** {self.date_str()}\n" \
              f"**Participants:** {', '.join([f'<@{p}>' for p in self.participants])}"

        channel = self.bot.get_channel(self.channel_id)

        if channel is None:
            return

        try:
            await channel.send(msg)
            logger.debug(f"watch_party {self.id}: successful notification")

        except (discord.Forbidden, discord.HTTPException):
            logger.debug(f"watch_party {self.id}: notification not allowed")
            return


class CreateView(ui.View):
    def __init__(self, cog, name, author_id):
        super().__init__(timeout=600)
        self.cog = cog
        self.name = name
        self.author_id = author_id
        self.participants = []

    @ui.select(cls=ui.UserSelect, placeholder="Select all the members you want to invite!", min_values=1, max_values=20)
    async def user_select(self, interaction, select: discord.ui.UserSelect):
        self.participants = [m.id for m in select.values]
        await interaction.response.defer()

    @ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction, _):
        await interaction.response.edit_message(content="Watch party creation cancelled", view=None)
        self.cleanup()

    @ui.button(label="Create", style=discord.ButtonStyle.green)
    async def create(self, interaction, _):
        party = await self.cog.create_party(interaction, self.name, self.participants)
        msg = f"Successfully created watch party `{party.name}` with ID: {party.id}"
        await interaction.response.edit_message(content=msg, view=None)
        self.cleanup()

    async def on_timeout(self):
        self.cleanup()

    def cleanup(self):
        self.cog.cache.pop(self.author_id, None)
        self.stop()


class Party(commands.GroupCog, name="watchparty"):
    def __init__(self, bot):
        self.bot = bot
        self.type = 2
        self.settings = {'languages': ['de', 'en'], 'settings': {'PREFER_DATES_FROM': "future"}}
        self.cache = {}
        self._task = self.bot.loop.create_task(self.party_loop())
        self._task.add_done_callback(self.loop_error_handler)
        self._lock = asyncio.Event(loop=bot.loop)
        self.current_watch_party = None
        self.garbage_collector.start()

    def cog_unload(self):
        self._task.cancel()
        self.garbage_collector.cancel()

    def restart(self, party=None):
        self._task.cancel()

        if party is None:
            self._lock.clear()

        self.current_watch_party = party
        self._task = self.bot.loop.create_task(self.party_loop())

    @tasks.loop(hours=24)
    async def garbage_collector(self):
        await self.bot.wait_until_unlocked()

        for guild in self.bot.guilds:
            query = "SELECT * FROM watch_parties WHERE guild_id = $1"
            rows = await self.bot.fetch(query, guild.id)
            parties = [WatchParty(None, row) for row in rows]

            for party in parties:
                invalid_channel = party.channel_id not in [c.id for c in guild.channels]
                invalid_author = guild.get_member(party.author_id) is None

                if invalid_channel or invalid_author:
                    query = "DELETE FROM watch_parties WHERE id = $1"
                    await self.bot.execute(query, party.id)
                    reason = "invalid channel" if invalid_channel else "invalid author"
                    logger.debug(f"deleted watch party {party.id} from guild {guild.id} due to {reason}")

    async def party_loop(self):
        await self.bot.wait_until_unlocked()
        while not self.bot.is_closed():

            if not self.current_watch_party:
                query = 'SELECT * FROM watch_parties WHERE next_date IS NOT NULL ORDER BY next_date LIMIT 1'
                data = await self.bot.fetchone(query)

                if data is not None:
                    self.current_watch_party = WatchParty(self.bot, data)

            if self.current_watch_party:
                difference = (self.current_watch_party.next_date - datetime.now())
                seconds = difference.total_seconds()

                logger.debug(f"watch_party {self.current_watch_party.id}: sleeping for {seconds} seconds")
                await asyncio.sleep(seconds)

                if seconds > -60:
                    logger.debug(f"reminder {self.current_watch_party.id}: send message")
                    await self.current_watch_party.send()
                else:
                    logger.debug(f"reminder {self.current_watch_party.id}: skipped due to timeout")

                await self.current_watch_party.create_next_date()
                self.current_watch_party = None
                self._lock.clear()

            else:
                await self._lock.wait()

    @staticmethod
    def loop_error_handler(task):
        try:
            exc = task.exception()
        except asyncio.CancelledError:
            return

        if not exc:
            return

        if not isinstance(exc, asyncio.CancelledError):
            # # python >= 3.10
            # traceback.print_exception(exc)
            # python < 4.0
            traceback.print_exception(type(exc), exc, exc.__traceback__)

    def cleanup(self, interaction):
        self.cache.pop(interaction.user.id, None)

    async def fetch_party(self, party_id):
        query = "SELECT * FROM watch_parties WHERE id = $1"
        row = await self.bot.fetchone(query, party_id)

        if row is not None:
            return WatchParty(self.bot, row)

    async def fetch_party_by_owner(self, interaction):
        query = "SELECT * FROM watch_parties WHERE guild_id = $1 AND author_id = $2"
        row = await self.bot.fetchone(query, interaction.guild.id, interaction.user.id)

        if row is not None:
            return WatchParty(self.bot, row)

    async def create_party(self, interaction, name, participants):
        raw_participants = json.dumps(participants, separators=(',', ':'))
        party = WatchParty(self.bot, (0, name, interaction.guild.id,
                                      interaction.channel_id, interaction.user.id,
                                      raw_participants, None, 0))

        await party.insert()

        if self.current_watch_party and party.next_date < self.current_watch_party.next_date:
            self.restart(party)

        return party

    @app_commands.command(name="create", description="Creates a new watch party in this server")
    async def create_(self, interaction, name: str):
        if self.cache.get(interaction.user.id) is not None:
            msg = "You already have an active watch party creation"
            await interaction.response.send_message(msg, ephemeral=True)
            return

        active_party = await self.fetch_party_by_owner(interaction)

        if active_party is not None:
            msg = f"You already have an active watch party: {active_party.name}"
            await interaction.response.send_message(msg, ephemeral=True)
            return

        self.cache[interaction.user.id] = True
        view = CreateView(self, name, interaction.user.id)
        await interaction.response.send_message(view=view)

    @app_commands.command(name="next_date", description="Sets the next date of your watch party")
    @app_commands.describe(date="the next date of your watch party in `DD.MM.YYYY HH:MM`",
                           recurring="the amount of days between each watch party if it should be recurring")
    async def next_date_(self, interaction, date: str, recurring: app_commands.Range[int, 0, 360] = 0):
        party = await self.fetch_party_by_owner(interaction)

        if party is None:
            msg = "You don't have an active watch party"
            await interaction.response.send_message(msg, ephemeral=True)
            return

        try:
            expected_date = dateparser.parse(date, **self.settings)
            party.next_date = expected_date
            party.recurring = recurring
        except Exception as error:
            logger.debug(error)
            expected_date = None

        if expected_date is None or expected_date < datetime.now():
            msg = "No valid time format or date is in the past"
            await interaction.response.send_message(msg, ephemeral=True)
            return

        query = "UPDATE watch_parties SET next_date = $1, recurring = $2 WHERE id = $3"
        await self.bot.execute(query, expected_date.timestamp(), recurring, party.id)

        # set current watch party if there is none
        if not self.current_watch_party:
            self.current_watch_party = party
            self._lock.set()

        # restart if new date is earlier than current watch party
        elif self.current_watch_party.next_date and expected_date < self.current_watch_party.next_date:
            self.restart(party)

        msg = f"Successfully set next date of watch party **{party.name}** to {party.date_str()}"
        await interaction.response.send_message(msg)

    @app_commands.command(name="list", description="Lists all watch parties in this Server")
    async def _list(self, interaction):
        party_rows = await self.bot.fetch("SELECT * FROM watch_parties WHERE guild_id = $1", interaction.guild.id)
        parties = [WatchParty(self.bot, row) for row in party_rows]

        if not parties:
            await interaction.response.send_message("There are no watch parties in this server!")
        else:
            embed = discord.Embed(title="Watch Parties in this server", color=discord.Color.blurple())
            description = []

            for party in parties:
                next_date = party.date_str(True) if party.next_date else "*nothing scheduled*"
                title = f"**{party.name}** by <@{party.author_id}>"

                description.extend([title, next_date])

                if party != parties[-1]:
                    description.append("\n")

            if description:
                embed.description = "\n".join(description)
            else:
                embed.description = "There are no watch parties in this server"

            await interaction.response.send_message(embed=embed)

    @app_commands.command(name="delete", description="Deletes your watch party in this server")
    async def delete_(self, interaction):
        party = await self.fetch_party_by_owner(interaction)

        if party is None:
            msg = "You don't have an active watch party"
            await interaction.response.send_message(msg, ephemeral=True)
        else:
            await party.delete()

            if self.current_watch_party == party:
                self.restart()

            msg = f"Successfully deleted watch party `{party.name}`"
            await interaction.response.send_message(msg)

    @app_commands.command(name="join", description="Joins a watch party in this server")
    @app_commands.describe(party_id="the ID of the watch party you want to join")
    async def join_(self, interaction, party_id: int):
        party = await self.fetch_party(party_id)

        if party is None:
            msg = f"There is no watch party with ID: {party_id}"
            await interaction.response.send_message(msg, ephemeral=True)
            return

        response = await party.add_participant(interaction.user.id)

        if response is False:
            msg = "You are already in this watch party"
            await interaction.response.send_message(msg, ephemeral=True)
        else:
            if self.current_watch_party == party:
                self.current_watch_party.participants.append(interaction.user.id)

            msg = f"Successfully joined watch party: {party.name}"
            await interaction.response.send_message(msg)

    @app_commands.command(name="leave", description="Leaves a watch party in this server")
    @app_commands.describe(party_id="the ID of the watch party you want to leave")
    async def leave_(self, interaction, party_id: int):
        party = await self.fetch_party(party_id)

        if party is None:
            msg = f"There is no watch party with `ID {party_id}`"
            await interaction.response.send_message(msg, ephemeral=True)
            return

        response = await party.remove_participant(interaction.user.id)

        if response is False:
            msg = "You are not in this watch party"
            await interaction.response.send_message(msg, ephemeral=True)
        else:
            if self.current_watch_party == party:
                self.current_watch_party.participants.remove(interaction.user.id)

            msg = f"Successfully left watch party: {party.name}"
            await interaction.response.send_message(msg)


async def setup(bot):
    await bot.add_cog(Party(bot))
