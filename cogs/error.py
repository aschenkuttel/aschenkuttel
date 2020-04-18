from discord.ext import commands
import utils


class Listen(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, utils.GuildOnly):
            msg = "Sorry Bruder, ich helf dir nur auf Servern"
            await ctx.send(embed=utils.error_embed(msg))

        elif isinstance(error, commands.CommandNotFound):
            count = ctx.invoked_with.count(ctx.prefix)
            if len(ctx.invoked_with) == count:
                return

            msg = "Der Command existiert nicht"
            await ctx.send(embed=utils.error_embed(msg))

        else:
            print(error)


def setup(bot):
    bot.add_cog(Listen(bot))
