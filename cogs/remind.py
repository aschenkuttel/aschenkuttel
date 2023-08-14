from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone
from discord.ui import TextInput, Modal
from utils import TimeZone
import dateutil.tz
import dateparser
import traceback
import asyncio
import discord
import logging
import utils

logger = logging.getLogger('self')


class Timer:
    def __init__(self, bot, record):
        self.bot = bot
        self.id = record['id']
        self.author_id = record['author_id']
        self.channel_id = record['channel_id']
        self.creation = datetime.fromtimestamp(record['creation'])
        self.expiration = datetime.fromtimestamp(record['expiration'])
        self.reason = record['reason']

    @classmethod
    def temporary(cls, bot, author_id, channel_id, creation, expiration, reason):
        return cls(bot, record={
            'id': None,
            'author_id': author_id,
            'channel_id': channel_id,
            'creation': creation,
            'expiration': expiration,
            'reason': reason,
        })

    async def send(self):
        embed = discord.Embed(colour=discord.Color.dark_gold())
        embed.description = self.reason

        channel = self.bot.get_channel(self.channel_id)
        author = await self.bot.fetch_user(self.author_id)

        if author is None:
            return

        if channel is None:
            channel = author

        try:
            msg = f"**Reminder:** {author.mention}"
            await channel.send(msg, embed=embed)
            logger.debug(f"reminder {self.id}: successfully")

        except (discord.Forbidden, discord.HTTPException):
            logger.debug(f"reminder {self.id}: not allowed")
            return


class ReminderModal(Modal):
    def __init__(self, callback):
        super().__init__(title="Reminder")
        self.callback = callback

    time_input = TextInput(label="Remind me in/at")
    reason_input = TextInput(label="Reason", style=discord.TextStyle.long, required=False)

    async def on_submit(self, interaction):
        try:
            await self.callback(interaction, self.time_input.value, self.reason_input.value)
        except Exception as error:
            traceback.print_exception(type(error), error, error.__traceback__)
            await interaction.response.send_message("Schreib Neel eine DM, damit er das fixen kann")

    async def on_error(self, interaction, error):
        pass


