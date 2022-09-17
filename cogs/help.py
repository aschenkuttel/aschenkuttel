from discord.ext import commands


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help")
    async def help_(self, ctx, category=None):
        """this message"""
        if category is None:
            names = []
            for name, cog in self.bot.cogs.items():
                if hasattr(cog, 'hidden') or name == "Help":
                    continue

                cmds = cog.get_commands()
                if not cmds:
                    continue

                names.append(name)

            names.append("")
            names.append(f"# {ctx.prefix}help category for their commands")
            msg = "```markdown\n{}\n```".format("\n".join(names))
            await ctx.send(msg)

        else:
            cog = self.bot.get_cog(category.capitalize())

            if cog is None:
                msg = f"There's no category named `{category}`"
                await ctx.send(msg)
                return

            cmds = list(cog.get_commands())

            batch = []
            for index, cmd in enumerate(cmds):
                if isinstance(cmd, commands.Group):
                    for sub_cmd in cmd.commands:
                        cmds.insert(index + 1, sub_cmd)

                if cmd.help is None:
                    continue

                if cmd.parent is not None:
                    name = f"{ctx.prefix}{cmd.parent.name} {cmd.name}"
                else:
                    name = f"{ctx.prefix}{cmd.name}"

                for ali in cmd.aliases:
                    name += f"/{ali}"

                batch.append(name)

                docstring = cmd.help.replace("\n", "\n# ")
                batch.append(f"# {docstring}")

            if batch:
                batch.insert(0, '')
                batch.insert(1, f"{cog.qualified_name}:")

            help_content = '\n'.join(batch)
            await ctx.send(f"```markdown\n{help_content}\n```")


async def setup(bot):
    await bot.add_cog(Help(bot))
