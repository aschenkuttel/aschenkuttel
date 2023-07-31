from discord.ext import commands
from discord import app_commands
import traceback
import logging
import utils
import sys

logger = logging.getLogger('self')


class Listen(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.tree.on_error = self.on_app_command_error

    @staticmethod
    async def on_app_command_error(interaction, error):
        error = getattr(error, 'original', error)
        msg = None

        if isinstance(error, app_commands.MissingPermissions):
            msg = "Sorry but you don't have the permissions for that"

        elif isinstance(error, utils.SummonerNotFound):
            msg = "There's no summoner with the given name"

        elif isinstance(error, utils.NoSummonerLinked):
            msg = "The member has no connected summoner"

        elif isinstance(error, utils.NoRiotResponse):
            msg = "The Riot API is currently not responding"

        elif isinstance(error, utils.NoBirthday):
            msg = "There's no birthday linked to this account"

        if msg:
            embed = utils.embed(msg, error=True)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            logger.debug(f"expected error with {interaction.data}: {error}")

        else:
            embed = utils.embed("something went wrong", error=True)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            logger.debug(f"error with {interaction.data}: {error}")
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        # till message intents are required
        error = getattr(error, 'original', error)
        msg = None

        if isinstance(error, commands.CommandNotFound):
            count = ctx.invoked_with.count(ctx.prefix)
            if len(ctx.invoked_with) == count:
                return

            msg = "please use slash commands instead: `/example`"

        if msg:
            await ctx.send(embed=utils.embed(msg, error=True))
            logger.debug(f"expected error with {ctx.message.content}: {error}")

        else:
            logger.debug(f"error with {ctx.message.content}: {error}")
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)


async def setup(bot):
    await bot.add_cog(Listen(bot))


