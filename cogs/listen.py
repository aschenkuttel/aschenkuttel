from discord.ext import commands
import traceback
import utils
import sys


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

            msg = f"Der Command `{ctx.invoked_with}` existiert nicht"

        elif isinstance(error, commands.NoPrivateMessage):
            msg = "Sorry, ich hab einen Freund..."

        elif isinstance(error, commands.NotOwner):
            msg = "Diesen Command darfst du leider nicht benutzen :/"

        elif isinstance(error, commands.BadArgument):
            msg = str(error)

        if msg:
            await ctx.send(embed=utils.embed(msg, error=True))

        else:
            print(f"Command Message: {ctx.message.content}")
            print("Command Error:")
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)


def setup(bot):
    bot.add_cog(Listen(bot))
