from interactions import Extension, Timestamp
from interactions.ext.prefixed_commands import prefixed_command
from datetime import datetime, timezone

devs = {856196104385986560, 1362053982444454119}

class DeveloperCommands(Extension):
	@prefixed_command()
	async def blacklist_server(self, ctx, guild_id: int, *, reason: str = "No reason provided"):
		if ctx.author.id not in devs:
			return

		guild = await self.client.fetch_guild(guild_id)
		if not guild:
			await ctx.send(f"Guild with ID {guild_id} not found.")
			return

		blacklisted_guilds = await self.bot.mem_cache.get("blacklisted_guilds")

		if not blacklisted_guilds:
			doc = await self.bot.db.blacklisted_guilds.find({}).to_list(length=None)
			blacklisted_guilds = {item["guild_id"]: item.get("reason", "No reason provided") for item in doc}
			await self.bot.mem_cache.set("blacklisted_guilds", blacklisted_guilds)

		if guild_id in blacklisted_guilds:
			await ctx.send(f"Guild ID `{guild_id}` is already blacklisted for reason `{blacklisted_guilds[guild_id]}`.")
			return

		blacklisted_guilds[guild_id] = reason
		await self.bot.mem_cache.set("blacklisted_guilds", blacklisted_guilds)

		await self.bot.db.blacklisted_guilds.insert_one({
			"guild_id": guild_id,
			"reason": reason,
			"blacklisted_at": ctx.message.created_at,
			"blacklisted_by": ctx.author.id
		})

		try:
			if guild := self.client.get_guild(guild_id):
				await guild.leave()
		except Exception:
			pass

		await ctx.send(f"Guild ID `{guild_id}` has been blacklisted for reason `{reason}` and left if present.")

	@prefixed_command()
	async def unblacklist_server(self, ctx, guild_id: int):
		if ctx.author.id not in devs:
			return
		blacklisted_guilds =await self.bot.mem_cache.get("blacklisted_guilds") or []
		if not blacklisted_guilds:
			doc = await self.bot.db.blacklisted_guilds.find({}).to_list(length=None)
			blacklisted_guilds = [item["guild_id"] for item in doc]
			await self.bot.mem_cache.set("blacklisted_guilds", blacklisted_guilds)
		if guild_id in blacklisted_guilds:
			blacklisted_guilds.remove(guild_id)
			await self.bot.mem_cache.set("blacklisted_guilds", blacklisted_guilds)
			await self.bot.db.blacklisted_guilds.delete_one({"guild_id": guild_id})
			await ctx.send(f"Guild ID {guild_id} has been removed from the blacklist.")
		else:
			await ctx.send(f"Guild ID {guild_id} is not in the blacklist.")

	@prefixed_command()
	async def view_blacklisted_server(self, ctx, guild_id: int):
		if ctx.author.id not in devs:
			return
		blacklisted_guild = await self.bot.db.blacklisted_guilds.find_one({"guild_id": guild_id})
		if blacklisted_guild:
			timestamp = blacklisted_guild.get("blacklisted_at")
			if timestamp:
				try:
					timestamp = str(Timestamp.fromdatetime(timestamp))
				except Exception:
					timestamp = "Unknown"
			else:
				timestamp = "Unknown"
			blacklisted_by_user_id = blacklisted_guild.get("blacklisted_by")
			blacklisted_by_user = f"<@{blacklisted_by_user_id}>" if blacklisted_by_user_id else "Unknown"
			await ctx.send(f"Guild ID `{guild_id}` is blacklisted for reason: `{blacklisted_guild.get('reason', 'No reason provided')}`.\nBlacklisted at: {timestamp}\nBlacklisted by User: {blacklisted_by_user} `({blacklisted_by_user_id})`")
		else:
			await ctx.send(f"Guild ID `{guild_id}` is not blacklisted.")

	@prefixed_command()
	async def load(self, ctx, extension_name: str):
		if ctx.author.id not in devs:
			return
		try:
			self.client.load_extension(f"Extensions.{extension_name}")
			await ctx.send(f"Extension '{extension_name}' loaded successfully.")
		except Exception as e:
			await ctx.send(f"Failed to load extension '{extension_name}': {e}")

	@prefixed_command()
	async def unload(self, ctx, extension_name: str):
		if ctx.author.id not in devs:
			return
		try:
			self.client.unload_extension(f"Extensions.{extension_name}")
			await ctx.send(f"Extension '{extension_name}' unloaded successfully.")
		except Exception as e:
			await ctx.send(f"Failed to unload extension '{extension_name}': {e}")

	@prefixed_command()
	async def reload(self, ctx, extension_name: str):
		if ctx.author.id not in devs:
			return
		try:
			self.client.reload_extension(f"Extensions.{extension_name}")
			await ctx.send(f"Extension '{extension_name}' reloaded successfully.")
		except Exception as e:
			await ctx.send(f"Failed to reload extension '{extension_name}': {e}")
			
	@prefixed_command()
	async def leave_guild(self, ctx, guild_id: int):
		if ctx.author.id not in devs:
			return
		guild = self.client.get_guild(guild_id)
		if guild:
			await guild.leave()
			await ctx.send(f"Left guild '{guild.name}' (ID: {guild_id}).")
		else:
			await ctx.send(f"Guild with ID {guild_id} not found.")
	
def setup(client):
	DeveloperCommands(client)
