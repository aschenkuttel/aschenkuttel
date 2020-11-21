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

    def get_fullest_channel(self, guild):
        ignored = self.config.get('hidden', guild.id, [])

        visible_channel = []
        for channel in guild.voice_channels:
            if channel == guild.afk_channel:
                continue
            elif channel.id in ignored:
                continue
            else:
                visible_channel.append(channel)

        def key(c):
            return len([m for m in c.members if not m.bot])

        listed = sorted(visible_channel, key=key, reverse=True)
        return listed[0] if listed and listed[0].members else None

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

        if guild in self.lock:
            return

        active = self.config.get('sound', guild.id)
        if not active:
            if vc:
                await vc.disconnect()
            return

        # member joins in channel
        if after.channel is not None:
            most_people = self.get_fullest_channel(guild)

            same_channel = after.channel == most_people
            not_inside = guild.me not in most_people.members

            if same_channel and not_inside:
                logger.debug(f'connecting to channel {most_people}')
                self.lock.append(guild)
                await asyncio.sleep(1)
                self.lock.remove(guild)

                if vc is None:
                    await most_people.connect()

                else:
                    member_ids = [m.id for m in before.channel.members]
                    member_ids.append(member.id)
                    self.cache[guild] = member_ids
                    await vc.move_to(most_people)

                logger.debug(f'connected to {most_people}')
                return

        elif vc is None:
            return

        # if after channel is None (leave) looks if its connected and the only
        # one in the channel and leaves if, since we handle channel moves above
        elif len(vc.channel.members) == 1:
            logger.debug(f'disconnected from {vc.channel}')
            await vc.disconnect()
            return

        if vc.channel in (before.channel, after.channel):
            state = 'connect' if after.channel == vc.channel else 'disconnect'
            sound_path = self.get_sound_path(member.id, state)

            # bot join connect which seems to take a while internally
            if guild.me == member:

                if before.channel is None:
                    while not vc.is_connected():
                        await asyncio.sleep(0.5)

                else:
                    member_ids = self.cache.get(guild, [])

                    ids = [m.id for m in vc.channel.members]
                    if sorted(member_ids) == sorted(ids):
                        return

            if not vc.is_playing():
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

    async def save_track(self, ctx, song):
        path = "{0.bot.path}/data/{0.invoked_with}/{0.author.id}.mp3"
        song.export(path.format(ctx))
        self.cache.pop(ctx.author.id)

    async def remove_track(self, state, user_id):
        try:
            path = f"{self.bot.path}/data/disconnect/{user_id}.mp3"
            func = functools.partial(os.remove, path)
            await self.bot.loop.run_in_executor(None, func)
            return f"Your {state} sound has been reset"

        except FileNotFoundError:
            return f"You don't have a {state} sound"

    @commands.command(name="connect")
    async def custom_(self, ctx, begin: float = None, end: float = 5.0):
        """either sets or removes your current sound"""
        if begin is not None:
            if (end - begin) > 5:
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

            def check(m):
                if ctx.author == m.author and ctx.channel == m.channel:
                    if m.content.lower() in ["y", "n"]:
                        return True

            try:
                msg = await self.bot.wait_for('message', check=check, timeout=30)

                if msg.content.lower() == "y":
                    await self.save_track(ctx, song)
                    await ctx.send("Your connect sound has been set up")

                else:
                    msg = "Reinvoke the command without your file now and change parameters"
                    await ctx.send(msg)

            except asyncio.TimeoutError:
                await reply.edit(content="The time has expired...")
                self.cache.pop(ctx.author.id)

        else:
            msg = await self.remove_track('connect', ctx.author.id)
            await ctx.send(msg)

    @commands.command(name="disconnect")
    async def disconnect_(self, ctx, begin: float = None, end: float = 5.0):
        """either sets or removes your current sound"""
        if begin is not None:
            if (end - begin) > 5:
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

            def check(m):
                if ctx.author == m.author and ctx.channel == m.channel:
                    if m.content.lower() in ["y", "n"]:
                        return True

            try:
                msg = await self.bot.wait_for('message', check=check, timeout=30)

                if msg.content.lower() == "y":
                    await self.save_track(ctx, song)
                    await ctx.send("Your disconnect sound has been set up")

                else:
                    msg = "Reinvoke the command without your file now and change parameters"
                    await ctx.send(msg)

            except asyncio.TimeoutError:
                await reply.edit(content="The time has expired...")
                self.cache.pop(ctx.author.id)

        else:
            msg = await self.remove_track('disconnect', ctx.author.id)
            await ctx.send(msg)


def setup(bot):
    bot.add_cog(Sounds(bot))
