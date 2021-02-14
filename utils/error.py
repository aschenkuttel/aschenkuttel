from discord.ext import commands


class SummonerNotFound(commands.CheckFailure):
    def __init__(self, arg):
        self.arg = arg
        super().__init__(f"summoner {self.arg} not found")


class NoSummonerLinked(commands.CheckFailure):
    def __init__(self, member):
        self.member = member
        super().__init__(f"{self.member.name} has no connected summoner")
