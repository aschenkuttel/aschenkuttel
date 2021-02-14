from discord.ext import commands
import discord
import utils


class Config(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.keywords = [
            'lobby',
            'prefix',
            'query',
            'starboard',
            'starcount',
            'league'
        ]
        self.features = [
            'sound',
            'icon'
        ]
        self.config = self.bot.config

    async def cog_check(self, ctx):
        if ctx.author.guild_permissions.administrator:
            return True
        else:
            raise commands.MissingPermissions(['administrator'])

    @commands.group(name="set", invoke_without_command=True)
    async def set(self, ctx):
        msg = f"`{ctx.prefix}set <{', '.join(self.keywords)}>`"
        await ctx.send(embed=utils.embed(msg))

    @set.command(name="lobby")
    async def lobby_(self, ctx, channel: discord.VoiceChannel):
        """sets your guilds lobby channel from which
        the summon command move its members"""
        current_id = self.config.get('lobby', ctx.guild.id)
        fail = True

        if current_id == channel.id:
            msg = "This channel is already the lobby"

        else:
            self.config.store('lobby', channel.id, ctx.guild.id)
            msg = f"{channel.mention} is now the lobby"
            fail = False

        await ctx.send(embed=utils.embed(msg, error=fail))

    @set.command(name="prefix")
    async def prefix_(self, ctx, new_prefix):
        """sets the guilds prefix of the bot"""
        prefix = self.config.get('prefix', ctx.guild.id)

        if prefix == new_prefix:
            msg = "This prefix is already the current one"
            await ctx.send(embed=utils.embed(msg, error=True))

        else:
            self.config.store('prefix', new_prefix, ctx.guild.id)
            msg = f"`{new_prefix}` is now the new prefix"
            await ctx.send(embed=utils.embed(msg))

    @set.command(name="query")
    async def icon_(self, ctx, query):
        """sets the icon query of your guild"""
        current_query = self.config.get('query', ctx.guild.id)

        if query == current_query:
            msg = "This keyword is already the query"
            await ctx.send(embed=utils.embed(msg, error=True))

        else:
            self.config.store('query', query, ctx.guild.id)
            msg = f"`{query}` is now the active query"
            await ctx.send(embed=utils.embed(msg))

    @set.command(name="starboard")
    async def starboard_(self, ctx):
        """sets the starboard of your guild in
        which starred messages will be posted"""
        channel_id = self.config.get('starboard', ctx.guild.id)

        if channel_id == ctx.channel.id:
            msg = "This channel is already the starboard"
            await ctx.send(embed=utils.embed(msg, error=True))

        else:
            self.config.store('starboard', ctx.channel.id, ctx.guild.id)
            msg = f"{ctx.channel.mention} is now the starboard"
            await ctx.send(embed=utils.embed(msg))

    @set.command(name="starcount")
    async def starcount_(self, ctx, amount: int):
        """sets the guilds limit on which messages
        will be embedded in the guilds starboard"""
        self.config.store('starcount', amount, ctx.guild.id)
        msg = f"The messages now need {amount} stars to be pinned"
        await ctx.send(embed=utils.embed(msg))

    @set.command(name="league")
    async def league_(self, ctx):
        """sets the league channel of your guild in
        which summoners get roasted and boasted"""
        channel_id = self.config.get('league', ctx.guild.id)

        if channel_id == ctx.channel.id:
            msg = "This channel is already the league channel"
            await ctx.send(embed=utils.embed(msg, error=True))

        else:
            self.config.store('league', ctx.channel.id, ctx.guild.id)
            msg = f"{ctx.channel.mention} is now the league channel"
            await ctx.send(embed=utils.embed(msg))

    @commands.group(invoke_without_command=True, name="remove")
    async def remove_(self, ctx, target):
        """removes on of your guilds config"""
        if target not in self.keywords:
            msg = f"`{ctx.prefix}remove <{', '.join(self.keywords)}>`"
            await ctx.send(embed=utils.embed(msg))

        else:
            response = self.config.remove(target, ctx.guild.id)

            if response is None:
                msg = f"There's no current {target}"

            else:
                msg = f"The {target} got removed"

            await ctx.send(embed=utils.embed(msg, error=not response))

    @commands.group(name="enable", aliases=["disable"], invoke_without_command=True)
    async def enable(self, ctx, feature):
        """enables or disables features like:
        join/leave sounds or random guild icon"""
        action = ctx.invoked_with.lower()

        if feature not in self.features:
            msg = f"`.{action} <{', '.join(self.features)}>`"
            await ctx.send(embed=utils.embed(msg, error=True))

        else:
            current = self.config.get(feature, ctx.guild.id)
            if (action == 'enable') is current:
                cur_action = "active" if current else "inactive"
                msg = f"The {feature} feature is already `{cur_action}`"
                await ctx.send(embed=utils.embed(msg, error=True))

            else:
                self.config.store(feature, not current, ctx.guild.id)
                new_action = "active" if not current else "inactive"
                msg = f"The {feature} feature is now {new_action}"
                await ctx.send(embed=utils.embed(msg))

                if feature == "sound" and ctx.guild.voice_client:
                    await ctx.guild.voice_client.disconnect()

    @commands.group(name="hide", invoke_without_command=True)
    async def hide(self, ctx, channel: discord.VoiceChannel):
        """hides given channel for the join/leave sound feature"""
        hidden_channel = self.config.get('hidden', ctx.guild.id)
        action = "hidden now..."

        if hidden_channel is None:
            self.config.store('hidden', [channel.id], ctx.guild.id)

        elif channel.id in hidden_channel:
            hidden_channel.remove(channel.id)
            self.config.save()
            action = "visible again..."

        else:
            hidden_channel.append(channel.id)
            self.config.save()

        msg = f"The channel `{channel.name}` is {action}"
        await ctx.send(embed=utils.embed(msg))

    @hide.command(name="list")
    async def list_(self, ctx):
        """shows all hidden channels"""
        hidden_ids = self.config.get('hidden', ctx.guild.id)

        if not hidden_ids:
            msg = "All channels are currently visible..."
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
        """clears all hidden channels"""
        hidden_ids = self.config.get('hidden', ctx.guild.id)

        if hidden_ids:
            hidden_ids.clear()
            self.config.save()

        msg = "All channels are visible again..."
        await ctx.send(embed=utils.embed(msg))


def setup(bot):
    bot.add_cog(Config(bot))
