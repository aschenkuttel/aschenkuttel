from discord.ext import commands
import utils


class Config(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.german = {
            'lobby': "Die",
            'prefix': "Der",
            'query': ["Das", "Schlagwort"],
            'starboard': "Das",
        }
        self.features = {'sound': "Join Sounds",
                         'icon': "Random Server Icons"}
        self.config = self.bot.config

    async def cog_check(self, ctx):
        if ctx.author.guild_permissions.administrator:
            return True
        else:
            raise commands.MissingPermissions(['administrator'])

    @commands.group(name="set", invoke_without_command=True)
    async def set(self, ctx):
        msg = f"`{ctx.prefix}set <{', '.join(self.german)}>`"
        await ctx.send(embed=utils.embed(msg))

    @set.command(name="lobby")
    async def lobby_(self, ctx, channel_id: int):
        current_id = self.config.get('lobby', ctx.guild.id)
        channel = self.bot.get_channel(channel_id)
        fail = True

        if current_id == channel_id:
            msg = "Dieser Channel ist bereits die aktuelle Lobby"

        elif channel in ctx.guild.voice_channels:
            self.config.store('lobby', ctx.guild.id, channel_id)
            msg = f"{channel.mention} ist nun die aktuelle Lobby"
            fail = False

        else:
            msg = "Die angegebene ID ist ungültig"

        await ctx.send(embed=utils.embed(msg, error=fail))

    @set.command(name="prefix")
    async def prefix_(self, ctx, new_prefix):
        prefix = self.config.get('prefix', ctx.guild.id)

        if prefix == new_prefix:
            msg = "Dieser Prefix ist bereits eingespeichert"
            await ctx.send(embed=utils.embed(msg, error=True))

        else:
            self.config.store('prefix', new_prefix, ctx.guild.id)
            msg = f"`{new_prefix}` ist nun der neue Prefix"
            await ctx.send(embed=utils.embed(msg))

    @set.command(name="query")
    async def icon_(self, ctx, query):
        current_query = self.config.get('query', ctx.guild.id)

        if query == current_query:
            msg = "Dieses Schlagwort ist bereits eingespeichert"
            await ctx.send(embed=utils.embed(msg, error=True))

        else:
            self.config.store('query', query, ctx.guild.id)
            msg = f"`{query}` ist nun das neue Schlagwort"
            await ctx.send(embed=utils.embed(msg))

    @set.command(name="starboard")
    async def starboard_(self, ctx):
        channel_id = self.config.get('starboard', ctx.guild.id)

        if channel_id == ctx.channel.id:
            msg = "Dieser Channel ist bereits das aktuelle Starboard"
            await ctx.send(embed=utils.embed(msg, error=True))

        else:
            self.config.store('starboard', ctx.channel.id, ctx.guild.id)
            msg = f"{ctx.channel.mention} ist nun das Starboard"
            await ctx.send(embed=utils.embed(msg))

    @set.command(name="starcount")
    async def starcount_(self, ctx, amount: int):
        self.config.store('starcount', amount, ctx.guild.id)
        msg = f"Eine Nachricht muss nun {amount} Sterne erreichen um angepinnt zu werden"
        await ctx.send(embed=utils.embed(msg))

    @commands.group(invoke_without_command=True, name="remove")
    async def remove_(self, ctx, target):
        pronoun = self.german.get(target)

        if pronoun is None:
            msg = f"`{ctx.prefix}remove <{', '.join(self.german)}>`"
            await ctx.send(embed=utils.embed(msg))

        else:
            response = self.config.remove(target, ctx.guild.id)
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

    @commands.group(name="enable", aliases=["disable"], invoke_without_command=True)
    async def enable(self, ctx, feature):
        action = ctx.invoked_with.lower()
        name = self.features.get(feature)

        if name is None:
            msg = f"`.{action} <{', '.join(self.features)}>`"
            await ctx.send(embed=utils.embed(msg, error=True))

        else:
            current = self.config.get(feature, ctx.guild.id)
            if (action == 'enable') is current:
                cur = "aktiv" if current else "inaktiv"
                msg = f"Die {name} sind bereits `{cur}`"
                await ctx.send(embed=utils.embed(msg, error=True))

            else:
                self.config.store(feature, not current, ctx.guild.id)
                new_action = "aktiv" if not current else "inaktiv"
                msg = f"Die {name} sind nun {new_action}"
                await ctx.send(embed=utils.embed(msg))

    @enable.command(name="logging")
    async def logging_(self, ctx):
        action = ctx.invoked_with.lower()
        current = self.config.get('logging', ctx.author.id)

        if (action == 'enable') is current:
            name = "aktiviert" if current is True else "deaktiviert"
            msg = f"Das Archivieren deiner Nachrichten ist bereits {name}..."
            await ctx.send(embed=utils.embed(msg))

        else:
            self.config.store('logging', not current, ctx.author.id)
            name = "aktiviert" if not current is True else "deaktiviert"
            msg = f"Das Archivieren deiner Nachrichten ist nun {name}"
            await ctx.send(embed=utils.embed(msg))

    @commands.group(name="hide", invoke_without_command=True)
    async def hide(self, ctx, channel_id: int):
        channel = self.bot.get_channel(channel_id)

        if channel is None:
            msg = "Die angegebene ID ist ungültig"
            await ctx.send(embed=utils.embed(msg, error=True))
            return

        action = "versteckt..."
        hidden_channel = self.config.get('hidden', ctx.guild.id)

        if hidden_channel is None:
            self.config.store('hidden', [channel.id], ctx.guild.id)

        elif channel.id in hidden_channel:
            hidden_channel.remove(channel.id)
            self.config.save()
            action = "wieder sichtbar..."

        else:
            hidden_channel.append(channel.id)
            self.config.save()

        msg = f"Der Channel `{channel.name}` ist nun {action}"
        await ctx.send(embed=utils.embed(msg))

    @hide.command(name="list")
    async def list_(self, ctx):
        hidden_ids = self.config.get('hidden', ctx.guild.id)
        if not hidden_ids:
            msg = "Es sind momentan alle Channel sichtbar"
            await ctx.send(embed=utils.embed(msg))
            return

        description = []
        for channel_id in hidden_ids.copy():
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                hidden_ids.remove(channel_id)

            else:
                description.append(f"**#{channel.name}**")

        embed = utils.embed("\n".join(description))
        await ctx.send(embed=embed)

    @hide.command(name="clear")
    async def clear_(self, ctx):
        hidden_ids = self.config.get('hidden', ctx.guild.id)

        if hidden_ids:
            hidden_ids.clear()
            self.config.save()

        msg = "Die Liste wurde erfolgreich zurückgesetzt..."
        await ctx.send(embed=utils.embed(msg))


def setup(bot):
    bot.add_cog(Config(bot))
