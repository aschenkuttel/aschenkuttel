from discord.ext import commands
from pydub import AudioSegment
import functools
import discord
import asyncio
import os
import io


class Sounds(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.lock = []
        self.cache = {}
        self.config = self.bot.config

    def get_fullest_channel(self, guild):
        ignored = self.config.get('hidden', guild.id)

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
        return listed[0]

    def get_sound_path(self, user_id, state):
        path = f"{self.bot.path}/data/{state}/{user_id}.mp3"

        if os.path.isfile(path):
            return path
        else:
            f"{self.bot.path}/data/{state}/default.wav"

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.guild.id != 213992901263228928:
            return

        if before.channel == after.channel:
            return

        guild = member.guild
        vc = guild.voice_client

        if guild in self.lock:
            return

        active = self.config.get('sounds', guild.id)
        if not active:
            if vc:
                await vc.disconnect()
            return

        # member joins in channel
        if after.channel is not None:
            most_people = self.get_fullest_channel(guild)

            if guild.me not in most_people.members:
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

                return

        # if after channel is None (leave) looks if its connected and the only
        # one in the channel and leaves if since we handle channel moves above
        if vc is None:
            return

        if len(vc.channel.members) == 1:
            await vc.disconnect()
            return

        if vc.channel in (before.channel, after.channel):
            state = "connect" if after.channel == vc.channel else "disconnect"
            sound_path = self.get_sound_path(member.id, state)

            # bot join connect which takes a while internally
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

    @commands.command(name="connect", aliases=["disconnect"])
    async def custom_(self, ctx, begin: float, to: float):
        if not 1 <= to - begin <= 5:
            msg = "Die Datei darf maximal 5 Sekunden lang sein :/"
            await ctx.send(msg)
            return

        if ctx.message.attachments:
            url = ctx.message.attachments[0].url
            async with self.bot.session.get(url) as file:
                data = await file.read()
                self.cache[ctx.author.id] = data

        else:
            data = self.cache.get(ctx.author.id)
            if data is None:
                msg = "Es ist keine Datei im Cache vorhanden"
                await ctx.send(msg)
                return

        func = functools.partial(self.edit_track, data, begin, to)
        song, new_file = await self.bot.loop.run_in_executor(None, func)

        msg = "Möchtest du diese Version übernehmen? Y/N"
        reply = await ctx.send(msg, file=discord.File(new_file, "version.mp3"))

        def check(m):
            if ctx.author == m.author and ctx.channel == m.channel:
                if m.content.lower() in ["y", "n"]:
                    return True

        try:
            msg = await self.bot.wait_for('message', check=check, timeout=30)

            if msg.content.lower() == "y":
                song.export(f"{self.bot.path}/data/{ctx.invoked_with}/{ctx.author.id}.mp3")
                msg = f"Dein {ctx.invoked_with.capitalize()}-Sound wurde eingerichtet"
                self.cache.pop(ctx.author.id)

            else:
                msg = "Bitte gebe nun den gleichen Command mit veränderten Zeiten an,\n" \
                      "deine Datei muss dabei nicht erneut hochgeladen werden."

            await ctx.send(msg)

        except asyncio.TimeoutError:
            await reply.edit(content="Die Zeit ist abgelaufen...")
            self.cache.pop(ctx.author.id)
            return

    @commands.command(name="clear")
    async def clear_(self, ctx, state):
        if state not in ["connect", "disconnect"]:
            msg = "Du musst entweder \"connect\" oder \"disconnect\" angeben"
            await ctx.send(msg)
            return

        try:
            folder = state.lower()
            filename = f"{ctx.author.id}.mp3"
            os.remove(f"{self.bot.path}/data/{folder}/{filename}")

        except FileNotFoundError:
            msg = f"Für dich ist kein {state.capitalize()}-Sound hinterlegt"
            await ctx.send(msg)


def setup(bot):
    bot.add_cog(Sounds(bot))
