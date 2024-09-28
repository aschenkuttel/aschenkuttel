reminder = '''
CREATE TABLE IF NOT EXISTS reminder (
id INTEGER PRIMARY KEY AUTOINCREMENT,
author_id BIGINT, channel_id BIGINT,
creation BIGINT, expiration BIGINT,
reason TEXT)
'''

starboard = '''
CREATE TABLE IF NOT EXISTS starboard (
guild_id BIGINT, channel_id BIGINT,
message_id BIGINT, author_id BIGINT,
date TIMESTAMP, content TEXT, attachment TEXT)
'''

movies = '''
CREATE TABLE IF NOT EXISTS movies (
id BIGINT PRIMARY KEY, title TEXT,
image_url TEXT, description TEXT,
rating FLOAT, year SMALLINT,
runtime INT, seconds INT)
'''

summoner = '''
CREATE TABLE IF NOT EXISTS summoner (
user_id BIGINT PRIMARY KEY, id TEXT,
account_id TEXT, puuid TEXT, name TEXT, tag CHAR(5),
icon_id INT, level SMALLINT, wins SMALLINT,
losses SMALLINT, tier TEXT, rank TEXT,
lp SMALLINT, mmr SMALLINT, last_match_id BIGINT)
'''

champions = '''
CREATE TABLE IF NOT EXISTS champions (
id INT PRIMARY KEY, riot_id TEXT, name TEXT,
description TEXT, data JSON)
'''

parties = '''
CREATE TABLE IF NOT EXISTS watch_parties (
id INTEGER PRIMARY KEY AUTOINCREMENT,
name TEXT, guild_id BIGINT, channel_id BIGINT,
author_id BIGINT, participants JSON,
next_date TIMESTAMP, recurring INT,
UNIQUE (guild_id, author_id))
'''

user_data = '''
CREATE TABLE IF NOT EXISTS userdata (
id BIGINT PRIMARY KEY, birthday TIMESTAMP,
timezone TEXT)
'''

queries = (reminder, starboard, movies, summoner, champions, parties, user_data)