from discord import app_commands


class InvalidSummonerName(app_commands.CheckFailure):
    def __init__(self, arg):
        self.arg = arg
        super().__init__(f"summoner name must be in the format `name#tag`")


class SummonerNotFound(app_commands.CheckFailure):
    def __init__(self, arg):
        self.arg = arg
        super().__init__(f"summoner `{self.arg}` not found")


class NoSummonerLinked(app_commands.CheckFailure):
    def __init__(self, member):
        self.member = member
        super().__init__(f"{self.member.name} has no connected summoner")


class InvalidRiotResponse(app_commands.CheckFailure):
    def __init__(self, status_code):
        self.status_code = status_code
        super().__init__(f"Invalid Riot API Response with status code: {status_code}")


class NoBirthday(app_commands.CheckFailure):
    def __init__(self):
        super().__init__("missing birthday")


class YoutubeVideoNotFound(app_commands.CheckFailure):
    def __init__(self):
        super().__init__("youtube video not found")


class YoutubeVideoTooBig(app_commands.CheckFailure):
    def __init__(self, file_size):
        super().__init__(f"youtube video exceeds 20MB limit with an estimated size of {file_size}MB")


all_errors = (
    InvalidSummonerName,
    SummonerNotFound,
    NoSummonerLinked,
    InvalidRiotResponse,
    NoBirthday,
    YoutubeVideoNotFound,
    YoutubeVideoTooBig
)
