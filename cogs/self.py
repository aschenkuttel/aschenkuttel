from discord.ext import commands


class Owner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        if await self.bot.is_owner(ctx.author):
            return True
        raise commands.NotOwner()

    @commands.command(name="reload")
    async def reload_(self, ctx, file):
        cog = f"extensions.{file}"
        self.bot.reload_extension(cog)
        msg = f"{file} wurde erfolgreich neugeladen"
        await ctx.send(msg)


def setup(bot):
    bot.add_cog(Owner(bot))
