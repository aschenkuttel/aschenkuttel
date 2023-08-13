from data.credentials import TOKEN, UNSPLASH_KEY, default_prefix
from discord.ext import commands
import aiosqlite
import discord
import aiohttp
import asyncio
import logging
import utils
import os

default_cogs = [
    "admin",  # done
    "birthday",  # done
    "config",  # done
    "league",  # done
    "misc",  # done
    "netflix",  # done
    "events",
    "remind",  # done
    "self",  # done
    "sound",  # done
    "star"  # done
]


class Aschenkuttel(commands.Bot):
    def __init__(self, *args, **kwargs):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        kwargs['intents'] = intents
        super().__init__(*args, **kwargs)
        self.path = os.path.dirname(__file__)
        self.default_prefix = default_prefix

        self.config = utils.ConfigHandler(self)
        self._lock = None
        self.session = None
        self.db = None

        self.activity = discord.Activity(type=2, name="Atilla Hildemann")
        self.add_check(self.global_check)
        self.help_command = None
        self.setup_loggers()

    async def setup_hook(self):
        self._lock = asyncio.Event()
        self.session = aiohttp.ClientSession()
        await self.setup_cogs()

        db_path = f"{self.path}/data/database.db"
        self.db = await aiosqlite.connect(db_path)
        await self.setup_tables()

        self._lock.set()
        print("Once upon a time...")

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

        movies = 'CREATE TABLE IF NOT EXISTS movies' \
                 '(id BIGINT PRIMARY KEY, title TEXT,' \
                 'image_url TEXT, description TEXT, ' \
                 'rating FLOAT, year SMALLINT, ' \
                 'runtime INT, seconds INT)'

        summoner = 'CREATE TABLE IF NOT EXISTS summoner' \
                   '(user_id BIGINT PRIMARY KEY, id TEXT,' \
                   'account_id TEXT, puuid TEXT, name TEXT,' \
                   'icon_id INT, level SMALLINT, wins SMALLINT,' \
                   'losses SMALLINT, tier TEXT, rank TEXT, ' \
                   'lp SMALLINT, last_match_id BIGINT)'

        birthday = 'CREATE TABLE IF NOT EXISTS birthday' \
                   '(guild_id BIGINT, user_id BIGINT, date TIMESTAMP, ' \
                   'PRIMARY KEY (guild_id, user_id))'

        parties = 'CREATE TABLE IF NOT EXISTS watch_parties' \
                  '(id INTEGER PRIMARY KEY AUTOINCREMENT, ' \
                  'name TEXT, guild_id BIGINT, channel_id BIGINT, ' \
                  'author_id BIGINT, participants JSON, ' \
                  'next_date TIMESTAMP, recurring INT, ' \
                  'UNIQUE (guild_id, author_id))'

        # parties = 'DROP TABLE watch_parties'

        query_pool = (reminder, starboard, movies,
                      summoner, birthday, parties)

        for query in query_pool:
            await self.execute(query)

    async def wait_until_unlocked(self):
        return await self._lock.wait()

    def is_set(self):
        return self._lock.is_set()

    async def execute(self, query, *args):
        await self.db.execute(query, args)
        await self.db.commit()

    async def fetch(self, query, *args):
        cursor = await self.db.execute(query, args)
        return await cursor.fetchall()

    async def fetchone(self, query, *args):
        cursor = await self.db.execute(query, args)
        return await cursor.fetchone()

    async def fetch_image(self, query, file=True):
        url = "https://api.unsplash.com/photos/random"
        payload = {'query': query, 'orientation': "landscape"}
        auth = {'Authorization': UNSPLASH_KEY}
        async with self.session.get(url, params=payload, headers=auth) as r:
            data = await r.json()

            try:
                small_url = data['urls']['small']

                if file is True:
                    async with self.session.get(small_url) as resp:
                        return await resp.read()
                else:
                    return small_url

            except KeyError:
                return

    @staticmethod
    async def global_check(ctx):
        if ctx.invoked_with in ("connect", "disconnect"):
            return True

        elif ctx.guild is None:
            raise commands.NoPrivateMessage()

        else:
            return True

    def setup_loggers(self):
        for name in ('discord', 'self'):
            logger = logging.getLogger(name)
            logger.setLevel(logging.DEBUG)
            handler = logging.FileHandler(filename=f'{self.path}/data/{name}.log',
                                          encoding='utf-8', mode='w')
            format_str = '%(asctime)s:%(levelname)s:%(name)s: %(message)s'
            handler.setFormatter(logging.Formatter(format_str))
            logger.addHandler(handler)

    async def setup_cogs(self):
        for file in os.listdir(f"{self.path}/cogs"):
            if file.endswith(".py"):
                try:
                    filename = file.split(".")[0]
                    cog_path = f"cogs.{filename}"
                    await self.load_extension(cog_path)
                except (commands.ExtensionNotFound, discord.ext.commands.NoEntryPointError):
                    print(f"module {file} not found")


self = Aschenkuttel(command_prefix=".", tree_cls=utils.AshTree)
self.run(TOKEN)
