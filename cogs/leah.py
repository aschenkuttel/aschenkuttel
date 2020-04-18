from discord.ext import commands


class Leah(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        if ctx.author.guild_permissions.administrator:
            return True
        raise commands.MissingPermissions(['administrator'])

    @commands.group(invoke_without_command=True, name="move")
    async def move_(self, ctx, channel_id: int):
        self.bot.config.save_item(ctx.guild.id, 'move', channel_id)
        msg = "Der neue Move-Channel wurde registriert"
        await ctx.send(msg)

    @commands.command(name="liveticker")
    async def liveticker_(self, ctx, channel_id: int = None):
        if channel_id:
            self.bot.config.save_item(ctx.guild.id, 'liveticker', channel_id)
        else:
            self.bot.config.remove_item(ctx.guild.id, 'liveticker')
        action = "gespeichert" if channel_id else "entfernt"
        msg = f"Der Liveticker-Channel wurde erfolgreich {action}."
        await ctx.send(msg)

    @commands.command(name="purge")
    async def purge_(self, ctx, amount: int = 10):
        await ctx.channel.purge(limit=amount)


def setup(bot):
    bot.add_cog(Leah(bot))
