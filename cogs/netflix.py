from utils import Keyword, input_to_seconds
from discord.ext import commands, tasks
from data.credentials import RAPID_KEY
from difflib import SequenceMatcher
from discord import app_commands
from html import unescape
import datetime
import logging
import asyncio
import discord
import random
import ftfy

logger = logging.getLogger('self')


class Movie:
    def __init__(self, entry):
        if isinstance(entry, dict):
            self.id = int(entry['netflixid'])
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

    @property
    def url(self):
        return f"https://www.netflix.com/watch/{self.id}"

    @property
    def mention(self):
        return f"[{self.title}]({self.url})"

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

        now = datetime.datetime.now()
        params = {
            "q": f"-!1990,{now.year}-!0,5-!0,10-!0-!Movie-!German-!Any-!gt0",
            "t": "ns",
            "cl": "39",
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
        embed = discord.Embed(title=movie.title, url=movie.url, color=0xE50914)
        embed.set_thumbnail(url=movie.image_url)
        header = f"**Rating:** {movie.rating}\n" \
                 f"**Runtime:** {movie.runtime}\n" \
                 f"**Released:** {movie.year}"
        embed.description = f"{header}\n{movie.description}"
        embed.set_footer(text=f"{len(self.movies)} movies in database")
        return embed

    @app_commands.command(name="netflix", description="returns a random german netflix movie")
    @app_commands.describe(genre="the genre of the movie")
    @app_commands.describe(year="the year the movie was released with <, > or =")
    @app_commands.describe(rating="the rating of the movie in 1.0-5.0 with <, > or =")
    @app_commands.describe(runtime="the runtime of the movie in minutes with <, > or =")
    async def netflix_(self, interaction,
                       genre: str = None,
                       year: Keyword = None,
                       rating: Keyword = None,
                       runtime: Keyword = None):
        possible_movies = []
        await self._lock.wait()

        for movie in self.movies.values():
            if genre and genre not in movie.description:
                continue

            if rating and not rating.compare(movie.rating):
                continue

            if year and not year.compare(movie.year):
                continue

            if runtime:
                input_sec = input_to_seconds(runtime.value)
                if not runtime.compare(input_sec, movie.seconds):
                    continue

            possible_movies.append(movie)

        if not possible_movies:
            msg = "sadly no movies were able to meet your requirements"
            await interaction.response.send_message(msg, ephemeral=True)

        else:
            movie = random.choice(possible_movies)
            embed = self.create_movie_embed(movie)
            await interaction.response.send_message(embed=embed)

    @app_commands.command(name="movie",
                          description="returns either movies with similar title then the user input or the movie with given id")
    @app_commands.describe(identifier="the id or title of the movie")
    async def movie_(self, interaction, identifier: str):
        if identifier.isnumeric():
            movie = self.movies.get(int(identifier))

            if movie is not None:
                embed = self.create_movie_embed(movie)
                await interaction.response.send_message(embed=embed)
                return

        possible_titles = []
        for movie in self.movies.values():
            prob = SequenceMatcher(None, identifier, movie.title).ratio()

            if prob >= 0.6 or identifier.lower() in movie.title.lower():
                possible_titles.append(movie)

        if possible_titles:
            represents = []
            idc = sorted(possible_titles[:20], key=lambda m: m.id, reverse=True)

            for movie in idc:
                rep = f"`{movie.id}` | `{movie.year}` {movie.mention}"
                represents.append(rep)

            embed = discord.Embed(description="\n".join(represents))
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("no movies found")


async def setup(bot):
    await bot.add_cog(Netflix(bot))
