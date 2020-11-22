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

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        error = getattr(error, 'original', error)
        msg = None

        if isinstance(error, commands.CommandNotFound):
            count = ctx.invoked_with.count(ctx.prefix)
            if len(ctx.invoked_with) == count:
                return

            msg = f"legit no clue what `{ctx.invoked_with}` should be"

        elif isinstance(error, commands.NoPrivateMessage):
            msg = "sorry I have a boyfriend..."

        elif isinstance(error, commands.NotOwner):
            msg = "sorry but you're not allowed to use this"

        elif isinstance(error, commands.MissingPermissions):
            msg = "sorry but you don't have the permissions for that"

        elif isinstance(error, commands.ChannelNotFound):
            msg = "The ID you passed is invalid"

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
