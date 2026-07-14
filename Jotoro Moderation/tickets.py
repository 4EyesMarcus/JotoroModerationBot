import asyncio
import io
from datetime import datetime, timezone

import nextcord
from nextcord import Interaction, slash_command
from nextcord.ext import commands

from database import (
    add_open_ticket,
    add_support_role,
    get_open_ticket_channel_id,
    get_support_role_ids,
    get_ticket_settings,
    remove_open_ticket,
    remove_support_role,
    set_ticket_settings,
)


class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @slash_command(
        name="setup_tickets",
        description="Set up the ticket system for this server",
    )
    async def setup_tickets(
        self,
        interaction: Interaction,
        logging_channel: nextcord.TextChannel,
        support_role: nextcord.Role,
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        guild = interaction.guild

        if interaction.user.id != guild.owner_id:
            await interaction.response.send_message(
                "Only the server owner can set up tickets.",
                ephemeral=True,
            )
            return

        bot_member = guild.me

        if bot_member is None or not bot_member.guild_permissions.manage_channels:
            await interaction.response.send_message(
                "I need the **Manage Channels** permission.",
                ephemeral=True,
            )
            return

        if support_role == guild.default_role:
            await interaction.response.send_message(
                "The `@everyone` role cannot be a support role.",
                ephemeral=True,
            )
            return

        log_permissions = logging_channel.permissions_for(bot_member)

        if not (
            log_permissions.view_channel
            and log_permissions.send_messages
            and log_permissions.attach_files
        ):
            await interaction.response.send_message(
                f"I need **View Channel**, **Send Messages**, and "
                f"**Attach Files** in {logging_channel.mention}.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        settings = await get_ticket_settings(guild.id)
        category = guild.get_channel(settings[0]) if settings else None

        if not isinstance(category, nextcord.CategoryChannel):
            category = nextcord.utils.get(guild.categories, name="Support Tickets")

        try:
            if not isinstance(category, nextcord.CategoryChannel):
                category = await guild.create_category(
                    name="Support Tickets",
                    reason=f"Ticket setup completed by {interaction.user}",
                )

            await set_ticket_settings(
                guild.id,
                category.id,
                logging_channel.id,
            )

            await add_support_role(guild.id, support_role.id)

        except nextcord.Forbidden:
            await interaction.followup.send(
                "I could not create or configure the ticket category.",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            f"Ticket setup complete.\n"
            f"Category: **{category.name}**\n"
            f"Logging channel: {logging_channel.mention}\n"
            f"Support role: {support_role.mention}",
            ephemeral=True,
        )

    @slash_command(
        name="add_support_role",
        description="Allow a role to access support tickets",
    )
    async def add_support_role_command(
        self,
        interaction: Interaction,
        role: nextcord.Role,
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                "Only the server owner can manage support roles.",
                ephemeral=True,
            )
            return

        added = await add_support_role(interaction.guild.id, role.id)

        await interaction.response.send_message(
            (
                f"{role.mention} was added as a support role."
                if added
                else f"{role.mention} is already a support role."
            ),
            ephemeral=True,
        )

    @slash_command(
        name="remove_support_role",
        description="Remove a role from ticket support access",
    )
    async def remove_support_role_command(
        self,
        interaction: Interaction,
        role: nextcord.Role,
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                "Only the server owner can manage support roles.",
                ephemeral=True,
            )
            return

        removed = await remove_support_role(interaction.guild.id, role.id)

        await interaction.response.send_message(
            (
                f"{role.mention} was removed from support roles."
                if removed
                else f"{role.mention} was not a support role."
            ),
            ephemeral=True,
        )

    @slash_command(
        name="support_roles",
        description="View configured ticket support roles",
    )
    async def support_roles(self, interaction: Interaction):
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        role_ids = await get_support_role_ids(interaction.guild.id)
        roles = [
            interaction.guild.get_role(role_id)
            for role_id in role_ids
        ]
        roles = [role for role in roles if role is not None]

        await interaction.response.send_message(
            (
                "**Support roles:**\n"
                + "\n".join(f"• {role.mention}" for role in roles)
                if roles
                else "No support roles are configured."
            ),
            ephemeral=True,
        )

    @slash_command(
        name="newticket",
        description="Create a private support ticket",
    )
    async def newticket(self, interaction: Interaction):
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        guild = interaction.guild
        member = interaction.user
        settings = await get_ticket_settings(guild.id)

        if not settings:
            await interaction.response.send_message(
                "Tickets are not set up. The server owner must run `/setup_tickets`.",
                ephemeral=True,
            )
            return

        category = guild.get_channel(settings[0])

        if not isinstance(category, nextcord.CategoryChannel):
            await interaction.response.send_message(
                "The configured ticket category no longer exists.",
                ephemeral=True,
            )
            return

        existing_channel_id = await get_open_ticket_channel_id(
            guild.id,
            member.id,
        )

        if existing_channel_id:
            existing_channel = guild.get_channel(existing_channel_id)

            if isinstance(existing_channel, nextcord.TextChannel):
                await interaction.response.send_message(
                    f"You already have an open ticket: {existing_channel.mention}",
                    ephemeral=True,
                )
                return

            await remove_open_ticket(guild.id, member.id)

        support_role_ids = await get_support_role_ids(guild.id)

        if not support_role_ids:
            await interaction.response.send_message(
                "No support roles are configured.",
                ephemeral=True,
            )
            return

        bot_member = guild.me

        if bot_member is None:
            await interaction.response.send_message(
                "I could not check my permissions.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        overwrites = {
            guild.default_role: nextcord.PermissionOverwrite(view_channel=False),
            member: nextcord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
            ),
            bot_member: nextcord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
                manage_messages=True,
                attach_files=True,
                embed_links=True,
            ),
        }

        support_mentions = []

        for role_id in support_role_ids:
            role = guild.get_role(role_id)

            if role is None:
                continue

            overwrites[role] = nextcord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
                manage_messages=True,
            )
            support_mentions.append(role.mention)

        safe_name = "".join(
            character
            for character in member.display_name.lower().replace(" ", "-")
            if character.isalnum() or character == "-"
        ).strip("-") or str(member.id)

        try:
            ticket_channel = await guild.create_text_channel(
                name=f"ticket-{safe_name}"[:100],
                category=category,
                topic=f"ticket_owner:{member.id}",
                overwrites=overwrites,
                reason=f"Support ticket created by {member}",
            )

            await add_open_ticket(
                guild.id,
                member.id,
                ticket_channel.id,
            )

        except nextcord.Forbidden:
            await interaction.followup.send(
                "I could not create the ticket channel.",
                ephemeral=True,
            )
            return

        embed = nextcord.Embed(
            title="Support Ticket",
            description=(
                f"{member.mention}, describe what you need help with.\n\n"
                "Use `/close` when the ticket is finished."
            ),
        )

        await ticket_channel.send(
            content=" ".join(support_mentions) or None,
            embed=embed,
            allowed_mentions=nextcord.AllowedMentions(
                roles=True,
                users=True,
                everyone=False,
            ),
        )

        await interaction.followup.send(
            f"Your ticket was created: {ticket_channel.mention}",
            ephemeral=True,
        )

    @slash_command(
        name="close",
        description="Close the current support ticket",
    )
    async def close_ticket(
        self,
        interaction: Interaction,
        reason: str = "Resolved",
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        channel = interaction.channel

        if not isinstance(channel, nextcord.TextChannel):
            await interaction.response.send_message(
                "This command must be used in a ticket channel.",
                ephemeral=True,
            )
            return

        if not channel.topic or not channel.topic.startswith("ticket_owner:"):
            await interaction.response.send_message(
                "This is not a Jotoro ticket channel.",
                ephemeral=True,
            )
            return

        try:
            ticket_owner_id = int(channel.topic.split(":", 1)[1])
        except (ValueError, IndexError):
            await interaction.response.send_message(
                "This ticket contains invalid owner information.",
                ephemeral=True,
            )
            return

        support_role_ids = set(
            await get_support_role_ids(interaction.guild.id)
        )
        member_role_ids = {
            role.id for role in interaction.user.roles
        }

        can_close = (
            interaction.user.id == ticket_owner_id
            or interaction.user.id == interaction.guild.owner_id
            or bool(member_role_ids.intersection(support_role_ids))
        )

        if not can_close:
            await interaction.response.send_message(
                "Only the ticket creator, server owner, or support staff can close it.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        settings = await get_ticket_settings(interaction.guild.id)
        logging_channel = (
            interaction.guild.get_channel(settings[1])
            if settings and settings[1]
            else None
        )

        transcript = await self.create_transcript(
            channel,
            ticket_owner_id,
            interaction.user,
            reason,
        )

        filename = f"{channel.name}-transcript.txt"
        owner = interaction.guild.get_member(ticket_owner_id)

        if owner:
            try:
                await owner.send(
                    f"Your ticket in **{interaction.guild.name}** was closed.",
                    file=nextcord.File(
                        io.BytesIO(transcript.encode("utf-8")),
                        filename=filename,
                    ),
                )
            except nextcord.HTTPException:
                pass

        if isinstance(logging_channel, nextcord.TextChannel):
            embed = nextcord.Embed(
                title="Ticket Closed",
                description=f"`{channel.name}` was closed.",
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(
                name="Ticket owner",
                value=f"<@{ticket_owner_id}> (`{ticket_owner_id}`)",
                inline=False,
            )
            embed.add_field(
                name="Closed by",
                value=f"{interaction.user.mention} (`{interaction.user.id}`)",
                inline=False,
            )
            embed.add_field(
                name="Reason",
                value=reason[:1024],
                inline=False,
            )

            try:
                await logging_channel.send(
                    embed=embed,
                    file=nextcord.File(
                        io.BytesIO(transcript.encode("utf-8")),
                        filename=filename,
                    ),
                )
            except nextcord.HTTPException as error:
                print(f"[TICKETS] Transcript failed: {error}")

        await remove_open_ticket(
            interaction.guild.id,
            ticket_owner_id,
        )

        await interaction.followup.send(
            "Ticket closed. This channel will be deleted in five seconds.",
            ephemeral=True,
        )

        await asyncio.sleep(5)

        try:
            await channel.delete(
                reason=f"Ticket closed by {interaction.user}: {reason}"
            )
        except nextcord.HTTPException as error:
            print(f"[TICKETS] Channel deletion failed: {error}")

    async def create_transcript(
        self,
        channel: nextcord.TextChannel,
        ticket_owner_id: int,
        closed_by: nextcord.Member,
        reason: str,
    ) -> str:
        lines = [
            "Jotoro Moderation Ticket Transcript",
            f"Guild: {channel.guild.name} ({channel.guild.id})",
            f"Channel: {channel.name} ({channel.id})",
            f"Ticket owner ID: {ticket_owner_id}",
            f"Created: {channel.created_at.isoformat()}",
            f"Closed by: {closed_by} ({closed_by.id})",
            f"Closed: {datetime.now(timezone.utc).isoformat()}",
            f"Reason: {reason}",
            "",
            "Messages:",
            "",
        ]

        async for message in channel.history(
            limit=None,
            oldest_first=True,
        ):
            timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
            content = message.clean_content or "[No text content]"

            if message.attachments:
                content += " | Attachments: " + ", ".join(
                    attachment.url
                    for attachment in message.attachments
                )

            lines.append(
                f"[{timestamp}] {message.author} ({message.author.id}): {content}"
            )

        return "\n".join(lines)


def setup(bot: commands.Bot):
    bot.add_cog(Tickets(bot))