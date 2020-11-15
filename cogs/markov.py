from discord.ext import commands
import random
import json


class Markov(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.path = f"{self.bot.path}/data/markov.json"

    @staticmethod
    def make_pairs(messages, amount):
        for content in messages:
            corpus = content.split()
            for i in range(len(corpus) - 1):
                try:
                    key = [corpus[i + n] for n in range(amount)]
                    value = [corpus[i + n + amount] for n in range(amount)]
                    yield " ".join(key), " ".join(value)
                except IndexError:
                    continue

    @commands.command(name="try")
    async def try_(self, ctx):
        cache = json.load(open(self.path, encoding='utf-8'))

        if str(ctx.author.id) not in cache:
            return

        user_messages = cache[str(ctx.author.id)].copy()
        del cache

        pairs = self.make_pairs(user_messages, amount=1)

        words = {}
        for word_1, word_2 in pairs:
            if word_1 in words.keys():
                words[word_1].append(word_2)
            else:
                words[word_1] = [word_2]

        first = random.choice(list(words))
        while first.islower():
            first = random.choice(list(words))

        chain = [first]

        counter = 0
        while counter < 10:
            try:
                word = random.choice(words[chain[-1]])
                chain.append(word)
                counter += 1

                if word.endswith(('.', '!', '?')):
                    break

            except KeyError:
                counter += 1
                continue

        await ctx.send(" ".join(chain))


def setup(bot):
    bot.add_cog(Markov(bot))
