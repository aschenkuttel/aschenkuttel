from typing import Literal, Optional
from discord.ext import commands
import discord
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
            await self.bot.reload_extension(f"cogs.{file}")
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
            cursor = await self.bot.db.execute(query)
            result = await cursor.fetchall()
            await self.bot.db.commit()
            await ctx.send(result)

        except Exception as error:
            await ctx.send(error)

    @commands.command()
    @commands.guild_only()
    @commands.is_owner()
    async def sync(self, ctx, guilds: commands.Greedy[discord.Object],
                   spec: Optional[Literal["~", "*", "^"]] = None) -> None:
        if not guilds:
            if spec == "~":
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            elif spec == "*":
                ctx.bot.tree.copy_global_to(guild=ctx.guild)
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            elif spec == "^":
                ctx.bot.tree.clear_commands(guild=ctx.guild)
                await ctx.bot.tree.sync(guild=ctx.guild)
                synced = []
            else:
                synced = await ctx.bot.tree.sync()

            await ctx.send(
                f"Synced {len(synced)} commands {'globally' if spec is None else 'to the current guild.'}"
            )
            return

        ret = 0
        for guild in guilds:
            try:
                await ctx.bot.tree.sync(guild=guild)
            except discord.HTTPException:
                pass
            else:
                ret += 1

        await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")


async def setup(bot):
    await bot.add_cog(Owner(bot))
