from interactions import Extension
from interactions.ext.prefixed_commands import prefixed_command

class DeveloperCommands(Extension):

	@prefixed_command()
	async def load(self, ctx, extension_name: str):
		if ctx.author.id != 856196104385986560:
			return
		try:
			self.client.load_extension(f"Extensions.{extension_name}")
			await ctx.send(f"Extension '{extension_name}' loaded successfully.")
		except Exception as e:
			await ctx.send(f"Failed to load extension '{extension_name}': {e}")

	@prefixed_command()
	async def unload(self, ctx, extension_name: str):
		if ctx.author.id != 856196104385986560:
			return
		try:
			self.client.unload_extension(f"Extensions.{extension_name}")
			await ctx.send(f"Extension '{extension_name}' unloaded successfully.")
		except Exception as e:
			await ctx.send(f"Failed to unload extension '{extension_name}': {e}")

	@prefixed_command()
	async def reload(self, ctx, extension_name: str):
		if ctx.author.id != 856196104385986560:
			return
		try:
			self.client.reload_extension(f"Extensions.{extension_name}")
			await ctx.send(f"Extension '{extension_name}' reloaded successfully.")
		except Exception as e:
			await ctx.send(f"Failed to reload extension '{extension_name}': {e}")
	
def setup(client):
	DeveloperCommands(client)