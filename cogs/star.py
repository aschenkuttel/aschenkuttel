from discord.ext import commands
import discord
import json


class Starboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.path = f"{self.bot.path}/data/starred.json"
        self._starred = {}
        self.star_setup()

    def star_setup(self):
        cache = json.load(open(self.path))
        data = {int(key): value for key, value in cache.items()}
        self._starred = data

    async def star_message(self, message, channel):
        starred = self._starred.get(message.guild.id)

        if starred is None:
            self._starred[message.guild.id] = {}
            starred = self._starred[message.guild.id]

        elif str(message.id) in starred:
            return

        embed = discord.Embed(description=message.content)
        embed.colour = discord.Color.gold()
        if message.embeds:
            data = message.embeds[0]
            if data.type == 'image':
                embed.set_image(url=data.url)

        if message.attachments:
            file = message.attachments[0]
            if file.url.lower().endswith(('png', 'jpeg', 'jpg', 'gif', 'webp')):
                embed.set_image(url=file.url)

            else:
                embed.add_field(name='Attachment', value=f'[{file.filename}]({file.url})',
                                inline=False)

        embed.add_field(name='Original', value=f'[Klick mich!]({message.jump_url})', inline=False)
        embed.set_author(name=message.author.display_name,
                         icon_url=message.author.avatar_url_as(format='png'))
        embed.timestamp = message.created_at
        msg = await channel.send(embed=embed)

        starred[str(message.id)] = msg.id
        json.dump(self._starred, open(self.path, 'w'))

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return

        if payload.emoji.name == "⭐":
            if payload.message_id in self._starred:
                return

            for m in self.bot.cached_messages:
                if payload.message_id == m.id:
                    message = m
                    break

            else:
                channel = self.bot.get_channel(payload.channel_id)
                message = await channel.fetch_message(payload.message_id)

            channel_id = self.bot.config.get('starboard', guild.id)
            channel = self.bot.get_channel(channel_id)

            if channel is None or channel == message.channel:
                return

            limit = self.bot.config.get('starcount', guild.id, default=5)

            for reaction in message.reactions:
                if reaction.emoji == "⭐" and reaction.count >= limit:
                    await self.star_message(message, channel)


def setup(bot):
    bot.add_cog(Starboard(bot))
