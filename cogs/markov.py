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

            parts = []
            for c in content:
                if c.isalnum():
                    parts.append(c)
                elif '.' in c or " " in c:
                    parts.append(c)

            clean = ''.join(parts)
            corpus = clean.split()

            for i in range(len(corpus) - 1):
                try:
                    value = [corpus[i + n] for n in range(1, amount + 1)]
                    yield corpus[i], " ".join(value)
                except IndexError:
                    continue

    @commands.command(name="try")
    async def try_(self, ctx, user_id: int = None):
        cache = json.load(open(self.path, encoding='utf-8'))

        if str(ctx.author.id) not in cache:
            return

        if user_id is None:
            user_messages = []
            for k, v in cache.items():
                user_messages.extend(v)

        else:
            try:
                user_messages = cache[str(user_id)].copy()
            except KeyError:
                msg = "Der User hat keine hinterlegten Nachrichten"
                await ctx.send(msg)
                return

        del cache
        pairs = self.make_pairs(user_messages, amount=2)

        words = {}
        for word_1, word_2 in pairs:
            if word_1 in words.keys():
                words[word_1].append(word_2)
            else:
                words[word_1] = [word_2]

        first = random.choice(list(words))
        while first.islower() or "." in first:
            first = random.choice(list(words))

        chain = [first]

        counter = 0
        while counter < 10:
            try:
                new_key = chain[-1].split(" ")[-1]
                word = random.choice(words[new_key])
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
