from discord.ext import commands
from pydub import AudioSegment
from pytube import YouTube
from discord import app_commands
import functools
import logging
import discord
import asyncio
import utils
import os
import io

logger = logging.getLogger('self')


class EditTimespan(discord.ui.Modal, title='Edit Timespan'):
    def __init__(self, view):
        super().__init__()
        self.view = view

    begin = discord.ui.TextInput(
        label='Begin',
        placeholder='0.0',
    )

    end = discord.ui.TextInput(
        label='End',
        placeholder='5.0',
    )

    async def on_submit(self, interaction):
        try:
            difference = float(self.end.value) - float(self.begin.value)
        except ValueError:
            await interaction.followup.send('input must be a number', ephemeral=True, delete_after=5)
            return

        if difference < 2:
            await interaction.followup.send("join-sound can't be shorter than 1 second", ephemeral=True, delete_after=5)
            return

        elif difference > 5:
            await interaction.followup.send("join-sound can't be longer than 5 seconds", ephemeral=True, delete_after=5)
            return

        self.view.begin = float(self.begin.value)
        self.view.end = float(self.end.value)

        for child in self.view.children:
            child.disabled = True

        await interaction.response.edit_message(view=self.view)

        func = functools.partial(self.view.edit_track)
        await self.view.bot.loop.run_in_executor(None, func)

        for child in self.view.children:
            child.disabled = False

        message = await interaction.original_response()
        await message.edit(attachments=[self.view.file], view=self.view)

    async def on_error(self, interaction, error: Exception) -> None:
        raise error
        logger.debug(f'Error with {interaction.data}: {error}')
        await interaction.followup.send('Oops! Something went wrong.', ephemeral=True)


class EditSoundView(discord.ui.View):
    def __init__(self, interaction, action, bytes_io):
        super().__init__(timeout=600)
        self.bot = interaction.client
        self.interaction = interaction
        self.action = action
        self.begin = 0.0
        self.end = 0.0
        self.song = None
        self.bytes_io = bytes_io
        self.file = discord.File(self.bytes_io, self.display_range)

    @property
    def display_range(self):
        return f"begin_{self.begin}_end_{self.end}.mp3"

    def edit_track(self):
        self.bytes_io.seek(0)
        song = AudioSegment.from_file(self.bytes_io)
        self.song = song[int(self.begin * 1000):int(self.end * 1000)]

        span_bytes_io = io.BytesIO()
        self.song.export(span_bytes_io, format='mp3')
        self.file = discord.File(span_bytes_io, self.display_range)

    async def save_track(self, user_id):
        raw_path = "{0}/data/{1}/{2}.mp3"
        path = raw_path.format(self.bot.path, self.action, user_id)

        func = functools.partial(self.song.export, path)
        await self.bot.loop.run_in_executor(None, func)

        span_bytes_io = io.BytesIO()
        self.song.export(span_bytes_io, format='mp3')
        return discord.File(span_bytes_io, "success.mp3")

    async def destroy(self, interaction=None):
        self.stop()
        self.bytes_io.close()
        self.file.close()

        if interaction is not None:
            await interaction.response.edit_message(view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, custom_id="cancel")
    async def cancel(self, interaction, _):
        await self.destroy(interaction)

    @discord.ui.button(label="Edit Timespan", style=discord.ButtonStyle.primary, custom_id="edit")
    async def edit(self, interaction, _):
        modal = EditTimespan(self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success, custom_id="confirm")
    async def confirm(self, interaction, _):
        if self.song is None:
            await interaction.response.send_message("You need to edit the timespan first", ephemeral=True)
            return

        file = await self.save_track(interaction.user.id)
        await interaction.response.edit_message(view=None, attachments=[file])

        await self.destroy()

    async def on_timeout(self) -> None:
        await self.interaction.edit_original_message(view=None)
        await self.destroy()


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
                if after.channel is not None:
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
    def download_youtube(url):
        video = YouTube(url)

        try:
            file_size = video.streams.get_audio_only().filesize_mb
        except Exception as error:
            logger.debug(f"pytube error: {error}")
            raise utils.YoutubeVideoNotFound()

        if file_size > 20:
            logger.debug(f"{url} exceeds 20mb")
            raise utils.YoutubeVideoTooBig(file_size)

        buffer = io.BytesIO()
        video.streams.get_audio_only().stream_to_buffer(buffer)
        buffer.seek(0)
        return buffer

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

    join_sound = app_commands.Group(name="join-sound", description="all commands related to your join-sound")

    @join_sound.command(name="youtube", description="sets your join-sound with a youtube video")
    @app_commands.describe(youtube_url="the youtube url of the sound you want to use")
    async def join_sound_edit(self, interaction, youtube_url: str):
        await interaction.response.defer(ephemeral=interaction.guild is not None)

        func = functools.partial(self.download_youtube, youtube_url)
        bytes_io = await self.bot.loop.run_in_executor(None, func)

        view = EditSoundView(interaction, "connect", bytes_io)
        await interaction.followup.send(file=view.file, view=view)

    @join_sound.command(name="local", description="sets your join-sound with a local file")
    async def join_sound_local(self, interaction, file: discord.Attachment):
        await interaction.response.defer(ephemeral=interaction.guild is not None)

        async with self.bot.session.get(file.url) as file:
            data = await file.read()
            bytes_io = io.BytesIO(data)

        view = EditSoundView(interaction, "connect", bytes_io)
        await interaction.followup.send(file=view.file, view=view)

    @join_sound.command(name="reset", description="resets your join-sound")
    async def join_sound_reset(self, interaction):
        try:
            path = f"{self.bot.path}/data/connect/{interaction.user.id}.mp3"
            func = functools.partial(os.remove, path)
            await self.bot.loop.run_in_executor(None, func)
            await interaction.response.send_message("Your join-sound has been reset")

        except FileNotFoundError:
            await interaction.response.send_message("You don't have a join-sound")

    leave_sound = app_commands.Group(name="leave-sound", description="all commands related to your leave-sound")

    @leave_sound.command(name="youtube", description="sets your leave-sound with a youtube video")
    @app_commands.describe(youtube_url="the youtube url of the sound you want to use")
    async def leave_sound_edit(self, interaction, youtube_url: str):
        await interaction.response.defer(ephemeral=interaction.guild is not None)

        func = functools.partial(self.download_youtube, youtube_url)
        bytes_io = await self.bot.loop.run_in_executor(None, func)

        view = EditSoundView(interaction, "disconnect", bytes_io)
        await interaction.followup.send(file=view.file, view=view)

    @leave_sound.command(name="local", description="sets your leave-sound with a local file")
    async def leave_sound_local(self, interaction, file: discord.Attachment):
        await interaction.response.defer(ephemeral=interaction.guild is not None)

        async with self.bot.session.get(file.url) as file:
            data = await file.read()
            bytes_io = io.BytesIO(data)

        view = EditSoundView(interaction, "disconnect", bytes_io)
        await interaction.followup.send(file=view.file, view=view)

    @leave_sound.command(name="reset", description="resets your leave-sound")
    async def leave_sound_reset(self, interaction):
        try:
            path = f"{self.bot.path}/data/disconnect/{interaction.user.id}.mp3"
            func = functools.partial(os.remove, path)
            await self.bot.loop.run_in_executor(None, func)
            await interaction.response.send_message("Your leave-sound has been reset")

        except FileNotFoundError:
            await interaction.response.send_message("You don't have a leave-sound")


async def setup(bot):
    await bot.add_cog(Sounds(bot))
