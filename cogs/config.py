from discord.ext import commands
import utils


class Config(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = bot.config
        self.german = {
            'liveticker': "Der",
            'lobby': "Die",
            'prefix': "Der",
            'query': ["Das", "Schlagwort"],
            'starboard': "Das",
        }
        self.features = {'sounds': "Join Sounds",
                         'random': "Random Server Icons"}

    async def cog_check(self, ctx):
        if ctx.author.guild_permissions.administrator:
            return True
        else:
            raise commands.MissingPermissions(['administrator'])

    @commands.group(name="set", invoke_without_command=True)
    async def set(self, ctx):
        msg = f"`{ctx.prefix}set <liveticker, lobby, prefix, random, starboard>`"
        await ctx.send(embed=utils.embed(msg))

    @set.command(name="liveticker")
    async def liveticker_(self, ctx, url=None):
        live = self.data.get(ctx.guild.id, 'live')
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
            elif live:
                live['id'] = ctx.channel.id
            else:
                live = {'id': ctx.channel.id, 'url': ""}

            self.data.store(ctx.guild.id, 'live', live)
            msg = f"{ctx.channel.mention} ist nun der aktuelle Liveticker"

        await ctx.send(embed=utils.embed(msg))

    @set.command(name="lobby")
    async def lobby_(self, ctx, channel_id: int):
        current_id = self.data.get(ctx.guild.id, 'lobby')
        channel = self.bot.get_channel(channel_id)
        fail = True

        if current_id == channel_id:
            msg = "Dieser Channel ist bereits die aktuelle Lobby"

        elif channel in ctx.guild.voice_channels:
            self.data.store(ctx.guild.id, 'lobby', channel_id)
            msg = f"{channel.mention} ist nun die aktuelle Lobby"
            fail = False

        else:
            msg = "Die angegebene ID ist ungültig"

        await ctx.send(embed=utils.embed(msg, error=fail))

    @set.command(name="prefix")
    async def prefix_(self, ctx, new_prefix):
        prefix = self.data.get(ctx.guild.id, 'prefix')
        if prefix and prefix == new_prefix:
            msg = "Dieser Prefix ist bereits eingespeichert"
            await ctx.send(embed=utils.embed(msg, error=True))

        else:
            self.data.store(ctx.guild.id, 'prefix', new_prefix)
            msg = f"`{new_prefix}` ist nun der neue Prefix"
            await ctx.send(embed=utils.embed(msg))

    @set.command(name="icon")
    async def icon_(self, ctx, icon):
        pass

    @set.command(name="starboard")
    async def starboard_(self, ctx):
        channel_id = self.data.get(ctx.guild.id, 'starboard')
        if channel_id and channel_id == ctx.channel.id:
            msg = "Dieser Channel ist bereits das aktuelle Starboard"
            await ctx.send(embed=utils.embed(msg, error=True))

        else:
            self.data.store(ctx.guild.id, 'starboard', ctx.channel.id)
            msg = f"{ctx.channel.mention} ist nun das Starboard"
            await ctx.send(embed=utils.embed(msg))

    @commands.group(invoke_without_command=True, name="remove")
    async def remove(self, ctx, target):
        if target not in self.german:
            msg = f"`{ctx.prefix}remove <{', '.join(self.german)}>`"
            await ctx.send(embed=utils.embed(msg))

        else:
            response = self.data.remove(ctx.guild.id, target)
            pronoun = self.german.get(target)

            if isinstance(pronoun, list):
                pronoun, name = pronoun

            else:
                name = target.capitalize()

            if response is None:
                pronoun = "keine" if target == "lobby" else "kein"
                base = "Es ist {} {} eingetragen"

            else:
                base = "{} {} wurde entfernt"

            msg = base.format(pronoun, name)
            await ctx.send(embed=utils.embed(msg, error=not response))

    @commands.group(name="enable", aliases=["disable"])
    async def enable_(self, ctx, feature):
        action = ctx.invoked_with.lower()
        name = self.features.get(feature)
        if name is None:
            msg = f"`.{action} <{', '.join(self.features)}>`"
            await ctx.send(embed=utils.embed(msg, error=True))

        else:
            current = self.data.get(ctx.guild.id, feature)

            if action == "enable" and current or action == "disable" and not current:
                cur = "aktiv" if current else "inaktiv"
                msg = f"Die {name} sind bereits `{cur}`"
                await ctx.send(embed=utils.embed(msg, error=True))

            else:
                self.data.store(ctx.guild.id, feature, not current)
                new_action = "aktiv" if not current else "inaktiv"
                msg = f"Die {name} sind nun {new_action}"
                await ctx.send(embed=utils.embed(msg))


def setup(bot):
    bot.add_cog(Config(bot))
