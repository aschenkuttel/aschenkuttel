from discord.ext import commands
from datetime import datetime
import dateparser
import asyncio
import discord
import logging


logger = logging.getLogger('self')


class Timer:
    def __init__(self, bot, data):
        self.bot = bot

        if len(data) == 6:
            data = list(data)
            self.id = data.pop(0)

        else:
            self.id = None

        self.author_id = data[0]
        self.channel_id = data[1]
        self.creation = datetime.fromtimestamp(data[2])
        self.expiration = datetime.fromtimestamp(data[3])
        self.reason = data[4]

    async def send(self):
        embed = discord.Embed(colour=discord.Color.dark_gold())
        embed.description = self.reason

        channel = self.bot.get_channel(self.channel_id)
        author = self.bot.get_user(self.author_id)

        if author is None:
            return

        if channel is None:
            channel = author

        try:
            msg = f"**Erinnerung:** {author.mention}"
            await channel.send(msg, embed=embed)
            logger.debug(f"reminder {self.id}: successfull")

        except (discord.Forbidden, discord.HTTPException):
            logger.debug(f"reminder {self.id}: not allowed")
            return


class Reminder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.type = 2
        self.char_limit = 200
        self.preset = "%d/%m/%Y | %H:%M:%S Uhr"
        self.set = {'PREFER_DATES_FROM': 'future'}
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
                data = await self.bot.fetchrow(query)

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

    @commands.command(name="now")
    async def now_(self, ctx):
        now = datetime.now()
        represent = now.strftime(self.preset)
        await ctx.send(f"`{represent}`")

    @commands.group(name="remind", invoke_without_command=True)
    async def remind(self, ctx, *, argument: commands.clean_content):
        args = argument.split("\n")
        time = args.pop(0)
        if args:
            reason = "\n".join(args).strip()[:self.char_limit]
        else:
            reason = "Kein Grund angegeben"

        expected_date = dateparser.parse(time, settings=self.set)
        if expected_date is None:
            msg = "Es konnte kein gültiges Zeitformat erkannt werden"
            await ctx.send(msg)
            return

        current_date = datetime.now()
        difference = (expected_date - current_date).total_seconds()

        embed = discord.Embed(colour=discord.Color.green())
        embed.description = "**Erinnerung registriert:**"
        represent = expected_date.strftime(self.preset)
        embed.set_footer(text=represent)

        if difference < 0:
            msg = "Der Zeitpunkt ist bereits vergangen"
            await ctx.send(msg)
            return

        current_stamp = current_date.timestamp()
        expected_stamp = expected_date.timestamp()
        arguments = [ctx.author.id, ctx.channel.id, current_stamp, expected_stamp, reason]
        reminder = Timer(self.bot, arguments)

        if difference < 60:
            await ctx.send(embed=embed)
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
            await ctx.send(embed=embed)

    @remind.command(name="list")
    async def list_(self, ctx):
        query = 'SELECT * FROM reminder WHERE author_id = $1 ORDER BY expiration'
        data = await self.bot.fetch(query, ctx.author.id)

        if not data:
            msg = "Du hast keine aktiven Reminder"
            await ctx.send(msg)

        else:
            reminders = []
            for row in data[:10]:
                timer = Timer(self.bot, row)
                date = timer.expiration.strftime(self.preset)
                reminders.append(f"`ID {timer.id}` | **{date}**")

            title = f"Deine Reminder ({len(data)} Insgesamt):"
            embed = discord.Embed(description="\n".join(reminders), title=title)
            await ctx.send(embed=embed)

    @remind.command(name="remove")
    async def remove_(self, ctx, reminder_id: int):
        query = 'DELETE FROM reminder WHERE author_id = $1 AND id = $2'

        response = await self.bot.fetchrow(query, ctx.author.id, reminder_id)
        await self.bot.db.commit()

        if response == "DELETE 0":
            msg = "Du hast keinen Reminder mit der angegebenen ID"
            return await ctx.send(msg)

        if self.current_reminder and self.current_reminder.id == reminder_id:
            self.restart()

        await ctx.send("Der Reminder wurde gelöscht")

    @remind.command(name="clear")
    async def clear_(self, ctx):
        query = 'DELETE FROM reminder WHERE author_id = $1 RETURNING id'

        deleted_rows = await self.bot.fetch(query, ctx.author.id)
        await self.bot.db.commit()

        if not deleted_rows:
            msg = "Du hast keine aktiven Reminder"
            await ctx.send(msg)
            return

        if self.current_reminder:
            old_ids = [rec['id'] for rec in deleted_rows]
            if self.current_reminder.id in old_ids:
                self.restart()

        msg = f"Alle deine Reminder wurden gelöscht ({len(deleted_rows)})"
        await ctx.send(msg)


def setup(bot):
    bot.add_cog(Reminder(bot))
