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


# def keyword(options, strip=False, **kwargs):
#     raw_input = options or ''
#     matches = re.findall(r'[^=\W]{3,}[<=>][^=\s]+', raw_input)
#     cache = {}
#
#     for match in matches:
#         if strip:
#             raw_input = raw_input.replace(match, '')
#
#         sign = re.findall(r'[<=>]', match.lower())[0]
#         if match.count(sign) != 1:
#             continue
#
#         orig_key, input_value = match.split(sign)
#         key, value = orig_key.lower(), input_value.lower()
#
#         try:
#             true_value = float(value)
#         except ValueError:
#
#             if input_value.isdigit():
#                 true_value = int(value)
#
#             elif value in ["true", "false"]:
#                 true_value = value == "true"
#
#             else:
#                 true_value = input_value
#
#         cache[key] = [sign, true_value]
#
#     for argument, default_value in kwargs.items():
#         input_pkg = cache.get(argument)
#
#         if input_pkg is None:
#             if isinstance(default_value, list):
#                 num = 1 if len(default_value) == 3 else 0
#                 default_value = default_value[num]
#
#             kwargs[argument] = Keyword(default_value)
#             continue
#
#         else:
#             sign, user_input = input_pkg
#
#         new_value = user_input
#         if default_value in [False, True]:
#             if not isinstance(user_input, bool):
#                 new_value = default_value
#
#         elif isinstance(default_value, list):
#             if len(default_value) == 3:
#                 minimum, default, maximum = default_value
#             else:
#                 minimum, maximum = default_value
#                 default = minimum
#
#             new_value = parse_integer(user_input, default, [minimum, maximum])
#
#         elif isinstance(default_value, int):
#             new_value = parse_integer(user_input, default_value)
#
#         kwargs[argument] = Keyword(new_value, sign)
#
#     keywords = list(kwargs.values())
#     if strip:
#         keywords.insert(0, raw_input.strip())
#
#     return keywords


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
