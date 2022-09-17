from discord.ext import commands
from utils import DefaultDict
import discord


class Starboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.star_cache = DefaultDict(list)
        self.bot.loop.create_task(self.star_setup())

    async def star_setup(self):
        await self.bot.wait_until_unlocked()
        query = 'SELECT guild_id, message_id FROM starboard ORDER BY guild_id'
        cache = await self.bot.fetch(query)

        for guild_id, message_id in cache:
            pack = self.star_cache[guild_id]
            pack.append(message_id)

    async def star_message(self, message, channel):
        embed = discord.Embed(description=message.content)
        embed.colour = discord.Color.gold()

        arguments = [message.guild.id, message.channel.id,
                     message.id, message.author.id,
                     message.created_at, message.content, None]

        if message.embeds:
            data = message.embeds[0]
            if data.type == 'image':
                embed.set_image(url=data.url)
                arguments[6] = data.url

        if message.attachments:
            file = message.attachments[0]
            arguments[6] = file.url

            if file.url.lower().endswith(('png', 'jpeg', 'jpg', 'gif', 'webp')):
                embed.set_image(url=file.url)

            else:
                embed.add_field(name='Attachment', inline=False,
                                value=f'[{file.filename}]({file.url})')

        embed.add_field(name='Original', inline=False,
                        value=f'[Jump Url]({message.jump_url})')

        embed.set_author(name=message.author.display_name,
                         icon_url=message.author.avatar_url_as(format='png'))

        embed.timestamp = message.created_at
        await channel.send(embed=embed)

        self.star_cache[message.guild.id].append(message.id)
        query = 'INSERT INTO starboard (guild_id, channel_id,' \
                'message_id, author_id, date, content, attachment) ' \
                'VALUES ($1, $2, $3, $4, $5, $6, $7)'
        await self.bot.execute(query, *arguments)
        
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return

        if payload.emoji.name == "⭐":
            stars = self.star_cache[guild.id]

            if payload.message_id in stars:
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


async def setup(bot):
    await bot.add_cog(Starboard(bot))
