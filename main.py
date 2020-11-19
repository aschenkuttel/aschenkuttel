from data.credentials import TOKEN, default_prefix
from discord.ext import commands
import aiosqlite
import discord
import aiohttp
import asyncio
import logging
import utils
import os

default_cogs = [
    "admin",
    "config",
    "icon",
    "listen",
    "remind",
    "self",
    "sound",
    "star",
    "utils"
]


class Aschenkuttel(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(command_prefix=self.prefix, *args, **kwargs)
        self.path = os.path.dirname(__file__)
        self.default_prefix = default_prefix

        self.config = utils.ConfigHandler(self)
        self._lock = asyncio.Event()
        self.session = None
        self.db = None

        self.activity = discord.Activity(type=2, name="Atilla Hildemann")
        self.add_check(self.global_check)
        self.remove_command("help")

        self.setup_loggers()
        self.setup_cogs()

    async def on_ready(self):
        if self.session is None:
            self.session = aiohttp.ClientSession(loop=self.loop)

        if self.db is None:
            db_path = f"{self.path}/data/database.db"
            self.db = await aiosqlite.connect(db_path)
            await self.setup_tables()

        self._lock.set()
        print("Es war einmal vor langer Zeit...")

    async def setup_tables(self):
        reminder = 'CREATE TABLE IF NOT EXISTS reminder' \
                   '(id INTEGER PRIMARY KEY AUTOINCREMENT,' \
                   'author_id BIGINT, channel_id BIGINT,' \
                   'creation BIGINT, expiration BIGINT,' \
                   'reason TEXT)'

        starboard = 'CREATE TABLE IF NOT EXISTS starboard' \
                    '(guild_id BIGINT, channel_id BIGINT,' \
                    'message_id BIGINT, author_id BIGINT,' \
                    'date TIMESTAMP, content TEXT, attachment TEXT)'

        message_logs = 'CREATE TABLE IF NOT EXISTS logging' \
                       '(guild_id BIGINT, channel_id BIGINT,' \
                       'message_id BIGINT, author_id BIGINT,' \
                       'date TIMESTAMP, content TEXT)'

        query_pool = (reminder, starboard, message_logs)
        for query in query_pool:
            await self.execute(query)

    async def wait_until_unlocked(self):
        return await self._lock.wait()

    async def execute(self, query, *args):
        await self.db.execute(query, args)
        await self.db.commit()

    async def fetch(self, query, *args):
        cursor = await self.db.execute(query, args)
        return await cursor.fetchall()

    async def fetchrow(self, query, *args):
        cursor = await self.db.execute(query, args)
        return await cursor.fetchone()

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

    def setup_loggers(self):
        for name in ('discord', 'self'):
            logger = logging.getLogger(name)
            logger.setLevel(logging.DEBUG)
            handler = logging.FileHandler(filename=f'{self.path}/data/{name}.log',
                                          encoding='utf-8', mode='w')
            format_str = '%(asctime)s:%(levelname)s:%(name)s: %(message)s'
            handler.setFormatter(logging.Formatter(format_str))
            logger.addHandler(handler)

    def setup_cogs(self):
        for file in default_cogs:
            try:
                cog_path = f"cogs.{file}"
                self.load_extension(cog_path)
            except commands.ExtensionNotFound:
                print(f"module {file} not found")


intents = discord.Intents.default()
intents.members = True

self = Aschenkuttel(intents=intents, case_insensitive=True)
self.run(TOKEN)
