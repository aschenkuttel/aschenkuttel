from discord.ext import commands
import discord
import utils


class Config(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = bot.config
        self.names = {
            'lobby': "Lobby",
            'live': "Liveticker"
        }

    async def cog_check(self, ctx):
        if ctx.author.guild_permissions.administrator:
            return True
        else:
            raise commands.MissingPermissions(['administrator'])

    @commands.group(invoke_without_command=True, name="set")
    async def set(self, ctx):
        pass

    @set.command(name="starboard")
    async def starboard_(self, ctx):
        self.bot.config.save_item(ctx.guild.id, 'starboard', ctx.channel.id)
        if ctx.guild.id not in self._starred:
            self._starred[ctx.guild.id] = {}
            json.dump(self._starred, open(f"{self.bot.path}/data/starred.json", 'w'))
        msg = f"{ctx.channel.mention} ist nun das Starboard"
        await ctx.send(msg)

    @set.command(name="lobby")
    async def lobby_(self, ctx, channel_id: int):
        current_id = self.data.get_item(ctx.guild.id, 'lobby')
        channel = self.bot.get_channel(channel_id)

        if current_id == channel_id:
            msg = "Dieser Channel ist bereits die aktuelle Lobby"

        elif channel in ctx.guild.voice_channels:
            self.data.save_item(ctx.guild.id, 'lobby', channel_id)
            msg = f"{channel.mention} ist nun die aktuelle Lobby"

        else:
            msg = "Die angegebene ID ist ungültig"

        await ctx.send(msg)

    @set.command(name="liveticker")
    async def live_(self, ctx, url=None):
        live = self.data.get_item(ctx.guild.id, 'live')
        if live and live['id'] == ctx.channel.id:
            if url:
                msg = "Die neue Liveticker URL wurde übernommen"
                live['url'] = url
                self.data.save()
            else:
                msg = "Dieser Channel ist bereits der aktuelle Liveticker"
                await ctx.send(embed=utils.embed(msg, error=True))

        else:
            if url:
                live = {'id': ctx.channel.id, 'url': url}
            else:
                live['id'] = ctx.channel.id

            self.data.save_item(ctx.guild.id, 'live', live)
            msg = f"{ctx.channel.mention} ist nun der aktuelle Liveticker"

        await ctx.send(embed=utils.embed(msg))

    @commands.group(invoke_without_command=True, name="remove")
    async def remove(self, ctx):
        pass

    @remove.command(name="lobby", aliases=["live"])
    async def lobby_(self, ctx):
        target = ctx.invoked_with.lower()
        response = self.data.remove_item(ctx.guild.id, target)
        name = self.names.get(target)

        if response is None:
            german = "keine" if target == "lobby" else "kein"
            msg = f"Es ist {german} {name} eingetragen"

        else:
            german = "Die" if target == "lobby" else "Der"
            msg = f"{german} {name} wurde entfernt"

        await ctx.send(embed=utils.embed(msg, error=not response))


def setup(bot):
    bot.add_cog(Config(bot))
