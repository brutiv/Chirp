from interactions import Extension, StringSelectOption, slash_command, slash_default_member_permission, Permissions, Button, ButtonStyle, StringSelectMenu
from interactions.api.events import Component

class Config(Extension):

    @slash_command(name="config", description="Configure bot settings", sub_cmd_name="set", sub_cmd_description="Set configuration options")
    @slash_default_member_permission(Permissions.MANAGE_GUILD)
    async def config(self, ctx):
        await ctx.defer(ephemeral=True)

        select_menu = StringSelectMenu(
            StringSelectOption(label="Promotion Log Channel", description="Channel to send promotions in", value="promotion_log"),
            StringSelectOption(label="Promotion Audit Log Channel", description="The channel to send promotion logs to", value="promotion_audit_log"),
            StringSelectOption(label="Infraction Log Channel", description="The channel to send infractions to", value="infraction_log"),
            StringSelectOption(label="Infraction Audit Log Channel", description="The channel to send infraction logs to", value="infraction_audit_log"),
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

            try: await self.bot.mem_cache.add(f"config_{ctx.guild.id}", {selected_setting_key: str(selected_channel.id)})
            except ValueError: 
                await self.bot.mem_cache.delete(f"config_{ctx.guild.id}")
                await self.bot.mem_cache.add(f"config_{ctx.guild.id}", {selected_setting_key: str(selected_channel.id)})

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

        config_data = await self.bot.mem_cache.get(f"config_{ctx.guild.id}")
        if not config_data:
            try:
                db_data = await self.bot.db.config.find_one({"guild_id": str(ctx.guild.id)})
                await self.bot.mem_cache.add(f"config_{ctx.guild.id}", db_data)
                config_data = db_data
            except Exception:
                config_data = {}
        
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

        embed_description = ""
        for key, value in display_data.items():
            channel_id_str = str(value)
            try:
                channel = ctx.guild.get_channel(int(channel_id_str))
                channel_mention = channel.mention if channel else f"Channel not found (ID: {channel_id_str})"
            except (ValueError, TypeError):
                channel_mention = f"Invalid Channel ID in config: {channel_id_str}"
            
            embed_description += f"**{key.replace('_', ' ').title()}**: {channel_mention}\n"

        await ctx.send(
            embed={
                "title": "Current Configuration",
                "description": embed_description,
                "thumbnail": {"url": ctx.guild.icon.url},
            },
            ephemeral=True,
        )

def setup(bot):
    Config(bot)