from discord.ext import commands, tasks
from bs4 import BeautifulSoup
import dateutil.parser
import collections
import discord
import asyncio
import utils
import json
import re


class LiveTicker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.live_loop.start()
        self.fail = collections.Counter()

    @staticmethod
    def clean(raw_html):
        net = re.compile('<.*?>')
        subbed = re.sub(net, '', raw_html)
        result = re.sub(r'\n\s*\n', '\n', subbed)
        return " ".join(result.split())

    def bad_response(self, guild_id):
        self.fail[guild_id] += 1

        if self.fail[guild_id] == 10:
            self.bot.config.remove(guild_id, 'live')
            self.fail[guild_id] = 0

    @tasks.loop(minutes=1)
    async def live_loop(self):
        for guild in self.bot.guilds:
            data = self.bot.config.get(guild.id, 'live')
            if data is None:
                continue

            channel = self.bot.get_channel(data['id'])
            if channel is None:
                continue

            try:
                cache = await self.bot.session.get(data['url'])
                soup = BeautifulSoup(await cache.text(), 'html.parser')
                json_data = soup.find('script', {'data-qa': "StructuredData"})

                if json_data is None:
                    self.bad_response(guild.id)
                    continue

                archive = json.loads(json_data.text)
                last_post = archive['liveBlogUpdate'][0]

            except Exception as error:
                self.bad_response(guild.id)
                print(error)
                continue

            date = dateutil.parser.parse(last_post['datePublished'])
            if data.get('last') == date.timestamp():
                continue

            desc = self.clean(last_post['articleBody'])
            if not desc:
                continue

            else:
                data['last'] = date.timestamp()
                self.bot.config.save()

            if len(desc) > 2040:
                continue

            title, url = last_post['headline'], last_post['url']
            embed = discord.Embed(title=title, description=desc, url=url)
            embed.timestamp = date

            await utils.silencer(channel.send(embed=embed))

    @live_loop.before_loop
    async def before_live(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(5)


def setup(bot):
    bot.add_cog(LiveTicker(bot))
