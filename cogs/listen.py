from discord.ext import commands, tasks
import traceback
import utils
import json
import sys


class Listen(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.save_markov.start()

    def cog_unload(self):
        print("call")
        self.save_markov.cancel()

    @tasks.loop(minutes=5)
    async def save_markov(self):
        path = f"{self.bot.path}/data/markov.json"
        str_cache = json.load(open(path, encoding='utf-8'))
        cache = {int(k): v for k, v in str_cache.items()}

        for user_id, messages in self.bot.markov_cache.items():
            if user_id in cache:
                cache[user_id].extend(messages)
            else:
                cache[user_id] = messages

        json.dump(cache, open(path, mode='w', encoding='utf-8'))
        self.bot.markov_cache.clear()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot is True:
            return

        prefix = self.bot.config.get('prefix', message.guild.id)
        if prefix is None:
            prefix = self.bot.default_prefix

        if message.content.startswith(prefix):
            return

        # log = self.bot.config.get('logging', message.author.id)
        # if log is False:
        #     return

        if len(message.content.split()) < 2:
            return
        
        try:
            cache = self.bot.markov_cache[message.author.id]
        except KeyError:
            cache = self.bot.markov_cache[message.author.id] = []

        cache.append(message.content)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        error = getattr(error, 'original', error)
        msg = None

        if isinstance(error, commands.CommandNotFound):
            count = ctx.invoked_with.count(ctx.prefix)
            if len(ctx.invoked_with) == count:
                return

            msg = f"Der Command `{ctx.invoked_with}` existiert nicht"

        elif isinstance(error, commands.NoPrivateMessage):
            msg = "Sorry, ich hab einen Freund..."

        elif isinstance(error, commands.NotOwner):
            msg = "Diesen Command darfst du leider nicht benutzen :/"

        elif isinstance(error, commands.BadArgument):
            msg = str(error)

        if msg:
            await ctx.send(embed=utils.embed(msg, error=True))

        else:
            print(f"Command Message: {ctx.message.content}")
            print("Command Error:")
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)


def setup(bot):
    bot.add_cog(Listen(bot))
