from discord.ext import commands, tasks
from utils import DefaultDict
import traceback
import logging
import utils
import sys

logger = logging.getLogger('self')


class Listen(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.markov_cache = DefaultDict(list)
        self.push_messages.start()

    def cog_unload(self):
        self.push_messages.cancel()

    @tasks.loop(minutes=1)
    async def push_messages(self):
        await self.bot.wait_until_unlocked()
        query = 'INSERT INTO logging (guild_id, channel_id,' \
                'message_id, author_id, date, content)' \
                'VALUES ($1, $2, $3, $4, $5, $6)'

        counter = 0
        for user_id, messages in self.markov_cache.items():
            arguments = []

            for msg in messages:
                batch = [msg.guild.id, msg.channel.id, msg.id,
                         msg.author.id, msg.created_at, msg.content]
                arguments.append(batch)

            await self.bot.db.executemany(query, arguments)
            counter += len(messages)

        await self.bot.db.commit()
        logger.debug(f'{counter} messages added to archive')

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot is True:
            return

        elif message.guild is None:
            return

        prefix = self.bot.config.get('prefix', message.guild.id)
        if prefix is None:
            prefix = self.bot.default_prefix

        if message.content.startswith(prefix):
            return

        # log = self.bot.config.get('logging', message.author.id)
        # if log is False:
        #     return

        words = message.content.split()
        if len(words) < 2:
            return

        pack = self.markov_cache[message.author.id]
        pack.append(message)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        error = getattr(error, 'original', error)
        msg = None

        if isinstance(error, commands.CommandNotFound):
            count = ctx.invoked_with.count(ctx.prefix)
            if len(ctx.invoked_with) == count:
                return

            msg = f"Der Command `{ctx.invoked_with}` existiert nicht"

        elif isinstance(error, commands.NoPrivateMessage):
            msg = "Sorry, ich hab einen Freund..."

        elif isinstance(error, commands.NotOwner):
            msg = "Diesen Command darfst du leider nicht benutzen :/"

        elif isinstance(error, commands.BadArgument):
            msg = str(error)

        if msg:
            await ctx.send(embed=utils.embed(msg, error=True))
            logger.debug(f"expected error with {ctx.message.content}: {error}")

        else:
            logger.debug(f"error with {ctx.message.content}: {error}")
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)


def setup(bot):
    bot.add_cog(Listen(bot))
