import aiohttp
from discord import app_commands
from discord.ext import commands, tasks
from data.credentials import RITO_KEY
from urllib.parse import quote
from utils import SummonerArg
from datetime import datetime
from typing import Union
import traceback
import asyncio
import discord
import logging
import random
import utils
import json
import os

logger = logging.getLogger('self')


class Summoner:
    all_tiers = ["IRON", "BRONZE", "SILVER",
                 "GOLD", "PLATINUM", "EMERALD", "DIAMOND",
                 "MASTER", "GRANDMASTER", "CHALLENGER"]
    all_ranks = ["IV", "III", "II", "I"]

    tier_colors = {
        "IRON": 0x5A5A5A,  # Gray
        "BRONZE": 0xCD7F32,  # Bronze
        "SILVER": 0xC0C0C0,  # Silver
        "GOLD": 0xFFD700,  # Gold
        "PLATINUM": 0xE5E4E2,  # Platinum
        "EMERALD": 0x50C878,  # Emerald Green
        "DIAMOND": 0xB9F2FF,  # Diamond Blue
        "MASTER": 0x800080,  # Purple
        "GRANDMASTER": 0xFF4500,  # Orange-Red
        "CHALLENGER": 0x1E90FF  # Dodger Blue
    }

    refresh_limit = 20

    def __init__(self, record):
        self.user_id = record['user_id']
        self.id = record['id']
        self.account_id = record['account_id']
        self.puuid = record['puuid']
        self.name = record['name']
        self.tag = record['tag']
        self.icon_id = record['icon_id']
        self.level = record['level']
        self.wins = record['wins']
        self.losses = record['losses']
        self.tier = record['tier']
        self.rank = record['rank']
        self.lp = record['lp']
        self.mmr = record['mmr']
        self.last_match_id = record['last_match_id']
        self._attempts = 0

    def __eq__(self, other):
        return self.id == other.id

    def __str__(self):
        return self.name

    @classmethod
    def from_api(cls, user_id, api_record):
        tier = api_record.get('tier')
        rank = api_record.get('rank')
        lp = api_record.get('leaguePoints', 0)

        if tier is None:
            mmr = 0
        else:
            tier_index = cls.all_tiers.index(tier) + 1
            rank_index = cls.all_ranks.index(rank) + 1
            mmr = tier_index * 1000 + rank_index * 101 + lp

        return cls({
            'user_id': user_id,
            'id': api_record['id'],
            'account_id': api_record['accountId'],
            'puuid': api_record['puuid'],
            'name': api_record['gameName'],
            'tag': api_record['tagLine'],
            'icon_id': api_record['profileIconId'],
            'level': api_record['summonerLevel'],
            'wins': api_record.get('wins', 0),
            'losses': api_record.get('losses', 0),
            'tier': tier,
            'rank': rank,
            'lp': lp,
            'mmr': mmr,
            'last_match_id': api_record.get('last_match_id')
        })

    @property
    def icon_url(self):
        return f"http://ddragon.leagueoflegends.com/cdn/13.9.1/img/profileicon/{self.icon_id}.png"

    @property
    def op_gg(self):
        name = self.name.replace(" ", "+")
        return f"https://www.op.gg/summoners/euw/{name}-{self.tag}"

    @property
    def str_rank(self):
        if self.tier is None:
            return "Unranked"
        elif self.tier in self.all_tiers[-3:]:
            return f"{self.tier} - {self.lp} LP"
        else:
            return f"{self.tier} {self.rank}"

    @property
    def str_rank_lp(self):
        if self.tier is None:
            return "Unranked"
        elif self.tier in self.all_tiers[-3:]:
            return f"{self.tier} - {self.lp} LP"
        else:
            return f"{self.tier} {self.rank} - {self.lp} LP"

    @property
    def int_rank(self):
        if self.tier is None:
            return 0

        tier_index = self.all_tiers.index(self.tier)
        rank_index = self.all_ranks.index(self.rank)
        return int(f"{tier_index}{rank_index + 1}")

    @property
    def unranked(self):
        return self.mmr == 0

    @property
    def games(self):
        return self.wins + self.losses

    def failed_attempt(self):
        self._attempts += 1
        if self._attempts > 4:
            return True

    @property
    def arguments(self):
        return (
            self.user_id,
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
            self.mmr,
            self.last_match_id
        )

    @property
    def colour(self):
        print("fetching colour")
        print(self.tier)
        print(self.tier_colors)
        print(self.tier_colors.get(self.tier))
        return self.tier_colors.get(self.tier, 0x785A28)


