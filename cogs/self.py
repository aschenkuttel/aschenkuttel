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
        try:
            self.bot.reload_extension(f"cogs.{file}")
            msg = f"`{file}.py` wurde erfolgreich neugeladen"

        except commands.ExtensionNotLoaded:
            msg = f"`{file}.py` konnte ich leider nicht finden"
        except commands.ExtensionFailed:
            msg = f"`{file}.py` konnte nicht geladen werden"

        await ctx.send(msg)


def setup(bot):
    bot.add_cog(Owner(bot))
