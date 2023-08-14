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

        elif isinstance(error, utils.all_errors):
            msg = str(error)

        if msg is not None:
            logger.debug(f"expected error with {interaction.data}: {error}")
            embed = utils.embed(msg, error=True)

            if interaction.response.is_done():
                await interaction.followup.send(embed=embed)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)

        else:
            logger.error(f"error with {interaction.data}: {error}")
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
            embed = utils.embed("something went wrong", error=True)

            if interaction.response.is_done():
                await interaction.followup.send(embed=embed)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)

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


