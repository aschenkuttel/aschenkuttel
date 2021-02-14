from discord.ext import commands, tasks
from data.credentials import RITO_KEY
from typing import Union
import discord
import logging
import random
import utils

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
        if self.tier in self.all_tiers[:3]:
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


class Match:
    def __init__(self, data):
        self.data = data
        self.participants = data['participants']


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
            "LOL, **{0}** ist somehow nach `{1.str_rank}` aufgestiegen?",
            "Wieviel hat `{1.str_rank}` gekostet, **{0}**?",
            "LOL, wieso nur `{1.str_rank}`. Climb mal schneller **{0}**",
            "Glückwunsch zu `{1.str_rank}`, **{0}**.",
            "**{0}** hat sich `{1.str_rank}` erkämpft!",
            "Endlich  `{1.str_rank}`, good job **{0}**.",
            "Wow, `{1.str_rank}`! Well played **{0}**.",
            "**{0}** ist nun Chall- äh `{1.str_rank}`. Gw!",
            "Achtung, Achtung! **{0}** ist nun eine `{1.str_rank}` Legende.",
            "**{0}** ist endlich `{1.str_rank}` und damit High Elo!",
            "Oha, **{0}** ist jetzt `{1.str_rank}`.\nHätte ich ihm niemals zugetraut!"
        ],
        'down': [
            "Glückwunsch **{0}**, du bist nach {1.str_rank} abgestiegen...",
            "**{0}** ist nach `{1.str_rank}` gedropped xdddddd",
            "`{1.str_rank}`. Good Job **{0}**.\nSind sicher deine Teammates schuld, right?",
            "**{0}** ist auf dem Weg nach Iron!\nAktuelle Station: `{1.str_rank}`.",
            "`{1.str_rank}`. Dein ernst **{0}**? xD",
            "Willst du weiter droppen **{0}** oder machst du bei "
            "`{1.str_rank}` jetzt erstmal Pause?",
            "`{1.str_rank}` XDDDDDDDDDDDDDD\nHoly shit wie bad kann man sein **{0}**.",
            "Yo **{0}**, hattest du Lags oder wieso `{1.str_rank}`?",
            "ALARM, ein wildes **{0}** ist gerade fett am droppen.\nIst atm `{1.str_rank}` xDDD",
            "Bist du besoffen oder wie hast du es nach `{1.str_rank}` geschafft, **{0}**? xD",
            "**{0}** möchte nicht mehr climben.\nStattdessen ist er nach `{1.str_rank}` gedroppt xD"
        ],
        'carry': [
            "Holy shit **{0}**, hast du gegen Bots gespielt\noder wie kommt `{1}` zusammen?",
            "`{1}`. Well played, **{0}**.",
            "`{1}`! NA-Soloq, right **{0}**?",
            "Yo **{0}**, wie viel zahlst du deinem Booster\ndamit er für dich `{1}` geht?",
            "Hallo, Herr Doktor? Ja es geht um **{0}**.\n"
            "Er hatte grade ein `{1}` Game und ich glaube sein Rücken ist kaputt.",
            "WOOOOOH, `{1}`! Crazy Performance **{0}**, GGWP!",
            "LOL **{0}**? `{1}`? Calm down Faker.",
            "`{1}`! **{0}** vor, noch ein Tor!",
            "Wait, **{0}**. Du hast ja doch Hände! `{1}`, wow!",
            "Oida! `{1}`! Hoffe dein Team hat dir 50 € gezahlt **{0}**."
        ],
        'int': [
            "`{1}`. Dein fucking ernst **{0}**? xD",
            "Ähm **{0}**, willst du deinen Acc nicht mehr oder warum `{1}`?",
            "Jo, kurz afk ein Ticket schreiben wegen **{0}**'s `{1}` Game.",
            "`{1}` XDDDDDDDDDDDDDD\nAch cmon **{0}**, das gibt so save nen Ban :D",
            "Unlucky Game **{0}**? `{1}`? xDDDDD",
            "Hey **{0}**, wen bist du denn in dem Game runtergerannt? "
            "Wer hat nen `{1}`-Inter in seinen Games verdient?",
            "`{1}`. Ich lass das mal unkommentiert so stehen, **{0}**.",
            "Grade **{0}**'s Matchhistory gecheckt und sehe `{1}`. AHAHAHAHA",
            "Hallo Riot Support? Es geht um **{0}**.\nJa genau, das `{1}` Game. Danke :)",
            "Okay **{0}**. `{1}`. Bitte sag mir, dass das Absicht war xDDDDD"
        ]
    }

    def __init__(self, bot):
        self.bot = bot
        self.summoner = {}
        self.bot.loop.create_task(self.load_summoner())
        self.engine.start()

    def cog_unload(self):
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

    @tasks.loop(minutes=1)
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

                name = f"{member.display_name} ({summoner})"
                if old_summoner.int_rank < summoner.int_rank:
                    base = random.choice(self.messages['up'])
                    msg = base.format(name, summoner)
                    messages.append(msg)

                elif old_summoner.int_rank > summoner.int_rank:
                    base = random.choice(self.messages['down'])
                    msg = base.format(name, summoner)
                    messages.append(msg)

                if old_summoner.last_match_id != summoner.last_match_id:
                    match = await self.fetch_match(summoner.last_match_id)

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
            data.get('wins'),
            data.get('losses'),
            data.get('tier'),
            data.get('rank'),
            data.get('leaguePoints'),
            data.get('last_match_id')
        ]

    @commands.command(name="im")
    async def im_(self, ctx, *, summoner_name):
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
            f"**Win | Lose:** {summoner.wins} | {summoner.losses}",
            f"**Rank:** {summoner.str_rank} ({summoner.lp} LP)"
        ]

        embed.description = "\n".join(parts)
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(League(bot))
