from discord.ext import commands
import random



class Sarah(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.quotes = self.load_quotes()
        self.answers = self.bot.msg['askSarah']

    def load_quotes(self):
        with open(f"{self.bot.path}/data/quotes.txt", 'r') as file:
            return file.readlines()

    @commands.command(name="asksarah")
    async def ask_sarah(self, ctx, question=None):
        if not question:
            await ctx.send("Du musst mich auch etwas fragen...")

        else:
            answer = random.choice(self.answers)
            await ctx.send(answer)

    @commands.command(name="quote")
    async def quote_(self, ctx):
        await ctx.send(random.choice(self.quotes))

    @commands.command(name="help")
    async def help_me_(self, ctx):
        await ctx.send("There is no help, we're all lost...")


def setup(bot):
    bot.add_cog(Sarah(bot))