class Reminder(commands.Cog):
    DEFAULT_TIMEZONE = dateutil.tz.gettz('Europe/Berlin')
    CHAR_LIMIT = 200

    def __init__(self, bot):
        self.bot = bot
        self.type = 2
        self.settings = {'languages': ['de', 'en'], 'settings': {'PREFER_DATES_FROM': "future"}}
        self.preset = "%d.%m.%Y | %H:%M:%S Uhr"
        self._task = self.bot.loop.create_task(self.remind_loop())
        self._task.add_done_callback(self.loop_error_handler)
        self._lock = asyncio.Event()
        self.current_reminder = None

    def cog_unload(self):
        self._task.cancel()

    def restart(self, reminder=None):
        self._task.cancel()

        if reminder is None:
            self._lock.clear()

        self.current_reminder = reminder
        self._task = self.bot.loop.create_task(self.remind_loop())

    async def remind_loop(self):
        await self.bot.wait_until_ready()

        while not self.bot.is_closed():

            if not self.current_reminder:
                query = 'SELECT * FROM reminder ORDER BY expiration'
                data = await self.bot.fetchone(query)

                if data is not None:
                    self.current_reminder = Timer(self.bot, data)

            if self.current_reminder:
                logger.debug(f"reminder {self.current_reminder.id}: sleeping")

                difference = (self.current_reminder.expiration - datetime.utcnow())
                seconds = difference.total_seconds()
                await asyncio.sleep(seconds)

                query = "DELETE FROM reminder WHERE id = $1"
                await self.bot.execute(query, self.current_reminder.id)

                logger.debug(f"reminder {self.current_reminder.id}: send message")
                await self.current_reminder.send()

                self.current_reminder = None
                self._lock.clear()

            else:
                logger.debug("reminder: waiting")
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

    async def save_reminder(self, interaction, raw_time, raw_reason):
        if len(raw_reason) > self.CHAR_LIMIT:
            msg = f"Reason must be less than {self.CHAR_LIMIT} characters"
            await interaction.response.send_message(msg, ephemeral=True)
            return

        try:
            expected_date = dateparser.parse(raw_time, **self.settings)
            user_zone = await self.get_timezone(interaction.user.id)
            zone = dateutil.tz.gettz(user_zone) if user_zone else self.DEFAULT_TIMEZONE
            expected_date = expected_date.astimezone(zone)

        except Exception as error:
            logger.debug(error)
            expected_date = None

        if expected_date is None:
            msg = "No valid time format"
            await interaction.response.send_message(msg, ephemeral=True)
            return

        embed = discord.Embed(colour=discord.Color.green())
        embed.description = "**Reminder registered:**"
        represent = expected_date.strftime(self.preset)
        embed.set_footer(text=represent)

        now = datetime.utcnow().replace(tzinfo=None)
        when = expected_date.astimezone(timezone.utc).replace(tzinfo=None)
        difference = (when - now).total_seconds()

        if difference < 0:
            msg = "The timestamp has already passed"
            await interaction.response.send_message(msg, ephemeral=True)
            return

        arguments = [
            interaction.user.id,
            interaction.channel.id,
            now.timestamp(),
            when.timestamp(),
            raw_reason or "No reason"
        ]

        reminder = Timer.temporary(self.bot, *arguments)

        if difference < 60:
            await interaction.response.send_message(embed=embed)
            await asyncio.sleep(difference)
            await reminder.send()

        else:
            query = 'INSERT INTO reminder ' \
                    '(author_id, channel_id, creation, expiration, reason)' \
                    ' VALUES ($1, $2, $3, $4, $5)'
            cursor = await self.bot.db.execute(query, arguments)
            reminder.id = cursor.lastrowid
            await self.bot.db.commit()

            if not self.current_reminder:
                self.current_reminder = reminder
                self._lock.set()

            else:
                if reminder.expiration < self.current_reminder.expiration:
                    self.restart(reminder)

            logger.debug(f"reminder {reminder.id}: registered")
            embed.description = f"{embed.description[:-3]} (ID {reminder.id}):**"
            await interaction.response.send_message(embed=embed)

    async def get_timezone(self, user_id):
        query = "SELECT timezone from userdata WHERE id = $1"
        record = await self.bot.fetchone(query, user_id)
        return record['timezone'] if record else None

    @app_commands.command(name="remind",
                          description="remind yourself after given time in the channel the command was invoked in")
    async def remind(self, interaction):
        modal = ReminderModal(self.save_reminder)
        await interaction.response.send_modal(modal)

    reminder = app_commands.Group(name="reminder", description="Aschenkuttel Reminder")

    @reminder.command(name="list", description="shows all your active reminders")
    async def list(self, interaction):
        query = 'SELECT * FROM reminder WHERE author_id = $1 ORDER BY expiration'
        data = await self.bot.fetch(query, interaction.user.id)

        if not data:
            msg = "You don't have any active reminders."
            await interaction.response.send_message(msg, ephemeral=True)

        else:
            reminders = []
            for row in data[:10]:
                timer = Timer(self.bot, row)
                date = timer.expiration.strftime(self.preset)
                reminders.append(f"`ID {timer.id}` | **{date}**")

            title = f"Your active reminders ({len(data)} in total):"
            embed = discord.Embed(description="\n".join(reminders), title=title)
            await interaction.response.send_message(embed=embed)

    @reminder.command(name="remove", description="removes reminder with given id")
    @app_commands.describe(reminder_id="ID of the reminder you want to delete")
    @app_commands.rename(reminder_id="id")
    async def remove(self, interaction, reminder_id: int):
        query = 'DELETE FROM reminder WHERE author_id = $1 AND id = $2'
        response = await self.bot.fetchone(query, interaction.user.id, reminder_id)
        await self.bot.db.commit()

        if response == "DELETE 0":
            msg = "You don't have an active reminder with that ID."
            await interaction.response.send_message(msg, ephemeral=True)
            return

        if self.current_reminder and self.current_reminder.id == reminder_id:
            self.restart()

        await interaction.response.send_message("Your reminder has been deleted.", ephemeral=True)

    @reminder.command(name="clear", description="deletes all active reminders")
    async def clear(self, interaction):
        query = 'SELECT count(*) FROM reminder WHERE author_id = $1'
        data = await self.bot.fetchone(query, interaction.user.id)
        total = data[0]

        if total == 0:
            msg = "You don't have any active reminders"
            await interaction.response.send_message(msg, ephemeral=True)
            return

        confirm = await interaction.prompt(f'Are you sure you want to delete {utils.Plural(total):reminder}?')
        if not confirm:
            await interaction.followup.send("Aborted", ephemeral=True)
            return

        query = 'DELETE FROM reminder WHERE author_id = $1'
        await self.bot.execute(query, interaction.user.id)

        if self.current_reminder and self.current_reminder.author_id == interaction.user.id:
            self.restart()

        msg = f'Successfully deleted {utils.Plural(total):reminder}.'
        await interaction.followup.send(msg, ephemeral=True)

    timezone = app_commands.Group(name='timezone',
                                  description='Commands related to managing or retrieving timezone info.')

    @timezone.command(name='set', description='Sets your timezone.')
    @app_commands.describe(tz='The timezone to change to.')
    async def timezone_set(self, interaction, tz: TimeZone):
        await self.bot.execute(
            'INSERT OR REPLACE INTO userdata (id, timezone) VALUES ($1, $2)',
            interaction.user.id, tz.key
        )

        msg = f'Your timezone has been set to {tz}.'
        await interaction.response.send_message(msg, ephemeral=True, delete_after=10)

    @timezone.command(name='info', description='Retrieves info about a timezone.')
    @app_commands.describe(tz='The timezone to get info about.')
    async def timezone_info(self, interaction, tz: TimeZone):
        embed = discord.Embed(title=tz.key, colour=discord.Colour.blurple())
        dt = discord.utils.utcnow().astimezone(dateutil.tz.gettz(tz.key))
        time = dt.strftime('%m.%d.%Y %I:%M %p')
        embed.add_field(name='Current Time', value=time)

        offset = dt.utcoffset()
        if offset is not None:
            minutes, _ = divmod(int(offset.total_seconds()), 60)
            hours, minutes = divmod(minutes, 60)
            embed.add_field(name='UTC Offset', value=f'{hours:+03d}:{minutes:02d}')

        await interaction.response.send_message(embed=embed)

    @timezone.command(name='get', description='Gets the timezone of a user.')
    @app_commands.describe(member='The member to get the timezone of. Defaults to yourself.')
    async def timezone_get(self, interaction, member: discord.Member = None):
        user = member or interaction.user
        self_query = user.id == interaction.user.id
        tz = await self.get_timezone(user.id)

        if tz is None:
            msg = f'{user} has not set their timezone.'
            await interaction.response.send_message(msg)
            return

        now = datetime.now(dateutil.tz.gettz(tz))
        time = now.strftime('%d.%m.%Y %I:%M %p')

        if not self_query:
            msg = f'Your timezone is `{tz}` and the current time is `{time}`.'
            await interaction.response.send_message(msg)
        else:
            msg = f'The current time for {user.mention} is `{time}`.'
            no_ping = discord.AllowedMentions(users=False)
            await interaction.response.send_message(msg, allowed_mentions=no_ping)

    @timezone.command(name='clear', description='Clears your timezone.')
    async def timezone_clear(self, interaction):
        await self.bot.execute('DELETE FROM userdata WHERE id = $1', interaction.user.id)
        await interaction.response.send_message('Your timezone has been cleared.', ephemeral=True)


async def setup(bot):
    await bot.add_cog(Reminder(bot))
