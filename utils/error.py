from discord.ext import commands


class SummonerNotFound(commands.CheckFailure):
    def __init__(self, arg):
        self.arg = arg
        super().__init__(f"summoner {self.arg} not found")


class NoSummonerLinked(commands.CheckFailure):
    def __init__(self, member):
        self.member = member
        super().__init__(f"{self.member.name} has no connected summoner")


class NoRiotResponse(commands.CheckFailure):
    def __init__(self, ):
        super().__init__("Riot API not responding")


class WrongDateFormat(commands.CheckFailure):
    def __init__(self):
        super().__init__("invalid date format")


class NoBirthday(commands.CheckFailure):
    def __init__(self):
        super().__init__("missing birthday")


class YoutubeVideoNotFound(commands.CheckFailure):
    def __init__(self):
        super().__init__("youtube video not found")


class YoutubeVideoTooBig(commands.CheckFailure):
    def __init__(self):
        super().__init__("youtube videos can't be bigger than 20MB")