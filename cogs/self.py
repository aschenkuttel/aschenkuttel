from discord.ext import commands
import logging


logger = logging.getLogger('self')


class Owner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.hidden = True

    async def cog_check(self, ctx):
        if await self.bot.is_owner(ctx.author):
            return True
        else:
            raise commands.NotOwner()

    @commands.command(name="reload")
    async def reload_(self, ctx, file):
        try:
            self.bot.reload_extension(f"cogs.{file}")
            msg = f"{file}.py has been reloaded"
            logger.debug(msg)

        except commands.ExtensionNotLoaded:
            msg = f"`{file}.py` not found"

        except commands.ExtensionFailed:
            msg = f"`{file}.py` could'nt be reloaded"

        await ctx.send(msg)

    @commands.command(name="sql")
    async def sql_(self, ctx, *, query):
        try:
            await self.bot.db.execute(query)
            await self.bot.db.commit()
            await ctx.send("Done")

        except Exception as error:
            await ctx.send(error)


def setup(bot):
    bot.add_cog(Owner(bot))
