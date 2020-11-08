from data.secret import TOKEN, cogs, default_prefix
from discord.ext import commands
import discord
import aiohttp
import logging
import utils
import json
import os

logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='data/discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)


class Aschenkuttel(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(command_prefix=self.prefix, *args, **kwargs)
        self.path = os.path.dirname(__file__)
        self.add_check(self.global_check)
        self.config = utils.ConfigHandler(self)
        self.msg = json.load(open(f"{self.path}/data/msg.json"))
        self.activity = discord.Activity(type=2, name="Billie Eilish")
        self.remove_command("help")
        self.session = None
        self.cog_setup()

    async def on_ready(self):
        if not self.session:
            self.session = aiohttp.ClientSession(loop=self.loop)

        print("Es war einmal vor langer Zeit...")

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
            return default_prefix

        prefix = self.config.get(message.guild.id, 'prefix')
        return prefix or default_prefix

    def cog_setup(self):
        for file in cogs:
            try:
                cog_path = f"cogs.{file}"
                self.load_extension(cog_path)
            except commands.ExtensionNotFound:
                print(f"module {file} not found")


self = Aschenkuttel(case_insensitive=True)
self.run(TOKEN)