class Champion:
    icon_base_uri = "https://ddragon.leagueoflegends.com/cdn/14.1.1/img/champion/"

    def __init__(self, record):
        self.id = record['id']
        self.riot_id = record['riot_id']
        self.name = record['name']
        self.description = record['description']
        self.data = json.loads(record['data'])
        self.image_url = self.data['image']['full']

    @property
    def icon_url(self):
        return f"{self.icon_base_uri}{self.image_url}"

    @property
    def arguments(self):
        return (
            self.id,
            self.riot_id,
            self.name,
            self.description,
            json.dumps(self.data)
        )


class Match:
    ranked_queue_ids = (
        420,  # 5v5 Ranked Solo
        440,  # 5v5 Ranked Flex
    )

    normal_queue_ids = (
        400,  # 5v5 Draft Pick
        490,  # 5v5 Quick Play
    )

    valid_queue_ids = ranked_queue_ids  # + normal_queue_ids

    game_modes = {
        420: "Solo Queue",
        440: "Flex Queue",
        400: "Draft Pick",
        490: "Quick Play",
    }

    def __init__(self, match, summoner_id):
        self.data = match['info']
        self.game_id = self.data['gameId']
        self.queue_id = self.data['queueId']
        self.game_duration = self.data['gameDuration']
        self.game_end = self.data['gameEndTimestamp'] / 1000

        self.summoner_id = summoner_id
        self.inapplicable = False
        self.player_data = None
        self.champion_id = None

        participants_dict = {player['summonerId']: player for player in self.data['participants']}
        self.player_data = participants_dict[self.summoner_id]
        self.champion_id = self.player_data['championId']

        team_dict = {team['teamId']: team for team in self.data['teams']}
        self.team_data = team_dict[self.player_data['teamId']]

        self.win = self.team_data['win']
        self.kills = self.player_data['kills']
        self.deaths = self.player_data['deaths']
        self.assists = self.player_data['assists']
        self.challenges = self.player_data['challenges']
        self.kd = self.kills / (self.deaths or 1)
        self.kda = self.challenges['kda']
        self.str_kda = f"{self.kills}/{self.deaths}/{self.assists}"
        self.lane = self.player_data['lane']
        self.role = self.player_data['role']
        self.support = self.role == "DUO_SUPPORT"

    @property
    def played_for(self):
        return f"{round(self.game_duration / 60)}:{self.game_duration % 60:02d}"

    @property
    def finished_at(self):
        return datetime.utcfromtimestamp(self.game_end).strftime("%d.%m.%Y %H:%M")

    @property
    def type(self):
        return self.game_modes.get(self.queue_id, self.data['gameMode'].capitalize())

    def best_performance(self):
        parts = self.kills + self.assists
        team_kills = 0
        kd_s = []

        for player in self.data['participants']:
            if player['teamId'] == self.team_data['teamId']:
                team_kills += player['kills']
                kd = player['kills'] / (player['deaths'] or 1)
                kd_s.append(kd)

        best_kd = sorted(kd_s, reverse=True)[0]
        percentage = round(parts / (team_kills or 1) * 100)
        return self.kd == best_kd and percentage >= 65

    def carry(self):
        if not self.win:
            return

        if (self.kills >= 10 and self.kd >= 2.5) or (self.kills >= 5 and self.kd >= 4):
            return True

        elif self.best_performance():
            return True

        elif self.support or self.lane == "JUNGLE":
            return self.kda > 3.5

    def int(self):
        return self.kda < 0.75 and self.deaths > 7

    def tilt(self):
        ping_count = 0

        for key in self.player_data:
            if 'Pings' in key:
                ping_count += self.player_data[key]

        return ping_count > 99

    def special_scenario(self):
        if self.summoner_id == "KenEY1p1tyFRVd4tZnr3YYX5FZxwMEzqeOFrG4C7E_HE6IE":
            if self.data['gameMode'] == "ARAM":
                return "{} spielt fucking ARAM? WTF!"


