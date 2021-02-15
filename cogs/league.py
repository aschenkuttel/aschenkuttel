from discord.ext import commands, tasks
from data.credentials import RITO_KEY
from typing import Union
import asyncio
import discord
import logging
import random
import utils
import os

logger = logging.getLogger('self')


class Summoner:
    all_tiers = ["CHALLENGER", "GRANDMASTER", "MASTER",
                 "DIAMOND", "PLATINUM", "GOLD",
                 "SILVER", "BRONZE", "IRON"]
    all_ranks = ["I", "II", "III", "IV"]

    def __init__(self, record):
        (self.user_id,
         self.id,
         self.account_id,
         self.puuid,
         self.name,
         self.icon_id,
         self.level,
         self.wins,
         self.losses,
         self.tier,
         self.rank,
         self.lp,
         self.last_match_id) = record
        self._attempts = 0

    def __eq__(self, other):
        return self.id == other.id

    def __str__(self):
        return self.name

    @property
    def icon_url(self):
        return f"http://ddragon.leagueoflegends.com/cdn/11.3.1/img/profileicon/{self.icon_id}.png"

    @property
    def op_gg(self):
        name = self.name.replace(" ", "+")
        return f"https://euw.op.gg/summoner/userName={name}"

    @property
    def str_rank(self):
        if self.tier is None:
            return "Unranked"
        elif self.tier in self.all_tiers[:3]:
            return self.tier
        else:
            return f"{self.tier} {self.rank}"

    @property
    def int_rank(self):
        if self.tier is None:
            return 0

        tier_index = self.all_tiers.index(self.tier)
        rank_index = self.all_ranks.index(self.rank)
        return int(f"{tier_index + 1}{rank_index}")

    @property
    def unranked(self):
        return self.int_rank == 0

    @property
    def games(self):
        return self.wins + self.losses

    def failed_attempt(self):
        self._attempts += 1
        if self._attempts > 4:
            return True


