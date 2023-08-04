import logging
import datetime
import discord
import re

logger = logging.getLogger('self')


def get_seconds_till(**kwargs):
    start_time = datetime.datetime.now()
    clean = start_time + datetime.timedelta(**kwargs)
    goal_time = clean.replace(hour=0, minute=0, second=0)
    return int((goal_time - start_time).total_seconds())


async def silencer(coroutine):
    try:
        response = await coroutine
        return response
    except (discord.Forbidden, discord.HTTPException) as error:
        logger.debug(f"silenced: {error}")
        return False


def embed(msg, *, footer=None, error=False):
    color = discord.Color.red() if error else discord.Color.blue()
    self = discord.Embed(description=msg, color=color)

    if footer:
        self.set_footer(text=footer)

    return self


class Plural:
    def __init__(self, value: int):
        self.value: int = value

    def __format__(self, format_spec: str) -> str:
        v = self.value
        singular, sep, plural = format_spec.partition('|')
        plural = plural or f'{singular}s'
        if abs(v) != 1:
            return f'{v} {plural}'
        return f'{v} {singular}'


def parse_integer(user_input, default, boundaries=None):
    if not isinstance(user_input, int):
        return default

    if boundaries:
        minimum, maximum = boundaries
        if user_input < minimum:
            return minimum
        elif user_input > maximum:
            return maximum

    return user_input


def input_to_seconds(user_input):
    seconds = 0
    seconds_per_unit = {"s": 1, "m": 60, "h": 3600}
    matches = re.findall(r'\d+\w', user_input)

    for match in matches:
        if match.isdigit():
            seconds += int(match)
        else:
            sec = seconds_per_unit[match[-1]]
            seconds += int(match[:-1]) * sec

    return seconds


def get_member_by_name(ctx, name):
    lower_name = name.lower()
    for member in ctx.guild.members:
        if member.display_name.lower() == lower_name:
            return member
        elif member.name.lower() == lower_name:
            return member