class League(commands.Cog):
    colour = 0x785A28
    europe_base_url = "https://europe.api.riotgames.com"
    europe_base_lol_url = "https://europe.api.riotgames.com/lol"
    euw_base_url = "https://euw1.api.riotgames.com"
    euw_base_lol_url = "https://euw1.api.riotgames.com/lol"

    summoner_query = ('INSERT INTO summoner (user_id, id, account_id, puuid, '
                      'name, icon_id, level, wins, losses, tier, rank, lp, mmr, last_match_id) '
                      'VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14) '
                      'ON CONFLICT (user_id) DO UPDATE SET user_id=user_id, id=$2, account_id=$3, '
                      'puuid=$4, name=$5, icon_id=$6, level=$7, wins=$8, '
                      'losses=$9, tier=$10, rank=$11, lp=$12, mmr=$13, last_match_id=$14')

    champions_query = ('INSERT INTO champions (id, riot_id, name, description, data) '
                       'VALUES ($1, $2, $3, $4, $5) ON CONFLICT (id) DO UPDATE SET '
                       'id=id, riot_id=$2, name=$3, description=$4, data=$5')

    messages = {
        'up': [
            "Wie viel hat `{1}` gekostet,\n{0}?",
            "LOL, wieso nur `{1}`?\nClimb mal schneller {0}",
            "Glückwunsch zu `{1}`\n{0}",
            "{0}\nhat sich `{1}` erkämpft!",
            "Endlich `{1}`,\ngood job {0}",
            "Wow, `{1}`!\nWell played {0}",
            "Oha, {0} ist jetzt `{1}`.\nHätte ich ihm niemals zugetraut!",
            "Hey {0}, `{1}`?\nHaste dafür dein letztes Taschengeld ausgegeben?",
            "Boah, `{1}`!\n{0}, haste heimlich trainiert?",
            "Krass, {0} ist jetzt `{1}`.\nWer hätte das gedacht?!",
            "Hey {0}, `{1}`?\nHaste dir den Account gekauft?",
        ],
        'down': [
            "Glückwunsch {0},\ndu bist nach `{1}` abgestiegen...",
            "`{1}`, Good Job {0}\nSind sicher deine Teammates schuld, right?",
            "{0} ist auf dem Weg nach Iron!\nAktuelle Station: `{1}`",
            "`{1}`.\nDein Ernst {0}? xd",
            "Yo {0},\nhattest du Lags oder wieso `{1}`?",
            "RIP {0}, `{1}` erreicht... Haste den Absturz wenigstens gefilmt?",
            "`{1}`, GJ {0}.\nWillkommen zurück in der Elo-Hell!",
            "`{1}`. Echt jetzt, {0}?\nHaste mit den Füßen gespielt?",
            "Yo {0}, was lief schief, dass du in `{1}` gelandet bist? Account-Sharing?",
            "{0}, `{1}`...\nMusst wohl noch paar Tutorials schauen, hm?",
            "Autsch {0}, `{1}` erreicht.\nWann kommt der Comeback-Stream?"
        ],
        'carry': [
            "Holy shit {0}, hast du gegen Bots gespielt\noder wie kommt `{1}` zusammen?",
            "`{1}`,\nwell played, {0}",
            "`{1}`? NA-Soloqueue,\nright {0} xd",
            "Yo {0}, wie viel zahlst du deinem\nBooster damit er für dich `{1}` geht?",
            "Hallo, Herr Doktor? Ja es geht um {0},\n"
            "er hatte grade ein `{1}` Game und ich glaube sein Rücken ist kaputt.",
            "LOL {0}? `{1}`?\nCalm down Faker...",
            "`{1}`! {0} vor,\nnoch ein Tor!",
            "Wait, {0}.\nDu hast ja doch Hände!? `{1}`, Wow!",
            "Oida `{1}`.\nHoffe dein Team hat dir 50 € gezahlt {0}",
            "Hey {0}, war das `{1}` Game eine Audition für LCS oder was?",
            "Schick mir bitte das Video, wie du mit verbundenen Augen `{1}` erreichst, {0}!",
            "Gz {0}, mit `{1}` hast du gerade die Definition von 'Carry' neu geschrieben!",
            "Mein lieber {0}, das `{1}` Game war schlichtweg beeindruckend!"
        ],
        'int': [
            "`{1}`.\nDein fucking Ernst {0}? xd",
            "Ähm {0}...,\nwillst du deinen Acc nicht mehr oder warum `{1}`?",
            "`{1}` XDDDDDDDDDDDDDD\nAch cmon {0}, das gibt so save nen Ban :D",
            "Hey {0}, wen bist du denn in dem Game runtergerannt?\n"
            "Wer hat nen `{1}`-Inter in seinen Games verdient?",
            "`{1}`.\nIch lass das mal unkommentiert so stehen, {0}",
            "Gerade {0}'s Matchhistory gecheckt und sehe `{1}`.\nAHAHAHAHAHAHAHAHAHAHA",
            "Hallo Riot Support? Es geht um {0}\nJa genau, das `{1}` Game. Danke :)",
            "{1}? Hey {0}, hoffentlich hast du ein gutes Rückgaberecht für deine ELO!",
            "Hallo {0}, wollte fragen, ob du das `{1}` Game als Kunstprojekt siehst?",
            "{1}, {0}. Mit welcher Hand spielst du normalerweise?",
            "Hey {0}, war das `{1}` Game ein Experiment, um zu sehen, wie weit man sinken kann?",
            "Lieber {0}, war das `{1}` Game ein Tribut an alte Bronze-Zeiten?",
            "Oh je, {0}. Ich hoffe, das `{1}` Game hat nicht zu bleibenden Schäden geführt!"
        ],
        'tilt': [
            "Hey {0}, ich glaube du solltest mal eine Pause machen mit deinen `{1}` Pings.",
            "`{1}` Pings und es wird noch heißer... {0}, wer hat dir das angetan?",
            "Wenn ich {1} Pings sehe, weiß ich, dass {0} wieder am Start ist.",
        ]
    }

    def __init__(self, bot):
        self.bot = bot
        self.champions = {}
        self.summoners = {}
        self.engine.start()

    def cog_unload(self):
        self.engine.cancel()

    async def load_summoner(self):
        await self.bot.wait_until_unlocked()
        query = 'SELECT * FROM summoner'
        cache = await self.bot.fetch(query)

        try:
            self.summoners = {rec['user_id']: Summoner(rec) for rec in cache}
        except Exception as error:
            print(f"error in load summoner: {error}")

        logger.debug(f"(LEAGUE) {len(self.summoners)} summoners loaded")

    async def refresh_summoners(self):
        summoners = {}
        batch = []

        for user_id, summoner in self.summoners.items():
            try:
                new_summoner = await self.fetch_summoner_by_puuid(summoner.puuid, user_id)
            except Exception as error:
                if not isinstance(error, utils.NoRiotResponse):
                    logger.error(f"(LEAGUE) refresh for {summoner.name} failed: {error}")

                resp = summoner.failed_attempt()

                if resp is True:
                    query = 'DELETE FROM summoner WHERE user_id = $1'
                    await self.bot.execute(query, summoner.user_id)

                    logger.debug(f"(LEAGUE) {summoner.name} removed from summoners")
                else:
                    summoners[user_id] = summoner

            else:
                summoners[user_id] = new_summoner
                batch.append(new_summoner.arguments)

            await asyncio.sleep(.1)

        await self.bot.db.executemany(self.summoner_query, batch)
        await self.bot.db.commit()
        return summoners

    async def load_champions(self):
        await self.bot.wait_until_unlocked()
        query = 'SELECT * FROM champions'
        cache = await self.bot.fetch(query)
        self.champions = {rec['id']: Champion(rec) for rec in cache}
        logger.debug(f"(LEAGUE) {len(self.champions)} champions loaded")

    async def refresh_champions(self):
        champions = {}
        batch = []

        url = "http://ddragon.leagueoflegends.com/cdn/14.1.1/data/en_US/champion.json"
        async with self.bot.session.get(url) as resp:
            cache = await resp.json()

        for pkg in cache['data'].values():
            champion = Champion({
                'id': int(pkg['key']),
                'riot_id': pkg['id'],
                'name': pkg['name'],
                'description': pkg['blurb'],
                'data': json.dumps(pkg)
            })

            champions[champion.id] = champion
            batch.append(champion.arguments)

        await self.bot.db.executemany(self.champions_query, batch)
        await self.bot.db.commit()
        logger.debug(f"(LEAGUE) {len(champions)} champions refreshed")
        return champions

    async def send_embed(self, channel, message, summoner=None, champion_id=None, colour=None):
        if summoner is not None and summoner.tier is not None:
            path = f"{self.bot.path}/data/league/{summoner.tier}.png"

            if os.path.isfile(path):
                file = discord.File(path, filename="tier.png")
                embed = discord.Embed(description=f"\u200b\n{message}", colour=self.colour)
                embed.set_thumbnail(url="attachment://tier.png")
                await utils.silencer(channel.send(file=file, embed=embed))
                await asyncio.sleep(2)
            else:
                logger.error(f"{path} not found")

        elif champion_id is not None:
            champion = self.champions.get(champion_id)

            if champion is None:
                logger.error(f"{champion_id} not found")
                return

            embed = discord.Embed(description=f"\u200b\n{message}", colour=colour or self.colour)
            embed.set_thumbnail(url=champion.icon_url)
            await utils.silencer(channel.send(embed=embed))

    @tasks.loop(minutes=10)
    async def engine(self):
        logger.debug("(LEAGUE) service started")

        try:
            self.champions = await self.refresh_champions()
            current_summoners = await self.refresh_summoners()
        except (utils.NoRiotResponse, aiohttp.ClientConnectorError, asyncio.TimeoutError):
            logger.debug("League Loop: no API response")
            return

        if current_summoners is None:
            logger.debug("(LEAGUE) no current summoner")
            return

        for guild in self.bot.guilds:
            channel_id = self.bot.config.get('league', guild.id)
            channel = guild.get_channel(channel_id)

            if channel is None:
                logger.debug(f"(LEAGUE) {guild.id} has no league channel")
                continue

            for member in guild.members:
                old_summoner = self.summoners.get(member.id)
                if old_summoner is None:
                    continue

                summoner = current_summoners.get(member.id)
                if summoner is None:
                    continue

                name = f"[{member.display_name}]({summoner.op_gg})"

                if old_summoner.int_rank < summoner.int_rank:
                    base = random.choice(self.messages['up'])
                    msg = base.format(name, summoner.str_rank)
                    await self.send_embed(channel, msg, summoner=summoner, colour=summoner.colour)

                elif old_summoner.int_rank > summoner.int_rank:
                    base = random.choice(self.messages['down'])
                    msg = base.format(name, summoner.str_rank)
                    await self.send_embed(channel, msg, summoner=summoner, colour=summoner.colour)

                if old_summoner.last_match_id != summoner.last_match_id:
                    try:
                        if summoner.last_match_id is None:
                            logger.debug(f"(LEAGUE) {member.id} has no last match")
                            continue

                        match_data = await self.fetch_match(summoner.last_match_id)

                        if match_data is None:
                            logger.debug(f"(LEAGUE) {summoner.last_match_id} is not a valid match")
                            continue

                    except utils.NoRiotResponse:
                        logger.debug("(LEAGUE) no API response")
                        continue

                    match = Match(match_data, summoner.id)
                    match.tilt()

                    if (datetime.utcnow().timestamp() - match.game_end) > 7200:
                        logger.info(f"Match {match.game_id} is too old")
                        continue

                    if match.queue_id not in Match.valid_queue_ids:
                        logger.info(f"Match {match.queue_id} is not a valid queue id")
                        continue

                    if match.carry():
                        base = random.choice(self.messages['carry'])
                        msg = base.format(name, match.str_kda)
                        colour = discord.Colour.green()
                        await self.send_embed(channel, msg, champion_id=match.champion_id, colour=colour)

                    elif match.int():
                        base = random.choice(self.messages['int'])
                        msg = base.format(name, match.str_kda)
                        colour = discord.Colour.red()
                        await self.send_embed(channel, msg, champion_id=match.champion_id, colour=colour)

                    elif match.tilt():
                        base = random.choice(self.messages['tilt'])
                        msg = base.format(name, match.challenges['ping'])
                        await self.send_embed(channel, msg, summoner=summoner)

                    elif base := match.special_scenario():
                        msg = base.format(name)
                        await self.send_embed(channel, msg, champion_id=match.champion_id)

                await asyncio.sleep(.1)

        self.summoners = current_summoners
        logger.debug("(LEAGUE) service finished")

    @engine.before_loop
    async def before_engine(self):
        await self.bot.wait_until_unlocked()
        await self.load_summoner()
        await self.load_champions()
        logger.debug("(LEAGUE) setup complete")

    @engine.error
    async def xd(self, error):
        formatted = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
        logger.error(f"(LEAGUE) {formatted}")
        print("logger?")
        raise error

    def get_summoner_by_member(self, member):
        summoner = self.summoners.get(member.id)

        if summoner is None:
            raise utils.NoSummonerLinked(member)
        else:
            return summoner

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

            if status_code != 404:
                raise utils.NoRiotResponse()

    async def fetch_riot_acc_by_rid(self, name, tag):
        sanitized_name = quote(name)
        sanitized_tag = quote(tag)
        url = f"{self.europe_base_url}/riot/account/v1/accounts/by-riot-id/{sanitized_name}/{sanitized_tag}"

        response = await self.fetch(url)

        if response is None:
            raise utils.SummonerNotFound(f"{name}#{tag}")
        else:
            return response

    async def fetch_riot_acc_by_puuid(self, puuid):
        try:
            url = f"{self.europe_base_url}/riot/account/v1/accounts/by-puuid/{puuid}"
            return await self.fetch(url)
        except Exception as e:
            logger.debug(f"Summoner with puuid {puuid} not found ({e})")
            return None

    async def fetch_summoner_by_rid(self, name, tag) -> Summoner:
        data = await self.fetch_riot_acc_by_rid(name, tag)
        return await self.fetch_summoner_by_puuid(data['puuid'])

    async def fetch_summoner_by_puuid(self, puuid, user_id=None) -> Summoner:
        data = await self.fetch(f"{self.euw_base_lol_url}/summoner/v4/summoners/by-puuid/{puuid}")
        acc_data = await self.fetch_riot_acc_by_puuid(puuid)

        if data is None or acc_data is None:
            raise utils.SummonerNotFound(puuid)
        else:
            data.update(acc_data)

        rank_data = await self.fetch_league(data['id'])
        matches = await self.fetch_matches(puuid)

        if rank_data is not None:
            data.update(rank_data)

        if matches:
            data['last_match_id'] = matches[0]

        return Summoner.from_api(user_id, data)

    async def fetch_league(self, id_):
        url = f"{self.euw_base_lol_url}/league/v4/entries/by-summoner/{id_}"
        cache = await self.fetch(url)

        if cache is None:
            return

        for ranked in cache:
            q_type = ranked.get("queueType")
            if q_type == "RANKED_SOLO_5x5":
                return ranked

    async def fetch_matches(self, puuid):
        url = f"{self.europe_base_lol_url}/match/v5/matches/by-puuid/{puuid}/ids?start=0&count=1"
        cache = await self.fetch(url)
        if cache is not None:
            return cache

    async def fetch_match(self, match_id):
        url = f"{self.europe_base_lol_url}/match/v5/matches/{match_id}"
        return await self.fetch(url)

    async def fetch_masteries(self, puuid):
        url = f"{self.euw_base_lol_url}/champion-mastery/v4/champion-masteries/by-puuid/{puuid}"
        return await self.fetch(url)

    league = app_commands.Group(name="league", description="commands for league of legends")

    @league.command(name="set", description="sets your connected summoner")
    @app_commands.describe(riot_acc="your riot account name (e.g. 'Riot Games#EUW')")
    async def set_(self, interaction, riot_acc: SummonerArg(shallow=True)):
        old_summoner = self.summoners.get(interaction.user.id)

        if old_summoner and old_summoner.puuid == riot_acc['puuid']:
            msg = f"`{old_summoner}` is already your connected summoner"

        elif riot_acc['puuid'] in [s.puuid for s in self.summoners.values()]:
            msg = f"`{riot_acc['gameName']} is already someones connected summoner`"

        else:
            summoner = await self.fetch_summoner_by_puuid(riot_acc['puuid'], interaction.user.id)
            self.summoners[interaction.user.id] = summoner
            await self.bot.execute(self.summoner_query, *summoner.arguments)
            msg = f"`{summoner}` is now your connected summoner"

        await interaction.response.send_message(msg)

    @app_commands.command(name="summoner",
                          description="gives some basic information about your or someone's connected summoner")
    @app_commands.describe(member="the member you want to get information about (optional)",
                           summoner="the summoner name you want to get information about (optional)")
    async def summoner_(self, interaction, member: discord.Member = None, summoner: SummonerArg = None):
        if summoner is None:
            summoner = self.get_summoner_by_member(member or interaction.user)

        title = f"{summoner.name} (LV {summoner.level})"
        embed = discord.Embed(title=title, url=summoner.op_gg, colour=self.colour)
        embed.set_thumbnail(url=summoner.icon_url)
        parts = [
            f"**Games played:** {summoner.games}",
            f"**Win/Lose:** {summoner.wins}/{summoner.losses}",
            f"**Rank:** {summoner.str_rank}"
        ]

        embed.description = "\n".join(parts)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="mastery",
                          description="gives the top 5 champion masteries of your or someone's connected summoner")
    @app_commands.describe(member="the member you want to get information about (optional)",
                           summoner="the summoner name you want to get information about (optional)")
    async def mastery_(self, interaction, member: discord.Member = None, summoner: str = None):
        if summoner is None:
            summoner = self.get_summoner_by_member(member or interaction.user)

        masteries = await self.fetch_masteries(summoner.puuid)
        title = f"{summoner.name} (LV {summoner.level})"
        embed = discord.Embed(title=title, url=summoner.op_gg, colour=self.colour)
        embed.set_thumbnail(url=summoner.icon_url)

        if masteries is None:
            embed.description = "No mastery data found"
        else:
            parts = []
            for mastery in masteries[:5]:
                champion = self.champions.get(mastery['championId'])
                champion_name = champion.name if champion else "Unknown"
                champion_points = f"{mastery['championPoints']:,}".replace(",", ".")
                parts.append(f"`{champion_points}` - **{champion_name}**")

            embed.description = "\n".join(parts)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="last_match", description="gives the last match of your or someone's connected summoner")
    @app_commands.describe(member="the member you want to get information about (optional)",
                           summoner="the summoner name you want to get information about (optional)")
    async def last_match_(self, interaction, member: discord.Member = None, summoner: SummonerArg = None):
        if summoner is None:
            summoner = self.get_summoner_by_member(member or interaction.user)

        match_data = await self.fetch_match(summoner.last_match_id)
        match = Match(match_data, summoner.id)
        champion = self.champions.get(match.champion_id)

        title = f"{summoner.name} (LV {summoner.level})"
        embed = discord.Embed(title=title, url=summoner.op_gg, colour=self.colour)
        embed.set_thumbnail(url=champion.icon_url if champion is not None else summoner.icon_url)

        if match_data is None:
            embed.description = "No match data found"
        else:
            parts = [
                f"**Mode:** {match.type}",
                f"**Lane:** {match.lane.capitalize()}",
                f"**Champion:** {champion.name if champion else 'Unknown'}",
                f"**Duration:** {match.played_for}",
                f"**KDA:** {match.str_kda}",
                f"**CS:** {match.player_data['totalMinionsKilled']}",
            ]

            embed.description = "\n".join(parts)

        embed.set_footer(text=f"Played at {match.finished_at}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ranking", description="shows the top 10 ranked players on the server")
    async def ranking_(self, interaction):
        query = 'SELECT * FROM summoner ORDER BY mmr DESC LIMIT 10'
        cache = await self.bot.fetch(query)

        lines = []

        for record in cache:
            summoner = Summoner(record)
            member = interaction.guild.get_member(summoner.user_id)

            if member is None or summoner.mmr == 0:
                continue

            content = f"[{member.display_name if member else 'Unknown'}]({summoner.op_gg})"
            line = f"`{len(lines) + 1}.` {content}\n{summoner.str_rank_lp}"
            lines.append(line)

        if not lines:
            await interaction.response.send_message("No ranked players found")
        else:
            embed = discord.Embed(title=f"Top {len(lines)} of {interaction.guild.name}", colour=self.colour)
            embed.description = "\n".join(lines)
            await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(League(bot))
