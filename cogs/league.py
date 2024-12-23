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
        "IRON": 0x372927,
        "BRONZE": 0xb38575,
        "SILVER": 0x2c3741,
        "GOLD": 0xb99462,
        "PLATINUM": 0x1a3e4a,
        "EMERALD": 0x104430,
        "DIAMOND": 0x7faede,
        "MASTER": 0x4a2355,
        "GRANDMASTER": 0x52272e,
        "CHALLENGER": 0x896d40
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

        if api_record.get('profileIconId') is None:
            print("ICON ID IS NONE")
            print(api_record)

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
    def full_name(self):
        return f"{self.name}#{self.tag}"

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

    @property
    def arguments(self):
        return (
            self.user_id,
            self.id,
            self.account_id,
            self.puuid,
            self.name,
            self.tag,
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
    MIN_KILL_PARTICIPATION = 50
    MAX_ACCEPTABLE_PING_AMOUNT = 75

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

    def __init__(self, match, summoner):
        self.data = match['info']
        self.game_id = self.data['gameId']
        self.queue_id = self.data['queueId']
        self.game_duration = self.data['gameDuration']
        self.game_end = self.data['gameEndTimestamp'] / 1000

        self.summoner = summoner
        self.inapplicable = False
        self.player_data = None
        self.champion_id = None

        participants_dict = {player['summonerId']: player for player in self.data['participants']}
        self.player_data = participants_dict[self.summoner.id]
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
        self._kill_participation = self.challenges.get('killParticipation', 0)
        self.team_damage_percentage = self.challenges.get('teamDamagePercentage', 0)
        self.kill_participation = round(self._kill_participation * 100)
        self.lane = self.player_data['lane']
        self.role = self.player_data['role']
        self.support = self.role == "DUO_SUPPORT"

        self.pinged_most = {}
        self.times_pinged = 0

        for key in self.player_data:
            if 'Pings' in key:
                self.times_pinged += self.player_data[key]

                if self.player_data[key] > self.pinged_most.get('times', 0):
                    self.pinged_most = {'times': self.player_data[key], 'type': key}

        self.pentas = self.player_data.get('pentaKills', 0)
        self.quadras = self.player_data.get('quadraKills', 0)

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
        kd_s = []

        for player in self.data['participants']:
            if player['teamId'] == self.team_data['teamId']:
                kd = player['kills'] / (player['deaths'] or 1)
                kd_s.append(kd)

        best_kd = sorted(kd_s, reverse=True)[0]
        return self.kd == best_kd and self.kill_participation >= self.MIN_KILL_PARTICIPATION

    def carried(self):
        if not self.win:
            return

        if not self.support and not self.team_damage_percentage > 0.2:
            logger.debug(
                f"Team damage percentage below: {self.team_damage_percentage} from {self.player_data['summonerName']}")
            return

        if self.kills >= 10 and self.kd >= 3:  # or (self.kills >= 5 and self.kd >= 4):
            return True

        elif self.best_performance():
            return True

        elif self.support or self.lane == "JUNGLE":
            return self.kda > 4

    def inted(self):
        return self.kda < 0.75 and self.deaths > 7

    def tilted(self):
        return self.times_pinged > self.MAX_ACCEPTABLE_PING_AMOUNT

    def special_scenario(self, messages, name):
        #  tobi spielt aram
        if self.summoner.id == "KenEY1p1tyFRVd4tZnr3YYX5FZxwMEzqeOFrG4C7E_HE6IE":
            if self.data['gameMode'] == "ARAM":
                return f"{name} spielt fucking ARAM? WTF!"

        elif self.quadras > 1 or self.pentas > 0:
            base = random.choice(messages['destroyed'])

            if self.pentas > 0:
                action = "`einen Penta`" if self.pentas == 1 else f"`{self.pentas} fucking Pentas`"
                return base.format(name, action)
            else:
                action = f"`{self.quadras} Quadras`"
                return base.format(name, action)


class League(commands.Cog):
    colour = 0x785A28
    europe_base_url = "https://europe.api.riotgames.com"
    europe_base_lol_url = "https://europe.api.riotgames.com/lol"
    euw_base_url = "https://euw1.api.riotgames.com"
    euw_base_lol_url = "https://euw1.api.riotgames.com/lol"

    summoner_query = ('INSERT INTO summoner (user_id, id, account_id, puuid, '
                      'name, tag, icon_id, level, wins, losses, tier, rank, lp, mmr, last_match_id) '
                      'VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15) '
                      'ON CONFLICT (user_id) DO UPDATE SET user_id=user_id, id=$2, account_id=$3, '
                      'puuid=$4, name=$5, tag=$6, icon_id=$7, level=$8, wins=$9, '
                      'losses=$10, tier=$11, rank=$12, lp=$13, mmr=$14, last_match_id=$15')

    champions_query = ('INSERT INTO champions (id, riot_id, name, description, data) '
                       'VALUES ($1, $2, $3, $4, $5) ON CONFLICT (id) DO UPDATE SET '
                       'id=id, riot_id=$2, name=$3, description=$4, data=$5')

    def __init__(self, bot):
        self.bot = bot
        self.champions = {}
        self.summoners = {}
        self.engine.start()

        with open(f"{self.bot.path}/data/league/message.json") as file:
            self.messages = json.load(file)

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
                if isinstance(error, utils.SummonerNotFound):
                    query = 'DELETE FROM summoner WHERE user_id = $1'
                    await self.bot.execute(query, summoner.user_id)
                    logger.debug(f"(LEAGUE) could not find {summoner.name} - removed from summoners")
                elif isinstance(error, utils.InvalidRiotResponse):
                    summoners[user_id] = summoner
                    logger.debug(f"(LEAGUE) refresh for {summoner.name} failed with code {error.status_code}")
                else:
                    summoners[user_id] = summoner
                    logger.error(f"(LEAGUE) refresh for {summoner.name} failed: {error}")

            else:
                summoners[user_id] = new_summoner
                batch.append(new_summoner.arguments)

            await asyncio.sleep(.1)

        await self.bot.db.executemany(self.summoner_query, batch)
        await self.bot.db.commit()

        logger.debug(f"(LEAGUE) {len(batch)} summoners refreshed")
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
            path = f"{self.bot.path}/data/league/rank/{summoner.tier}.png"

            if os.path.isfile(path):
                file = discord.File(path, filename="tier.png")
                embed = discord.Embed(description=f"\u200b\n{message}", colour=colour or self.colour)
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
        except (utils.InvalidRiotResponse, aiohttp.ClientConnectorError, asyncio.TimeoutError):
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
                    base = random.choice(self.messages['climbed'])
                    msg = base.format(name, summoner.str_rank)
                    await self.send_embed(channel, msg, summoner=summoner, colour=summoner.colour)

                elif old_summoner.int_rank > summoner.int_rank:
                    base = random.choice(self.messages['dropped'])
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

                    except utils.InvalidRiotResponse:
                        logger.debug("(LEAGUE) no API response")
                        continue

                    try:
                        match = Match(match_data, summoner)

                        if (datetime.utcnow().timestamp() - match.game_end) > 7200:
                            logger.info(f"Match {match.game_id} is too old")
                            continue

                        if match.queue_id not in Match.valid_queue_ids:
                            logger.info(f"Match {match.queue_id} is not a valid queue id")
                            continue

                        if msg := match.special_scenario(self.messages, name):
                            await self.send_embed(channel, msg, champion_id=match.champion_id)

                        elif match.carried():
                            base = random.choice(self.messages['carried'])
                            msg = base.format(name, match.str_kda)
                            colour = discord.Colour.green()
                            await self.send_embed(channel, msg, champion_id=match.champion_id, colour=colour)

                        elif match.inted():
                            base = random.choice(self.messages['inted'])
                            msg = base.format(name, match.str_kda)
                            colour = discord.Colour.red()
                            await self.send_embed(channel, msg, champion_id=match.champion_id, colour=colour)

                        elif match.tilted():
                            base = random.choice(self.messages['tilted'])
                            msg = base.format(name, f"{match.times_pinged} Pings")
                            await self.send_embed(channel, msg, champion_id=match.champion_id)

                    except Exception as error:
                        logger.error(
                            f"(LEAGUE) match {summoner.last_match_id} from {summoner.full_name} failed: {error}")
                        continue

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
    async def on_engine_error(self, error):
        await self.bot.wait_until_ready()
        owner = self.bot.get_user(self.bot.owner_id)

        formatted = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        logger.error(f"(LEAGUE) {formatted}")

        if owner is not None:
            await owner.send(f"league engine error: {formatted}")
        else:
            logger.error("owner not found")

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
            logger.debug(f"url: {url}")
            logger.debug(f"status code: {status_code}")
            logger.debug(f"message: {status.get('message')}")

            if status_code != 404:
                raise utils.InvalidRiotResponse(status_code)

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
        url = f"{self.europe_base_url}/riot/account/v1/accounts/by-puuid/{puuid}"
        return await self.fetch(url)

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
        embed = discord.Embed(title=title, url=summoner.op_gg, colour=summoner.colour)
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
        embed = discord.Embed(title=title, url=summoner.op_gg, colour=summoner.colour)
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
        match = Match(match_data, summoner)
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
