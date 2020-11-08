import datetime
import discord


def get_seconds_till(**kwargs):
    start_time = datetime.datetime.now()
    clean = start_time + datetime.timedelta(**kwargs)
    goal_time = clean.replace(hour=0, minute=0, second=0)
    return int((goal_time - start_time).total_seconds())


async def silencer(coroutine):
    try:
        response = await coroutine
        return response
    except (discord.Forbidden, discord.HTTPException):
        return False


def embed(msg, *, footer=None, error=False):
    if error:
        color = discord.Color.red()
    else:
        color = discord.Color.blue()

    self = discord.Embed(description=msg, color=color)
    if footer:
        self.set_footer(text=footer)

    return self
