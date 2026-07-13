import nextcord
from nextcord import Interaction, SlashOption, slash_command
from nextcord.ext import commands

from database import (
    clear_banned_links,
    ensure_default_banned_links,
    get_setup_status,
    save_initial_setup,
)


DEFAULT_BLOCKED_LINKS = [
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


class Setup(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @slash_command(
        name="setup",
        description="Complete Jotoro Moderation setup for this server",
    )
    async def setup_command(
        self,
        interaction: Interaction,

        muted_role: nextcord.Role = SlashOption(
            name="muted_role",
            description="Role applied when Jotoro mutes someone",
            required=True,
        ),

        banned_words: str = SlashOption(
            name="banned_words",
            description="Use Jotoro's default banned-word list or start empty",
            required=True,
            choices={
                "Use Jotoro's default list": "default",
                "Start with an empty custom list": "empty",
            },
        ),

        banned_links: str = SlashOption(
            name="banned_links",
            description="Use Jotoro's default banned-link list or start empty",
            required=True,
            choices={
                "Use Jotoro's default list": "default",
                "Start with an empty custom list": "empty",
            },
        ),

        changelog_channel: nextcord.TextChannel = SlashOption(
            name="changelog_channel",
            description="Channel where Jotoro updates will be posted",
            required=True,
        ),
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used inside a server.",
                ephemeral=True,
            )
            return

        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                "Only the server owner can complete Jotoro setup.",
                ephemeral=True,
            )
            return

        bot_member = interaction.guild.me

        if bot_member is None:
            await interaction.response.send_message(
                "I could not check my server permissions.",
                ephemeral=True,
            )
            return

        changelog_permissions = changelog_channel.permissions_for(bot_member)

        if not (
            changelog_permissions.view_channel
            and changelog_permissions.send_messages
        ):
            await interaction.response.send_message(
                f"I cannot post in {changelog_channel.mention}. "
                "Give me **View Channel** and **Send Messages** there first.",
                ephemeral=True,
            )
            return

        if muted_role >= bot_member.top_role:
            await interaction.response.send_message(
                f"My highest role must be placed above {muted_role.mention} "
                "before I can assign or remove it.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        use_default_words = banned_words == "default"
        use_default_links = banned_links == "default"

        # Remove any previously stored link list before applying the new choice.
        await clear_banned_links(interaction.guild.id)

        if use_default_links:
            await ensure_default_banned_links(
                interaction.guild.id,
                DEFAULT_BLOCKED_LINKS,
            )

        await save_initial_setup(
            guild_id=interaction.guild.id,
            muted_role_id=muted_role.id,
            changelog_channel_id=changelog_channel.id,
            use_default_words=use_default_words,
            use_default_links=use_default_links,
        )

        embed = nextcord.Embed(
            title="Jotoro Moderation Setup Complete",
            description=(
                "The main moderation settings for this server have been saved."
            ),
        )

        embed.add_field(
            name="Muted role",
            value=muted_role.mention,
            inline=False,
        )

        embed.add_field(
            name="Banned-word list",
            value=(
                "Jotoro's default list is enabled."
                if use_default_words
                else (
                    "Started empty. Use `/add_word` to create this "
                    "server's custom list."
                )
            ),
            inline=False,
        )

        embed.add_field(
            name="Banned-link list",
            value=(
                "Jotoro's default link list is enabled."
                if use_default_links
                else (
                    "Started empty. Use `/ban_link` to create this "
                    "server's custom list."
                )
            ),
            inline=False,
        )

        embed.add_field(
            name="Changelog channel",
            value=(
                f"Bot updates will be posted in "
                f"{changelog_channel.mention}."
            ),
            inline=False,
        )

        embed.add_field(
            name="You can change these later",
            value=(
                "Run `/setup` again to replace these settings.\n"
                "Use `/add_word`, `/remove_word`, and `/ban_link` "
                "to customize moderation."
            ),
            inline=False,
        )

        await interaction.followup.send(
            embed=embed,
            ephemeral=True,
        )

    @slash_command(
        name="setup_status",
        description="Show this server's Jotoro setup status",
    )
    async def setup_status(self, interaction: Interaction):
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used inside a server.",
                ephemeral=True,
            )
            return

        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                "Only the server owner can view setup status.",
                ephemeral=True,
            )
            return

        status = await get_setup_status(interaction.guild.id)

        if status is None or not status[4]:
            await interaction.response.send_message(
                "Setup is incomplete. Run `/setup`.",
                ephemeral=True,
            )
            return

        (
            muted_role_id,
            changelog_channel_id,
            use_default_words,
            use_default_links,
            setup_completed,
        ) = status

        muted_role = interaction.guild.get_role(muted_role_id)
        changelog_channel = interaction.guild.get_channel(
            changelog_channel_id
        )

        embed = nextcord.Embed(
            title="Jotoro Moderation Setup Status",
        )

        embed.add_field(
            name="Setup",
            value="✅ Complete" if setup_completed else "❌ Incomplete",
            inline=False,
        )

        embed.add_field(
            name="Muted role",
            value=(
                muted_role.mention
                if muted_role
                else "⚠️ Configured role no longer exists"
            ),
            inline=False,
        )

        embed.add_field(
            name="Default words",
            value="Enabled" if use_default_words else "Disabled",
            inline=True,
        )

        embed.add_field(
            name="Default links",
            value="Enabled" if use_default_links else "Disabled",
            inline=True,
        )

        embed.add_field(
            name="Changelog channel",
            value=(
                changelog_channel.mention
                if isinstance(
                    changelog_channel,
                    nextcord.TextChannel,
                )
                else "⚠️ Configured channel no longer exists"
            ),
            inline=False,
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )

    @commands.Cog.listener()
    async def on_guild_join(self, guild: nextcord.Guild):
        channel = self.find_setup_channel(guild)

        if channel is None:
            print(
                f"[SETUP] No usable setup channel in "
                f"{guild.name} ({guild.id})."
            )
            return

        owner_mention = (
            guild.owner.mention
            if guild.owner
            else "Server owner"
        )

        embed = nextcord.Embed(
            title="Welcome to Jotoro Moderation",
            description=(
                "Before automatic moderation is ready, the server owner "
                "must complete the initial setup."
            ),
        )

        embed.add_field(
            name="Run this command",
            value="`/setup`",
            inline=False,
        )

        embed.add_field(
            name="Setup will ask for",
            value=(
                "• The server's muted role\n"
                "• Whether to use Jotoro's default banned words\n"
                "• Whether to use Jotoro's default banned links\n"
                "• A channel for Jotoro changelogs"
            ),
            inline=False,
        )

        embed.add_field(
            name="Changelog channel",
            value=(
                "Select an existing text channel, or create one such as "
                "`#jotoro-updates` before running `/setup`."
            ),
            inline=False,
        )

        try:
            await channel.send(
                content=(
                    f"{owner_mention}, please run `/setup` "
                    "to configure Jotoro Moderation."
                ),
                embed=embed,
                allowed_mentions=nextcord.AllowedMentions(
                    users=True,
                    roles=False,
                    everyone=False,
                ),
            )
        except nextcord.HTTPException as error:
            print(
                f"[SETUP] Could not send join instructions "
                f"in {guild.name}: {error}"
            )

    @staticmethod
    def find_setup_channel(
        guild: nextcord.Guild,
    ) -> nextcord.TextChannel | None:
        bot_member = guild.me

        if bot_member is None:
            return None

        if guild.system_channel:
            permissions = guild.system_channel.permissions_for(
                bot_member
            )

            if permissions.view_channel and permissions.send_messages:
                return guild.system_channel

        for channel in guild.text_channels:
            permissions = channel.permissions_for(bot_member)

            if permissions.view_channel and permissions.send_messages:
                return channel

        return None


def setup(bot: commands.Bot):
    bot.add_cog(Setup(bot))