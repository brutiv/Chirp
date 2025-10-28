import random, string
from datetime import datetime, timezone
from interactions import Extension, slash_command, slash_option, OptionType, User, Role, Timestamp, Modal, ShortText

class Promotions(Extension):

    @slash_command(name="promotions", description="Promotion management commands")
    async def promotions(self, ctx):
        pass

    @promotions.subcommand(sub_cmd_name="promote", sub_cmd_description="Promote a member")
    @slash_option(
        name="member",
        description="The member to promote",
        required=True,
        opt_type=OptionType.USER
    )
    @slash_option(
        name="new_role",
        description="The new role to assign to the member",
        required=True,
        opt_type=OptionType.ROLE
    )
    @slash_option(
        name="reason",
        description="Reason for the promotion",
        required=False,
        opt_type=OptionType.STRING
    )
    async def promote(self, ctx, member: User, new_role: Role, reason: str = None):
        await ctx.defer(ephemeral=True)

        config = await self.bot.mem_cache.get(f"guild_config_{ctx.guild.id}")
        if not config:
            config = await self.bot.db.config.find_one({"guild_id": str(ctx.guild.id)})
            if not config:
                config = {}
            await self.bot.mem_cache.set(f"guild_config_{ctx.guild.id}", config)
        promotion_issuer_role_id = config.get("promotion_issuer_role")

        if promotion_issuer_role_id:
            promotion_issuer_role = ctx.guild.get_role(int(promotion_issuer_role_id))
            if not promotion_issuer_role:
                try:
                    promotion_issuer_role = await ctx.guild.fetch_role(int(promotion_issuer_role_id))
                except Exception:
                    promotion_issuer_role = None
            if not promotion_issuer_role:
                await ctx.send(embed={"description": "<:warning:1430730420307234916> Promotion issuer role not found in the guild."}, ephemeral=True)
                return
            if promotion_issuer_role not in ctx.author.roles:
                await ctx.send(embed={"description": "<:warning:1430730420307234916> You don't have permission to promote others."}, ephemeral=True)
                return
            
        if member.id == ctx.author.id:
            await ctx.send(embed={"description": "<:warning:1430730420307234916> You cannot promote yourself."}, ephemeral=True)
            return

        promotion_id = (random.choices(string.ascii_uppercase + string.digits, k=8))
        promotion_id_str = ''.join(promotion_id)
            
        promotion_channel_id = config.get("promotion_log")
        promotion_audit_message = None
        if promotion_channel_id:
            promotion_channel = ctx.guild.get_channel(int(promotion_channel_id))
            if not promotion_channel:
                try:
                    promotion_channel = await ctx.guild.fetch_channel(int(promotion_channel_id))
                except Exception:
                    promotion_channel = None
            if promotion_channel:
                promotion_message = await promotion_channel.send(
                    f"{member.mention}",
                    embed={
                        "description": f"**{member}**, you have been promoted.\n\n> **New Role:** @{new_role.name}\n> **Reason:** {reason if reason else 'No reason provided'}\n> **Promotion ID:** {promotion_id_str}",
                        "author": {"name": f"Signed, {ctx.author}", "icon_url": ctx.author.display_avatar.url},
                        "thumbnail": {"url": member.display_avatar.url},
                    }
                )
        promotion_audit_channel_id = config.get("promotion_audit_log")
        promotion_audit_message = None
        if promotion_audit_channel_id:
            promotion_audit_channel = ctx.guild.get_channel(int(promotion_audit_channel_id))
            if not promotion_audit_channel:
                try:
                    promotion_audit_channel = await ctx.guild.fetch_channel(int(promotion_audit_channel_id))
                except Exception:
                    promotion_audit_channel = None
            if promotion_audit_channel:
                promotion_audit_message = await promotion_audit_channel.send(
                    embed={
                        "title": "Promotion Audit Log",
                        "description": f"> **Member Promoted:** {member.mention}\n> **New Role:** @{new_role.name}\n> **Promoted By:** {ctx.author.mention}\n> **Reason:** {reason if reason else 'No reason provided'}\n> **Promotion ID:** {promotion_id_str}",
                        "author": {"name": f"Signed, {ctx.author}", "icon_url": ctx.author.display_avatar.url},
                        "thumbnail": {"url": member.display_avatar.url},
                    }
                )
        

        try: await member.add_role(new_role, reason=f"Promoted by {ctx.author} | Reason: {reason if reason else 'No reason provided'} | Promotion ID: {promotion_id_str}")
        except Exception: pass
        try:
            await member.send(
                embed={
                    "description": f"You have been promoted in **{ctx.guild.name}**!\n\n> **New Role:** @{new_role.name}\n> **Reason:** {reason if reason else 'No reason provided'}\n> **Promotion ID:** {promotion_id_str}\n\nCongratulations!",
                    "author": {"name": f"Signed, {ctx.author}", "icon_url": ctx.author.display_avatar.url},
                    "footer": {"text": f"{self.bot.user.username}", "icon_url": self.bot.user.display_avatar.url},
                    "thumbnail": {"url": ctx.guild.icon.url if ctx.guild.icon else member.display_avatar.url},
                }
            )
        except Exception:
            pass
        await self.bot.db.promotions.insert_one({
            "promotion_id": promotion_id_str,
            "guild_id": str(ctx.guild.id),
            "member_id": str(member.id),
            "new_role_id": str(new_role.id),
            "issued_by_id": str(ctx.author.id),
            "promotion_message_id": promotion_message.id if promotion_channel_id else None,
            "promotion_audit_message_id": promotion_audit_message.id if promotion_audit_channel_id else None,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat()
        })
        await self.bot.mem_cache.set(f"promotion_{promotion_id_str}", {
            "promotion_id": promotion_id_str,
            "guild_id": str(ctx.guild.id),
            "member_id": str(member.id),
            "new_role_id": str(new_role.id),
            "issued_by_id": str(ctx.author.id),
            "promotion_message_id": promotion_message.id if promotion_channel_id else None,
            "promotion_audit_message_id": promotion_audit_message.id if promotion_audit_channel_id else None,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat()
        })
        await ctx.send(
            embed={
                "description": f"<:check:1430728952535842907> Successfully promoted **{member}** to **@{new_role.name}**.",
            },
            ephemeral=True
        )

    @promotions.subcommand(sub_cmd_name="view", sub_cmd_description="View promotion details by ID or for a member")
    @slash_option(
        name="promotion_id",
        description="The Promotion ID to view",
        required=False,
        opt_type=OptionType.STRING
    )
    @slash_option(
        name="member",
        description="The member to view promotions for",
        required=False,
        opt_type=OptionType.USER
    )
    async def view_promotion(self, ctx, promotion_id: str = None, member: User = None):
        await ctx.defer(ephemeral=True)


        config = await self.bot.mem_cache.get(f"guild_config_{ctx.guild.id}")
        if not config:
            config = await self.bot.db.config.find_one({"guild_id": str(ctx.guild.id)})
            if not config:
                config = {}
            await self.bot.mem_cache.set(f"guild_config_{ctx.guild.id}", config)
        promotion_issuer_role_id = config.get("promotion_issuer_role")

        if promotion_issuer_role_id:
            promotion_issuer_role = ctx.guild.get_role(int(promotion_issuer_role_id))
            if not promotion_issuer_role:
                try:
                    promotion_issuer_role = await ctx.guild.fetch_role(int(promotion_issuer_role_id))
                except Exception:
                    promotion_issuer_role = None
            if not promotion_issuer_role:
                await ctx.send(embed={"description": "<:warning:1430730420307234916> Promotion issuer role not found in the guild."}, ephemeral=True)
                return
            if promotion_issuer_role not in ctx.author.roles:
                await ctx.send(embed={"description": "<:warning:1430730420307234916> You don't have permission to view promotions."}, ephemeral=True)
                return
        
        if not promotion_id and not member:
            return await ctx.send(embed={"description": "<:warning:1430730420307234916> You must provide either a Promotion ID or a member to view."}, ephemeral=True)

        if promotion_id and member:
            return await ctx.send(embed={"description": "<:warning:1430730420307234916> You can only provide a Promotion ID or a member, not both."}, ephemeral=True)

        if promotion_id:
            promotion_data = await self.bot.mem_cache.get(f"promotion_{promotion_id}")

            if not promotion_data:
                promotion_data = await self.bot.db.promotions.find_one(
                    {"promotion_id": promotion_id, "guild_id": str(ctx.guild.id)}
                )
                if not promotion_data:
                    await ctx.send(
                        embed={
                            "description": "<:warning:1430730420307234916> No promotion found with the given Promotion ID.",
                        },
                        ephemeral=True
                    )
                    return
                await self.bot.mem_cache.set(f"promotion_{promotion_id}", promotion_data)
            else:
                if promotion_data.get("guild_id") != str(ctx.guild.id):
                    await ctx.send(
                        embed={
                            "description": "<:warning:1430730420307234916> No promotion found with the given Promotion ID.",
                        },
                        ephemeral=True
                    )
                    return
            
            member_obj = ctx.guild.get_member(int(promotion_data["member_id"])) or await self.bot.fetch_user(int(promotion_data["member_id"]))
            new_role = ctx.guild.get_role(int(promotion_data["new_role_id"])) or await ctx.guild.fetch_role(int(promotion_data["new_role_id"]))
            issued_by = ctx.guild.get_member(int(promotion_data["issued_by_id"])) or await self.bot.fetch_user(int(promotion_data["issued_by_id"]))

            timestamp = promotion_data.get("timestamp")
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp).replace(tzinfo=timezone.utc)
                    timestamp = str(Timestamp.fromdatetime(dt))
                except Exception:
                    timestamp = "Unknown"
            else:
                timestamp = "Unknown"

            await ctx.send(
                embed={
                    "title": f"Promotion Details: {promotion_id}",
                    "fields": [
                        {"name": "Member", "value": f"{member_obj} ({member_obj.id})" if member_obj else f"Member not found ({promotion_data['member_id']})", "inline": True},
                        {"name": "New Role", "value": f"{new_role.mention} ({new_role.id})" if new_role else f"Role not found ({promotion_data['new_role_id']})", "inline": True},
                        {"name": "Issued By", "value": f"{issued_by} ({issued_by.id})" if issued_by else f"Issuer not found ({promotion_data['issued_by_id']})", "inline": True},
                        {"name": "Reason", "value": promotion_data.get("reason") or "No reason provided", "inline": False},
                        {"name": "Timestamp", "value": timestamp, "inline": False},
                    ],
                    "thumbnail": {"url": member_obj.display_avatar.url if member_obj else None},
                },
                ephemeral=True
            )
        
        if member:
            promotions_cursor = self.bot.db.promotions.find({"member_id": str(member.id), "guild_id": str(ctx.guild.id)})
            promotions_list = await promotions_cursor.to_list(length=100)

            if not promotions_list:
                return await ctx.send(embed={"description": f"No promotions found for **{member}**."}, ephemeral=True)

            description_lines = []
            for promo in promotions_list:
                timestamp_str = "Unknown"
                if promo.get("timestamp"):
                    try:
                        dt = datetime.fromisoformat(promo["timestamp"]).replace(tzinfo=timezone.utc)
                        timestamp_str = str(Timestamp.fromdatetime(dt))
                    except Exception:
                        pass
                
                new_role = ctx.guild.get_role(int(promo["new_role_id"]))
                role_mention = new_role.mention if new_role else f"@{promo['new_role_id']}"
                reason = promo.get('reason') or 'No reason provided'
                
                description_lines.append(
                    f"**ID:** `{promo['promotion_id']}` - {timestamp_str}\n"
                    f"**Role:** {role_mention} - **Reason:** *{reason}*"
                )

            embed = {
                "title": f"Promotions for {member.display_name}",
                "description": "\n\n".join(description_lines),
                "thumbnail": {"url": member.display_avatar.url},
                "footer": {"text": f"Found {len(promotions_list)} promotion(s)."}
            }
            await ctx.send(embed=embed, ephemeral=True)

    @promotions.subcommand(sub_cmd_name="revoke", sub_cmd_description="Revoke a promotion")
    @slash_option(
        name="promotion_id",
        description="The Promotion ID to revoke",
        required=True,
        opt_type=OptionType.STRING
    )
    async def revoke_promotion(self, ctx, promotion_id: str):
        await ctx.defer(ephemeral=True)

        config = await self.bot.mem_cache.get(f"guild_config_{ctx.guild.id}")
        if not config:
            config = await self.bot.db.config.find_one({"guild_id": str(ctx.guild.id)})
            if not config:
                config = {}
            await self.bot.mem_cache.set(f"guild_config_{ctx.guild.id}", config)
        promotion_issuer_role_id = config.get("promotion_issuer_role")

        if promotion_issuer_role_id:
            promotion_issuer_role = ctx.guild.get_role(int(promotion_issuer_role_id))
            if not promotion_issuer_role:
                try:
                    promotion_issuer_role = await ctx.guild.fetch_role(int(promotion_issuer_role_id))
                except Exception:
                    promotion_issuer_role = None
            if not promotion_issuer_role:
                await ctx.send(embed={"description": "<:warning:1430730420307234916> Promotion issuer role not found in the guild."}, ephemeral=True)
                return
            if promotion_issuer_role not in ctx.author.roles:
                await ctx.send(embed={"description": "<:warning:1430730420307234916> You don't have permission to revoke promotions."}, ephemeral=True)
                return

        promotion_data = await self.bot.mem_cache.get(f"promotion_{promotion_id}")

        if not promotion_data:
            promotion_data = await self.bot.db.promotions.find_one(
                {"promotion_id": promotion_id, "guild_id": str(ctx.guild.id)}
            )
            if not promotion_data:
                await ctx.send(
                    embed={
                        "description": "<:warning:1430730420307234916> No promotion found with the given Promotion ID.",
                    },
                    ephemeral=True
                )
                return
            await self.bot.mem_cache.set(f"promotion_{promotion_id}", promotion_data)
        else:
            if promotion_data.get("guild_id") != str(ctx.guild.id):
                await ctx.send(
                    embed={
                        "description": "<:warning:1430730420307234916> No promotion found with the given Promotion ID.",
                    },
                    ephemeral=True
                )
                return
        
        member = ctx.guild.get_member(int(promotion_data["member_id"]))
        if not member:
            try:
                member = await self.bot.fetch_user(int(promotion_data["member_id"]))
            except Exception:
                member = None
        if member.id == ctx.author.id:
            await ctx.send(embed={"description": "<:warning:1430730420307234916> You cannot revoke your own promotion."}, ephemeral=True)
            return
        new_role = ctx.guild.get_role(int(promotion_data["new_role_id"]))
        if not new_role:
            try:
                new_role = await ctx.guild.fetch_role(int(promotion_data["new_role_id"]))
            except Exception:
                new_role = None

        if member:
            timestamp = promotion_data.get("timestamp")
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp).replace(tzinfo=timezone.utc)
                    timestamp = str(Timestamp.fromdatetime(dt))
                except Exception:
                    timestamp = "Unknown"
            else:
                timestamp = "Unknown"
            promotion_revoked_embed = {
                "description": f"***Promotion ID {promotion_id} has been revoked by {ctx.author}***\n\n> **Member:** {member}\n> **Role Revoked:** @{new_role.name if new_role else 'Role not found'}\n> **Original Reason:** {promotion_data['reason'] if promotion_data['reason'] else 'No reason provided'}\n> **Issued At:** {timestamp}",
                "thumbnail": {"url": member.display_avatar.url},
                "author": {"name": f"Signed, {ctx.author}", "icon_url":ctx.author.display_avatar.url},
            }
            promotion_message_id = promotion_data.get("promotion_message_id")
            if promotion_message_id:
                config = await self.bot.mem_cache.get(f"guild_config_{ctx.guild.id}")
                if not config:
                    config = await self.bot.db.config.find_one({"guild_id": str(ctx.guild.id)})
                    if not config:
                        config = {}
                    await self.bot.mem_cache.set(f"guild_config_{ctx.guild.id}", config)
                promotion_channel_id = config.get("promotion_log")
                if promotion_channel_id:
                    promotion_channel = ctx.guild.get_channel(int(promotion_channel_id))
                    if not promotion_channel:
                        try:
                            promotion_channel = await ctx.guild.fetch_channel(int(promotion_channel_id))
                        except Exception:
                            promotion_channel = None
                    if promotion_channel:
                        try:
                            promotion_message = await promotion_channel.fetch_message(promotion_message_id)
                            await promotion_message.edit(embed=promotion_revoked_embed)
                        except Exception:
                            pass
                promotion_audit_channel_id = config.get("promotion_audit_log")
                if promotion_audit_channel_id:
                    promotion_audit_channel = ctx.guild.get_channel(int(promotion_audit_channel_id))
                    if not promotion_audit_channel:
                        try:
                            promotion_audit_channel = await ctx.guild.fetch_channel(int(promotion_audit_channel_id))
                        except Exception:
                            promotion_audit_channel = None
                    if promotion_audit_channel:
                        promotion_audit_message_id = promotion_data.get("promotion_audit_message_id")
                        if promotion_audit_message_id:
                            try:
                                promotion_audit_message = await promotion_audit_channel.fetch_message(promotion_audit_message_id)
                                await promotion_audit_message.edit(embed=promotion_revoked_embed)
                            except Exception:
                                pass
            try: await member.remove_role(new_role, reason=f"Promotion revoked by {ctx.author} | Promotion ID: {promotion_id}")
            except Exception: pass
            await self.bot.db.promotions.delete_one({"promotion_id": promotion_id, "guild_id": str(ctx.guild.id)})
            await self.bot.mem_cache.delete(f"promotion_{promotion_id}")
            await ctx.send(
                embed={
                    "description": f"<:check:1430728952535842907> Successfully revoked promotion of **{member}** from **@{new_role.name}**.",
                },
                ephemeral=True
            )
        else:
            await ctx.send(
                embed={
                    "description": "<:warning:1430730420307234916> Member does not have the promoted role or member not found.",
                },
                ephemeral=True
            )

    @promotions.subcommand(sub_cmd_name="edit", sub_cmd_description="Edit a promotion's details")
    @slash_option(
        name="promotion_id",
        description="The Promotion ID to edit",
        required=True,
        opt_type=OptionType.STRING
    )
    async def edit_promotion(self, ctx, promotion_id: str):

        config = await self.bot.mem_cache.get(f"guild_config_{ctx.guild.id}")
        if not config:
            config = await self.bot.db.config.find_one({"guild_id": str(ctx.guild.id)})
            if not config:
                config = {}
            await self.bot.mem_cache.set(f"guild_config_{ctx.guild.id}", config)
        promotion_issuer_role_id = config.get("promotion_issuer_role")

        if promotion_issuer_role_id:
            promotion_issuer_role = ctx.guild.get_role(int(promotion_issuer_role_id))
            if not promotion_issuer_role:
                try:
                    promotion_issuer_role = await ctx.guild.fetch_role(int(promotion_issuer_role_id))
                except Exception:
                    promotion_issuer_role = None
            if not promotion_issuer_role:
                await ctx.send(embed={"description": "<:warning:1430730420307234916> Promotion issuer role not found in the guild."}, ephemeral=True)
                return
            if promotion_issuer_role not in ctx.author.roles:
                await ctx.send(embed={"description": "<:warning:1430730420307234916> You don't have permission to edit promotions."}, ephemeral=True)
                return

        promotion_data = await self.bot.mem_cache.get(f"promotion_{promotion_id}")
        if not promotion_data:
            promotion_data = await self.bot.db.promotions.find_one(
                {"promotion_id": promotion_id, "guild_id": str(ctx.guild.id)}
            )
            if not promotion_data:
                await ctx.send(embed={"description": "<:warning:1430730420307234916> No promotion found with the given Promotion ID."}, ephemeral=True)
                return

        modal = Modal(
            ShortText(label="Reason", custom_id="reason", value=promotion_data.get("reason"), placeholder="New reason for the promotion", required=False),
            title=f"Editing Promotion {promotion_id}",
        )
        await ctx.send_modal(modal)
        modal_ctx = await self.bot.wait_for_modal(modal, timeout=120)
        
        new_reason = modal_ctx.responses["reason"]

        promotion_data["reason"] = new_reason

        await self.bot.db.promotions.update_one(
            {"promotion_id": promotion_id, "guild_id": str(ctx.guild.id)},
            {"$set": {"reason": new_reason}}
        )
        await self.bot.mem_cache.set(f"promotion_{promotion_id}", promotion_data)

        member = await self.bot.fetch_user(int(promotion_data["member_id"]))
        new_role = await ctx.guild.fetch_role(int(promotion_data["new_role_id"]))
        issuer = await self.bot.fetch_user(int(promotion_data["issued_by_id"]))

        promotion_message_id = promotion_data.get("promotion_message_id")
        promotion_channel_id = config.get("promotion_log")
        if promotion_message_id and promotion_channel_id:
            try:
                channel = await self.bot.fetch_channel(int(promotion_channel_id))
                message = await channel.fetch_message(promotion_message_id)
                await message.edit(
                    embed={
                        "description": f"**{member}**, you have been promoted.\n\n> **New Role:** @{new_role.name}\n> **Reason:** {new_reason if new_reason else 'No reason provided'}\n> **Promotion ID:** {promotion_id}",
                        "author": {"name": f"Signed, {issuer}", "icon_url": issuer.display_avatar.url},
                        "thumbnail": {"url": member.display_avatar.url},
                    }
                )
            except Exception:
                pass

        promotion_audit_message_id = promotion_data.get("promotion_audit_message_id")
        promotion_audit_channel_id = config.get("promotion_audit_log")
        if promotion_audit_message_id and promotion_audit_channel_id:
            try:
                channel = await self.bot.fetch_channel(int(promotion_audit_channel_id))
                message = await channel.fetch_message(promotion_audit_message_id)
                await message.edit(
                    embed={
                        "title": "Promotion Audit Log",
                        "description": f"> **Member Promoted:** {member.mention}\n> **New Role:** @{new_role.name}\n> **Promoted By:** {issuer.mention}\n> **Reason:** {new_reason if new_reason else 'No reason provided'}\n> **Promotion ID:** {promotion_id}",
                        "author": {"name": f"Signed, {issuer}", "icon_url": issuer.display_avatar.url},
                        "thumbnail": {"url": member.display_avatar.url},
                    }
                )
            except Exception:
                pass

        await modal_ctx.send(
            embed={
                "description": f"<:check:1430728952535842907> Successfully edited promotion **{promotion_id}**.",
            },
            ephemeral=True
        )

def setup(bot):
    Promotions(bot)