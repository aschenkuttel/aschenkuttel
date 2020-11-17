import asyncio

from data.secret import TOKEN, cogs, default_prefix
from discord.ext import commands
import aiosqlite
import discord
import aiohttp
import logging
import utils
import os

path = os.path.dirname(__file__)
logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename=f'{path}/data/discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

intents = discord.Intents.default()
intents.members = True


class Aschenkuttel(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(command_prefix=self.prefix, *args, **kwargs)
        self.path = path
        self.add_check(self.global_check)
        self.config = utils.ConfigHandler(self)
        self.activity = discord.Activity(type=2, name="Atilla Hildemann")
        self.default_prefix = default_prefix
        self._lock = asyncio.Event()
        self.remove_command("help")
        self.markov_cache = {}
        self.session = None
        self.db = None
        self.cog_setup()

    async def on_ready(self):
        if self.session is None:
            self.session = aiohttp.ClientSession(loop=self.loop)

        if self.db is None:
            db_path = f"{self.path}/data/database.db"
            self.db = await aiosqlite.connect(db_path)
            await self.setup()

        self._lock.set()
        print("Es war einmal vor langer Zeit...")

    async def setup(self):
        query = 'CREATE TABLE IF NOT EXISTS reminder' \
                '(id INTEGER PRIMARY KEY AUTOINCREMENT,' \
                ' author_id BIGINT, channel_id BIGINT,' \
                ' creation BIGINT, expiration BIGINT,' \
                ' reason TEXT)'
        await self.db.execute(query)
        await self.db.commit()

    async def wait_until_unlocked(self):
        return await self._lock.wait()

    @staticmethod
    async def global_check(ctx):
        if ctx.invoked_with in ("connect", "disconnect"):
            return True

        elif ctx.guild is None:
            raise commands.NoPrivateMessage()

        else:
            return True

    async def prefix(self, _, message):
        if message.guild is None:
            return self.default_prefix

        prefix = self.config.get('prefix', message.guild.id)
        return prefix or self.default_prefix

    def cog_setup(self):
        for file in cogs:
            try:
                cog_path = f"cogs.{file}"
                self.load_extension(cog_path)
            except commands.ExtensionNotFound:
                print(f"module {file} not found")


self = Aschenkuttel(intents=intents, case_insensitive=True)
self.run(TOKEN)