class League(commands.Cog):
    base_url = "https://euw1.api.riotgames.com/lol"
    query = 'INSERT INTO summoner (user_id, id, account_id, puuid, ' \
            'name, icon_id, level, wins, losses, tier, rank, lp, last_match_id) ' \
            'VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13) ' \
            'ON CONFLICT (user_id) DO UPDATE SET id=$2, account_id=$3, ' \
            'puuid=$4, name=$5, icon_id=$6, level=$7, wins=$8, ' \
            'losses=$9, tier=$10, rank=$11, lp=$12, last_match_id=$13'
    colour = 0x785A28
    messages = {
        'up': [
            "Wie viel hat `{1.str_rank}` gekostet,\n{0}?",
            "LOL, wieso nur `{1.str_rank}`?\nClimb mal schneller {0}",
            "Glückwunsch zu `{1.str_rank}`,\n{0}",
            "{0}\nhat sich`{1.str_rank}` erkämpft!",
            "Endlich `{1.str_rank}`,\ngood job {0}",
            "Wow, `{1.str_rank}`!\nWell played {0}",
            "Oha, {0} ist jetzt `{1.str_rank}`.\nHätte ich ihm niemals zugetraut!"
        ],
        'down': [
            "Glückwunsch {0},\ndu bist nach {1.str_rank} abgestiegen...",
            "`{1.str_rank}`. Good Job {0}.\nSind sicher deine Teammates schuld, right?",
            "{0} ist auf dem Weg nach Iron!\nAktuelle Station: `{1.str_rank}`",
            "`{1.str_rank}`.\nDein Ernst {0}? xd",
            "Yo {0},\nhattest du Lags oder wieso `{1.str_rank}`?",
        ],
        'carry': [
            "Holy shit {0}, hast du gegen Bots gespielt\noder wie kommt `{1}` zusammen?",
            "`{1}`, well played, {0}",
            "`{1}`? NA-Soloqueue, right {0} xd",
            "Yo {0}, wie viel zahlst du deinem\nBooster damit er für dich `{1}` geht?",
            "Hallo, Herr Doktor? Ja es geht um {0},\n"
            "er hatte grade ein `{1}` Game und ich glaube sein Rücken ist kaputt.",
            "LOL {0}? `{1}`? Calm down Faker...",
            "`{1}`! {0} vor, noch ein Tor!",
            "Wait, {0}. Du hast ja doch Hände!? `{1}`, Wow!",
            "Oida `{1}`. Hoffe dein Team hat dir 50 € gezahlt {0}"
        ],
        'int': [
            "`{1}`. Dein fucking Ernst {0}? xd",
            "Ähm {0}, willst du deinen Acc nicht mehr oder warum `{1}`?",
            "`{1}` XDDDDDDDDDDDDDD\nAch cmon {0}, das gibt so save nen Ban :D",
            "Hey {0}, wen bist du denn in dem Game runtergerannt?\n"
            "Wer hat nen `{1}`-Inter in seinen Games verdient?",
            "`{1}`. Ich lass das mal unkommentiert so stehen, {0}",
            "Gerade {0}'s Matchhistory gecheckt und sehe `{1}`.\nAHAHAHAHAHAHAHAHAHAHA",
            "Hallo Riot Support? Es geht um {0}\nJa genau, das `{1}` Game. Danke :)",
        ]
    }

    def __init__(self, bot):
        self.bot = bot
        self.champion = {}
        self.summoner = {}
        self.bot.loop.create_task(self.load_summoner())
        self.refresh_champions.start()
        self.engine.start()

    def cog_unload(self):
        self.refresh_champions.cancel()
        self.engine.cancel()

    async def load_summoner(self):
        await self.bot.wait_until_unlocked()
        query = 'SELECT * FROM summoner'
        cache = await self.bot.fetch(query)
        self.summoner = {rec[0]: Summoner(rec) for rec in cache}

    async def refresh_summoner(self):
        summoners = {}
        batch = []

        for user_id, summoner in self.summoner.items():
            try:
                data = await self.fetch_summoner(summoner.account_id, id_=True)
            except utils.SummonerNotFound:
                resp = summoner.failed_attempt()

                if resp is True:
                    query = f'DELETE FROM summoner WHERE user_id = $1'
                    await self.bot.execute(query, summoner.user_id)
                else:
                    summoners[user_id] = summoner
            else:
                arguments = self.parse_arguments(user_id, data)
                new_summoner_obj = Summoner(arguments)
                summoners[user_id] = new_summoner_obj
                batch.append(arguments)

        await self.bot.db.executemany(self.query, batch)
        return summoners

    @tasks.loop(hours=24)
    async def refresh_champions(self):
        await self.bot.wait_until_unlocked()
        url = "http://ddragon.leagueoflegends.com/cdn/11.3.1/data/en_US/champion.json"
        async with self.bot.session.get(url) as resp:
            cache = await resp.json()

        for pkg in cache['data'].values():
            id_ = int(pkg['key'])
            self.champion[id_] = pkg

    async def send_embed(self, channel, summoner, msg):
        path = f"{self.bot.path}/data/league/{summoner.tier}.png"

        if os.path.isfile(path):
            file = discord.File(path, filename="tier.png")
            embed = discord.Embed(description=f"\u200b\n{msg}", colour=self.colour)
            embed.set_thumbnail(url="attachment://tier.png")
            await utils.silencer(channel.send(file=file, embed=embed))
            await asyncio.sleep(2)
        else:
            logger.error(f"{path} not found")

    @tasks.loop(minutes=10)
    async def engine(self):
        if not self.bot.is_set():
            return

        logger.debug("starting league engine")
        current_summoner = await self.refresh_summoner()
        if current_summoner is None:
            return

        for guild in self.bot.guilds:
            channel_id = self.bot.config.get('league', guild.id)
            channel = guild.get_channel(channel_id)

            if channel is None:
                continue

            messages = []
            for member in guild.members:
                old_summoner = self.summoner.get(member.id)
                if old_summoner is None:
                    continue

                summoner = current_summoner.get(member.id)
                if summoner is None:
                    continue

                name = f"[{member.display_name}]({summoner.op_gg})"
                if old_summoner.int_rank < summoner.int_rank:
                    base = random.choice(self.messages['up'])
                    msg = base.format(name, summoner)
                    await self.send_embed(channel, summoner, msg)

                elif old_summoner.int_rank > summoner.int_rank:
                    base = random.choice(self.messages['down'])
                    msg = base.format(name, summoner)
                    await self.send_embed(channel, summoner, msg)

                if old_summoner.last_match_id != summoner.last_match_id:
                    match = await self.fetch_match(summoner.last_match_id)

                    if match['gameType'] != "MATCHED_GAME":
                        continue

                    participant_id = None
                    for data in match['participantIdentities']:
                        if data['player']['summonerId'] == summoner.id:
                            participant_id = data['participantId']
                            break

                    player_data = None
                    for data in match['participants']:
                        if data['participantId'] == participant_id:
                            player_data = data

                    if player_data is not None:
                        stats = player_data['stats']
                        ratio = stats['kills'] / stats['deaths'] or 1
                        dif = 0 if match['gameMode'] == "CLASSIC" else 5
                        support = player_data['timeline']['role'] == "DUO_SUPPORT"

                        if support and stats['assists'] >= (20 + dif * 2) and stats['deaths'] <= 5:
                            base = random.choice(self.messages['carry'])
                            k_d = f"{stats['kills']}/{stats['deaths']}/{stats['assists']}"
                            msg = base.format(name, k_d)
                            messages.append(msg)

                        elif stats['kills'] >= (10 + dif) and ratio >= 2.5:
                            base = random.choice(self.messages['carry'])
                            k_d = f"{stats['kills']}/{stats['deaths']}"
                            msg = base.format(name, k_d)
                            messages.append(msg)

                        elif stats['deaths'] >= (10 + dif) and ratio <= 0.3 and not support:
                            base = random.choice(self.messages['int'])
                            k_d = f"{stats['kills']}/{stats['deaths']}"
                            msg = base.format(name, k_d)
                            messages.append(msg)

                        if summoner.id == "KenEY1p1tyFRVd4tZnr3YYX5FZxwMEzqeOFrG4C7E_HE6IE":
                            if match['gameMode'] == "ARAM":
                                msg = f"{name} spielt fucking ARAM? WTF!"
                                messages.append(msg)

            if messages:
                description = "\n\n".join(messages)
                embed = discord.Embed(description=description, colour=self.colour)
                await utils.silencer(channel.send(embed=embed))

        self.summoner = current_summoner
        logger.debug("league engine done")

    def get_summoner_by_member(self, ctx, argument):
        if argument is None:
            member = ctx.author
        else:
            member = utils.get_member_named(ctx, argument)

        if member is not None:
            summoner = self.summoner.get(member.id)
            if summoner is None:
                raise utils.NoSummonerLinked(member)
            else:
                return summoner

    async def save_summoner(self, user_id, data):
        arguments = self.parse_arguments(user_id, data)
        await self.bot.execute(self.query, *arguments)

        new_summoner = Summoner(arguments)
        self.summoner[user_id] = new_summoner
        return new_summoner

    async def fetch(self, url) -> Union[list, dict]:
        headers = {'X-Riot-Token': RITO_KEY}
        async with self.bot.session.get(url, headers=headers) as resp:
            cache = await resp.json()

            if isinstance(cache, list):
                return cache

            status = cache.get('status')

            if status is None:
                return cache

            status_code = status.get('status_code')
            logger.debug(f"status code: {status_code}")
            logger.debug(f"message: {status.get('message')}")

    async def fetch_summoner_basic(self, argument, id_=False):
        base = f"{self.base_url}/summoner/v4/summoners"

        if id_ is True:
            url = f"{base}/by-account/{argument}"
        else:
            url = f"{base}/by-name/{argument}"

        result = await self.fetch(url)
        if result is None:
            raise utils.SummonerNotFound(argument)
        else:
            return result

    async def fetch_league(self, id_):
        url = f"{self.base_url}/league/v4/entries/by-summoner/{id_}"
        cache = await self.fetch(url)

        if cache is None:
            return

        for ranked in cache:
            q_type = ranked.get("queueType")
            if q_type == "RANKED_SOLO_5x5":
                return ranked

    async def fetch_matches(self, account_id):
        url = f"{self.base_url}/match/v4/matchlists/by-account/{account_id}"
        cache = await self.fetch(url)
        return cache.get('matches')

    async def fetch_match(self, match_id):
        url = f"{self.base_url}/match/v4/matches/{match_id}"
        return await self.fetch(url)

    async def fetch_summoner(self, argument, id_=False):
        if not isinstance(argument, dict):
            data = await self.fetch_summoner_basic(argument, id_=id_)
        else:
            data = argument

        rank_data = await self.fetch_league(data['id'])
        matches = await self.fetch_matches(data['accountId'])

        if rank_data is not None:
            data.update(rank_data)

        if matches:
            data['last_match_id'] = matches[0]['gameId']

        return data

    @staticmethod
    def parse_arguments(user_id, data):
        return [
            user_id,
            data['id'],
            data['accountId'],
            data['puuid'],
            data['name'],
            data['profileIconId'],
            data['summonerLevel'],
            data.get('wins', 0),
            data.get('losses', 0),
            data.get('tier'),
            data.get('rank'),
            data.get('leaguePoints', 0),
            data.get('last_match_id')
        ]

    @commands.command(name="league")
    async def league_(self, ctx, *, summoner_name):
        """sets your connected summoner"""
        data = await self.fetch_summoner_basic(summoner_name)
        old_summoner = self.summoner.get(ctx.author.id)

        if old_summoner and old_summoner.id == data['id']:
            msg = f"`{old_summoner}` is already your connected summoner"

        elif data['id'] in self.summoner:
            msg = f"`{data['name']} is already someones connected summoner`"

        else:
            data_set = await self.fetch_summoner(data)
            summoner = await self.save_summoner(ctx.author.id, data_set)
            msg = f"`{summoner}` is now your connect summoner"

        await ctx.send(msg)

    @commands.command(name="summoner")
    async def summoner_(self, ctx, *, argument=None):
        """gives some basic information about your, someones
        connected summoner or some external summoner"""
        summoner = self.get_summoner_by_member(ctx, argument)

        if summoner is None:
            data = await self.fetch_summoner(argument)
            arguments = self.parse_arguments(None, data)
            summoner = Summoner(arguments)

        title = f"{summoner.name} (LV {summoner.level})"
        embed = discord.Embed(title=title, url=summoner.op_gg, colour=self.colour)
        embed.set_thumbnail(url=summoner.icon_url)
        parts = [
            f"**Games played:** {summoner.games}",
            f"**Win/Lose:** {summoner.wins}/{summoner.losses}",
            f"**Rank:** {summoner.str_rank} ({summoner.lp} LP)"
        ]

        embed.description = "\n".join(parts)
        await ctx.send(embed=embed)

    @commands.command(name="check")
    async def check_(self, ctx, *, username):
        """checks if given summoner name is already used or free,
        keep in mind that it only looks for availability and not
        if the given summoner name is valid as well"""
        try:
            if len(username) > 16:
                msg = "too long"
            else:
                await self.fetch_summoner_basic(username)
                msg = "unavailable"
        except utils.SummonerNotFound:
            msg = "available"

        await ctx.send(f"`{username}` is {msg}")


def setup(bot):
    bot.add_cog(League(bot))
