import json
import os
import re
import time
from datetime import datetime, timedelta, timezone

import nextcord
from nextcord import Interaction, slash_command
from nextcord.ext import commands

from database import (
    add_banned_link,
    add_custom_banned_word,
    add_whitelisted_word,
    clear_mute_state,
    ensure_default_banned_links,
    get_all_changelog_channels,
    get_banned_links,
    get_custom_banned_words,
    get_guild_moderation_records,
    get_member_moderation_record,
    get_moderation_log_channel,
    get_moderation_preferences,
    get_muted_role,
    get_warning_count,
    get_whitelisted_words,
    mark_mute_inactive,
    record_mute,
    remove_custom_banned_word,
    remove_whitelisted_word,
    reset_warning_count,
    set_changelog_channel,
    set_moderation_log_channel,
    set_muted_role,
    set_warning_count,
)

BOT_OWNER_ID = 595415508283686948


def default_blocked_links() -> list[str]:
    return [
        "https://www.pornhub.com",
        "https://www.onlyfans.com",
        "https://www.pornlive.com",
        "https://www.xvideos.com",
        "https://www.xhamster.com",
        "https://www.xnxx.com",
        "https://www.youporn.com",
        "https://www.hclips.com",
        "https://www.porn.com",
        "https://www.tnaflix.com",
        "https://www.tube8.com",
        "https://www.spankbang.com",
        "https://www.brazzers.com",
    ]


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.profanity_file_path = os.path.join(base_dir, "profanity.txt")
        self.twitch_file_path = os.path.join(base_dir, "twitch.json")

        if not os.path.exists(self.twitch_file_path):
            with open(self.twitch_file_path, "w", encoding="utf-8") as file:
                json.dump({}, file, indent=4)

        try:
            with open(self.profanity_file_path, "r", encoding="utf-8") as file:
                self.profanity = {
                    line.strip().lower() for line in file if line.strip()
                }
        except FileNotFoundError:
            print("[MODERATION] profanity.txt was not found.")
            self.profanity = set()

    @staticmethod
    def member_is_timed_out(
        member: nextcord.Member,
    ) -> tuple[bool, datetime | None]:
        timeout_until = getattr(
            member,
            "communication_disabled_until",
            None,
        )

        if timeout_until is None:
            return False, None

        if timeout_until.tzinfo is None:
            timeout_until = timeout_until.replace(
                tzinfo=timezone.utc
            )

        return (
            timeout_until > datetime.now(timezone.utc),
            timeout_until,
        )

    @staticmethod
    def format_remaining_time(
        end_time: datetime | None,
    ) -> str:
        if end_time is None:
            return "Until manually removed"

        remaining = end_time - datetime.now(timezone.utc)
        seconds = max(int(remaining.total_seconds()), 0)

        if seconds <= 0:
            return "Expired"

        days, seconds = divmod(seconds, 86400)
        hours, seconds = divmod(seconds, 3600)
        minutes, _ = divmod(seconds, 60)

        parts = []

        if days:
            parts.append(f"{days}d")

        if hours:
            parts.append(f"{hours}h")

        if minutes or not parts:
            parts.append(f"{minutes}m")

        return " ".join(parts)

    async def send_mod_log(
        self,
        guild: nextcord.Guild,
        title: str,
        description: str,
        member: nextcord.Member | None = None,
        moderator: nextcord.Member | nextcord.User | None = None,
        reason: str | None = None,
    ) -> bool:
        channel_id = await get_moderation_log_channel(
            guild.id
        )

        if channel_id is None:
            print(
                f"[MODERATION] No moderation log channel is configured "
                f"for {guild.name} ({guild.id})."
            )
            return False

        channel = guild.get_channel(channel_id)

        if not isinstance(channel, nextcord.TextChannel):
            print(
                f"[MODERATION] Configured moderation log channel "
                f"{channel_id} is missing in {guild.name} ({guild.id})."
            )
            return False

        embed = nextcord.Embed(
            title=title,
            description=description,
            timestamp=datetime.now(timezone.utc),
        )

        if member is not None:
            embed.add_field(
                name="Member",
                value=member.mention,
                inline=False,
            )

        if moderator is not None:
            embed.add_field(
                name="Moderator",
                value=moderator.mention,
                inline=False,
            )

        if reason:
            embed.add_field(
                name="Reason",
                value=reason[:1024],
                inline=False,
            )

        try:
            await channel.send(embed=embed)
            return True
        except nextcord.HTTPException as error:
            print(
                f"[MODERATION] Could not send a log in "
                f"{guild.name}: {error}"
            )
            return False

    async def safe_record_mute(
        self,
        guild_id: int,
        user_id: int,
        mute_type: str,
        timeout_end_time: float | None = None,
    ) -> bool:
        """Record mute history without blocking the actual moderation action."""
        try:
            await record_mute(
                guild_id,
                user_id,
                mute_type=mute_type,
                timeout_end_time=timeout_end_time,
            )
            return True
        except Exception as error:
            print(
                f"[MODERATION] Mute was applied, but its database "
                f"record failed for user {user_id} in guild "
                f"{guild_id}: {error}"
            )
            return False

    async def clear_member_mute(
        self,
        member: nextcord.Member,
        moderator: nextcord.Member | nextcord.User,
        reset_warnings: bool,
        reason: str,
    ) -> tuple[bool, bool]:
        guild = member.guild
        muted_role_id = await get_muted_role(guild.id)
        muted_role = (
            guild.get_role(muted_role_id)
            if muted_role_id
            else None
        )

        removed_role = False
        removed_timeout = False

        if muted_role and muted_role in member.roles:
            await member.remove_roles(
                muted_role,
                reason=reason,
            )
            removed_role = True

        timed_out, _ = self.member_is_timed_out(member)

        if timed_out:
            await member.timeout(
                timeout=None,
                reason=reason,
            )
            removed_timeout = True

        await clear_mute_state(
            guild.id,
            member.id,
            reset_warnings=reset_warnings,
        )

        if reset_warnings:
            await reset_warning_count(
                guild.id,
                member.id,
            )

        return removed_role, removed_timeout

    @slash_command(name="ban", description="Ban a member from this Discord")
    async def ban(
        self,
        interaction: Interaction,
        member: nextcord.Member,
        reason: str = "No reason provided",
    ):
        if not interaction.user.guild_permissions.ban_members:
            await interaction.response.send_message(
                "You do not have permission to ban members.", ephemeral=True
            )
            return
        try:
            await member.ban(reason=reason)
            await interaction.response.send_message(
                f"{member} was banned by {interaction.user.mention}. Reason: {reason}"
            )
            await self.send_mod_log(
                interaction.guild,
                "Member Banned",
                "A member was banned from the server.",
                member=member,
                moderator=interaction.user,
                reason=reason,
            )
        except nextcord.Forbidden:
            await interaction.response.send_message(
                "I could not ban that member. Check my permissions and role position.",
                ephemeral=True,
            )

    @slash_command(name="kick", description="Kick a member from this Discord")
    async def kick(
        self,
        interaction: Interaction,
        member: nextcord.Member,
        reason: str = "No reason provided",
    ):
        if not interaction.user.guild_permissions.kick_members:
            await interaction.response.send_message(
                "You do not have permission to kick members.", ephemeral=True
            )
            return
        try:
            await member.kick(reason=reason)
            await interaction.response.send_message(
                f"{member} was kicked by {interaction.user.mention}. Reason: {reason}"
            )
            await self.send_mod_log(
                interaction.guild,
                "Member Kicked",
                "A member was kicked from the server.",
                member=member,
                moderator=interaction.user,
                reason=reason,
            )
        except nextcord.Forbidden:
            await interaction.response.send_message(
                "I could not kick that member. Check my permissions and role position.",
                ephemeral=True,
            )

    @slash_command(name="purge", description="Delete up to 100 recent messages")
    async def purge(self, interaction: Interaction, limit: int):
        if not interaction.channel.permissions_for(interaction.user).manage_messages:
            await interaction.response.send_message(
                "You do not have permission to delete messages.", ephemeral=True
            )
            return
        if limit < 1 or limit > 100:
            await interaction.response.send_message(
                "Choose a number between 1 and 100.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=limit)
        await interaction.followup.send(
            f"Deleted {len(deleted)} message(s).", ephemeral=True
        )

    @slash_command(
        name="set_muted_role",
        description="Change the muted role after initial setup",
    )
    async def set_muted_role_command(
        self,
        interaction: Interaction,
        role: nextcord.Role,
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used inside a server.",
                ephemeral=True,
            )
            return

        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                "Only the server owner can change the muted role.",
                ephemeral=True,
            )
            return

        if role >= interaction.guild.me.top_role:
            await interaction.response.send_message(
                "My highest role must be above the muted role before I can assign it.",
                ephemeral=True,
            )
            return

        await set_muted_role(
            interaction.guild.id,
            role.id,
        )

        await interaction.response.send_message(
            f"The muted role was changed to {role.mention}.",
            ephemeral=True,
        )

    @slash_command(
        name="set_modlog_channel",
        description="Choose where moderation actions are logged",
    )
    async def set_modlog_channel_command(
        self,
        interaction: Interaction,
        channel: nextcord.TextChannel,
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used inside a server.",
                ephemeral=True,
            )
            return

        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                "Only the server owner can set the moderation log channel.",
                ephemeral=True,
            )
            return

        bot_member = interaction.guild.me

        if bot_member is None:
            await interaction.response.send_message(
                "I could not check my permissions.",
                ephemeral=True,
            )
            return

        permissions = channel.permissions_for(bot_member)

        if not (
            permissions.view_channel
            and permissions.send_messages
            and permissions.embed_links
        ):
            await interaction.response.send_message(
                f"I need **View Channel**, **Send Messages**, and "
                f"**Embed Links** in {channel.mention}.",
                ephemeral=True,
            )
            return

        await set_moderation_log_channel(
            interaction.guild.id,
            channel.id,
        )

        await interaction.response.send_message(
            f"Moderation logs will now be sent to {channel.mention}.",
            ephemeral=True,
        )

        await self.send_mod_log(
            interaction.guild,
            "Moderation Logging Enabled",
            "Jotoro will now record moderation actions in this channel.",
            moderator=interaction.user,
        )

    @slash_command(
        name="test_modlog",
        description="Test the configured moderation log channel",
    )
    async def test_modlog(
        self,
        interaction: Interaction,
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used inside a server.",
                ephemeral=True,
            )
            return

        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                "Only the server owner can test moderation logging.",
                ephemeral=True,
            )
            return

        sent = await self.send_mod_log(
            interaction.guild,
            "Moderation Log Test",
            "The moderation logging system is working correctly.",
            moderator=interaction.user,
        )

        await interaction.response.send_message(
            (
                "The test log was delivered successfully."
                if sent
                else (
                    "The test log could not be delivered. Run "
                    "`/set_modlog_channel` again and check my channel permissions."
                )
            ),
            ephemeral=True,
        )

    @slash_command(
        name="mute",
        description="Give a member the configured muted role",
    )
    async def mute(
        self,
        interaction: Interaction,
        member: nextcord.Member,
        reason: str,
    ):
        if not interaction.user.guild_permissions.mute_members:
            await interaction.response.send_message(
                "You do not have permission to mute members.",
                ephemeral=True,
            )
            return

        muted_role_id = await get_muted_role(
            interaction.guild.id
        )

        if muted_role_id is None:
            await interaction.response.send_message(
                "No muted role is configured. Run `/setup` first "
                "or use `/set_muted_role`.",
                ephemeral=True,
            )
            return

        muted_role = interaction.guild.get_role(
            muted_role_id
        )

        if muted_role is None:
            await interaction.response.send_message(
                "The configured muted role no longer exists.",
                ephemeral=True,
            )
            return

        bot_member = interaction.guild.me

        if bot_member is None:
            await interaction.response.send_message(
                "I could not check my role permissions.",
                ephemeral=True,
            )
            return

        if not bot_member.guild_permissions.manage_roles:
            await interaction.response.send_message(
                "I need the **Manage Roles** permission to apply the muted role.",
                ephemeral=True,
            )
            return

        if muted_role >= bot_member.top_role:
            await interaction.response.send_message(
                "My highest role must be above the configured muted role.",
                ephemeral=True,
            )
            return

        if member == interaction.guild.owner:
            await interaction.response.send_message(
                "Discord does not allow me to mute the server owner.",
                ephemeral=True,
            )
            return

        if member.top_role >= bot_member.top_role:
            await interaction.response.send_message(
                "My highest role must be above that member's highest role.",
                ephemeral=True,
            )
            return

        if muted_role in member.roles:
            await interaction.response.send_message(
                f"{member.mention} already has the muted role.",
                ephemeral=True,
            )
            return

        try:
            await member.add_roles(
                muted_role,
                reason=(
                    f"Muted by {interaction.user}: "
                    f"{reason}"
                ),
            )

            await self.safe_record_mute(
                interaction.guild.id,
                member.id,
                mute_type="role",
                timeout_end_time=None,
            )

            await interaction.response.send_message(
                f"{member.mention} was muted. Reason: {reason}"
            )

            await self.send_mod_log(
                interaction.guild,
                "Member Muted",
                "The configured muted role was applied.",
                member=member,
                moderator=interaction.user,
                reason=reason,
            )

        except nextcord.Forbidden:
            await interaction.response.send_message(
                "I could not assign the muted role. "
                "Check my permissions and role position.",
                ephemeral=True,
            )

    @slash_command(
        name="unmute",
        description="Remove a member's muted role or Discord timeout",
    )
    async def unmute(
        self,
        interaction: Interaction,
        member: nextcord.Member,
    ):
        if not interaction.user.guild_permissions.mute_members:
            await interaction.response.send_message(
                "You do not have permission to unmute members.",
                ephemeral=True,
            )
            return

        try:
            removed_role, removed_timeout = (
                await self.clear_member_mute(
                    member=member,
                    moderator=interaction.user,
                    reset_warnings=False,
                    reason=f"Unmuted by {interaction.user}",
                )
            )
        except nextcord.Forbidden:
            await interaction.response.send_message(
                "I could not remove that mute. "
                "Check my permissions and role position.",
                ephemeral=True,
            )
            return

        if not removed_role and not removed_timeout:
            await interaction.response.send_message(
                f"{member.mention} is not currently muted.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"{member.mention} was unmuted."
        )

        await self.send_mod_log(
            interaction.guild,
            "Member Unmuted",
            "The member's active mute was removed. "
            "Their warning count was preserved.",
            member=member,
            moderator=interaction.user,
        )

    @slash_command(
        name="clear_mute",
        description="Unmute a member and reset their AutoMod warnings",
    )
    async def clear_mute(
        self,
        interaction: Interaction,
        member: nextcord.Member,
        reason: str = "Mute record cleared by staff",
    ):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "You do not have permission to clear mute records.",
                ephemeral=True,
            )
            return

        warnings, mute_count, _, _, _ = (
            await get_member_moderation_record(
                interaction.guild.id,
                member.id,
            )
        )

        try:
            removed_role, removed_timeout = (
                await self.clear_member_mute(
                    member=member,
                    moderator=interaction.user,
                    reset_warnings=True,
                    reason=reason,
                )
            )
        except nextcord.Forbidden:
            await interaction.response.send_message(
                "I could not remove the member's role or timeout. "
                "Check my permissions and role position.",
                ephemeral=True,
            )
            return

        changed = (
            removed_role
            or removed_timeout
            or warnings > 0
        )

        await interaction.response.send_message(
            (
                f"{member.mention} was removed from the muted list, "
                "their active mute was cleared, and their warnings "
                f"were reset. Historical mutes: **{mute_count}**."
                if changed
                else (
                    f"{member.mention} had no active mute or warnings. "
                    f"Historical mutes: **{mute_count}**."
                )
            ),
            ephemeral=True,
        )

        await self.send_mod_log(
            interaction.guild,
            "Mute Record Cleared",
            "The member was unmuted and their active warnings were reset. "
            "Historical mute totals were preserved.",
            member=member,
            moderator=interaction.user,
            reason=reason,
        )

    @slash_command(
        name="warnings",
        description="View a member's warnings and mute history",
    )
    async def warnings_command(
        self,
        interaction: Interaction,
        member: nextcord.Member,
    ):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message(
                "You do not have permission to view moderation records.",
                ephemeral=True,
            )
            return

        (
            warning_count,
            mute_count,
            database_muted,
            _,
            mute_type,
        ) = await get_member_moderation_record(
            interaction.guild.id,
            member.id,
        )

        muted_role_id = await get_muted_role(
            interaction.guild.id
        )
        muted_role = (
            interaction.guild.get_role(muted_role_id)
            if muted_role_id
            else None
        )

        has_muted_role = bool(
            muted_role and muted_role in member.roles
        )
        timed_out, timeout_until = (
            self.member_is_timed_out(member)
        )

        currently_muted = (
            database_muted
            or has_muted_role
            or timed_out
        )

        if timed_out:
            active_method = "Discord timeout"
            remaining = self.format_remaining_time(
                timeout_until
            )
        elif has_muted_role:
            active_method = "Muted role"
            remaining = "Until manually removed"
        elif currently_muted:
            active_method = mute_type or "Stored mute record"
            remaining = "Stored state may be stale"
        else:
            active_method = "None"
            remaining = "Not muted"

        embed = nextcord.Embed(
            title=f"Moderation Record — {member.display_name}",
        )

        embed.add_field(
            name="Active warnings",
            value=str(warning_count),
            inline=True,
        )

        embed.add_field(
            name="Times muted",
            value=str(mute_count),
            inline=True,
        )

        embed.add_field(
            name="Currently muted",
            value="Yes" if currently_muted else "No",
            inline=True,
        )

        embed.add_field(
            name="Mute method",
            value=active_method,
            inline=True,
        )

        embed.add_field(
            name="Remaining",
            value=remaining,
            inline=True,
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )

    @slash_command(
        name="muted_members",
        description="List members currently muted by role or timeout",
    )
    async def muted_members(
        self,
        interaction: Interaction,
    ):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message(
                "You do not have permission to view muted members.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        muted_role_id = await get_muted_role(guild.id)
        muted_role = (
            guild.get_role(muted_role_id)
            if muted_role_id
            else None
        )

        records = {
            user_id: (
                warnings,
                mute_count,
                database_muted,
                timeout_end,
                mute_type,
            )
            for (
                user_id,
                warnings,
                mute_count,
                database_muted,
                timeout_end,
                mute_type,
            ) in await get_guild_moderation_records(guild.id)
        }

        lines = []

        for member in guild.members:
            has_muted_role = bool(
                muted_role and muted_role in member.roles
            )
            timed_out, timeout_until = (
                self.member_is_timed_out(member)
            )

            record = records.get(
                member.id,
                (0, 0, False, None, None),
            )

            (
                warning_count,
                mute_count,
                database_muted,
                _,
                mute_type,
            ) = record

            actually_muted = has_muted_role or timed_out

            if not actually_muted:
                if database_muted:
                    await mark_mute_inactive(
                        guild.id,
                        member.id,
                    )
                continue

            if timed_out:
                method = "Timeout"
                remaining = self.format_remaining_time(
                    timeout_until
                )
            else:
                method = "Muted role"
                remaining = "Manual removal"

            lines.append(
                f"**{member.display_name}** — "
                f"Warnings: **{warning_count}** | "
                f"Times muted: **{mute_count}** | "
                f"{method}: **{remaining}**"
            )

        if not lines:
            await interaction.followup.send(
                "No members are currently muted.",
                ephemeral=True,
            )
            return

        chunks = []
        current_chunk = ""

        for line in lines:
            candidate = (
                f"{current_chunk}\n{line}"
                if current_chunk
                else line
            )

            if len(candidate) > 3900:
                chunks.append(current_chunk)
                current_chunk = line
            else:
                current_chunk = candidate

        if current_chunk:
            chunks.append(current_chunk)

        for index, chunk in enumerate(chunks, start=1):
            embed = nextcord.Embed(
                title=(
                    "Currently Muted Members"
                    if len(chunks) == 1
                    else (
                        f"Currently Muted Members "
                        f"— Part {index}"
                    )
                ),
                description=chunk,
            )

            await interaction.followup.send(
                embed=embed,
                ephemeral=True,
            )

    @slash_command(
        name="whitelist",
        description="Add or remove a word from this server's whitelist",
    )
    async def whitelist(
        self,
        interaction: Interaction,
        action: str,
        word: str,
    ):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "You do not have permission to manage the whitelist.",
                ephemeral=True,
            )
            return

        action = action.strip().lower()
        word = word.strip().lower()

        if action == "add":
            changed = await add_whitelisted_word(interaction.guild.id, word)
            message = (
                f"`{word}` was added to the whitelist."
                if changed
                else f"`{word}` is already whitelisted."
            )
        elif action == "remove":
            changed = await remove_whitelisted_word(interaction.guild.id, word)
            message = (
                f"`{word}` was removed from the whitelist."
                if changed
                else f"`{word}` was not whitelisted."
            )
        else:
            message = "The action must be `add` or `remove`."

        await interaction.response.send_message(message, ephemeral=True)

    @slash_command(
        name="list_whitelisted",
        description="List this server's whitelisted words",
    )
    async def list_whitelisted(self, interaction: Interaction):
        words = await get_whitelisted_words(interaction.guild.id)
        await interaction.response.send_message(
            (
                "**Whitelisted words:**\n```text\n"
                + "\n".join(words)
                + "\n```"
                if words
                else "This server has no whitelisted words."
            ),
            ephemeral=True,
        )

    @slash_command(name="add_word", description="Add a custom banned word")
    async def add_word(self, interaction: Interaction, word: str):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "You do not have permission to add banned words.",
                ephemeral=True,
            )
            return

        word = word.strip().lower()
        changed = await add_custom_banned_word(interaction.guild.id, word)

        await interaction.response.send_message(
            (
                f"`{word}` was added to this server's banned-word list."
                if changed
                else f"`{word}` is already in this server's banned-word list."
            ),
            ephemeral=True,
        )

    @slash_command(name="remove_word", description="Remove a custom banned word")
    async def remove_word(self, interaction: Interaction, word: str):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "You do not have permission to remove banned words.",
                ephemeral=True,
            )
            return

        word = word.strip().lower()
        changed = await remove_custom_banned_word(interaction.guild.id, word)

        await interaction.response.send_message(
            (
                f"`{word}` was removed from this server's banned-word list."
                if changed
                else f"`{word}` was not in this server's custom banned-word list."
            ),
            ephemeral=True,
        )

    @slash_command(name="list_banned", description="List banned words")
    async def list_banned(self, interaction: Interaction):
        custom_words = set(
            await get_custom_banned_words(interaction.guild.id)
        )
        use_default_words, _ = await get_moderation_preferences(
            interaction.guild.id
        )

        active_words = (
            self.profanity.union(custom_words)
            if use_default_words
            else custom_words
        )
        words = sorted(active_words)

        if not words:
            await interaction.response.send_message(
                "No banned words are configured.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        for index in range(0, len(words), 50):
            chunk = words[index:index + 50]
            embed = nextcord.Embed(
                title=f"Banned Words — Part {index // 50 + 1}",
                description="\n".join(chunk)[:4000],
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @slash_command(
        name="resetwarnings",
        description="Reset a member's AutoMod warning count",
    )
    async def reset_warnings(
        self,
        interaction: Interaction,
        member: nextcord.Member = None,
    ):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "You do not have permission to reset warnings.",
                ephemeral=True,
            )
            return

        member = member or interaction.user

        previous_warnings = await get_warning_count(
            interaction.guild.id,
            member.id,
        )

        await reset_warning_count(
            interaction.guild.id,
            member.id,
        )

        await interaction.response.send_message(
            (
                f"Warnings for {member.mention} were reset "
                f"from **{previous_warnings}** to **0**."
                if previous_warnings
                else f"{member.mention} already has zero warnings."
            ),
            ephemeral=True,
        )

        if previous_warnings:
            await self.send_mod_log(
                interaction.guild,
                "Warnings Reset",
                "A member's active AutoMod warnings were reset.",
                member=member,
                moderator=interaction.user,
            )

    @slash_command(name="ban_link", description="Ban a link from this server")
    async def ban_link(self, interaction: Interaction, link: str):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "You do not have permission to ban links.",
                ephemeral=True,
            )
            return

        link = link.strip()
        changed = await add_banned_link(interaction.guild.id, link)

        await interaction.response.send_message(
            (
                f"That link is now banned:\n`{link}`"
                if changed
                else f"That link is already banned:\n`{link}`"
            ),
            ephemeral=True,
        )

    @slash_command(
        name="list_banned_links",
        description="List all banned links for this server",
    )
    async def list_banned_links(self, interaction: Interaction):
        _, use_default_links = await get_moderation_preferences(
            interaction.guild.id
        )

        if use_default_links:
            await ensure_default_banned_links(
                interaction.guild.id,
                default_blocked_links(),
            )

        links = await get_banned_links(interaction.guild.id)

        await interaction.response.send_message(
            (
                "**Banned links:**\n```text\n"
                + "\n".join(links)
                + "\n```"
                if links
                else "This server has no banned links."
            ),
            ephemeral=True,
        )

    @slash_command(name="sendreport", description="Send a bug report to the bot owner")
    async def sendreport(self, interaction: Interaction, message: str):
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                "Only the server owner can submit a report.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        owner = self.bot.get_user(BOT_OWNER_ID)

        if owner is None:
            try:
                owner = await self.bot.fetch_user(BOT_OWNER_ID)
            except nextcord.HTTPException:
                owner = None

        if owner is None:
            await interaction.followup.send(
                "The bot owner could not be reached.",
                ephemeral=True,
            )
            return

        report = (
            "**New Jotoro Moderation Report**\n"
            f"Server: {interaction.guild.name}\n"
            f"Guild ID: {interaction.guild.id}\n"
            f"Server owner: {interaction.user} ({interaction.user.id})\n\n"
            f"Report:\n{message}"
        )

        try:
            await owner.send(report)
            await interaction.followup.send(
                "Your report was sent to the bot owner.",
                ephemeral=True,
            )
        except nextcord.HTTPException:
            await interaction.followup.send(
                "The report could not be delivered.",
                ephemeral=True,
            )

    @slash_command(
        name="set_changelog_channel",
        description="Set this server's changelog channel",
    )
    async def set_changelog_channel_command(
        self,
        interaction: Interaction,
        channel: nextcord.TextChannel,
    ):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "You do not have permission to set the changelog channel.",
                ephemeral=True,
            )
            return

        await set_changelog_channel(interaction.guild.id, channel.id)
        await interaction.response.send_message(
            f"The changelog channel was set to {channel.mention}.",
            ephemeral=True,
        )

    @slash_command(
        name="send_changelogs",
        description="Send a changelog to all configured servers",
    )
    async def send_changelogs(
        self,
        interaction: Interaction,
        message: str,
    ):
        if interaction.user.id != BOT_OWNER_ID:
            await interaction.response.send_message(
                "You are not authorized to use this command.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        sent_count = 0

        for guild_id, channel_id in await get_all_changelog_channels():
            guild = self.bot.get_guild(guild_id)
            channel = guild.get_channel(channel_id) if guild else None

            if isinstance(channel, nextcord.TextChannel):
                try:
                    await channel.send(
                        f"**Jotoro Moderation Changelog**\n{message}"
                    )
                    sent_count += 1
                except nextcord.HTTPException as error:
                    print(f"[CHANGELOG] Failed in guild {guild_id}: {error}")

        await interaction.followup.send(
            f"Changelog sent to {sent_count} server(s).",
            ephemeral=True,
        )

    @slash_command(name="discords", description="List every server using the bot")
    async def discords(self, interaction: Interaction):
        if interaction.user.id != BOT_OWNER_ID:
            await interaction.response.send_message(
                "You are not authorized to use this command.",
                ephemeral=True,
            )
            return

        names = "\n".join(
            f"• {guild.name} ({guild.id})" for guild in self.bot.guilds
        )
        await interaction.response.send_message(
            f"**Servers using Jotoro Moderation:**\n{names}",
            ephemeral=True,
        )

    # Twitch configuration remains in twitch.json until twitch.py is enabled.
    def load_twitch_data(self) -> dict:
        try:
            with open(self.twitch_file_path, "r", encoding="utf-8") as file:
                data = json.load(file)
                return data if isinstance(data, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_twitch_data(self, data: dict) -> None:
        temporary_path = f"{self.twitch_file_path}.tmp"
        with open(temporary_path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4)
        os.replace(temporary_path, self.twitch_file_path)

    @staticmethod
    def get_guild_twitch_data(data: dict, guild_id: str) -> dict:
        return data.setdefault(
            guild_id,
            {
                "notification_channel_id": None,
                "mention_role_id": None,
                "twitch_channels": [],
            },
        )

    @staticmethod
    def normalize_twitch_username(value: str) -> str:
        username = value.strip().lower()

        for prefix in (
            "https://www.twitch.tv/",
            "https://twitch.tv/",
            "http://www.twitch.tv/",
            "http://twitch.tv/",
            "www.twitch.tv/",
            "twitch.tv/",
        ):
            if username.startswith(prefix):
                username = username[len(prefix):]
                break

        return username.split("?", 1)[0].split("/", 1)[0].strip()

    @slash_command(
        name="setnotificationchannel",
        description="Set this server's Twitch notification channel and role",
    )
    async def setnotificationchannel(
        self,
        interaction: Interaction,
        channel: nextcord.TextChannel,
        role: nextcord.Role = None,
    ):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "You do not have permission to configure Twitch notifications.",
                ephemeral=True,
            )
            return

        data = self.load_twitch_data()
        guild_data = self.get_guild_twitch_data(
            data, str(interaction.guild.id)
        )
        guild_data["notification_channel_id"] = channel.id
        guild_data["mention_role_id"] = role.id if role else None
        self.save_twitch_data(data)

        await interaction.response.send_message(
            f"Twitch notifications will be sent to {channel.mention} "
            f"and will mention {role.mention if role else 'no role'}.",
            ephemeral=True,
        )

    @slash_command(
        name="addtwitchchannel",
        description="Add a Twitch channel to this server",
    )
    async def addtwitchchannel(
        self,
        interaction: Interaction,
        twitch_channel: str,
    ):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "You do not have permission to manage Twitch channels.",
                ephemeral=True,
            )
            return

        username = self.normalize_twitch_username(twitch_channel)

        if not username:
            await interaction.response.send_message(
                "Provide a valid Twitch username or channel URL.",
                ephemeral=True,
            )
            return

        data = self.load_twitch_data()
        guild_data = self.get_guild_twitch_data(
            data, str(interaction.guild.id)
        )
        channels = guild_data["twitch_channels"]

        if username in channels:
            await interaction.response.send_message(
                f"`{username}` is already followed by this server.",
                ephemeral=True,
            )
            return

        channels.append(username)
        channels.sort()
        self.save_twitch_data(data)

        await interaction.response.send_message(
            f"Added `{username}` to this server's Twitch notifications.",
            ephemeral=True,
        )

    @slash_command(
        name="removetwitchchannel",
        description="Remove a Twitch channel from this server",
    )
    async def removetwitchchannel(
        self,
        interaction: Interaction,
        twitch_channel: str,
    ):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "You do not have permission to manage Twitch channels.",
                ephemeral=True,
            )
            return

        username = self.normalize_twitch_username(twitch_channel)
        data = self.load_twitch_data()
        guild_data = self.get_guild_twitch_data(
            data, str(interaction.guild.id)
        )
        channels = guild_data["twitch_channels"]

        if username not in channels:
            await interaction.response.send_message(
                f"`{username}` is not followed by this server.",
                ephemeral=True,
            )
            return

        channels.remove(username)
        self.save_twitch_data(data)

        await interaction.response.send_message(
            f"Removed `{username}` from this server's Twitch notifications.",
            ephemeral=True,
        )

    @slash_command(
        name="listtwitchchannels",
        description="List Twitch channels followed by this server",
    )
    async def listtwitchchannels(self, interaction: Interaction):
        data = self.load_twitch_data()
        guild_data = self.get_guild_twitch_data(
            data, str(interaction.guild.id)
        )
        channels = guild_data["twitch_channels"]

        if not channels:
            await interaction.response.send_message(
                "This server is not following any Twitch channels.",
                ephemeral=True,
            )
            return

        formatted = "\n".join(
            f"• [{username}](https://www.twitch.tv/{username})"
            for username in sorted(channels)
        )

        await interaction.response.send_message(
            f"**Twitch channels followed by this server:**\n{formatted}",
            ephemeral=True,
        )
    @slash_command(
    name="help",
    description="View Jotoro Moderation commands and setup information",
        )
    async def help_command(self, interaction: Interaction):
        embed = nextcord.Embed(
            title="Jotoro Moderation Help",
            description=(
                "Use the sections below to find the commands you need. "
                "Some commands require administrator, moderator, or server-owner permissions."
            ),
        )

        embed.add_field(
            name="⚙️ Server Setup",
            value=(
            "`/setup` — Configure moderation, lists, muted role, and changelogs.\n"
            "`/setup_status` — Review the current server configuration.\n"
            "`/setup_tickets` — Create the ticket category and choose support settings."
            ),
            inline=False,
        )

        embed.add_field(
            name="🛡️ Moderation",
            value=(
            "`/ban` — Ban a member.\n"
            "`/kick` — Kick a member.\n"
            "`/mute` — Apply the configured muted role.\n"
            "`/unmute` — Remove a role mute or Discord timeout.\n"
            "`/clear_mute` — Unmute a member and reset warnings.\n"
            "`/warnings` — View one member's moderation record.\n"
            "`/muted_members` — List everyone currently muted.\n"
            "`/set_muted_role` — Change the server's muted role.\n"
            "`/set_modlog_channel` — Choose the moderation log channel.\n"
            "`/test_modlog` — Verify that moderation logs can be delivered.\n"
            "`/purge` — Delete recent messages.\n"
            "`/resetwarnings` — Reset warnings without changing mute history."
            ),
            inline=False,
        )

        embed.add_field(
            name="🚫 Words and Links",
            value=(
            "`/add_word` — Add a custom banned word.\n"
            "`/remove_word` — Remove a custom banned word.\n"
            "`/list_banned` — View active banned words.\n"
            "`/whitelist` — Add or remove a whitelisted word.\n"
            "`/list_whitelisted` — View whitelisted words.\n"
            "`/ban_link` — Add a server-specific blocked link.\n"
            "`/list_banned_links` — View active blocked links."
            ),
            inline=False,
        )

        embed.add_field(
            name="🎫 Tickets",
            value=(
            "`/newticket` — Create a private support ticket.\n"
            "`/close` — Close the current ticket and generate a transcript.\n"
            "`/add_support_role` — Add a ticket support role.\n"
            "`/remove_support_role` — Remove a support role.\n"
            "`/support_roles` — View configured support roles."
            ),
            inline=False,
        )

        embed.add_field(
            name="📢 Updates and Support",
            value=(
            "`/sendreport` — Send a bug report or request to the bot owner.\n"
            "`/set_changelog_channel` — Change where bot updates are posted."
            ),
            inline=False,
        )

        embed.add_field(
            name="📺 Twitch",
            value="Twitch live notifications are currently in development.",
            inline=False,
        )

        embed.set_footer(
            text="Jotoro Moderation • Use /setup first on new servers"
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )

    @commands.Cog.listener()
    async def on_message(self, message: nextcord.Message):
        if message.author.bot or message.guild is None:
            return

        if (
            message.author.guild_permissions.manage_messages
            or message.author.guild_permissions.ban_members
        ):
            return

        _, use_default_links = await get_moderation_preferences(
            message.guild.id
        )

        if use_default_links:
            await ensure_default_banned_links(
                message.guild.id,
                default_blocked_links(),
            )

        lowered_content = message.content.lower()

        for link in await get_banned_links(message.guild.id):
            if link.lower() in lowered_content:
                try:
                    await message.delete()
                    await message.channel.send(
                        f"{message.author.mention}, that link is banned from this Discord."
                    )
                    await self.send_mod_log(
                        message.guild,
                        "Blocked Link Removed",
                        (
                            f"A blocked link was removed from "
                            f"{message.channel.mention}."
                        ),
                        member=message.author,
                        reason="Matched the server's blocked-link list",
                    )
                except nextcord.Forbidden:
                    print(
                        f"[MODERATION] Missing permissions in guild {message.guild.id}."
                    )
                return

        await self.check_message(message)

    async def check_message(self, message: nextcord.Message):
        custom_words = set(
            await get_custom_banned_words(message.guild.id)
        )
        whitelisted_words = set(
            await get_whitelisted_words(message.guild.id)
        )

        use_default_words, _ = await get_moderation_preferences(
            message.guild.id
        )

        active_words = (
            self.profanity.union(custom_words)
            if use_default_words
            else custom_words
        )

        banned_words = {
            word
            for word in active_words
            if word and word not in whitelisted_words
        }

        if not banned_words:
            return

        pattern = r"\b(?:{})\b".format(
            "|".join(
                sorted(
                    (re.escape(word) for word in banned_words),
                    key=len,
                    reverse=True,
                )
            )
        )

        if not re.search(pattern, message.content.lower()):
            return

        try:
            await message.delete()
        except nextcord.Forbidden:
            print(
                f"[MODERATION] Could not delete message | "
                f"Server: {message.guild.name} ({message.guild.id}) | "
                f"Channel: #{message.channel.name} | "
                f"User: {message.author}"
            )
            return

        current_warnings = await get_warning_count(
            message.guild.id, message.author.id
        )
        new_warning_count = current_warnings + 1

        timeout_seconds = {
            2: 300,
            3: 3600,
            4: 604800,
        }.get(new_warning_count)

        if new_warning_count >= 5:
            await set_warning_count(
                message.guild.id,
                message.author.id,
                new_warning_count,
            )
            await message.channel.send(
                f"{message.author.mention}, you were banned after repeated moderation offenses."
            )
            try:
                await message.author.ban(
                    reason="Reached five automatic moderation offenses"
                )
                await self.send_mod_log(
                    message.guild,
                    "AutoMod Ban",
                    "A member was banned after reaching five offenses.",
                    member=message.author,
                    reason="Reached five automatic moderation offenses",
                )
            except nextcord.Forbidden:
                await message.channel.send(
                    "I could not ban that member. Check my permissions and role position."
                )
            return

        timeout_end = (
            time.time() + timeout_seconds if timeout_seconds else None
        )

        await set_warning_count(
            message.guild.id,
            message.author.id,
            new_warning_count,
            timeout_end,
        )

        if new_warning_count == 1:
            await message.channel.send(
                f"{message.author.mention}, your message contained a banned word. "
                "This is your warning before being timed out."
            )
            await self.send_mod_log(
                message.guild,
                "AutoMod Warning",
                (
                    f"A banned-word violation was removed from "
                    f"{message.channel.mention}."
                ),
                member=message.author,
                reason="Automatic moderation offense 1 of 5",
            )
            return

        timeout_labels = {
            2: "5 minutes",
            3: "1 hour",
            4: "1 week",
        }

        try:
            await message.author.timeout(
                timeout=timedelta(seconds=timeout_seconds),
                reason="Automatic moderation offense",
            )

            await self.safe_record_mute(
                message.guild.id,
                message.author.id,
                mute_type="timeout",
                timeout_end_time=timeout_end,
            )

            await message.channel.send(
                f"{message.author.mention}, your message contained a banned word. "
                f"You have been timed out for {timeout_labels[new_warning_count]}."
            )

            await self.send_mod_log(
                message.guild,
                "AutoMod Timeout",
                (
                    f"A banned-word violation was removed from "
                    f"{message.channel.mention}.\n"
                    f"Duration: **{timeout_labels[new_warning_count]}**\n"
                    f"Current warnings: **{new_warning_count}**"
                ),
                member=message.author,
                reason="Automatic moderation offense",
            )
        except nextcord.Forbidden:
            muted_role_id = await get_muted_role(message.guild.id)
            muted_role = (
                message.guild.get_role(muted_role_id)
                if muted_role_id
                else None
            )

            if muted_role:
                try:
                    await message.author.add_roles(
                        muted_role,
                        reason="Automatic moderation offense",
                    )

                    await self.safe_record_mute(
                        message.guild.id,
                        message.author.id,
                        mute_type="role",
                        timeout_end_time=None,
                    )

                    await message.channel.send(
                        f"{message.author.mention}, the muted role was applied "
                        "because I could not use Discord timeout."
                    )

                    await self.send_mod_log(
                        message.guild,
                        "AutoMod Muted Role",
                        (
                            f"A banned-word violation was removed from "
                            f"{message.channel.mention}. "
                            "Discord timeout was unavailable, so the "
                            "configured muted role was applied."
                        ),
                        member=message.author,
                        reason=(
                            f"Automatic moderation offense "
                            f"{new_warning_count} of 5"
                        ),
                    )
                except nextcord.Forbidden:
                    await message.channel.send(
                        "I could not timeout or mute that member. "
                        "Check my permissions and role position."
                    )
            else:
                await message.channel.send(
                    "I could not timeout that member, and no muted role is configured."
                )


def setup(bot: commands.Bot):
    bot.add_cog(Moderation(bot))
