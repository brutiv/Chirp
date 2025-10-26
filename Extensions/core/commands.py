from interactions import slash_command, Extension, listen

class CoreCommands(Extension):

    @listen()
    async def on_guild_join(self, event):
        guild = event.guild
        blacklisted_guilds = await self.bot.mem_cache.get("blacklisted_guilds") or []
        if guild.id in blacklisted_guilds:
            await guild.leave()
            return
        if not self.bot.ready:
            return
        studio_server_id = 1430984964283043916
        studio_server = self.client.get_guild(studio_server_id)
        if studio_server:
            bot_logs_channel_id = 1430984965826543733
            bot_logs_channel = studio_server.get_channel(bot_logs_channel_id)
            if bot_logs_channel:
                await bot_logs_channel.send(embed={
                    "title": "Joined New Guild",
                    "fields": [
                        {"name": "Guild Name", "value": guild.name, "inline": True},
                        {"name": "Guild ID", "value": str(guild.id), "inline": True},
                        {"name": "Member Count", "value": str(guild.member_count), "inline": True},
                    ]
                })

    @listen()
    async def on_guild_left(self, event):
        guild = event.guild
        blacklisted_guilds = await self.bot.mem_cache.get("blacklisted_guilds") or []
        if guild.id in blacklisted_guilds:
            await guild.leave()
            return
        if not self.bot.ready:
            return
        studio_server_id = 1430984964283043916
        studio_server = self.client.get_guild(studio_server_id)
        if studio_server:
            bot_logs_channel_id = 1430984965826543733
            bot_logs_channel = studio_server.get_channel(bot_logs_channel_id)
            if bot_logs_channel:
                await bot_logs_channel.send(embed={
                    "title": "Left Guild",
                    "fields": [
                        {"name": "Guild Name", "value": guild.name, "inline": True},
                        {"name": "Guild ID", "value": str(guild.id), "inline": True},
                        {"name": "Member Count", "value": str(guild.member_count), "inline": True},
                    ]
                })

    @slash_command(name="ping", description="Replies with Pong!")
    async def ping(self, ctx):
        await ctx.defer(ephemeral=True)
        await ctx.send(embed={"description": f"<:check:1430728952535842907> Pong! Latency: {round(self.bot.latency * 1000)}ms"})

def setup(bot):
    CoreCommands(bot)