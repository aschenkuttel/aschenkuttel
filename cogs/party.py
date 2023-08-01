from discord.ext import commands, tasks
from discord import app_commands
from discord import ui
import asyncio
import logging
import discord
import json

logger = logging.getLogger('self')


class WatchParty:
    def __init__(self, args):
        (
            self.id,
            self.name,
            self.guild_id,
            self.channel_id,
            self.author_id,
            raw_participants,
            self.next_date,
            self.recurring
        ) = args

        self.participants = json.loads(raw_participants)

    def __eq__(self, other):
        return self.id == other.id

    @property
    def date_str(self):
        if self.next_date is None:
            return "nothing scheduled"
        else:
            time = self.next_date.strftime("%H:%M")
            weekday = self.next_date.strftime("%A")

            if self.recurring:
                return f"{time} every {weekday}"
            else:
                return f"{time} on {weekday}"

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
        party_id, party_name = await self.cog.create_party(interaction, self.name, self.participants)
        msg = f"Successfully created watch party `{party_name}` with ID: {party_id}"
        await interaction.response.edit_message(content=msg, view=None)
        self.cleanup()

    async def on_timeout(self):
        self.cleanup()

    def cleanup(self):
        self.cog.cache.pop(self.name, None)
        self.stop()


class Party(commands.GroupCog, name="watchparty"):
    def __init__(self, bot):
        self.bot = bot
        self.type = 2
        self.cache = {}
        # self._task = self.bot.loop.create_task(self.party_loop())
        self._lock = asyncio.Event(loop=bot.loop)
        self.current_reminder = None

    @tasks.loop(hours=24)
    async def garbage_collector(self):
        await self.bot.wait_until_unlocked()

        for guild in self.bot.guilds:
            query = "SELECT * FROM watch_parties WHERE guild_id = $1"
            rows = await self.bot.fetch(query, guild.id)
            parties = [WatchParty(row) for row in rows]

            for party in parties:
                invalid_channel = party.channel_id not in [c.id for c in guild.channels]
                invalid_author = guild.get_member(party.author_id) is None

                if invalid_channel or invalid_author:
                    query = "DELETE FROM watch_parties WHERE id = $1"
                    await self.bot.execute(query, party.id)
                    reason = "invalid channel" if invalid_channel else "invalid author"
                    logger.debug(f"deleted watch party {party.id} from guild {guild.id} due to {reason}")


    # async def party_loop(self):
    #     await self.bot.wait_until_unlocked()
    #     while not self.bot.is_closed():
    #
    #         if not self.current_reminder:
    #             query = 'SELECT * FROM reminder ORDER BY expiration'
    #             data = await self.bot.fetchone(query)
    #
    #             if data is not None:
    #                 self.current_reminder = Timer(self.bot, data)
    #
    #         if self.current_reminder:
    #             logger.debug(f"reminder {self.current_reminder.id}: sleeping")
    #
    #             difference = (self.current_reminder.expiration - datetime.now())
    #             seconds = difference.total_seconds()
    #             await asyncio.sleep(seconds)
    #
    #             query = "DELETE FROM reminder WHERE id = $1"
    #             await self.bot.execute(query, self.current_reminder.id)
    #
    #             if seconds > -60:
    #                 logger.debug(f"reminder {self.current_reminder.id}: send message")
    #                 await self.current_reminder.send()
    #
    #             self.current_reminder = None
    #             self._lock.clear()
    #
    #         else:
    #             await self._lock.wait()

    # @commands.group(name="watchparty")
    # async def watchparty(self, ctx):
    #     pass

    # @watchparty.command(name="create")
    # async def _create(self, ctx, name, date):
    #     pass
    #
    # @watchparty.command(name="join")
    # async def _join(self, ctx, name):
    #     pass
    #
    # @watchparty.command(name="leave")
    # async def _leave(self, ctx, name):
    #     pass

    def cleanup(self, interaction):
        self.cache.pop(interaction.user.id, None)

    async def fetch_party(self, party_id):
        query = "SELECT * FROM watch_parties WHERE id = $1"
        row = await self.bot.fetchone(query, party_id)

        if row is not None:
            return WatchParty(row)

    async def fetch_party_by_owner(self, interaction):
        query = "SELECT * FROM watch_parties WHERE guild_id = $1 AND author_id = $2"
        row = await self.bot.fetchone(query, interaction.guild.id, interaction.user.id)

        if row is not None:
            return WatchParty(row)

    async def create_party(self, interaction, name, participants):
        query = "INSERT INTO watch_parties (name, guild_id, channel_id, author_id, participants, next_date, recurring) " \
                "VALUES ($1, $2, $3, $4, $5, $6, $7)"

        users = json.dumps(participants, separators=(',', ':'))
        await self.bot.db.execute(query, (name, interaction.guild.id,
                                          interaction.channel_id, interaction.user.id,
                                          users, None, False))
        await self.bot.db.commit()

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

    @app_commands.command(name="list", description="Lists all watch parties in this Server")
    async def _list(self, interaction):
        party_rows = await self.bot.fetch("SELECT * FROM watch_parties WHERE guild_id = $1", interaction.guild.id)
        parties = [WatchParty(row) for row in party_rows]

        if not parties:
            await interaction.response.send_message("There are no watch parties in this server!")
        else:
            embed = discord.Embed(title="Watch Parties in this server", color=0x2F3136)
            description = []

            for party in parties:
                next_date = party.next_date.strftime("%d.%m.%Y %H:%M") if party.next_date else "*nothing scheduled*"
                title = f"**{party.name}** by <@{party.author_id}>"

                description.extend([title, next_date])

                if party != parties[-1]:
                    description.append("\n")

            if description:
                embed.description = "\n".join(description)
            else:
                embed.description = "There are no watch parties in this server"

            await interaction.response.send_message(embed=embed)


    @app_commands.command(name="delete", description="Deletes a watch party in this server")
    async def delete_(self, interaction):
        party = await self.fetch_party_by_owner(interaction)

        if party is None:
            msg = "You don't have an active watch party"
            await interaction.response.send_message(msg, ephemeral=True)
            return

        query = "DELETE FROM watch_parties WHERE id = $1"
        await self.bot.execute(query, party.id)
        await interaction.response.send_message(f"Successfully deleted watch party: {party.name}")

    @app_commands.command(name="join", description="Joins a watch party in this server")
    async def join_(self, interaction, party_id: int):
        party = await self.fetch_party(party_id)

        if party is None:
            msg = f"There is no watch party with ID: {party_id}"
            await interaction.response.send_message(msg, ephemeral=True)
            return

        if interaction.user.id in party.participants:
            msg = "You are already in this watch party"
            await interaction.response.send_message(msg, ephemeral=True)
            return

        party.participants.append(interaction.user.id)
        query = "UPDATE watch_parties SET participants = $1 WHERE id = $2"
        await self.bot.execute(query, json.dumps(party.participants), party.id)
        await interaction.response.send_message(f"Successfully joined watch party: {party.name}")

    @app_commands.command(name="leave", description="Leaves a watch party in this server")
    async def leave_(self, interaction, party_id: int):
        party = await self.fetch_party(party_id)

        if party is None:
            msg = f"There is no watch party with ID: {party_id}"
            await interaction.response.send_message(msg, ephemeral=True)
            return

        if interaction.user.id not in party.participants:
            msg = "You are not in this watch party"
            await interaction.response.send_message(msg, ephemeral=True)
            return

        party.participants.remove(interaction.user.id)
        query = "UPDATE watch_parties SET participants = $1 WHERE id = $2"
        await self.bot.execute(query, json.dumps(party.participants), party.id)
        await interaction.response.send_message(f"Successfully left watch party: `{party.name}`")

async def setup(bot):
    await bot.add_cog(Party(bot))
