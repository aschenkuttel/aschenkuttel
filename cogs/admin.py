from discord.ext import commands


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        if ctx.author.guild_permissions.administrator:
            return True
        raise commands.MissingPermissions(['administrator'])

    @commands.command(name="purge")
    async def purge_(self, ctx, amount: int = 10):
        await ctx.channel.purge(limit=amount + 1)


def setup(bot):
    bot.add_cog(Admin(bot))
