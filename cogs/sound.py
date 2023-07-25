from discord.ext import commands
from pydub import AudioSegment
import functools
import logging
import discord
import asyncio
import os
import io

logger = logging.getLogger('self')


class Sounds(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.lock = []
        self.cache = {}
        self.config = self.bot.config

    @commands.Cog.listener()
    async def on_ready(self):
        print("Joining voice channels...")

        for guild in self.bot.guilds:
            vc = guild.voice_client

            active = self.config.get('sound', guild.id)
            if not active:
                continue

            most_people = self.get_fullest_channel(guild)

            if most_people is not None:
                if vc:
                    await vc.move_to(most_people)
                else:
                    await most_people.connect()

                logger.debug(f'connected to {most_people}')

    def get_fullest_channel(self, guild):
        ignored = self.config.get('hidden', guild.id, [])

        visible_channel = []
        for channel in guild.voice_channels:
            if channel == guild.afk_channel:
                continue
            elif channel.id in ignored:
                continue
            elif not channel.permissions_for(guild.me).connect:
                continue
            else:
                visible_channel.append(channel)

        def key(c):
            return len([m for m in c.members if not m.bot])

        listed = sorted(visible_channel, key=key, reverse=True)
        if listed and [m for m in listed[0].members if not m.bot]:
            return listed[0]
        else:
            return None

    def get_sound_path(self, user_id, state):
        path = f"{self.bot.path}/data/{state}/{user_id}.mp3"

        if os.path.isfile(path):
            return path
        else:
            return f"{self.bot.path}/data/{state}/default.wav"

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if before.channel == after.channel:
            return

        guild = member.guild
        vc = guild.voice_client

        active = self.config.get('sound', guild.id)
        if not active:
            return

        most_people = self.get_fullest_channel(guild)

        if vc and most_people is None:
            logger.debug(f'disconnected from {vc.channel}')
            await vc.disconnect(force=True)
            return

        if most_people is not None and guild.me not in most_people.members:
            await asyncio.sleep(1)

            if vc is None:
                await most_people.connect()

            else:
                member_ids = [m.id for m in after.channel.members]
                self.cache[guild] = member_ids
                await vc.move_to(most_people)

            logger.debug(f'connected to {most_people}')
            return

        if vc and vc.channel in (before.channel, after.channel):
            # bot join connect which seems to take a while internally
            if guild.me == member:
                while not vc.is_connected():
                    await asyncio.sleep(0.2)

                else:
                    member_ids = self.cache.get(guild, [])
                    ids = [m.id for m in vc.channel.members]

                    if sorted(member_ids) == sorted(ids):
                        print("same members CACHE HIT")
                        return

            if not vc.is_playing() and vc.is_connected():
                state = 'connect' if after.channel == vc.channel else 'disconnect'
                sound_path = self.get_sound_path(member.id, state)

                logger.debug(f'playing {state}-sound from {member}')
                sound = discord.FFmpegPCMAudio(source=sound_path)
                source = discord.PCMVolumeTransformer(sound, 0.18)
                vc.play(source=source)

    @staticmethod
    def edit_track(data, begin, to):
        song = AudioSegment.from_file(io.BytesIO(data), format="mp3")
        song = song[int(begin * 1000):int(to * 1000)]
        new_file = io.BytesIO()
        song.export(new_file, format='mp3')
        return song, new_file

    async def save_track(self, ctx, state, song):
        raw_path = "{0.bot.path}/data/{1}/{0.author.id}.mp3"
        path = raw_path.format(ctx, state)
        func = functools.partial(song.export, path)
        await self.bot.loop.run_in_executor(None, func)
        self.cache.pop(ctx.author.id)

    async def wait_for(self, ctx, reply):
        def check(m):
            if ctx.author == m.author and ctx.channel == m.channel:
                if m.content.lower() in ["y", "n"]:
                    return True

        try:
            msg = await self.bot.wait_for('message', check=check, timeout=30)
            if msg.content.lower() == "y":
                return True
            else:
                msg = "Reinvoke the command without your file now and change parameters"
                await ctx.send(msg)

        except asyncio.TimeoutError:
            await reply.edit(content="The time has expired...")
            self.cache.pop(ctx.author.id)

    @commands.command(name="connect", aliases=["disconnect"])
    async def connect_(self, ctx, begin: float = None, end: float = None):
        """sets your current sound when you pass an audio file
        with the command and state a point of time in seconds
        for the beginning and end of your sound, if you don't
        pass anything your sound will be deleted"""
        state = ctx.invoked_with.lower()

        if begin is not None:
            if ((end or 5) - begin) > 5:
                msg = "The maximum duration is 5 seconds"
                await ctx.send(msg)
                return

            if ctx.message.attachments:
                url = ctx.message.attachments[0].url

                async with self.bot.session.get(url) as file:
                    data = await file.read()
                    self.cache[ctx.author.id] = data

            else:
                cached_data = self.cache.get(ctx.author.id)
                if cached_data is None:
                    msg = "There's nothing in cache, you need to\n" \
                          "upload your audio file with the command"
                    await ctx.send(msg)
                    return

            func = functools.partial(self.edit_track, data, begin, end)
            song, new_file = await self.bot.loop.run_in_executor(None, func)

            msg = "Do you want to use this version? Y/N"
            file = discord.File(new_file, "version.mp3")
            reply = await ctx.send(msg, file=file)

            response = await self.wait_for(ctx, reply)
            if response is True:
                path = f"{self.bot.path}/data/{state}/{ctx.author.id}.mp3"
                func = functools.partial(song.export, path)
                await self.bot.loop.run_in_executor(None, func)
                self.cache.pop(ctx.author.id)

                await ctx.send(f"Your {state} sound has been set up")

        else:
            try:
                path = f"{self.bot.path}/data/{state}/{ctx.author.id}.mp3"
                func = functools.partial(os.remove, path)
                await self.bot.loop.run_in_executor(None, func)
                await ctx.send(f"Your {state} sound has been reset")

            except FileNotFoundError:
                await ctx.send(f"You don't have a {state} sound")


async def setup(bot):
    await bot.add_cog(Sounds(bot))
