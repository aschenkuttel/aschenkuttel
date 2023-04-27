import aiohttp
from discord.ext import commands, tasks
from data.credentials import RITO_KEY
from datetime import datetime
from typing import Union
import traceback
import asyncio
import discord
import logging
import random
import utils
import os

logger = logging.getLogger('self')


class Summoner:
    all_tiers = ["IRON", "BRONZE", "SILVER",
                 "GOLD", "PLATINUM", "DIAMOND",
                 "MASTER", "GRANDMASTER", "CHALLENGER"]
    all_ranks = ["IV", "III", "II", "I"]

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
        elif self.tier in self.all_tiers[-3:]:
            return f"{self.tier} {self.lp} LP"
        else:
            return f"{self.tier} {self.rank}"

    @property
    def int_rank(self):
        if self.tier is None:
            return 0

        tier_index = self.all_tiers.index(self.tier)
        rank_index = self.all_ranks.index(self.rank)
        return int(f"{tier_index}{rank_index + 1}")

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


class Match:
    valid_queue_ids = (
        400,  # 5v5 Draft Pick
        420,  # 5v5 Ranked Solo
        430,  # 5v5 Blind Pick
        440,  # 5v5 Ranked Flex
    )

    def __init__(self, match, summoner_id):
        self.data = match['info']
        self.summoner_id = summoner_id
        self.inapplicable = False
        self.player_data = None
        self.champion_id = None

        if (datetime.utcnow().timestamp() - (self.data['gameEndTimestamp'] / 1000)) > 7200:
            logger.info(f"Match {self.data['gameId']} is too old")
            self.inapplicable = True
            return

        if self.data['queueId'] not in self.valid_queue_ids:
            logger.info(type(self.data['queueId']))
            logger.info(f"Match {self.data['queueId']} is not a valid queue id")
            self.inapplicable = True
            return

        participants_dict = {player['summonerId']: player for player in self.data['participants']}
        self.player_data = participants_dict[self.summoner_id]
        self.champion_id = self.player_data['championId']

        team_dict = {team['teamId']: team for team in self.data['teams']}
        self.team_data = team_dict[self.player_data['teamId']]

        self.win = self.team_data['win']
        self.kills = self.player_data['kills']
        self.deaths = self.player_data['deaths']
        self.assists = self.player_data['assists']
        self.kd = self.kills / (self.deaths or 1)
        self.kda = (self.kills + self.assists) / (self.deaths or 1)
        self.str_kda = f"{self.kills}/{self.deaths}/{self.assists}"

        self.lane = self.player_data['lane']
        self.role = self.player_data['role']
        self.support = self.role == "DUO_SUPPORT"

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

    def special_scenario(self):
        if self.summoner_id == "KenEY1p1tyFRVd4tZnr3YYX5FZxwMEzqeOFrG4C7E_HE6IE":
            if self.data['gameMode'] == "ARAM":
                return "{} spielt fucking ARAM? WTF!"


