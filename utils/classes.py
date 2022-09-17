from discord.ext import commands
import utils
import json


class ConfigHandler:
    def __init__(self, bot):
        self.bot = bot
        self.path = f"{self.bot.path}/data/config.json"
        self._config = self.config_setup()

    def config_setup(self):
        file = json.load(open(self.path))
        data = {int(key): value for key, value in file.items()}
        return data

    def save(self):
        with open(self.path, 'w') as file:
            json.dump(self._config, file)

    def store(self, key, item, guild_id):
        config = self._config.get(guild_id)

        if not config:
            self._config[guild_id] = {key: item}
        else:
            config[key] = item

        self.save()

    def get(self, key, guild_id, default=None):
        config = self._config.get(guild_id, {})
        item = config.get(key, default)
        return item

    def remove(self, key, guild_id):
        config = self._config.get(guild_id)
        if config:
            job = config.pop(key, None)
            if job:
                self.save()
            return job


class Cooldown:
    def __init__(self):
        self._cache = []

    def update(self, member_id):
        if member_id in self._cache:
            return False

        else:
            self._cache.append(member_id)
            return True

    def clear(self):
        self._cache.clear()


class DefaultDict(dict):
    def __init__(self, default=dict):
        dict.__init__(self)
        self.default = default

    def __getitem__(self, item):
        value = self.get(item)

        if value is not None:
            return value

        else:
            value = self[item] = self.default()
            return value


class Keyword:
    def __init__(self, value, sign="="):
        self.value = value
        self.sign = sign

    def compare(self, other, first=None):
        value = first or self.value
        if value is None:
            return True

        if self.sign == "<":
            return other < value
        elif self.sign == ">":
            return other > value
        else:
            return other == value

    def __bool__(self):
        return bool(self.value)


class Member(commands.Converter):
    async def convert(self, ctx, argument):
        member = utils.get_member_by_name(ctx, argument)
        if member is None:
            raise commands.MemberNotFound(argument)
        else:
            return member
