from discord.ext import commands
import datetime
import discord


def get_seconds():
    now = datetime.datetime.now()
    clean = now + datetime.timedelta(days=1)
    goal_time = clean.replace(hour=0, minute=0, second=0, microsecond=0)
    start_time = now.replace(microsecond=0)
    return (goal_time - start_time).seconds


class GuildOnly(commands.CheckFailure):
    pass


def embed(msg, *, footer=None, error=False):
    if error:
        color = discord.Color.red()
    else:
        color = discord.Color.blue()

    self = discord.Embed(description=msg, color=color)
    if footer:
        self.set_footer(text=footer)

    return self
