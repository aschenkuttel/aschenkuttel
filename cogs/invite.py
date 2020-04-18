from discord.ext import commands
import discord


class Invites(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = {}

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            data = []
            try:
                for invite in await guild.invites():
                    data.append(invite)
                self.data.update({guild.id: data})
            except discord.Forbidden:
                continue

    @commands.Cog.listener()
    async def on_member_join(self, member):
        data = []
        for invite in await member.guild.invites():
            data.append(invite)
        old = self.data.get(member.guild.id)
        result = None
        for entry in data:
            for old_entry in old:
                a = entry.uses == old_entry.uses + 1 and entry == old_entry
                b = entry not in old and entry.uses == 1
                c = old_entry not in data and old_entry.uses == 0
                if a or b or c:
                    result = entry if not c else old_entry
        if result:
            original_invite = result
        else:
            async for entry in member.guild.audit_logs(
                    limit=20, action=discord.AuditLogAction.invite_create):
                if entry.after.max_uses == 1 and entry.after.code not in [iv.code for iv in data]:
                    original_invite = entry
                    break
            else:
                print("nothing found")
        self.data[member.guild.id] = data


def setup(bot):
    bot.add_cog(Invites(bot))
