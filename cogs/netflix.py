from utils import keyword, input_to_seconds
from discord.ext import commands, tasks
from data.credentials import RAPID_KEY
from difflib import SequenceMatcher
from html import unescape
import datetime
import logging
import asyncio
import discord
import typing
import random
import ftfy

logger = logging.getLogger('self')


class Movie:
    def __init__(self, entry):
        if isinstance(entry, dict):
            self.id = entry['netflixid']
            self.title = self.parse(entry['title'])
            self.image_url = entry['image']
            self.description = self.parse(entry['synopsis'])
            self.rating = float(entry['rating'] or 0)
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

    @staticmethod
    def parse(string):
        html = unescape(string)
        return ftfy.fix_encoding(html)


class Netflix(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.headers = {
            "x-rapidapi-key": RAPID_KEY,
            "x-rapidapi-host": "unogs-unogs-v1.p.rapidapi.com"
        }
        self.url = "https://unogs-unogs-v1.p.rapidapi.com/aaapi.cgi"
        self.movies = {}
        self._lock = asyncio.Event()
        self.refresh_movies.start()

    def cog_unload(self):
        self.refresh_movies.cancel()

    @tasks.loop(hours=48)
    async def refresh_movies(self):
        await self.bot.wait_until_unlocked()

        if not self._lock.is_set():
            data = await self.bot.fetch('SELECT * FROM movies')
            movies = [Movie(rec) for rec in data]
            self.movies = {m.id: m for m in movies}

            if self.movies:
                self._lock.set()
                return

        down = "downloadable"
        now = datetime.datetime.now()
        params = {
            "q": f"-!1990,{now.year}-!0,5-!0,10-!0-!Movie-!Any-!Any-!gt0-!{down}",
            "t": "ns",
            "cl": "39",  # German Code
            "st": "adv",
            "ob": "Relevance",
            "sa": "and"
        }

        page = 1
        args = []
        movies = {}
        while True:
            params['p'] = str(page)
            kwargs = {'headers': self.headers, 'params': params}
            async with self.bot.session.get(self.url, **kwargs) as resp:
                data = await resp.json()

                for entry in data['ITEMS']:
                    movie = Movie(entry)
                    movies[movie.id] = movie
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

    def create_movie_embed(self, movie):
        url = f"https://www.netflix.com/watch/{movie.id}"
        embed = discord.Embed(title=movie.title, url=url, color=0xE50914)
        embed.set_thumbnail(url=movie.image_url)
        header = f"**Rating:** {movie.rating}\n" \
                 f"**Runtime:** {movie.runtime}\n" \
                 f"**Released:** {movie.year}"
        embed.description = f"{header}\n{movie.description}"
        embed.set_footer(text=f"{len(self.movies)} movies in database")
        return embed

    @commands.command(name="netflix")
    async def netflix_(self, ctx, *, args=None):
        """Returns random german netflix movie, specify further with
        these keywords: year, rating and runtime. Keywords are used
        like this: key=value. You can use both <> operators as well.
        For example .netflix year>2000 rating>5 which would return
        all movies released after 2000 with a rating more than 5"""
        kwargs = {'rating': None, 'year': None, 'runtime': None}
        genre, rating, year, runtime = keyword(args, strip=True, **kwargs)

        possible_movies = []
        await self._lock.wait()
        for movie in self.movies.values():
            if genre not in movie.description:
                continue

            if not rating.compare(movie.rating):
                continue

            if not year.compare(movie.year):
                continue

            if runtime:
                input_sec = input_to_seconds(runtime.value)
                if not year.compare(input_sec, movie.seconds):
                    continue

            possible_movies.append(movie)

        if not possible_movies:
            msg = "sadly no movies were able to meet your requirements"
            await ctx.send(msg)

        else:
            movie = random.choice(possible_movies)
            embed = self.create_movie_embed(movie)
            await ctx.send(embed=embed)

    @commands.command(name="movie")
    async def movie_(self, ctx, *, title_or_id: typing.Union[int, str]):
        """returns either movies with similar title than the user input
        or the movie which has the given id"""
        if isinstance(title_or_id, int):
            movie = self.movies.get(title_or_id)
            if movie is not None:
                embed = self.create_movie_embed(movie)
                await ctx.send(embed=embed)
                return

        possible_titles = []
        title = str(title_or_id)
        for movie in self.movies.values():
            prob = SequenceMatcher(None, title, movie.title).ratio()

            if prob >= 0.6:
                rep = f"`{movie.id}` | {movie.title}"
                possible_titles.append(rep)

        if possible_titles:
            desc = "\n".join(possible_titles)
        else:
            desc = "no movies found"

        embed = discord.Embed(description=desc)
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Netflix(bot))
