from discord.ext import commands
from discord import app_commands
from discord.ui import select, View, UserSelect, TextInput
import asyncio
import logging


import discord

logger = logging.getLogger('self')


class WatchParty(commands.GroupCog, name="watchparty"):
    def __init__(self, bot):
        self.bot = bot
        self.parties = {}
        self.type = 2
        # self._task = self.bot.loop.create_task(self.party_loop())
        self._lock = asyncio.Event(loop=bot.loop)
        self.current_reminder = None

    # async def party_loop(self):
    #     await self.bot.wait_until_unlocked()
    #     while not self.bot.is_closed():
    #
    #         if not self.current_reminder:
    #             query = 'SELECT * FROM reminder ORDER BY expiration'
    #             data = await self.bot.fetchone(query)
    #
    #             if data is not None:
    #                 self.current_reminder = Timer(self.bot, data)
    #
    #         if self.current_reminder:
    #             logger.debug(f"reminder {self.current_reminder.id}: sleeping")
    #
    #             difference = (self.current_reminder.expiration - datetime.now())
    #             seconds = difference.total_seconds()
    #             await asyncio.sleep(seconds)
    #
    #             query = "DELETE FROM reminder WHERE id = $1"
    #             await self.bot.execute(query, self.current_reminder.id)
    #
    #             if seconds > -60:
    #                 logger.debug(f"reminder {self.current_reminder.id}: send message")
    #                 await self.current_reminder.send()
    #
    #             self.current_reminder = None
    #             self._lock.clear()
    #
    #         else:
    #             await self._lock.wait()

    # @commands.group(name="watchparty")
    # async def watchparty(self, ctx):
    #     pass

    # @watchparty.command(name="create")
    # async def _create(self, ctx, name, date):
    #     pass
    #
    # @watchparty.command(name="join")
    # async def _join(self, ctx, name):
    #     pass
    #
    # @watchparty.command(name="leave")
    # async def _leave(self, ctx, name):
    #     pass

    @app_commands.command(name="list")
    async def _list(self, interaction):
        parties = await self.bot.fetch("SELECT * FROM watchparty WHERE guild_id = $1", interaction.guild.id)

        if not parties:
            await interaction.response.send_message("There are no watch parties in this server!")
        else:
            embed = discord.Embed(title="Watch Parties", description="Here are all the watch parties in this server!")

            for party in parties:
                embed.add_field(name=party["name"], value=party["date"], inline=False)

            await interaction.response.send_message(embed=embed)

    @app_commands.command(name="create")
    async def create(self, interaction):




        await interaction.response.send_message("create")

    @app_commands.command(name="invite")
    async def _invite(self, interaction):
        view = View()

        member_select = UserSelect(
            placeholder="Select all the members you want to invite!",
            min_values=1,
            max_values=20
        )

        view.add_item(member_select)

        await interaction.response.send_message(view=view)

async def setup(bot):
    await bot.add_cog(WatchParty(bot))
