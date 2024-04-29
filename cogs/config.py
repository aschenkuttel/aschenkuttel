from discord.ext import commands
from discord import app_commands
import discord
import utils


class Config(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = self.bot.config

    set = app_commands.Group(name="set", description="sets one of your guilds config")

    @set.command(name="lobby", description="sets the lobby of your guild from which the summon command moves members")
    @app_commands.describe(channel="the channel you want to set as lobby")
    @app_commands.checks.has_permissions(administrator=True)
    async def lobby_(self, interaction, channel: discord.VoiceChannel):
        current_id = self.config.get('lobby', interaction.guild.id)

        if current_id == channel.id:
            msg = "This channel is already the lobby"
            await interaction.response.send_message(embed=utils.embed(msg, error=True), ephemeral=True)

        else:
            self.config.store('lobby', channel.id, interaction.guild.id)
            msg = f"{channel.mention} is now the lobby"
            await interaction.response.send_message(embed=utils.embed(msg))

    @set.command(name="bdayboard", description="sets the bdayboard of your guild in which birthdays will be announced")
    @app_commands.describe(channel="the channel you want to set as lobby")
    @app_commands.checks.has_permissions(administrator=True)
    async def bdayboard_(self, interaction, channel: discord.TextChannel):
        channel_id = self.config.get('bdayboard', interaction.guild.id)

        if channel_id == channel.id:
            msg = "This channel is already the bdayboard"
            await interaction.response.send_message(embed=utils.embed(msg, error=True), ephemeral=True)

        else:
            self.config.store('bdayboard', channel.id, interaction.guild.id)
            msg = f"{channel.mention} is now the bdayboard"
            await interaction.response.send_message(embed=utils.embed(msg))

    @set.command(name="starboard",
                 description="sets the starboard of your guild in which starred messages will be posted")
    @app_commands.describe(channel="the channel you want to set as the starboard")
    @app_commands.checks.has_permissions(administrator=True)
    async def starboard_(self, interaction, channel: discord.TextChannel):
        channel_id = self.config.get('starboard', interaction.guild.id)

        if channel_id == channel.id:
            msg = "This channel is already the starboard"
            await interaction.response.send_message(embed=utils.embed(msg, error=True), ephemeral=True)

        else:
            self.config.store('starboard', channel.id, interaction.guild.id)
            msg = f"{channel.mention} is now the starboard"
            await interaction.response.send_message(embed=utils.embed(msg))

    @set.command(name="starcount",
                 description="sets the guilds limit on which messages will be embedded in the guilds starboard")
    @app_commands.describe(amount="the amount of stars needed to pin a message")
    @app_commands.checks.has_permissions(administrator=True)
    async def starcount_(self, interaction, amount: int):
        self.config.store('starcount', amount, interaction.guild.id)
        msg = f"The messages now need {amount} stars to be pinned"
        await interaction.response.send_message(embed=utils.embed(msg))

    @set.command(name="league",
                 description="sets the leagueboard of your guild in which summoners get roasted and boasted")
    @app_commands.describe(channel="the channel you want to set as the league channel")
    @app_commands.checks.has_permissions(administrator=True)
    async def league_(self, interaction, channel: discord.TextChannel):
        channel_id = self.config.get('league', interaction.guild.id)

        if channel_id == channel.id:
            msg = "This channel is already the league channel"
            await interaction.response.send_message(embed=utils.embed(msg, error=True), ephemeral=True)

        else:
            self.config.store('league', channel.id, interaction.guild.id)
            msg = f"{channel.mention} is now the league channel"
            await interaction.response.send_message(embed=utils.embed(msg))

    @app_commands.command(name="remove", description="removes one of your guilds config")
    @app_commands.describe(target=f"one of the following options")
    @app_commands.choices(target=utils.config_options)
    @app_commands.checks.has_permissions(administrator=True)
    async def remove(self, interaction, target: app_commands.Choice[str]):
        response = self.config.remove(target.value, interaction.guild.id)

        if response is None:
            msg = f"There's no current {target.name}"
            await interaction.response.send_message(embed=utils.embed(msg, error=True), ephemeral=True)

        else:
            msg = f"The {target.name} got removed"
            await interaction.response.send_message(embed=utils.embed(msg))

    @app_commands.command(name="enable", description="enables features like: join/leave sounds or random guild icon")
    @app_commands.choices(feature=utils.config_features)
    @app_commands.checks.has_permissions(administrator=True)
    async def enable(self, interaction, feature: app_commands.Choice[str]):
        await self.toggle(interaction, feature, True)

    @app_commands.command(name="disable", description="disables features like: join/leave sounds or random guild icon")
    @app_commands.choices(feature=utils.config_features)
    @app_commands.checks.has_permissions(administrator=True)
    async def disable(self, interaction, feature: app_commands.Choice[str]):
        await self.toggle(interaction, feature, False)

    async def toggle(self, interaction, feature, state):
        current = self.config.get(feature.value, interaction.guild.id)

        if state is current:
            cur_action = "active" if current else "inactive"
            msg = f"The {feature.name} is already `{cur_action}`"
            await interaction.response.send_message(embed=utils.embed(msg, error=True), ephemeral=True)

        else:
            self.config.store(feature.value, not current, interaction.guild.id)
            new_action = "active" if not current else "inactive"
            msg = f"The {feature.name} is now {new_action}"
            await interaction.response.send_message(embed=utils.embed(msg))

            if feature.value == "sound" and interaction.guild.voice_client:
                await interaction.guild.voice_client.disconnect()

    hide = app_commands.Group(name="hide", description="ignores given channels for the join sounds")

    @hide.command(name="toggle", description="toggles given channel for the join sounds")
    @app_commands.describe(channel="the channel you want to either hide or make visible again")
    @app_commands.checks.has_permissions(administrator=True)
    async def toggle_(self, interaction, channel: discord.VoiceChannel):
        hidden_channel = self.config.get('hidden', interaction.guild.id)
        action = "hidden now..."

        if hidden_channel is None:
            self.config.store('hidden', [channel.id], interaction.guild.id)

        elif channel.id in hidden_channel:
            hidden_channel.remove(channel.id)
            self.config.save()
            action = "visible again..."

        else:
            hidden_channel.append(channel.id)
            self.config.save()

        msg = f"The channel `{channel.name}` is {action}"
        await interaction.response.send_message(embed=utils.embed(msg))

    @hide.command(name="list", description="shows all hidden channels")
    @app_commands.checks.has_permissions(administrator=True)
    async def list_(self, interaction):
        hidden_ids = self.config.get('hidden', interaction.guild.id)

        if not hidden_ids:
            msg = "All channels are currently visible..."
            await interaction.response.send_message(embed=utils.embed(msg))
            return

        description = []
        for channel_id in hidden_ids.copy():
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                hidden_ids.remove(channel_id)

            else:
                description.append(f"**#{channel.name}**")

        embed = utils.embed("\n".join(description))
        await interaction.response.send_message(embed=embed)

    @hide.command(name="clear", description="clears all hidden channels")
    @app_commands.checks.has_permissions(administrator=True)
    async def clear_(self, interaction):
        hidden_ids = self.config.get('hidden', interaction.guild.id)

        if hidden_ids:
            hidden_ids.clear()
            self.config.save()

        msg = "All channels are visible again..."
        await interaction.response.send_message(embed=utils.embed(msg))


async def setup(bot):
    await bot.add_cog(Config(bot))
