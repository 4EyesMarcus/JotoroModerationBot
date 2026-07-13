import json
import os
import re
import time
from datetime import timedelta

import nextcord
from nextcord import Interaction, slash_command
from nextcord.ext import commands

from database import (
    add_banned_link,
    add_custom_banned_word,
    add_whitelisted_word,
    ensure_default_banned_links,
    get_all_changelog_channels,
    get_banned_links,
    get_custom_banned_words,
    get_moderation_preferences,
    get_muted_role,
    get_warning_count,
    get_whitelisted_words,
    remove_custom_banned_word,
    remove_whitelisted_word,
    reset_warning_count,
    set_changelog_channel,
    set_muted_role,
    set_warning_count,
)


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

    @slash_command(name="mute", description="Give a member the configured muted role")
    async def mute(
        self,
        interaction: Interaction,
        member: nextcord.Member,
        reason: str,
    ):
        if not interaction.user.guild_permissions.mute_members:
            await interaction.response.send_message(
                "You do not have permission to mute members.", ephemeral=True
            )
            return
        muted_role_id = await get_muted_role(interaction.guild.id)
        if muted_role_id is None:
            await interaction.response.send_message(
                "No muted role is configured. Run `/setup` first or use `/set_muted_role`.",
                ephemeral=True,
            )
            return
        muted_role = interaction.guild.get_role(muted_role_id)
        if muted_role is None:
            await interaction.response.send_message(
                "The configured muted role no longer exists.", ephemeral=True
            )
            return
        try:
            await member.add_roles(
                muted_role, reason=f"Muted by {interaction.user}: {reason}"
            )
            await interaction.response.send_message(
                f"{member.mention} was muted. Reason: {reason}"
            )
        except nextcord.Forbidden:
            await interaction.response.send_message(
                "I could not assign the muted role. Check my permissions and role position.",
                ephemeral=True,
            )

    @slash_command(name="unmute", description="Remove the configured muted role")
    async def unmute(self, interaction: Interaction, member: nextcord.Member):
        if not interaction.user.guild_permissions.mute_members:
            await interaction.response.send_message(
                "You do not have permission to unmute members.", ephemeral=True
            )
            return
        muted_role_id = await get_muted_role(interaction.guild.id)
        muted_role = (
            interaction.guild.get_role(muted_role_id) if muted_role_id else None
        )
        if muted_role is None:
            await interaction.response.send_message(
                "No valid muted role is configured.", ephemeral=True
            )
            return
        if muted_role not in member.roles:
            await interaction.response.send_message(
                f"{member.mention} is not muted.", ephemeral=True
            )
            return
        try:
            await member.remove_roles(
                muted_role, reason=f"Unmuted by {interaction.user}"
            )
            await interaction.response.send_message(
                f"{member.mention} was unmuted."
            )
        except nextcord.Forbidden:
            await interaction.response.send_message(
                "I could not remove the muted role.", ephemeral=True
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
        description="Reset a member's automatic moderation warnings",
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
        had_warnings = await reset_warning_count(
            interaction.guild.id, member.id
        )

        muted_role_id = await get_muted_role(interaction.guild.id)
        muted_role = (
            interaction.guild.get_role(muted_role_id)
            if muted_role_id
            else None
        )

        if muted_role and muted_role in member.roles:
            try:
                await member.remove_roles(
                    muted_role,
                    reason=f"Warnings reset by {interaction.user}",
                )
            except nextcord.Forbidden:
                pass

        await interaction.response.send_message(
            (
                f"Warnings for {member.mention} were reset."
                if had_warnings
                else f"{member.mention} already has zero warnings."
            ),
            ephemeral=True,
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
                f"[MODERATION] Could not delete a message in guild {message.guild.id}."
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
            await message.channel.send(
                f"{message.author.mention}, your message contained a banned word. "
                f"You have been timed out for {timeout_labels[new_warning_count]}."
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
                    await message.channel.send(
                        f"{message.author.mention}, the muted role was applied "
                        "because I could not use Discord timeout."
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