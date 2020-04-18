import collections
import random
import json
import os


class ConfigHandler:
    def __init__(self):
        self.cache = os.path.dirname(__file__)
        self.path = f"{self.cache}/data/config.json"
        self._config = self.config_setup()

    def config_setup(self):
        file = json.load(open(self.path))
        data = {int(key): value for key, value in file.items()}
        return data

    def save(self):
        with open(self.path, 'w') as file:
            json.dump(self._config, file)

    def save_item(self, guild_id, key, item):
        config = self._config.get(guild_id)
        if not config:
            self._config[guild_id] = {key: item}
        else:
            config[key] = item
        self.save()

    def get_item(self, guild_id, key):
        config = self._config.get(guild_id)
        item = config.get(key) if config else None
        return item

    def remove_item(self, guild_id, key):
        config = self._config.get(guild_id)
        job = config.pop(key) if config else None
        self.save()
        return job


class IconHandler:
    def __init__(self):
        self.root = os.path.dirname(__file__)
        self.path = f"{self.root}/data/archive.json"
        self._config = self.setup()
        self._cache = {}

    def setup(self):
        file = json.load(open(self.path))
        data = {int(key): value for key, value in file.items()}
        return data

    def save_file(self):
        with open(self.path, 'w') as file:
            json.dump(self._config, file)

    def submit_icon(self, ctx, url):
        data = self._config.get(ctx.guild.id)
        if data is None:
            pack = {'icon': {}, 'pending': {}}
            data = self._config[ctx.guild.id] = pack
        pending = data['pending'].get(str(ctx.author.id))
        if pending is None:
            data['pending'][str(ctx.author.id)] = [url]
        else:
            if len(pending) == 3:
                return False
            pending.append(url)
        self.save_file()
        return True

    def random_icon(self, guild):
        data = self._config.get(guild.id)
        icons = data.get('icons') if data else None
        if not icons:
            return

        cache = {}
        for idc, urls in icons.items():
            for u in urls:
                cache[u] = idc

        while True:
            url = random.choice(cache)
            user_id = cache[url]
            if len(cache) < 4:
                return url, user_id
            cache = self._cache.get(guild.id)
            if cache is None:
                cache = self._cache[guild.id] = collections.deque(maxlen=3)
            elif url in cache:
                continue
            cache.append(url)
            return url, user_id

    def get_pending(self, guild):
        data = self._config.get(guild.id)
        pending = data.get('pending') if data else None
        if not pending:
            return


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
