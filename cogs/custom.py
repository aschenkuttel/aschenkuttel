from discord.ext import commands, tasks
from pydub import AudioSegment
import functools
import discord
import asyncio
import utils
import io
import os


class Custom(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._cache = {}
        self._watch = True
        self.cd = utils.Cooldown()
        self.cooldown_loop.start()
        self.invisible_channel = [644278634156261406]
        self.watchtower.start()

    @tasks.loop(seconds=10)
    async def cooldown_loop(self):
        self.cd.clear()

    def get_custom(self, user_id, folder):
        path = f"{self.bot.path}/data/{folder}/{user_id}.mp3"
        return path if os.path.isfile(path) else None

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        vc = member.guild.voice_client
        me = member.guild.me
        if member == self.bot.user or me.voice is None:
            return
        if before.channel == after.channel or vc is None:
            return
        if self.cd.update(member.id) is False:
            return
        if me.voice.channel in (before.channel, after.channel):
            state = "connect" if after.channel == me.voice.channel else "disconnect"
            custom = self.get_custom(member.id, state)
            file = custom or f"{self.bot.path}/data/{state}/default.wav"
            if not vc.is_connected():
                vc = await me.voice.channel.connect()
            if not vc.is_playing():
                source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(source=file), 0.18)
                vc.play(source=source)

    @tasks.loop(minutes=2)
    async def watchtower(self):
        if self._watch is False:
            return

        for guild in self.bot.guilds:

            if guild.id != 213992901263228928:
                continue

            channels = []
            for channel in guild.voice_channels:
                if channel == guild.afk_channel:
                    continue
                elif channel.id in self.invisible_channel:
                    continue
                channels.append(channel)

            listed = sorted(channels, key=lambda c: len(c.members), reverse=True)
            full = listed[0] if listed and listed[0].members else None
            if not full:
                continue

            vc = guild.voice_client
            if guild.me in full.members:

                members = [guild.me]
                for channel in listed:
                    for member in channel.members:
                        if not member.bot:
                            members.append(member)

                if len(members) == 1:
                    await vc.disconnect()

                elif len(full.members) == 1 and listed[1].members:
                    await vc.move_to(listed[1])

            else:
                if not vc:
                    await full.connect()
                else:
                    await vc.move_to(full)

    @watchtower.before_loop
    async def before_watch(self):
        await self.bot.wait_until_ready()

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
            msg = "Die Datei darf maximal 5 Sekunden lang sein"
            return await ctx.send(msg)

        if ctx.message.attachments:
            url = ctx.message.attachments[0].url
            async with self.bot.session.get(url) as file:
                data = await file.read()
                self._cache[ctx.author.id] = data
        else:
            data = self._cache.get(ctx.author.id)
            if data is None:
                msg = "Es ist keine Datei im Cache vorhanden"
                return await ctx.send(msg)

        command = ctx.invoked_with
        func = functools.partial(self.edit_track, data, begin, to)
        song, new_file = await self.bot.loop.run_in_executor(None, func)
        msg = "Möchtest du diese Version übernehmen? Y/N"
        await ctx.send(msg, file=discord.File(new_file, "version.mp3"))
        try:
            def check(m):
                if ctx.author == m.author and ctx.channel == m.channel:
                    if m.content.lower() in ["y", "n"]:
                        return True

            msg = await self.bot.wait_for('message', check=check, timeout=30)
            if msg.content.lower() == "y":
                song.export(f"{self.bot.path}/data/{ctx.invoked_with}/{ctx.author.id}.mp3")
                await ctx.send(f"Dein {command.capitalize()}-Sound wurde aktualisiert")
                self._cache.pop(ctx.author.id)
            else:
                return
        except asyncio.TimeoutError:
            return

    @commands.command(name="clear")
    async def clear_(self, ctx, state):
        if state not in ["connect", "disconnect"]:
            return
        try:
            os.remove(f"{self.bot.path}/data/{state}/{ctx.author.id}.mp3")
        except FileNotFoundError:
            msg = f"Du besitzt keinen custom {state.capitalize()}-Sound"
            await ctx.send(msg)


def setup(bot):
    bot.add_cog(Custom(bot))
