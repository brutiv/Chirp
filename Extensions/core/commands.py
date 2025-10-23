from interactions import slash_command, Extension

class CoreCommands(Extension):
    @slash_command(name="ping", description="Replies with Pong!")
    async def ping(self, ctx):
        await ctx.defer(ephemeral=True)
        await ctx.send(embed={"description": f"<:check:1430728952535842907> Pong! Latency: {round(self.bot.latency * 1000)}ms"})

def setup(bot):
    CoreCommands(bot)