from discord.ext import commands
from discord import app_commands
from datetime import datetime
from discord.ui import TextInput, Modal
import dateparser
import asyncio
import discord
import logging

logger = logging.getLogger('dsbot')


class Timer:
    def __init__(self, bot, data):
        self.bot = bot

        if len(data) == 6:
            data = list(data)
            self.id = data.pop(0)

        else:
            self.id = 0

        self.author_id = data[0]
        self.channel_id = data[1]
        self.creation = datetime.fromtimestamp(data[2])
        self.expiration = datetime.fromtimestamp(data[3])
        self.reason = data[4]

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
            logger.debug(f"reminder {self.id}: successfull")

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
        await self.callback(interaction, self.time_input.value, self.reason_input.value)

    async def on_error(self, interaction, error):
        pass


class Reminder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.type = 2
        self.char_limit = 200
        self.settings = {'languages': ['de', 'en'], 'settings': {'PREFER_DATES_FROM': "future"}}
        self.preset = "%d.%m.%Y | %H:%M:%S Uhr"
        self._task = self.bot.loop.create_task(self.remind_loop())
        self._lock = asyncio.Event(loop=bot.loop)
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
        await self.bot.wait_until_unlocked()
        while not self.bot.is_closed():

            if not self.current_reminder:
                query = 'SELECT * FROM reminder ORDER BY expiration'
                data = await self.bot.fetchone(query)

                if data is not None:
                    self.current_reminder = Timer(self.bot, data)

            if self.current_reminder:
                logger.debug(f"reminder {self.current_reminder.id}: sleeping")

                difference = (self.current_reminder.expiration - datetime.now())
                seconds = difference.total_seconds()
                await asyncio.sleep(seconds)

                query = "DELETE FROM reminder WHERE id = $1"
                await self.bot.execute(query, self.current_reminder.id)

                if seconds > -60:
                    logger.debug(f"reminder {self.current_reminder.id}: send message")
                    await self.current_reminder.send()

                self.current_reminder = None
                self._lock.clear()

            else:
                await self._lock.wait()

    async def save_reminder(self, interaction, raw_time, raw_reason):
        if raw_reason:
            reason = raw_reason.strip()[:self.char_limit]
        else:
            reason = "No reason"

        try:
            expected_date = dateparser.parse(raw_time, **self.settings)
        except Exception as error:
            logger.debug(error)
            expected_date = None

        if expected_date is None:
            msg = "No valid time format"
            await interaction.response.send_message(msg, ephemeral=True)
            return

        current_date = datetime.now()
        difference = (expected_date - current_date).total_seconds()

        embed = discord.Embed(colour=discord.Color.green())
        embed.description = "**Reminder registered:**"
        represent = expected_date.strftime(self.preset)
        embed.set_footer(text=represent)

        if difference < 0:
            msg = "The timestamp has already passed"
            await interaction.response.send_message(msg, ephemeral=True)
            return

        current_stamp = current_date.timestamp()
        expected_stamp = expected_date.timestamp()
        arguments = [interaction.user.id, interaction.channel.id, current_stamp, expected_stamp, reason]
        reminder = Timer(self.bot, arguments)

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
            msg = "You don't have any active reminders"
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
            msg = "You don't have an active reminder with that ID"
            await interaction.response.send_message(msg, ephemeral=True)
            return

        if self.current_reminder and self.current_reminder.id == reminder_id:
            self.restart()

        await interaction.response.send_message("Your reminder has been deleted")

    @reminder.command(name="clear", description="deletes all active reminders")
    async def clear(self, interaction):
        query = 'DELETE FROM reminder WHERE author_id = $1 RETURNING id'
        deleted_rows = await self.bot.fetch(query, interaction.user.id)
        await self.bot.db.commit()

        if not deleted_rows:
            msg = "You don't have any active reminders"
            await interaction.response.send_message(msg, ephemeral=True)
            return

        if self.current_reminder:
            old_ids = [rec['id'] for rec in deleted_rows]
            if self.current_reminder.id in old_ids:
                self.restart()

        msg = f"All your active reminders have been deleted ({len(deleted_rows)})"
        await interaction.response.send_message(msg)


async def setup(bot):
    await bot.add_cog(Reminder(bot))
