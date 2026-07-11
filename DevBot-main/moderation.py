from asyncio import Event
import nextcord
from nextcord import slash_command, Interaction
from nextcord.ext import commands
import os
import json
import time
import asyncio
import re

YOUR_DISCORD_USERNAME = 595415508283686948  # Replace with your actual Discord ID


# Function to return the default blocked links
def default_blocked_links():
    return [
        "https://www.pornhub.com",
        "https://www.onlyfans.com",
        "https://www.pornlive.com",
        "https://www.xVideos.com",
        "https://www.xHamster.com",
        "https://www.XNXX.com",
        "https://www.YouPorn.com",
        "https://www.HClips.com",
        "https://www.porn.com",
        "https://www.tnaflix.com",
        "https://www.tube8.com",
        "https://www.spankbang.com",
        "https://www.brazzers.com",
    ]


# Function to add a new server with default blocked links
def add_new_server(server_id: str, blocked_links_dict: dict):
    blocked_links_dict[server_id] = default_blocked_links()


class moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.whitelist = {}

        self.profanity_file_path = os.path.join(
            os.path.dirname(__file__), "profanity.txt"
        )
        self.whitelist_file_path = os.path.join(
            os.path.dirname(__file__), "whitelist.json"
        )
        self.warnings_file_path = os.path.join(
            os.path.dirname(__file__), "user_warnings.json"
        )
        self.settings_file_path = os.path.join(
            os.path.dirname(__file__), "settings.json"
        )
        self.words_file_path = os.path.join(
            os.path.dirname(__file__), "added_words.json"
        )
        self.links_file_path = os.path.join(os.path.dirname(__file__), "links.json")
        self.changelog_file_path = os.path.join(
            os.path.dirname(__file__), "changelog.json"
        )
        self.twitch_file_path = os.path.join(os.path.dirname(__file__), "twitch.json")

        # Create twitch.json on first run so all Twitch settings stay in one file.
        if not os.path.exists(self.twitch_file_path):
            with open(self.twitch_file_path, "w", encoding="utf-8") as f:
                json.dump({}, f, indent=4)

        # Loading Data Files
        try:
            with open(self.profanity_file_path, "r") as f:
                self.profanity = f.read().splitlines()
        except FileNotFoundError:
            print("File not found: profanity.txt")
            self.profanity = []
        try:
            with open(self.whitelist_file_path, "r") as f:
                self.whitelist = json.load(f)
        except FileNotFoundError:
            print("File not found: whitelist.json")
            self.whitelist = {}
        try:
            with open(self.warnings_file_path, "r") as f:
                self.data = json.load(f)
        except FileNotFoundError:
            self.data = {}

    # Defines settings

    def get_settings():
        with open("settings.json", "r") as f:
            settings = json.load(f)
        return settings

    def save_settings(settings):
        with open("settings.json", "w") as f:
            json.dump(settings, f)

    # Moderation Commands

    @slash_command(
        name="whitelist", description="Add or remove a word from the whitelist"
    )
    async def whitelist(self, ctx: Interaction, action: str = None, word: str = None):
        if not ctx.user.guild_permissions.administrator:
            await ctx.send(
                "You do not have the required permissions to use this command."
            )
            return

        if action not in ["add", "remove"]:
            await ctx.send(
                "Invalid action. Please specify 'add' or 'remove' as the first argument."
            )
            return

        if not word:
            await ctx.send("Please specify a word to whitelist.")
            return

        whitelist_file_path = os.path.join(
            os.getcwd(), "whitelist.json"
        )  # use a single file for all guilds

        try:
            with open(whitelist_file_path, "r") as f:
                self.whitelist = json.load(f)
        except FileNotFoundError:
            self.whitelist = {}

        guild_id = str(ctx.guild.id)
        if guild_id not in self.whitelist:
            self.whitelist[guild_id] = {}

        if action == "add":
            if word in self.whitelist[guild_id] and self.whitelist[guild_id][word]:
                await ctx.send(f"{word} is already whitelisted.")
                return
            if word in self.profanity and word not in self.whitelist[guild_id]:
                self.profanity.remove(word)
                with open(self.profanity_file_path, "w") as f:
                    f.write("\n".join(self.profanity))
            self.whitelist[guild_id][word] = True
            with open(whitelist_file_path, "w") as f:
                json.dump(self.whitelist, f)
            await ctx.send(f"{word} has been added to the whitelist.")
        elif action == "remove":
            if word not in self.whitelist[guild_id]:
                await ctx.send(f"{word} is not currently whitelisted.")
                return
            del self.whitelist[guild_id][word]
            with open(whitelist_file_path, "w") as f:
                json.dump(self.whitelist, f)
            with open(self.profanity_file_path, "a") as f:
                f.write("\n" + word)
            await ctx.send(f"{word} has been removed from the whitelist.")

    # Moderation Commands

    @slash_command(name="ban", description="Ban a member of this discord")
    async def ban(
        self,
        ctx: Interaction,
        member: nextcord.Member = nextcord.SlashOption(
            name="member", description="Please provide a reason"
        ),
        reason: str = nextcord.SlashOption(
            name="reason", description="Please provide a reason"
        ),
    ):
        if not ctx.user.guild_permissions.ban_members:
            await ctx.send(
                "You do not have the required permissions to use this command."
            )
            return

        if not reason:
            reason = "No reason"
        await member.ban(reason=reason)
        await ctx.response.send_message(
            f"{member} has been banned by {ctx.user.mention} for {reason}"
        )

    @slash_command(name="unban", description="Unban a member of this discord")
    async def unban(
        self,
        ctx: Interaction,
        member: nextcord.Member = nextcord.SlashOption(
            name="member", description="Please provide a reason"
        ),
    ):
        if not ctx.user.guild_permissions.ban_members:
            await ctx.send(
                "You do not have the required permissions to use this command."
            )
        await ctx.guild.unban(user=member)
        await ctx.response.send_message(f"{member} has been unbanned")

    @slash_command(name="kick", description="Kick a member of this discord")
    async def kick(
        self,
        ctx: Interaction,
        member: nextcord.Member = nextcord.SlashOption(
            name="member", description="Please provide a reason"
        ),
    ):
        if not ctx.user.guild_permissions.kick_members:
            await ctx.response.send_message(
                "You do not have the required permissions to use this command."
            )
        else:
            await ctx.guild.kick(user=member)
            await ctx.response.send_message(f"{member} has been kicked")

    @slash_command(name="mute", description="Mute Member in text chat")
    async def mute(self, ctx: Interaction, member: nextcord.Member, reason: str):
        settings_file_path = os.path.join(os.path.dirname(__file__), "settings.json")

        # Check if the user has permission to use the command
        if not ctx.user.guild_permissions.mute_members:
            await ctx.send(
                "You do not have the required permissions to use this command."
            )
            return

        # Load the settings from the settings.json file
        try:
            with open(settings_file_path, "r") as f:
                settings = json.load(f)
        except FileNotFoundError:
            await ctx.send("Settings file not found.")
            return

        guild_id = str(ctx.guild.id)
        muted_role_id = settings.get(guild_id, {}).get("muted_role_id")

        # Check if a muted role is specified in the settings
        if muted_role_id is None:
            await ctx.send("No muted role is specified in the settings.")
            return

        muted_role = ctx.guild.get_role(muted_role_id)

        # Check if the muted role exists in the server
        if muted_role is None:
            await ctx.send("The specified muted role does not exist in the server.")
            return

        # Assign the muted role to the member
        await member.add_roles(muted_role)
        await ctx.send(f"{member.mention} has been muted because {reason}")

    @slash_command(name="unmute", description="Unmute a muted member")
    async def unmute(self, ctx: Interaction, member: nextcord.Member):
        settings_file_path = os.path.join(os.path.dirname(__file__), "settings.json")

        # Check if the user has permission to use the command
        if not ctx.user.guild_permissions.mute_members:
            await ctx.send(
                "You do not have the required permissions to use this command."
            )
            return

        # Load the settings from the settings.json file
        try:
            with open(settings_file_path, "r") as f:
                settings = json.load(f)
        except FileNotFoundError:
            await ctx.send("Settings file not found.")
            return

        guild_id = str(ctx.guild.id)
        muted_role_id = settings.get(guild_id, {}).get("muted_role_id")

        # Check if a muted role is specified in the settings
        if muted_role_id is None:
            await ctx.send("No muted role is specified in the settings.")
            return

        muted_role = ctx.guild.get_role(muted_role_id)

        # Check if the muted role exists in the server
        if muted_role is None:
            await ctx.send("The specified muted role does not exist in the server.")
            return

        # Remove the muted role from the member
        await member.remove_roles(muted_role)
        await ctx.send(f"{member.mention} has been unmuted.")

    @slash_command(name="purge", description="Delete a specified number of messages")
    async def purge(self, interaction: nextcord.Interaction, limit: int):
        if not interaction.channel.permissions_for(interaction.user).manage_messages:
            await interaction.response.send_message(
                "You do not have permission to delete messages."
            )
            return

        # Defer the interaction response
        await interaction.response.defer()

        messages_to_delete = await interaction.channel.history(limit=None).flatten()
        messages_to_delete = messages_to_delete[:limit]

        for message in messages_to_delete:
            await message.delete()

    @slash_command(name="sendreport", description="Send a report/bug to the bot owner")
    async def sendreport(self, interaction: nextcord.Interaction, message: str):
        # Check if the user invoking the command is the owner of the server
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                "Only the server owner can submit a report.", ephemeral=True
            )
            return

        # Defer the interaction response
        await interaction.response.defer()

        user = self.bot.get_user(595415508283686948)  # Replace with your user ID
        if user:
            try:
                await user.send(f"Report from {interaction.user.mention}:\n{message}")
                await interaction.followup.send(
                    "Your report has been sent to the bot owner."
                )
            except nextcord.HTTPException:
                await interaction.followup.send(
                    "There was an error sending your report. Please try again later."
                )
        else:
            await interaction.followup.send(
                "The bot owner could not be found. Please try again later."
            )

    @slash_command(name="list_banned", description="Lists all profanity words.")
    async def list_banned(self, ctx: Interaction):
        if not ctx.user.guild_permissions.administrator:
            await ctx.send(
                "You do not have the required permissions to use this command."
            )
            return
        # Get the full path to the profanity file
        profanity_file_path = os.path.join(os.path.dirname(__file__), "profanity.txt")

        # Open the profanity file and read its contents
        with open(profanity_file_path, "r") as profanity_file:
            profanity_words = [line.strip() for line in profanity_file]

        # Split the profanity words into chunks of 50 to avoid exceeding the character limit
        profanity_word_chunks = [
            profanity_words[i : i + 50] for i in range(0, len(profanity_words), 50)
        ]

        # Create an embed for each chunk of profanity words
        for i, chunk in enumerate(profanity_word_chunks):
            words_embed = nextcord.Embed(title="List of Profanity Words")
            words_embed.add_field(
                name=f"Profanity Words (part {i + 1})",
                value="\n".join(chunk),
                inline=False,
            )

            # Truncate any fields that are longer than 1024 characters
            for field in words_embed.fields:
                if len(field.value) > 1024:
                    field.value = field.value[:1021] + "..."

            await ctx.send(embed=words_embed)

    @slash_command(name="list_whitelisted", description="Lists all whitelisted words.")
    async def list_whitelisted(self, ctx: Interaction):
        if not ctx.user.guild_permissions.administrator:
            await ctx.send(
                "You do not have the required permissions to use this command."
            )
            return
        # Get the full path to the whitelist file
        whitelist_file_path = os.path.join(os.path.dirname(__file__), "whitelist.json")

        # Open the whitelist file and read its contents
        with open(whitelist_file_path, "r") as whitelist_file:
            whitelist_words = json.load(whitelist_file)

        # Convert any frozensets to strings
        whitelist_words = [str(word) for word in whitelist_words]

        # Split the whitelist words into chunks of 50 to avoid exceeding the character limit
        whitelist_word_chunks = [
            whitelist_words[i : i + 50] for i in range(0, len(whitelist_words), 50)
        ]

        # Create an embed for each chunk of whitelist words
        for i, chunk in enumerate(whitelist_word_chunks):
            words_embed = nextcord.Embed(title="List of Whitelisted Words")
            words_embed.add_field(
                name=f"Whitelist Words (part {i + 1})",
                value="\n".join(chunk),
                inline=False,
            )

            # Truncate any fields that are longer than 1024 characters
            for field in words_embed.fields:
                if len(field.value) > 1024:
                    field.value = field.value[:1021] + "..."

            await ctx.send(embed=words_embed)

    @slash_command(name="add_word", description="Add a new word to the profanity list")
    async def add_word(self, ctx: Interaction, words: str):
        if not ctx.user.guild_permissions.administrator:
            await ctx.send(
                "You do not have the required permissions to use this command."
            )
            return
        profanity_file_path = os.path.join(os.path.dirname(__file__), "profanity.txt")
        added_words_file_path = os.path.join(
            os.path.dirname(__file__), "added_words.json"
        )
        with (
            open(profanity_file_path, "r+") as profanity_file,
            open(added_words_file_path, "r+") as added_words_file,
        ):
            words_list = profanity_file.readlines()
            added_words_dict = json.load(added_words_file)

            if words.lower() + "\n" in words_list:
                await ctx.send("This word is already in the profanity list.")
            else:
                guild_id = str(ctx.guild.id)
                if guild_id not in added_words_dict:
                    added_words_dict[guild_id] = []
                if words.lower() not in added_words_dict[guild_id]:
                    added_words_dict[guild_id].append(words.lower())
                    added_words_file.seek(0)
                    json.dump(added_words_dict, added_words_file, indent=4)
                    await ctx.send(
                        f"{words} has been added to the profanity list for this guild."
                    )
                else:
                    await ctx.send(
                        "This word has already been added to the profanity list for this guild."
                    )

    @slash_command(
        name="remove_word",
        description="Remove a word from the guild-specific profanity list",
    )
    async def remove_word(self, ctx: Interaction, word: str):
        added_words_file_path = os.path.join(
            os.path.dirname(__file__), "added_words.json"
        )
        if not ctx.user.guild_permissions.administrator:
            await ctx.send(
                "You do not have the required permissions to use this command."
            )
            return
        with open(added_words_file_path, "r+") as added_words_file:
            added_words_dict = json.load(added_words_file)

            guild_id = str(ctx.guild.id)
            if (
                guild_id in added_words_dict
                and word.lower() in added_words_dict[guild_id]
            ):
                added_words_dict[guild_id].remove(word.lower())
                added_words_file.seek(0)
                added_words_file.truncate()
                json.dump(added_words_dict, added_words_file, indent=4)
                await ctx.send(
                    f"{word} has been removed from the profanity list for this guild."
                )
            else:
                await ctx.send("This word is not in the profanity list for this guild.")

    @slash_command(
        name="change_muted_role", description="Change the muted role for this server"
    )
    async def change_muted_role(self, ctx: Interaction, role: nextcord.Role):
        settings_file_path = os.path.join(os.path.dirname(__file__), "settings.json")
        if not ctx.user.guild_permissions.administrator:
            await ctx.send(
                "You do not have the required permissions to use this command."
            )
            return

        # Open the settings file
        with open(settings_file_path, "r+") as f:
            # Load the existing settings
            settings = json.load(f)

            # Get the guild ID
            guild_id = str(ctx.guild.id)

            # Check if the guild already exists in the settings
            if guild_id not in settings:
                settings[guild_id] = {}

            # Update the muted role for the guild in the settings
            settings[guild_id]["muted_role_id"] = role.id

            # Save the updated settings
            f.seek(0)
            json.dump(settings, f, indent=4)

        await ctx.send(f"The muted role for this server has been set to {role.mention}")

    @slash_command(name="help", description="Displays all available commands")
    async def help(
        self,
        ctx: Interaction,
    ):
        await ctx.response.send_message("""```General Commands
        \n/help - displays all the available commands
        \n/ban - bans a member of the discord
        \n/kick - Kicks a member from the discord
        \n/unban - Unbans a member that was banned
        \n/purge - Delete a specified number of messages
        \n/mute - mute a specific member in discord
        \n/unmute - unmute a specific member in discord
        \n/list_banned - List all profanity words
        \n/list_whitelisted - List all whitelisted words
        \n/add_word - Add a custom word to the profanity list
        \n/remove_word - Remove your custom word from profanity list
        \n/whitelist - remove or add words to the whitelist
        \n/newticket - Makes a new ticket under category ticket
        \n!close - Closes the ticket (Only creator of the ticket can close)
        \n/support_roles - View the support roles for your discord
        \n/add_support_role - Add a support role for your discord
        \n/remove_support_role - Remove a support role from your discord
        \n/set_logging_channel - Set the channel where all ticket logs will go
        \n/ban_link - Bans a link from the discord and erases the link from the message
        \n/set_changelog_channel - Sets the channel for the bot to send updates for it in```""")

    def load_twitch_data(self) -> dict:
        """Load all guild Twitch settings from twitch.json."""
        try:
            with open(self.twitch_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_twitch_data(self, data: dict) -> None:
        """Save all guild Twitch settings to twitch.json."""
        with open(self.twitch_file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

    def get_guild_twitch_data(self, data: dict, guild_id: str) -> dict:
        """Return a guild's Twitch settings, creating defaults when needed."""
        return data.setdefault(
            guild_id,
            {
                "notification_channel_id": None,
                "mention_role_id": None,
                "twitch_channels": [],
            },
        )

    @slash_command(
        name="setnotificationchannel",
        description="Set this server's Twitch notification channel and role",
    )
    async def setnotificationchannel(
        self,
        ctx: Interaction,
        channel: nextcord.TextChannel,
        role: nextcord.Role = None,
    ):
        if not ctx.user.guild_permissions.administrator:
            await ctx.send(
                "You do not have the required permissions to use this command.",
                ephemeral=True,
            )
            return

        data = self.load_twitch_data()
        guild_data = self.get_guild_twitch_data(data, str(ctx.guild.id))
        guild_data["notification_channel_id"] = channel.id
        guild_data["mention_role_id"] = role.id if role else None
        self.save_twitch_data(data)

        role_text = role.mention if role else "no mention role"
        await ctx.send(
            f"Twitch notifications for this server will be sent to "
            f"{channel.mention} with {role_text}."
        )

    @slash_command(
        name="addtwitchchannel",
        description="Add a Twitch channel to this Discord server",
    )
    async def addtwitchchannel(self, ctx: Interaction, twitch_channel: str):
        if not ctx.user.guild_permissions.administrator:
            await ctx.send(
                "You do not have the required permissions to use this command.",
                ephemeral=True,
            )
            return

        twitch_channel = (
            twitch_channel.strip().lower().replace("https://www.twitch.tv/", "")
        )
        twitch_channel = twitch_channel.replace("https://twitch.tv/", "").strip("/")
        if not twitch_channel:
            await ctx.send(
                "Please provide a valid Twitch channel name.", ephemeral=True
            )
            return

        data = self.load_twitch_data()
        guild_data = self.get_guild_twitch_data(data, str(ctx.guild.id))
        channels = guild_data["twitch_channels"]

        if twitch_channel in channels:
            await ctx.send(
                f"`{twitch_channel}` is already followed by this Discord server.",
                ephemeral=True,
            )
            return

        channels.append(twitch_channel)
        self.save_twitch_data(data)
        await ctx.send(
            f"Added `{twitch_channel}` to this Discord server's Twitch notifications."
        )

    @slash_command(
        name="removetwitchchannel",
        description="Remove a Twitch channel from this Discord server",
    )
    async def removetwitchchannel(self, ctx: Interaction, twitch_channel: str):
        if not ctx.user.guild_permissions.administrator:
            await ctx.send(
                "You do not have the required permissions to use this command.",
                ephemeral=True,
            )
            return

        twitch_channel = (
            twitch_channel.strip().lower().replace("https://www.twitch.tv/", "")
        )
        twitch_channel = twitch_channel.replace("https://twitch.tv/", "").strip("/")
        data = self.load_twitch_data()
        guild_data = self.get_guild_twitch_data(data, str(ctx.guild.id))
        channels = guild_data["twitch_channels"]

        if twitch_channel not in channels:
            await ctx.send(
                f"`{twitch_channel}` is not followed by this Discord server.",
                ephemeral=True,
            )
            return

        channels.remove(twitch_channel)
        self.save_twitch_data(data)
        await ctx.send(
            f"Removed `{twitch_channel}` from this Discord server's Twitch notifications."
        )

    @slash_command(
        name="listtwitchchannels",
        description="List Twitch channels followed by this Discord server",
    )
    async def listtwitchchannels(self, ctx: Interaction):
        data = self.load_twitch_data()
        guild_data = self.get_guild_twitch_data(data, str(ctx.guild.id))
        channels = guild_data["twitch_channels"]

        if not channels:
            await ctx.send("This Discord server is not following any Twitch channels.")
            return

        formatted_channels = "\n".join(f"• {name}" for name in sorted(channels))
        await ctx.send(
            f"Twitch channels followed by this Discord server:\n{formatted_channels}"
        )

    # AutoMod

    async def on_message(self, message: nextcord.Message):
        if message.author == self.user:
            return

        if not message.guild:
            return

        ctx = await self.get_context(message)
        await self.check_message(ctx=ctx, message=message)
        await self.check_message(message)

    async def check_message(self, message: nextcord.Message):
        profanity_file_path = os.path.join(os.path.dirname(__file__), "profanity.txt")
        whitelist_file_path = os.path.join(os.path.dirname(__file__), "whitelist.json")
        warnings_file_path = os.path.join(
            os.path.dirname(__file__), "user_warnings.json"
        )
        settings_file_path = os.path.join(os.path.dirname(__file__), "settings.json")
        words_file_path = os.path.join(os.path.dirname(__file__), "added_words.json")
        if (
            message.author.guild_permissions.manage_messages
            or message.author.guild_permissions.ban_members
        ):
            return

        timeouts = {
            2: 300,
            3: 3600,
            4: 604800,
            5: -1,
        }  # Map offense count to timeout duration in seconds. -1 for ban.

        try:
            with open(profanity_file_path, "r") as f:
                profanity = f.read().splitlines()
        except FileNotFoundError:
            print("File not found: profanity.txt")
            return

        try:
            with open(words_file_path, "r") as f:
                guild_words_data = json.load(f)
                guild_banned_words = guild_words_data.get(str(message.guild.id), [])
        except FileNotFoundError:
            print("File not found: added_words.json")
            guild_banned_words = []

        banned_words = set(word for word in profanity + guild_banned_words if word)

        try:
            with open(whitelist_file_path, "r") as f:
                whitelist = json.load(f)
        except FileNotFoundError:
            print("File not found: whitelist.json")
            whitelist = []

        try:
            with open(warnings_file_path, "r") as f:
                data = json.load(f)
                warning_data = data.get(str(message.author.id))
                user_warnings = warning_data.get("offenses") if warning_data else 0
                print(f"user_warnings before increment: {user_warnings}")
        except FileNotFoundError:
            print("File not found: user_warnings.json")
            user_warnings = 0

        try:
            with open(settings_file_path, "r") as f:
                settings = json.load(f)
                muted_role_id = settings.get(str(message.guild.id), {}).get(
                    "muted_role_id"
                )
        except FileNotFoundError:
            print("File not found: settings.json")

        muted_role = None
        if muted_role_id:
            muted_role = message.guild.get_role(muted_role_id)

        banned_word_pattern = r"\b(?:{})\b".format(
            "|".join(map(re.escape, banned_words))
        )
        banned_word_match = re.search(banned_word_pattern, message.content.lower())

        if banned_word_match and banned_word_match.group() not in whitelist:
            await message.delete()

            if muted_role is None:
                await message.channel.send(
                    f"{message.author.mention}, Please contact the admin of the server to set a muted role."
                )
                return

            if user_warnings >= 5:
                await message.channel.send(
                    f"{message.author.mention}, you have been banned for repeated offenses."
                )
                await message.author.ban()
                del data[str(message.author.id)]
            else:
                timeout_duration = timeouts.get(user_warnings + 1, 0)
                data[str(message.author.id)] = {
                    "timeout_end_time": time.time() + timeout_duration,
                    "offenses": user_warnings + 1,
                }
                print(f"user_warnings after increment: {user_warnings + 1}")
                if user_warnings == 0:
                    await message.channel.send(
                        f"{message.author.mention}, your message contained a banned word. This is your warning before being timed out."
                    )
                elif user_warnings == 1:
                    await message.channel.send(
                        f"{message.author.mention}, your message contained a banned word for not listening, 5m timeout"
                    )
                elif user_warnings == 2:
                    await message.channel.send(
                        f"{message.author.mention}, your message contained a banned word for not listening, 1 hour timeout."
                    )
                elif user_warnings == 3:
                    await message.channel.send(
                        f"{message.author.mention}, your message contained a banned word for not listening, 1 week timeout."
                    )
                elif user_warnings == 4:
                    await message.channel.send(
                        f"{message.author.mention}, you still dont know how to listen so enjoy the ban <3"
                    )
                    await message.author.ban(
                        reason="Reached maximum number of offenses"
                    )
                if timeout_duration > 0:
                    await message.author.add_roles(muted_role)
                    try:
                        await asyncio.sleep(timeout_duration)
                    finally:
                        await message.author.remove_roles(muted_role)
                with open(warnings_file_path, "w") as f:
                    json.dump(data, f, indent=None)

    @slash_command(
        name="resetwarnings", description="Reset the warnings for a specified member."
    )
    async def reset_warnings(self, ctx: Interaction, member: nextcord.Member = None):
        warnings_file_path = os.path.join(
            os.path.dirname(__file__), "user_warnings.json"
        )
        settings_file_path = os.path.join(os.path.dirname(__file__), "settings.json")

        if not ctx.user.guild_permissions.administrator:
            await ctx.send(
                "You do not have the required permissions to use this command."
            )
            return

        if member is None:
            member = ctx.user

        try:
            with open(warnings_file_path, "r") as f:
                data = json.load(f)
                if str(member.id) in data and data[str(member.id)] != 0:
                    data[str(member.id)] = 0  # set warnings to 0
                    with open(warnings_file_path, "w") as f:
                        json.dump(data, f)
                    await ctx.send(f"Warnings for {member.mention} have been reset.")
                else:
                    await ctx.send(f"{member.mention} already has 0 warnings.")
        except FileNotFoundError:
            print("File not found: user_warnings.json")
            await ctx.send("Failed to reset warnings.")

        try:
            with open(settings_file_path, "r") as f:
                settings = json.load(f)
                muted_role_id = settings.get(str(ctx.guild.id), {}).get("muted_role_id")
        except FileNotFoundError:
            print("File not found: settings.json")
            muted_role_id = None

        muted_role = None
        if muted_role_id:
            muted_role = ctx.guild.get_role(muted_role_id)

        if muted_role and muted_role in member.roles:
            try:
                await member.remove_roles(muted_role)
                await ctx.send(f"{member.mention} has been unmuted.")
            except nextcord.Forbidden:
                await ctx.send(
                    f"I couldn't remove the muted role from {member.mention} due to missing permissions."
                )

    @slash_command(name="ban_link", description="Ban a link from the discord")
    async def ban_link(self, ctx, link: str):
        links_file_path = os.path.join(os.path.dirname(__file__), "links.json")
        guild_id = ctx.guild.id
        banned_links_file = links_file_path
        if not ctx.user.guild_permissions.administrator:
            await ctx.send(
                "You do not have the required permissions to use this command."
            )
            return

        try:
            with open(banned_links_file, "r") as file:
                banned_links = json.load(file)
        except FileNotFoundError:
            banned_links = {}

        if str(guild_id) not in banned_links:
            banned_links[str(guild_id)] = []

        if link not in banned_links[str(guild_id)]:
            banned_links[str(guild_id)].append(link)

            with open(banned_links_file, "w") as file:
                json.dump(banned_links, file, indent=4)

            await ctx.send(f"That link is banned from this Discord: {link}")
        else:
            await ctx.send(f"That link is already banned from this Discord: {link}")

    @slash_command(
        name="list_banned_links", description="List all banned links for this server"
    )
    async def list_banned_links(self, ctx):
        links_file_path = os.path.join(os.path.dirname(__file__), "links.json")
        guild_id = ctx.guild.id
        banned_links_file = links_file_path
        if not ctx.user.guild_permissions.administrator:
            await ctx.send(
                "You do not have the required permissions to use this command."
            )
            return

        try:
            with open(banned_links_file, "r") as file:
                banned_links = json.load(file)
        except FileNotFoundError:
            banned_links = {}

        if str(guild_id) not in banned_links:
            await ctx.send("There are no banned links for this server.")
        else:
            banned_links_list = banned_links[str(guild_id)]
            if not banned_links_list:
                await ctx.send("There are no banned links for this server.")
            else:
                banned_links_str = "\n".join(banned_links_list)
                await ctx.send(
                    f"Banned links for this server:\n```{banned_links_str}```"
                )

    @slash_command(
        name="send_changelogs", description="Send changelogs to specified channels"
    )
    async def send_changelogs(self, ctx, *, message: str):
        changelog_file_path = os.path.join(os.path.dirname(__file__), "changelog.json")

        if ctx.user.id != 595415508283686948:
            await ctx.send(
                "You do not have the required permissions to use this command."
            )
            return

        with open(changelog_file_path, "r") as f:
            changelog_data = json.load(f)

        for guild in self.bot.guilds:
            guild_id = str(guild.id)
            if guild_id in changelog_data:
                channel_id = changelog_data[guild_id]["channel_id"]
                channel = self.bot.get_channel(channel_id)

                if channel:
                    await channel.send(f"Change Logs - {message}")
                else:
                    print(
                        f"Could not find a suitable channel to send the change logs in {guild.name}"
                    )

        await ctx.send(
            "Change logs have been sent to specified channels in all servers."
        )

    @slash_command(name="discords", description="Sends a list of all discords")
    async def discords(self, ctx):
        if ctx.user.id == 595415508283686948:  # Replace with your user ID
            guilds = self.bot.guilds
            guild_names = "\n".join([guild.name for guild in guilds])
            await ctx.send(f"Bot is in the following guilds:\n{guild_names}")
        else:
            await ctx.send("You are not authorized to use this command.")

    @slash_command(
        name="set_changelog_channel", description="Set the channel for changelogs"
    )
    async def set_changelog_channel(self, ctx, channel: nextcord.TextChannel):
        changelog_file_path = os.path.join(os.path.dirname(__file__), "changelog.json")
        if not ctx.user.guild_permissions.administrator:
            await ctx.send(
                "You do not have the required permissions to use this command.",
                hidden=True,
            )
            return

        guild_id = str(ctx.guild.id)

        # Load the existing data
        with open(changelog_file_path, "r") as f:
            changelog_data = json.load(f)

        # Update the data with the new channel ID
        if guild_id not in changelog_data:
            changelog_data[guild_id] = {}
        changelog_data[guild_id]["channel_id"] = channel.id

        # Save the updated data
        with open(changelog_file_path, "w") as f:
            json.dump(changelog_data, f, indent=4)

        await ctx.send(f"Changelog channel has been set to {channel.mention}")

    @commands.Cog.listener()
    async def on_message(self, message: nextcord.Message):
        if message.author.bot:
            return

        links_file_path = os.path.join(os.path.dirname(__file__), "links.json")
        guild_id = message.guild.id

        try:
            with open(links_file_path, "r") as file:
                banned_links = json.load(file)
        except FileNotFoundError:
            banned_links = {}

        # Check if the server is in the banned_links dictionary, otherwise add it with default blocked links
        if str(guild_id) not in banned_links:
            add_new_server(str(guild_id), banned_links)
            with open(links_file_path, "w") as file:
                json.dump(banned_links, file)

        guild_banned_links = banned_links[str(guild_id)]

        for link in guild_banned_links:
            if link in message.content:
                await message.delete()
                await message.channel.send(
                    f"{message.author.mention}, that link is banned from this Discord."
                )
                break

        await self.check_message(message)

    async def on_ready(self, ctx):
        application_commands = await application_commands()
        changelog_command = None
        for command in application_commands:
            if command.name == "send_changelogs":
                changelog_command = command
                break

        if changelog_command:
            permissions = [
                nextcord.PermissionOverwrite(
                    target_type="member", target_id=595415508283686948, permission=True
                )
            ]
            await changelog_command.set_permissions(ctx.user.id, permissions)


def setup(bot: commands.Bot):
    bot.add_cog(moderation(bot))
