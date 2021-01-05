from utils import keyword, input_to_seconds
from discord.ext import commands, tasks
from data.credentials import RAPID_KEY
from collections import deque
from html import unescape
import datetime
import logging
import asyncio
import discord
import random


logger = logging.getLogger('self')


class Movie:
    def __init__(self, entry):
        if isinstance(entry, dict):
            self.id = entry['netflixid']
            self.title = unescape(entry['title'])
            self.image_url = entry['image']
            self.description = unescape(entry['synopsis'])
            self.rating = float(entry['rating'])
            self.year = int(entry['released'])
            self.runtime = entry['runtime']
            self.seconds = input_to_seconds(self.runtime)

        else:
            self.id = entry[0]
            self.title = entry[1]
            self.image_url = entry[2]
            self.description = entry[3]
            self.rating = entry[4]
            self.year = entry[5]
            self.runtime = entry[6] or "Unknown"
            self.seconds = entry[7]


class Netflix(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.headers = {
            "x-rapidapi-key": RAPID_KEY,
            "x-rapidapi-host": "unogs-unogs-v1.p.rapidapi.com"
        }
        self.url = "https://unogs-unogs-v1.p.rapidapi.com/aaapi.cgi"
        self.movies = []
        self._lock = asyncio.Event()
        self.archive = deque(maxlen=10)
        self.refresh_movies.start()

    @tasks.loop(hours=24)
    async def refresh_movies(self):
        await self.bot.wait_until_unlocked()

        if not self._lock.is_set():
            data = await self.bot.fetch('SELECT * FROM movies')
            self.movies = [Movie(rec) for rec in data]

            if self.movies:
                self._lock.set()
                return

        down = "downloadable"
        now = datetime.datetime.now()
        params = {
            "q": f"-!1990,{now.year}-!3,5-!6,10-!0-!Movie-!Any-!Any-!gt100-!{down}",
            "t": "ns",
            "cl": "39",  # German Code
            "st": "adv",
            "ob": "Relevance",
            "sa": "and"
        }

        page = 1
        args = []
        movies = []
        while True:
            params['p'] = str(page)
            kwargs = {'headers': self.headers, 'params': params}
            async with self.bot.session.get(self.url, **kwargs) as resp:
                data = await resp.json()

                for entry in data['ITEMS']:
                    movie = Movie(entry)
                    movies.append(movie)
                    values = [movie.id, movie.title, movie.image_url,
                              movie.description, movie.rating, movie.year,
                              movie.runtime, movie.seconds]
                    args.append(values)

                if len(data['ITEMS']) != 100:
                    break

            page += 1
            await asyncio.sleep(1)

        query = 'INSERT INTO movies ' \
                '(id, title, image_url, description,' \
                'rating, year, runtime, seconds)' \
                'VALUES ($1, $2, $3, $4, $5, $6, $7, $8)'

        self._lock.clear()

        await self.bot.db.execute('DELETE FROM movies')
        await self.bot.db.executemany(query, args)
        await self.bot.db.commit()
        self.movies = movies

        self._lock.set()

        logger.debug(f"refreshed movies: {len(movies)}")

    @commands.command(name="netflix")
    async def netflix_(self, ctx, *, args=None):
        kwargs = {'rating': None, 'year': None, 'runtime': None}
        rating, year, runtime = keyword(args, **kwargs)

        possible_movies = []
        await self._lock.wait()
        for movie in self.movies:
            if movie in self.archive:
                continue

            if rating and not rating.compare(movie.rating):
                continue

            if year and not year.compare(movie.year):
                continue

            if runtime:
                input_sec = input_to_seconds(runtime.value)
                if not year.compare(input_sec, movie.seconds):
                    continue

            possible_movies.append(movie)

        if not possible_movies:
            msg = "Sadly no movies were able to meet your requirements"
            await ctx.send(msg)

        else:
            movie = random.choice(possible_movies)
            url = f"https://www.netflix.com/watch/{movie.id}"
            embed = discord.Embed(title=movie.title, url=url, color=0xE50914)
            embed.set_thumbnail(url=movie.image_url)
            header = f"**Rating:** {movie.rating}\n" \
                     f"**Runtime:** {movie.runtime}\n" \
                     f"**Released:** {movie.year}"
            embed.description = f"{header}\n{movie.description}"
            embed.set_footer(text=f"{len(self.movies)} movies in database")
            self.archive.append(movie)
            await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Netflix(bot))
