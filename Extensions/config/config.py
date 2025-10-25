from interactions import Extension, Modal, ShortText, StringSelectOption, slash_command, slash_default_member_permission, Permissions, Button, ButtonStyle, StringSelectMenu
from interactions.api.events import Component

class Config(Extension):

	async def _refresh_config_cache(self, guild_id: int):
		doc = await self.bot.db.config.find_one({"guild_id": str(guild_id)}) or {}
		await self.bot.mem_cache.set(f"config_{guild_id}", doc)
		return doc

	@slash_command(name="config", description="Configure bot settings", sub_cmd_name="set", sub_cmd_description="Set configuration options")
	@slash_default_member_permission(Permissions.MANAGE_GUILD)
	async def config(self, ctx):
		await ctx.defer(ephemeral=True)

		select_menu = StringSelectMenu(
			StringSelectOption(label="Promotion Issuer Role", description="Role assigned to members who can promote others", value="promotion_issuer_role"),
			StringSelectOption(label="Infraction Issuer Role", description="Role assigned to members who can issue infractions", value="infraction_issuer_role"),
			StringSelectOption(label="Promotion Log Channel", description="Channel to send promotions in", value="promotion_log"),
			StringSelectOption(label="Promotion Audit Log Channel", description="The channel to send promotion logs to", value="promotion_audit_log"),
			StringSelectOption(label="Infraction Log Channel", description="The channel to send infractions to", value="infraction_log"),
			StringSelectOption(label="Infraction Audit Log Channel", description="The channel to send infraction logs to", value="infraction_audit_log"),
			StringSelectOption(label="Infraction Types", description="Add/Remove infraction types", value="infraction_types"),
			placeholder="Select a configuration setting to modify",
			custom_id="config_menu",
			min_values=1,
			max_values=1,
		)

		embed = {
			"title": "Configuration Menu",
			"description": "Select the setting you want to configure from the menu below.",
			"thumbnail": {"url": ctx.guild.icon.url},
		}

		await ctx.send(embed=embed, components=select_menu)

		try:
			interaction_ctx = await self.bot.wait_for_component(
				components=select_menu,
				timeout=120,
			)
			
			if interaction_ctx.ctx.author.id != ctx.author.id:
				await interaction_ctx.ctx.send("This menu isn't for you!", ephemeral=True)
				return
			
			await interaction_ctx.ctx.defer(edit_origin=True)
			
			selected_setting_key = interaction_ctx.ctx.values[0]

			channel_options = [
				StringSelectOption(label=channel.name, value=str(channel.id))
				for channel in ctx.guild.channels
				if channel.type in [0]
			]

			if len(channel_options) > 25:
				channel_options = channel_options[:25]

			if not channel_options:
				await ctx.edit(
					embed={
						"title": "No Channels Available",
						"description": "No suitable text channels were found in this guild.",
						"thumbnail": {"url": ctx.guild.icon.url},
					},
					components=[],
				)
				return
			channel_selector_menu = StringSelectMenu(
				*channel_options,
				custom_id="channel_selector_menu",
				placeholder=f"Select a channel for {selected_setting_key.replace('_', ' ').title()}",
				min_values=1,
				max_values=1,
			)

			role_options = [
				StringSelectOption(label=role.name, value=str(role.id))
				for role in ctx.guild.roles
			]

			if len(role_options) > 25:
				role_options = role_options[:25]

			if not role_options:
				await ctx.edit(
					embed={
						"title": "No Roles Available",
						"description": "No roles were found in this guild.",
						"thumbnail": {"url": ctx.guild.icon.url},
					},
					components=[],
				)
				return
			
			if "role" in selected_setting_key:
				role_selector_menu = StringSelectMenu(
					*role_options,
					custom_id="role_selector_menu",
					placeholder=f"Select a role for {selected_setting_key.replace('_', ' ').title()}",
					min_values=1,
					max_values=1,
				)

				await ctx.edit(
					embed={
						"title": f"Select Role for {selected_setting_key.replace('_', ' ').title()}",
						"description": "Choose a role from the menu below.",
						"thumbnail": {"url": ctx.guild.icon.url},
					},
					components=role_selector_menu,
				)

				role_interaction_ctx = await self.bot.wait_for_component(
					components=role_selector_menu,
					timeout=120,
				)
				
				if role_interaction_ctx.ctx.author.id != ctx.author.id:
					await role_interaction_ctx.ctx.send("This menu isn't for you!", ephemeral=True)
					return
				
				await ctx.edit(embed={"title": "Processing...", "description": "Updating configuration..."}, components=[])

				await role_interaction_ctx.ctx.defer(edit_origin=True)
				
				selected_role_id_str = role_interaction_ctx.ctx.values[0]
				selected_role = ctx.guild.get_role(int(selected_role_id_str))

				await self.bot.db.config.update_one(
					{"guild_id": str(ctx.guild.id)},
					{"$set": {selected_setting_key: str(selected_role.id)}},
					upsert=True,
				)

				await self._refresh_config_cache(ctx.guild.id)

				await ctx.edit(
					embed={
						"title": "Configuration Updated",
						"description": f"Set **{selected_setting_key.replace('_', ' ').title()}** to {selected_role.mention}.",
						"thumbnail": {"url": ctx.guild.icon.url},
					},
					components=[],
				)
				return
			
			if "infraction_types" == selected_setting_key:
				add_remove_selector = StringSelectMenu(
					StringSelectOption(label="Add Infraction Type", description="Add a new infraction type", value="add_infraction_type"),
					StringSelectOption(label="Remove Infraction Type", description="Remove an existing infraction type", value="remove_infraction_type"),
					custom_id="infraction_type_action_menu",
					placeholder="Select an action",
					min_values=1,
					max_values=1,
				)

				await ctx.edit(
					embed={
						"title": "Infraction Types Configuration",
						"description": "Choose to add or remove an infraction type from the menu below.",
						"thumbnail": {"url": ctx.guild.icon.url},
					},
					components=add_remove_selector,
				)

				action_interaction_ctx = await self.bot.wait_for_component(
					components=add_remove_selector,
					timeout=120,
				)

				if action_interaction_ctx.ctx.author.id != ctx.author.id:
					await action_interaction_ctx.ctx.send("This menu isn't for you!", ephemeral=True)
					return
				
				action_selected = action_interaction_ctx.ctx.values[0]
				if action_selected == "add_infraction_type":
					modal = Modal(
						ShortText(
							label="Infraction Type",
							placeholder="Strike, Warning, Activity Notice, etc.",
							custom_id="infraction_type",
							required=True,
							max_length=30,
						),
						title="Add Infraction Type",
					)
					await action_interaction_ctx.ctx.send_modal(modal)
					modal_ctx = await self.bot.wait_for_modal(modal=modal, timeout=120)
					infraction_type_name = modal_ctx.responses["infraction_type"]

					await self.bot.db.config.update_one(
						{"guild_id": str(ctx.guild.id)},
						{"$addToSet": {"infraction_types": infraction_type_name}},
						upsert=True,
					)
					await self._refresh_config_cache(ctx.guild.id)

					await modal_ctx.send(embed={
						"title": "Infraction Type Added",
						"description": f"Successfully added infraction type: **{infraction_type_name}**",
						"thumbnail": {"url": ctx.guild.icon.url},
					}, ephemeral=True)
					return

				elif action_selected == "remove_infraction_type":
					config_data = await self.bot.mem_cache.get(f"config_{ctx.guild.id}") or await self._refresh_config_cache(ctx.guild.id)
					if not config_data or "infraction_types" not in config_data or not config_data["infraction_types"]:
						await ctx.edit(
							embed={
								"title": "No Infraction Types Found",
								"description": "There are no infraction types to remove.",
								"thumbnail": {"url": ctx.guild.icon.url},
							},
							components=[],
						)
						return

					infraction_type_options = [
						StringSelectOption(label=itype, value=itype)
						for itype in config_data["infraction_types"]
					]
					infraction_type_selector = StringSelectMenu(
						*infraction_type_options,
						custom_id="infraction_type_selector_menu",
						placeholder="Select an infraction type to remove",
						min_values=1,
						max_values=1,
					)
					await ctx.edit(
						embed={
							"title": "Select Infraction Type to Remove",
							"description": "Choose an infraction type from the menu below.",
							"thumbnail": {"url": ctx.guild.icon.url},
						},
						components=infraction_type_selector,
					)
					type_interaction_ctx = await self.bot.wait_for_component(
						components=infraction_type_selector,
						timeout=120,
					)
					if type_interaction_ctx.ctx.author.id != ctx.author.id:
						await type_interaction_ctx.ctx.send("This menu isn't for you!", ephemeral=True)
						return
					selected_type = type_interaction_ctx.ctx.values[0]
					await self.bot.db.config.update_one(
						{"guild_id": str(ctx.guild.id)},
						{"$pull": {"infraction_types": selected_type}},
					)
					await self._refresh_config_cache(ctx.guild.id)
					await ctx.edit(
						embed={
							"title": "Infraction Type Removed",
							"description": f"Successfully removed infraction type: **{selected_type}**",
							"thumbnail": {"url": ctx.guild.icon.url},
						},
						components=[],
					)
					return

			await ctx.edit(
				embed={
					"title": f"Select Channel for {selected_setting_key.replace('_', ' ').title()}",
					"description": "Choose a channel from the menu below.",
					"thumbnail": {"url": ctx.guild.icon.url},
				},
				components=channel_selector_menu,
			)

			channel_interaction_ctx = await self.bot.wait_for_component(
				components=channel_selector_menu,
				timeout=120,
			)
			
			if channel_interaction_ctx.ctx.author.id != ctx.author.id:
				await channel_interaction_ctx.ctx.send("This menu isn't for you!", ephemeral=True)
				return
			
			await ctx.edit(embed={"title": "Processing...", "description": "Updating configuration..."}, components=[])

			await channel_interaction_ctx.ctx.defer(edit_origin=True)
			
			selected_channel_id_str = channel_interaction_ctx.ctx.values[0]
			selected_channel = ctx.guild.get_channel(int(selected_channel_id_str))

			await self.bot.db.config.update_one(
				{"guild_id": str(ctx.guild.id)},
				{"$set": {selected_setting_key: str(selected_channel.id)}},
				upsert=True,
			)

			await self._refresh_config_cache(ctx.guild.id)

			await ctx.edit(
				embed={
					"title": "Configuration Updated",
					"description": f"Set **{selected_setting_key.replace('_', ' ').title()}** to {selected_channel.mention}.",
					"thumbnail": {"url": ctx.guild.icon.url},
				},
				components=[],
			)

		except TimeoutError:
			try:
				await ctx.edit(
					embed={
						"title": "Configuration Menu Expired",
						"description": "You did not make a selection in time. Please run the command again to configure settings.",
						"thumbnail": {"url": ctx.guild.icon.url},
					},
					components=[],
				)
			except Exception:
				try:
					await ctx.send("Configuration timed out. Please run the command again.", ephemeral=True)
				except Exception:
					pass

	@config.subcommand(sub_cmd_name="view", sub_cmd_description="View current configuration settings")
	@slash_default_member_permission(Permissions.MANAGE_GUILD)
	async def view_config(self, ctx):
		await ctx.defer(ephemeral=True)

		key = f"config_{ctx.guild.id}"
		config_data = await self.bot.mem_cache.get(key)
		if not config_data:
			config_data = await self._refresh_config_cache(ctx.guild.id) or {}

		if not config_data:
			return await ctx.send(
				embed={
					"title": "No Configuration Found",
					"description": "No configuration settings have been set for this guild.",
					"thumbnail": {"url": ctx.guild.icon.url},
				},
				ephemeral=True,
			)

		display_data = {k: v for k, v in config_data.items() if k not in ['_id', 'guild_id']}
		if not display_data:
			return await ctx.send(
				embed={
					"title": "Configuration Empty",
					"description": "Configuration document exists but no specific settings are set.",
					"thumbnail": {"url": ctx.guild.icon.url},
				},
				ephemeral=True,
			)

		def _resolve_channel(val):
			try:
				ch = ctx.guild.get_channel(int(val))
				return f"<#{ch.id}>" if ch else f"<#{val}>"
			except Exception:
				return None

		def _resolve_role(val):
			try:
				r = ctx.guild.get_role(int(val))
				return f"<@&{r.id}>" if r else f"<@&{val}>"
			except Exception:
				return None

		embed_lines = []
		for key_name, val in display_data.items():
			pretty = key_name.replace('_', ' ').title()
			if isinstance(val, (list, tuple)):
				if not val:
					embed_lines.append(f"{pretty}: (empty)")
				else:
					embed_lines.append(f"{pretty}: {', '.join(map(str, val))}")
				continue

			s = str(val)

			if "role" in key_name:
				resolved = _resolve_role(s)
				embed_lines.append(f"{pretty}: {resolved or s}\n")
			elif "channel" in key_name or "log" in key_name:
				resolved = _resolve_channel(s)
				embed_lines.append(f"{pretty}: {resolved or s}\n")
			else:
				embed_lines.append(f"{pretty}: {s}\n")

		await ctx.send(
			embed={
				"title": "Current Configuration",
				"description": "\n".join(embed_lines),
				"thumbnail": {"url": ctx.guild.icon.url},
			},
			ephemeral=True,
		)

def setup(bot):
	Config(bot)