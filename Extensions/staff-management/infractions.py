import random, string, ast, json, interactions, re
from datetime import datetime, timezone, timedelta
from interactions import Extension, slash_command, slash_option, OptionType, User, Timestamp, AutocompleteContext

class Infractions(Extension):

	def parse_temporary_duration(self, value: str):
		if not value:
			return None
		cleaned = ''.join(value.lower().split())
		if not cleaned:
			return None
		if not re.fullmatch(r'(\d+[smhdw])+', cleaned):
			return None
		unit_map = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400, 'w': 604800}
		total = 0
		for amount, unit in re.findall(r'(\d+)([smhdw])', cleaned):
			total += int(amount) * unit_map[unit]
		if total <= 0:
			return None
		return datetime.utcnow() + timedelta(seconds=total)

	@slash_command(name="infractions", description="Infractions management commands", sub_cmd_name="infract", sub_cmd_description="Infract a member")
	@slash_option(
		name="member",
		description="The member to Infract",
		required=True,
		opt_type=OptionType.USER
	)
	@slash_option(
		name="type",
		description="The type of infraction",
		required=True,
		opt_type=OptionType.STRING,
		autocomplete=True
	)
	@slash_option(
		name="reason",
		description="Reason for the infraction",
		required=False,
		opt_type=OptionType.STRING
	)
	@slash_option(
		name="temporary",
		description="Duration for a temporary infraction (e.g., 30d, 1w)",
		required=False,
		opt_type=OptionType.STRING
	)
	async def infractions(self, ctx, member: User, type: str, reason: str = None, temporary: str = None):
		await ctx.defer(ephemeral=True)

		config = await self.bot.mem_cache.get(f"guild_config_{ctx.guild.id}")
		if not config:
			config = await self.bot.db.config.find_one({"guild_id": str(ctx.guild.id)})
			if not config:
				config = {}
			await self.bot.mem_cache.set(f"guild_config_{ctx.guild.id}", config)
		infraction_issuer_role_id = config.get("infraction_issuer_role")

		if infraction_issuer_role_id:
			infraction_issuer_role = ctx.guild.get_role(int(infraction_issuer_role_id))
			if not infraction_issuer_role:
				try:
					infraction_issuer_role = await ctx.guild.fetch_role(int(infraction_issuer_role_id))
				except Exception:
					infraction_issuer_role = None
			if not infraction_issuer_role:
				await ctx.send(embed={"description": "<:warning:1430730420307234916> Infraction issuer role not found in the guild."}, ephemeral=True)
				return
			if infraction_issuer_role not in ctx.author.roles:
				await ctx.send(embed={"description": "<:warning:1430730420307234916> You don't have permission to infract others."}, ephemeral=True)
				return
			
		if member.id == ctx.author.id:
			await ctx.send(embed={"description": "<:warning:1430730420307234916> You cannot infract yourself."}, ephemeral=True)
			return
		
		infraction_types = config.get("infraction_types", []) or []
		if type not in infraction_types:
			await ctx.send(embed={"description": "<:warning:1430730420307234916> The specified infraction type is not valid."}, ephemeral=True)
			return

		temporary_value = temporary.strip() if temporary else None
		expires_at_iso = None
		expiration_display = None
		if temporary_value:
			expiration_dt = self.parse_temporary_duration(temporary_value)
			if not expiration_dt:
				await ctx.send(embed={"description": "<:warning:1430730420307234916> Temporary duration must be formatted like 30d, 1w, or 2h30m."}, ephemeral=True)
				return
			expires_at_iso = expiration_dt.isoformat()
			try:
				expiration_display = str(Timestamp.fromdatetime(expiration_dt.replace(tzinfo=timezone.utc)))
			except Exception:
				expiration_display = None
		expires_line = f"\n> **Expires:** {expiration_display}" if expiration_display else ""

		issued_at = datetime.utcnow()
		timestamp_iso = issued_at.isoformat()
		infraction_id = (random.choices(string.ascii_uppercase + string.digits, k=8))
		infraction_id_str = ''.join(infraction_id)
			
		infraction_channel_id = config.get("infraction_log")
		infraction_message = None
		infraction_audit_message = None
		if infraction_channel_id:
			infraction_channel = ctx.guild.get_channel(int(infraction_channel_id))
			if not infraction_channel:
				try:
					infraction_channel = await ctx.guild.fetch_channel(int(infraction_channel_id))
				except Exception:
					infraction_channel = None
			if infraction_channel:
				infraction_message = await infraction_channel.send(
					f"{member.mention}",
					embed={
						"description": f"**{member}**, you have been infracted.\n\n> **Infraction Type:** {type}\n> **Reason:** {reason if reason else 'No reason provided'}\n> **Infraction ID:** {infraction_id_str}{expires_line}",
						"author": {"name": f"Signed, {ctx.author}", "icon_url": ctx.author.display_avatar.url},
						"thumbnail": {"url": member.display_avatar.url},
					}
				)
		infraction_audit_channel_id = config.get("infraction_audit_log")
		infraction_audit_message = None
		if infraction_audit_channel_id:
			infraction_audit_channel = ctx.guild.get_channel(int(infraction_audit_channel_id))
			if not infraction_audit_channel:
				try:
					infraction_audit_channel = await ctx.guild.fetch_channel(int(infraction_audit_channel_id))
				except Exception:
					infraction_audit_channel = None
			if infraction_audit_channel:
				infraction_audit_message = await infraction_audit_channel.send(
					embed={
						"title": "Infraction Audit Log",
						"description": f"> **Member Infracted:** {member.mention}\n> **Infraction Type:** {type}\n> **Infracted By:** {ctx.author.mention}\n> **Reason:** {reason if reason else 'No reason provided'}\n> **Infraction ID:** {infraction_id_str}{expires_line}",
						"author": {"name": f"Signed, {ctx.author}", "icon_url": ctx.author.display_avatar.url},
						"thumbnail": {"url": member.display_avatar.url},
					}
				)
		
		try:
			await member.send(
				embed={
					"description": f"You have been infracted in **{ctx.guild.name}**!\n\n> **Infraction Type** {type}\n> **Reason:** {reason if reason else 'No reason provided'}\n> **Infraction ID:** {infraction_id_str}{expires_line}",
					"author": {"name": f"Signed, {ctx.author}", "icon_url": ctx.author.display_avatar.url},
					"footer": {"text": f"{self.bot.user.username}", "icon_url": self.bot.user.display_avatar.url},
					"thumbnail": {"url": ctx.guild.icon.url if ctx.guild.icon else member.display_avatar.url},
				}
			)
		except Exception as e:
			pass
		await self.bot.db.infractions.insert_one({
			"infraction_id": infraction_id_str,
			"guild_id": str(ctx.guild.id),
			"member_id": str(member.id),
			"infraction_type": type,
			"issued_by_id": str(ctx.author.id),
			"infraction_message_id": infraction_message.id if infraction_message else None,
			"infraction_audit_message_id": infraction_audit_message.id if infraction_audit_message else None,
			"reason": reason,
			"timestamp": timestamp_iso,
			"expires_at": expires_at_iso,
			"temporary_duration": temporary_value
		})
		await self.bot.mem_cache.set(f"infraction_{infraction_id_str}", {
			"infraction_id": infraction_id_str,
			"guild_id": str(ctx.guild.id),
			"member_id": str(member.id),
			"infraction_type": type,
			"issued_by_id": str(ctx.author.id),
			"infraction_message_id": infraction_message.id if infraction_message else None,
			"infraction_audit_message_id": infraction_audit_message.id if infraction_audit_message else None,
			"reason": reason,
			"timestamp": timestamp_iso,
			"expires_at": expires_at_iso,
			"temporary_duration": temporary_value
		})
		await ctx.send(
			embed={
				"description": f"<:check:1430728952535842907> Successfully infracted **{member}**{f' (expires {expiration_display})' if expiration_display else ''}.",
			},
			ephemeral=True
		)

	@infractions.autocomplete("type")
	async def infraction_type_autocomplete(self, ctx: AutocompleteContext):
		cfg = await self.bot.mem_cache.get(f"config_{ctx.guild.id}")
		if isinstance(cfg, str):
			try:
				cfg = ast.literal_eval(cfg)
			except Exception:
				cfg = {}
		if not cfg:
			cfg = await self.bot.db.config.find_one({"guild_id": str(ctx.guild.id)}) or {}
			await self.bot.mem_cache.set(f"config_{ctx.guild.id}", cfg)

		infraction_types = cfg.get("infraction_types", []) or []

		if isinstance(infraction_types, str):
			try:
				parsed = ast.literal_eval(infraction_types)
				infraction_types = parsed if isinstance(parsed, list) else [parsed]
			except Exception:
				infraction_types = [infraction_types]

		if not isinstance(infraction_types, list):
			infraction_types = [str(infraction_types)]

		cleaned = []
		seen = set()
		for item in infraction_types:
			if item is None:
				continue
			s = str(item).strip()
			if not s:
				continue
			s = s[:100]
			if s in seen:
				continue
			seen.add(s)
			cleaned.append(s)

		q = (getattr(ctx, "input_text", "") or "").lower()
		if q:
			filtered = [s for s in cleaned if q in s.lower()]
		else:
			filtered = cleaned

		filtered = filtered[:25]

		choices = [{"name": s, "value": s} for s in filtered]

		if not choices:
			choices = [{"name": "No infraction types set", "value": "none"}]

		send_fn = getattr(ctx, "send_autocomplete", None) or getattr(ctx, "send", None)
		if callable(send_fn):
			try:
				await send_fn(choices)
				return
			except TypeError:
				pass
			except Exception:
				pass

		return choices

	@infractions.subcommand(sub_cmd_name="view", sub_cmd_description="View infraction details by Infraction ID")
	@slash_option(
		name="infraction_id",
		description="The Infraction ID to view",
		required=True,
		opt_type=OptionType.STRING
	)
	async def view_infraction(self, ctx, infraction_id: str):
		await ctx.defer(ephemeral=True)

		config = await self.bot.mem_cache.get(f"guild_config_{ctx.guild.id}")
		if not config:
			config = await self.bot.db.config.find_one({"guild_id": str(ctx.guild.id)})
			if not config:
				config = {}
			await self.bot.mem_cache.set(f"guild_config_{ctx.guild.id}", config)
		infraction_issuer_role_id = config.get("infraction_issuer_role")

		if infraction_issuer_role_id:
			infraction_issuer_role = ctx.guild.get_role(int(infraction_issuer_role_id))
			if not infraction_issuer_role:
				try:
					infraction_issuer_role = await ctx.guild.fetch_role(int(infraction_issuer_role_id))
				except Exception:
					infraction_issuer_role = None
			if not infraction_issuer_role:
				await ctx.send(embed={"description": "<:warning:1430730420307234916> Infraction issuer role not found in the guild."}, ephemeral=True)
				return
			if infraction_issuer_role not in ctx.author.roles:
				await ctx.send(embed={"description": "<:warning:1430730420307234916> You don't have permission to view infractions."}, ephemeral=True)
				return

		infraction_data = await self.bot.mem_cache.get(f"infraction_{infraction_id}")

		if not infraction_data:
			infraction_data = await self.bot.db.infractions.find_one(
				{"infraction_id": infraction_id, "guild_id": str(ctx.guild.id)}
			)
			if not infraction_data:
				await ctx.send(
					embed={
						"description": "<:warning:1430730420307234916> No infraction found with the given Infraction ID.",
					},
					ephemeral=True
				)
				return
			await self.bot.mem_cache.set(f"infraction_{infraction_id}", infraction_data)
		else:
			if infraction_data.get("guild_id") != str(ctx.guild.id):
				await ctx.send(
					embed={
						"description": "<:warning:1430730420307234916> No infraction found with the given Infraction ID.",
					},
					ephemeral=True
				)
				return
		
		member = ctx.guild.get_member(int(infraction_data["member_id"]))
		if not member:
			try:
				member = await self.bot.fetch_user(int(infraction_data["member_id"]))
			except Exception:
				member = None
		infraction_type = infraction_data.get("infraction_type", "Unknown")
		issued_by = ctx.guild.get_member(int(infraction_data["issued_by_id"]))
		if not issued_by:
			try:
				issued_by = await self.bot.fetch_user(int(infraction_data["issued_by_id"]))
			except Exception:
				issued_by = None


		timestamp = infraction_data.get("timestamp")
		if timestamp:
			try:
				dt = datetime.fromisoformat(timestamp).replace(tzinfo=timezone.utc)
				timestamp = str(Timestamp.fromdatetime(dt))
			except Exception:
				timestamp = "Unknown"
		else:
			timestamp = "Unknown"
		expires_at = infraction_data.get("expires_at")
		expires_display = "Never"
		if expires_at:
			try:
				expires_dt = datetime.fromisoformat(expires_at)
				display_dt = Timestamp.fromdatetime(expires_dt.replace(tzinfo=timezone.utc))
				expires_display = str(display_dt)
				if expires_dt < datetime.utcnow():
					expires_display = f"{expires_display} (expired)"
			except Exception:
				expires_display = "Unknown"
		temporary_value = infraction_data.get("temporary_duration") or ""

		description_lines = [
			f"> **Member:** {member.mention if member else f'ID: {infraction_data['member_id']}'}",
			f"> **Infraction Type:** {infraction_type}",
			f"> **Issued By:** {issued_by.mention if issued_by else f'ID: {infraction_data['issued_by_id']}'}",
			f"> **Reason:** {infraction_data.get('reason') or 'No reason provided'}",
			f"> **Issued At:** {timestamp}",
			f"> **Expires:** {expires_display}",
		]

		await ctx.send(
			embed={
				"title": f"Infraction Details: {infraction_id}",
				"description": "\n".join(description_lines),
				"thumbnail": {"url": member.display_avatar.url if member and member.display_avatar else (ctx.guild.icon.url if ctx.guild.icon else None)},
				"author": {"name": f"Signed, {issued_by}", "icon_url": issued_by.display_avatar.url if issued_by else None},
			},
			ephemeral=True
		)

	@infractions.subcommand(sub_cmd_name="revoke", sub_cmd_description="Revoke a infraction")
	@slash_option(
		name="infraction_id",
		description="The Infraction ID to revoke",
		required=True,
		opt_type=OptionType.STRING
	)
	async def revoke_infraction(self, ctx, infraction_id: str):
		await ctx.defer(ephemeral=True)

		config = await self.bot.mem_cache.get(f"guild_config_{ctx.guild.id}")
		if not config:
			config = await self.bot.db.config.find_one({"guild_id": str(ctx.guild.id)})
			if not config:
				config = {}
			await self.bot.mem_cache.set(f"guild_config_{ctx.guild.id}", config)
		infraction_issuer_role_id = config.get("infraction_issuer_role")

		if infraction_issuer_role_id:
			infraction_issuer_role = ctx.guild.get_role(int(infraction_issuer_role_id))
			if not infraction_issuer_role:
				try:
					infraction_issuer_role = await ctx.guild.fetch_role(int(infraction_issuer_role_id))
				except Exception:
					infraction_issuer_role = None
			if not infraction_issuer_role:
				await ctx.send(embed={"description": "<:warning:1430730420307234916> Infraction issuer role not found in the guild."}, ephemeral=True)
				return
			if infraction_issuer_role not in ctx.author.roles:
				await ctx.send(embed={"description": "<:warning:1430730420307234916> You don't have permission to revoke infractions."}, ephemeral=True)
				return

		infraction_data = await self.bot.mem_cache.get(f"infraction_{infraction_id}")

		if not infraction_data:
			infraction_data = await self.bot.db.infractions.find_one(
				{"infraction_id": infraction_id, "guild_id": str(ctx.guild.id)}
			)
			if not infraction_data:
				await ctx.send(
					embed={
						"description": "<:warning:1430730420307234916> No infraction found with the given Infraction ID.",
					},
					ephemeral=True
				)
				return
			await self.bot.mem_cache.set(f"infraction_{infraction_id}", infraction_data)
		else:
			if infraction_data.get("guild_id") != str(ctx.guild.id):
				await ctx.send(
					embed={
						"description": "<:warning:1430730420307234916> No infraction found with the given Infraction ID.",
					},
					ephemeral=True
				)
				return
		
		member = ctx.guild.get_member(int(infraction_data["member_id"]))
		if not member:
			try:
				member = await self.bot.fetch_user(int(infraction_data["member_id"]))
			except Exception:
				member = None
		if member.id == ctx.author.id:
			await ctx.send(embed={"description": "<:warning:1430730420307234916> You cannot revoke your own infraction."}, ephemeral=True)
			return
		infraction_type = infraction_data.get("infraction_type", "Unknown")

		if member:
			timestamp = infraction_data.get("timestamp")
			if timestamp:
				try:
					dt = datetime.fromisoformat(timestamp).replace(tzinfo=timezone.utc)
					timestamp = str(Timestamp.fromdatetime(dt))
				except Exception:
					timestamp = "Unknown"
			else:
				timestamp = "Unknown"
			expires_at = infraction_data.get("expires_at")
			expires_display = "Never"
			if expires_at:
				try:
					expires_dt = datetime.fromisoformat(expires_at)
					display_dt = Timestamp.fromdatetime(expires_dt.replace(tzinfo=timezone.utc))
					expires_display = str(display_dt)
					if expires_dt < datetime.utcnow():
						expires_display = f"{expires_display} (expired)"
				except Exception:
					expires_display = "Unknown"
			temporary_value = infraction_data.get("temporary_duration") or ""
			infraction_revoked_embed = {
				"description": f"***Infraction ID {infraction_id} has been revoked by {ctx.author} ({ctx.author.id})***\n\n> **Member:** {member} `({member.id})`\n> **Infraction Type**: {infraction_type}\n> **Original Reason:** {infraction_data['reason'] if infraction_data['reason'] else 'No reason provided'}\n> **Issued At:** {timestamp}\n> **Expires:** {expires_display}\n> **Temporary Input:** {temporary_value if temporary_value else 'None'}",
				"thumbnail": {"url": member.display_avatar.url},
				"author": {"name": f"Signed, {ctx.author}", "icon_url":ctx.author.display_avatar.url},
			}
			infraction_message_id = infraction_data.get("infraction_message_id")
			if infraction_message_id:
				config = await self.bot.mem_cache.get(f"guild_config_{ctx.guild.id}")
				if not config:
					config = await self.bot.db.config.find_one({"guild_id": str(ctx.guild.id)})
					if not config:
						config = {}
					await self.bot.mem_cache.set(f"guild_config_{ctx.guild.id}", config)
				infraction_channel_id = config.get("infraction_log")
				if infraction_channel_id:
					infraction_channel = ctx.guild.get_channel(int(infraction_channel_id))
					if not infraction_channel:
						try:
							infraction_channel = await ctx.guild.fetch_channel(int(infraction_channel_id))
						except Exception:
							infraction_channel = None
					if infraction_channel:
						try:
							infraction_message = await infraction_channel.fetch_message(infraction_message_id)
							await infraction_message.edit(embed=infraction_revoked_embed)
						except Exception:
							pass
				infraction_audit_channel_id = config.get("infraction_audit_log")
				if infraction_audit_channel_id:
					infraction_audit_channel = ctx.guild.get_channel(int(infraction_audit_channel_id))
					if not infraction_audit_channel:
						try:
							infraction_audit_channel = await ctx.guild.fetch_channel(int(infraction_audit_channel_id))
						except Exception:
							infraction_audit_channel = None
					if infraction_audit_channel:
						infraction_audit_message_id = infraction_data.get("infraction_audit_message_id")
						if infraction_audit_message_id:
							try:
								infraction_audit_message = await infraction_audit_channel.fetch_message(infraction_audit_message_id)
								await infraction_audit_message.edit(embed=infraction_revoked_embed)
							except Exception:
								pass
			await self.bot.db.infractions.delete_one({"infraction_id": infraction_id, "guild_id": str(ctx.guild.id)})
			await self.bot.mem_cache.delete(f"infraction_{infraction_id}")
			await ctx.send(
				embed={
					"description": f"<:check:1430728952535842907> Successfully revoked infraction of **{member}**.",
				},
				ephemeral=True
			)
		else:
			await ctx.send(
				embed={
					"description": "<:warning:1430730420307234916> Member not found, cannot revoke infraction.",
				},
				ephemeral=True
			)

def setup(bot):
	Infractions(bot)