class League(commands.Cog):
    euw_base_url = "https://euw1.api.riotgames.com/lol"
    europe_base_url = "https://europe.api.riotgames.com/lol"
    champion_icon_url = "http://ddragon.leagueoflegends.com/cdn/11.14.1/img/champion/"
    # query = 'INSERT INTO summoner (user_id, id, account_id, puuid, ' \
    #         'name, icon_id, level, wins, losses, tier, rank, lp, last_match_id) ' \
    #         'VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13) ' \
    #         'ON CONFLICT (user_id) DO UPDATE SET id=$2, account_id=$3, ' \
    #         'puuid=$4, name=$5, icon_id=$6, level=$7, wins=$8, ' \
    #         'losses=$9, tier=$10, rank=$11, lp=$12, last_match_id=$13'

    # we have to use this monstrosity since sqlite3 on ubuntu doesnt support
    # on conflict update, don't ask me why
    query = 'INSERT OR REPLACE INTO summoner (user_id, id, account_id, puuid, ' \
            'name, icon_id, level, wins, losses, tier, rank, lp, last_match_id) ' \
            'VALUES ($1, $2, $3, $4,' \
            'COALESCE($5, (SELECT name FROM summoner WHERE user_id = $1)),' \
            'COALESCE($6, (SELECT icon_id FROM summoner WHERE user_id = $1)),' \
            'COALESCE($7, (SELECT level FROM summoner WHERE user_id = $1)),' \
            'COALESCE($8, (SELECT wins FROM summoner WHERE user_id = $1)),' \
            'COALESCE($9, (SELECT losses FROM summoner WHERE user_id = $1)),' \
            'COALESCE($10, (SELECT tier FROM summoner WHERE user_id = $1)),' \
            'COALESCE($11, (SELECT rank FROM summoner WHERE user_id = $1)),' \
            'COALESCE($12, (SELECT lp FROM summoner WHERE user_id = $1)),' \
            'COALESCE($13, (SELECT last_match_id FROM summoner WHERE user_id = $1)))'

    colour = 0x785A28
    messages = {
        'up': [
            "Wie viel hat `{1}` gekostet,\n{0}?",
            "LOL, wieso nur `{1}`?\nClimb mal schneller {0}",
            "Glückwunsch zu `{1}`\n{0}",
            "{0}\nhat sich`{1}` erkämpft!",
            "Endlich `{1}`,\ngood job {0}",
            "Wow, `{1}`!\nWell played {0}",
            "Oha, {0} ist jetzt `{1}`.\nHätte ich ihm niemals zugetraut!",
            "Hey {0}, `{1}`? Haste dafür dein letztes Taschengeld ausgegeben?",
            "Boah, `{1}`! {0}, haste heimlich trainiert?",
            "Krass, {0} ist jetzt `{1}`. Wer hätte das gedacht?!"
        ],
        'down': [
            "Glückwunsch {0},\ndu bist nach `{1}` abgestiegen...",
            "`{1}`. Good Job {0}\nSind sicher deine Teammates schuld, right?",
            "{0} ist auf dem Weg nach Iron!\nAktuelle Station: `{1}`",
            "`{1}`.\nDein Ernst {0}? xd",
            "Yo {0},\nhattest du Lags oder wieso `{1}`?",
            "RIP {0}, `{1}` erreicht... Haste den Absturz wenigstens gefilmt?",
            "`{1}`. GJ {0}, willkommen zurück in der Elo-Hell!",
            "`{1}`. Echt jetzt, {0}? Haste mit den Füßen gespielt?",
            "Yo {0}, was lief schief, dass du in `{1}` gelandet bist? Account-Sharing?",
            "{0}, `{1}`... Musst wohl noch paar Tutorials schauen, hm?",
            "Autsch {0}, `{1}` erreicht. Wann kommt der Comeback-Stream?"
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
        ]
    }

    def __init__(self, bot):
        self.bot = bot
        self.champion = {}
        self.summoner = {}
        self._reload_lock = asyncio.Event()
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
        self._reload_lock.set()

    async def refresh_summoner(self):
        summoners = {}
        batch = []

        for user_id, summoner in self.summoner.items():
            try:
                data = await self.fetch_summoner(summoner.account_id, id_=True)
            except utils.SummonerNotFound:
                resp = summoner.failed_attempt()

                if resp is True:
                    query = 'DELETE FROM summoner WHERE user_id = $1'
                    await self.bot.execute(query, summoner.user_id)
                else:
                    summoners[user_id] = summoner
            else:
                arguments = self.parse_arguments(user_id, data)
                new_summoner_obj = Summoner(arguments)
                summoners[user_id] = new_summoner_obj
                batch.append(arguments)

            await asyncio.sleep(.1)

        await self.bot.db.executemany(self.query, batch)
        await self.bot.db.commit()
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

    async def send_embed(self, channel, message, summoner=None, champion_id=None):
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
            icon_name = self.champion[champion_id]['image']['full']
            embed = discord.Embed(description=f"\u200b\n{message}", colour=self.colour)
            embed.set_thumbnail(url=f"{self.champion_icon_url}{icon_name}")
            await utils.silencer(channel.send(embed=embed))

    @tasks.loop(minutes=15)
    async def engine(self):
        logger.debug("League: loop start")

        if not self._reload_lock.is_set():
            await self.load_summoner()
            logger.debug("League: summoners loaded")
            return

        try:
            current_summoner = await self.refresh_summoner()
        except (utils.NoRiotResponse, aiohttp.ClientConnectorError, asyncio.TimeoutError):
            logger.debug("League Loop: no API response")
            return

        if current_summoner is None:
            logger.debug("League: no current summoner")
            return

        for guild in self.bot.guilds:
            channel_id = self.bot.config.get('league', guild.id)
            channel = guild.get_channel(channel_id)

            if channel is None:
                logger.debug(f"League: {guild.id} has no league channel")
                continue

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
                    msg = base.format(name, summoner.str_rank)
                    await self.send_embed(channel, msg, summoner=summoner)

                elif old_summoner.int_rank > summoner.int_rank:
                    base = random.choice(self.messages['down'])
                    msg = base.format(name, summoner.str_rank)
                    await self.send_embed(channel, msg, summoner=summoner)

                if old_summoner.last_match_id != summoner.last_match_id:
                    try:
                        if summoner.last_match_id is None:
                            logger.debug(f"League: {member.id} has no last match")
                            continue
                        
                        match_data = await self.fetch_match(summoner.last_match_id)

                        if match_data is None:
                            logger.debug(f"League: {summoner.last_match_id} is not a valid match")
                            continue

                    except utils.NoRiotResponse:
                        logger.debug("League: no API response")
                        continue

                    match = Match(match_data, summoner.id)

                    if match.inapplicable:
                        continue

                    if match.carry():
                        base = random.choice(self.messages['carry'])
                        msg = base.format(name, match.str_kda)
                        await self.send_embed(channel, msg, champion_id=match.champion_id)

                    elif match.int():
                        base = random.choice(self.messages['int'])
                        msg = base.format(name, match.str_kda)
                        await self.send_embed(channel, msg, champion_id=match.champion_id)

                    elif base := match.special_scenario():
                        msg = base.format(name)
                        await self.send_embed(channel, msg, champion_id=match.champion_id)

                await asyncio.sleep(.1)

        self.summoner = current_summoner
        logger.debug("League: loop end")

    @engine.error
    async def on_engine_error(self, error):
        formatted = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
        logger.error(f"League: {formatted}")
        raise error

    def get_summoner_by_member(self, ctx, argument):
        if argument is None:
            member = ctx.author
        else:
            member = utils.get_member_by_name(ctx, argument)

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

            if status_code != 404:
                raise utils.NoRiotResponse()

    async def fetch_summoner_basic(self, argument, id_=False):
        base = f"{self.euw_base_url}/summoner/v4/summoners"

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
        url = f"{self.euw_base_url}/league/v4/entries/by-summoner/{id_}"
        cache = await self.fetch(url)

        if cache is None:
            return

        for ranked in cache:
            q_type = ranked.get("queueType")
            if q_type == "RANKED_SOLO_5x5":
                return ranked

    async def fetch_matches(self, puuid):
        url = f"{self.europe_base_url}/match/v5/matches/by-puuid/{puuid}/ids?start=0&count=1"
        cache = await self.fetch(url)
        if cache is not None:
            return cache

    async def fetch_match(self, match_id):
        url = f"{self.europe_base_url}/match/v5/matches/{match_id}"
        return await self.fetch(url)

    async def fetch_summoner(self, argument, id_=False):
        if id_ is True:
            data = await self.fetch_summoner_basic(argument, id_=id_)
        else:
            data = argument

        rank_data = await self.fetch_league(data['id'])
        matches = await self.fetch_matches(data['puuid'])

        if rank_data is not None:
            data.update(rank_data)

        if matches:
            data['last_match_id'] = matches[0]

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
            msg = f"`{summoner}` is now your connected summoner"

        await ctx.send(msg)

    @commands.command(name="summoner")
    async def summoner_(self, ctx, *, argument=None):
        """gives some basic information about your, someone's
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


async def setup(bot):
    await bot.add_cog(League(bot))
