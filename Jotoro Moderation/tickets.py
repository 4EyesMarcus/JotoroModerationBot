import os
import json
import nextcord
import asyncio
import logging
import io
import datetime
from io import BytesIO
from nextcord.ext import commands
from nextcord import slash_command

class tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.support_file_path = os.path.join(os.path.dirname(__file__), "support.json")
        self.ticketlogs_file_path = os.path.join(os.path.dirname(__file__), "ticketlogs.json")

    @slash_command(name="newticket", description="Create a new ticket")
    async def newticket(self, ctx):
        # Call the create_ticket function to create a new ticket channel
        ticket_channel = await self.create_ticket(ctx)

        if ticket_channel is None:
            # If the ticket channel could not be created, send an error message to the user
            await ctx.send("Could not create ticket channel. Please try again later.")
            return

        # Send a message to the user with the new channel link
        await ctx.send(f"Created ticket {ticket_channel.mention}.")


    
    @slash_command(name="support_roles", description="View Current Support Roles")
    async def support_roles(self, ctx):
        support_file_path = os.path.join(os.path.dirname(__file__), "support.json")
        if not ctx.user.guild_permissions.administrator:
            await ctx.send("You do not have the required permissions to use this command.")
            return


        # Read the support roles from the file
        with open(support_file_path, "r") as f:
            support_data = json.load(f)

        support_roles = support_data.get(str(ctx.guild.id), [])

        if not support_roles:
            # If no roles are set, let the user know
            await ctx.send("No support roles have been set for this guild.")
        else:
            # Send the list of support roles to the user
            role_list = ", ".join(support_roles)
            await ctx.send(f"The support roles for this server are: {role_list}")


    @slash_command(name="add_support_role", description="Manually add a support role for your Discord server")
    async def add_support_role(self, ctx):
        support_file_path = os.path.join(os.path.dirname(__file__), "support.json")
        if not ctx.user.guild_permissions.administrator:
            await ctx.send("You do not have the required permissions to use this command.")
            return

        # Read the existing support data from the file
        with open(support_file_path, "r") as f:
            support_data = json.load(f)

        # Ask the user for the role name
        prompt_view = nextcord.ui.View()
        prompt_view.input = nextcord.ui.TextInput(label="Please enter the name of the support role:")
        prompt_message = await ctx.send("Please enter the name of the support role:", view=prompt_view)

        # Wait for the user to enter the role name
        def check(m):
            return m.author == ctx.user and m.channel == ctx.channel
        try:
            message = await self.bot.wait_for("message", check=check, timeout=60.0)
            role_name = message.content
        except asyncio.TimeoutError:
            await prompt_message.delete()
            await ctx.send("Timed out waiting for a response. Please try again.")
            return

        # Find the role with the given name
        role = nextcord.utils.get(ctx.guild.roles, name=role_name)
        if role is None:
            await ctx.send(f"No role with the name '{role_name}' was found in this server. Please try again.")
            return

        # Add the role ID to the support data for the guild
        guild_id = str(ctx.guild.id)
        existing_role_ids = support_data.get(guild_id, [])
        if role.id not in existing_role_ids:
            existing_role_ids.append(role.id)

        # Update the support data for the guild with the new role ID
        support_data[guild_id] = existing_role_ids
        with open(support_file_path, "w") as f:
            json.dump(support_data, f)

        # Send a confirmation message to the user
        await ctx.send(f"The role {role_name} has been added as a support role for this server.")


    @slash_command(name="remove_support_role", description="Manually remove a support role for your Discord server")
    async def remove_support_role(self, ctx):
        support_file_path = os.path.join(os.path.dirname(__file__), "support.json")
        if not ctx.user.guild_permissions.administrator:
            await ctx.send("You do not have the required permissions to use this command.")
            return

        # Read the existing support data from the file
        with open(support_file_path, "r") as f:
            support_data = json.load(f)

        # Ask the user for the role name
        prompt_view = nextcord.ui.View()
        prompt_view.input = nextcord.ui.TextInput(label="Please enter the name of the support role you want to remove:")
        prompt_message = await ctx.send("Please enter the name of the support role you want to remove:", view=prompt_view)

        # Wait for the user to enter the role name
        def check(m):
            return m.author == ctx.user and m.channel == ctx.channel

        try:
            message = await self.bot.wait_for("message", check=check, timeout=60.0)
            role_name = message.content
        except asyncio.TimeoutError:
            await prompt_message.delete()
            await ctx.send("Timed out waiting for a response. Please try again.")
            return

        # Remove the role from the support data for the guild
        guild_id = str(ctx.guild.id)
        existing_roles = support_data.get(guild_id, [])
        if role_name in existing_roles:
            existing_roles.remove(role_name)

        # Update the support data for the guild with the removed role
        support_data[guild_id] = existing_roles
        with open(support_file_path, "w") as f:
            json.dump(support_data, f)

        # Send a confirmation message to the user
        await ctx.send(f"The role {role_name} has been removed as a support role for this server.")

    @slash_command(name="set_logging_channel", description="Set the logging channel for ticket closures")
    async def set_logging_channel(self, ctx):
        if not ctx.user.guild_permissions.administrator:
            await ctx.send("You do not have the required permissions to use this command.")
            return
        # Ask the user for the logging channel
        prompt_view = nextcord.ui.View()
        prompt_view.input = nextcord.ui.TextInput(label="Please enter the name of the logging channel:")
        prompt_message = await ctx.send("Please enter the name of the logging channel:", view=prompt_view)

        # Wait for the user to enter the channel name
        def check(m):
            return m.author == ctx.user and m.channel == ctx.channel
        try:
            message = await self.bot.wait_for("message", check=check, timeout=60.0)
            logging_channel_name = message.content
        except asyncio.TimeoutError:
            await prompt_message.delete()
            await ctx.send("Timed out waiting for a response. Please try again.")
            return

        # Get the logging channel object
        logging_channel = nextcord.utils.get(ctx.guild.channels, name=logging_channel_name)

        if logging_channel is None:
            await ctx.send(f"Could not find a channel named {logging_channel_name}.")
            return

        # Read the existing logging data from the file
        logging_file_path = os.path.join(os.path.dirname(__file__), "ticketlogs.json")
        with open(logging_file_path, "r") as f:
            logging_data = json.load(f)

        # Update the logging data for the guild
        guild_id = str(ctx.guild.id)
        logging_data[guild_id] = str(logging_channel.id)

        # Write the updated logging data to the file
        with open(logging_file_path, "w") as f:
            json.dump(logging_data, f)

        await ctx.send(f"Ticket closure logs will now be sent to {logging_channel.mention}.")

    # Command Functions
    @commands.Cog.listener()
    async def on_message(self, message: nextcord.Message):
        if message.author.bot:
            return
        if message.channel.name.endswith("-ticket"):
            # Check if the message is a slash command
            if not message.content.startswith("!"):
                return

            # Check if the slash command is '/close'
            command_name = message.content.split()[0][1:]
            if command_name != "close":
                return

            # Check if the user who sent the message is the same as the one who created the ticket
            if int(message.author.id) != int(message.channel.topic):
                await message.channel.send("Only the ticket creator can close this ticket.")
                return

            await self.close_ticket(message)

    async def create_ticket(self, ctx):
        support_file_path = os.path.join(os.path.dirname(__file__), "support.json")

        # Read the support roles from the file
        with open(support_file_path, "r") as f:
            support_data = json.load(f)

        support_roles = support_data.get(str(ctx.guild.id), [])

        if not support_roles:
            # If no roles are set, let the user know
            await ctx.send("No support roles have been set for this guild.")
            return None

        # Get the pre-defined category "Tickets"
        category_name = "tickets"
        category = nextcord.utils.get(ctx.guild.categories, name=category_name)

        if category is None:
            await ctx.send(f"Could not find {category_name} category.")
            return None

        # Get the category's overwrites
        category_overwrites = category.overwrites

        # Set up the overwrites for the new channel
        overwrites = category_overwrites.copy()
        for role_name in support_roles:
            role = nextcord.utils.get(ctx.guild.roles, name=role_name)
            if role is not None:
                overwrites[role] = nextcord.PermissionOverwrite(read_messages=True, read_message_history=True, send_messages=True, manage_channels=True, manage_messages=True)

        # Set the name of the new channel
        channel_name = f"{ctx.user.name}-ticket"

        # Check if a channel with the given name already exists
        existing_channel = nextcord.utils.get(ctx.guild.channels, name=channel_name)

        if existing_channel is not None:
            await ctx.send(f"A channel with the name {channel_name} already exists.")
            return None

        # Create the new channel in the "Tickets" category
        channel = await category.create_text_channel(name=channel_name, overwrites=overwrites)

        # Set the topic of the channel to the user ID who created the ticket
        await channel.edit(topic=str(ctx.user.id))

        return channel
    
    async def get_ticket_log(self, channel: nextcord.TextChannel) -> str:
        messages = []
        async for message in channel.history(limit=None):
            if message.author.bot:
                continue
            if message.content.startswith(f"{self.bot.command_prefix}close"):
                continue
            messages.append(f"{message.author.name}#{message.author.discriminator} ({message.author.id}) - {message.created_at.strftime('%Y-%m-%d %H:%M:%S')} UTC:\n{message.content}\n")
        messages.reverse()
        return "".join(messages)

    async def close_ticket(self, message: nextcord.Message):
        # Check if the user has the required role to close the ticket
        support_file_path = os.path.join(os.path.dirname(__file__), "support.json")
        with open(support_file_path, "r") as f:
            support_data = json.load(f)

        support_roles = support_data.get(str(message.guild.id), [])

        # Get the ID of the ticket creator from the channel topic
        creator_id = int(message.channel.topic)

        can_close_ticket = False
        member = message.guild.get_member(creator_id)
        if member:
            for role_name in support_roles:
                role = nextcord.utils.get(message.guild.roles, name=role_name)
                if role and role in member.roles:
                    can_close_ticket = True
                    break
            if member.id == message.author.id:
                can_close_ticket = True

        # Check if the user has curator role
        curator_role = nextcord.utils.get(message.guild.roles, name="curator")
        if curator_role and curator_role in message.author.roles:
            can_close_ticket = True

        # Check if the user has support role
        for member in message.channel.members:
            for role_name in support_roles:
                role = nextcord.utils.get(message.guild.roles, name=role_name)
                if role and role in member.roles:
                    can_close_ticket = True
                    break

        if not can_close_ticket:
            await message.channel.send("Only the ticket creator, users with the required role, or curators can close this ticket." if member else "Only users with the required role or curators can close this ticket.")
            return

        # Send a message to the user to confirm the ticket closure
        await message.channel.send("Ticket closed. If you need further assistance, please create a new ticket.")

        # Log the ticket closure
        logging_file_path = os.path.join(os.path.dirname(__file__), "ticketlogs.json")
        with open(logging_file_path, "r") as f:
            logging_data = json.load(f)

        guild_id = str(message.guild.id)
        if guild_id not in logging_data:
            # If there is no logging channel set, return
            return

        logging_channel_id = logging_data[guild_id]
        logging_channel = message.guild.get_channel(int(logging_channel_id))
        if logging_channel is None:
            # If the logging channel is not found, return
            return

        # Get the ticket creator
        creator = message.guild.get_member(int(message.channel.topic))

        # Create a log file and send it to the user's DM
        log_file_content = f"Ticket closed by {message.author.name}#{message.author.discriminator} ({message.author.id}) at {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC.\n"
        log_file_content += f"Ticket created by {creator.name}#{creator.discriminator} ({creator.id}) at {message.channel.created_at.strftime('%Y-%m-%d %H:%M:%S')} UTC.\n"
        log_file_content += f"Ticket closed in channel {message.channel.mention}.\n"

        # Get the ticket log and write it to the log file
        ticket_log = await self.get_ticket_log(message.channel)
        log_file_content += ticket_log

        log_file = nextcord.File(BytesIO(log_file_content.encode()), filename=f"{creator.name}-log.txt")
        try:
            await creator.send(file=log_file)
        except nextcord.Forbidden:
            logging.warning(f"Could not send DM to {creator.name}#{creator.discriminator} ({creator.id})")
        except Exception as e:
            logging.error(f"An error occurred while sending the ticket closure log to {creator.name}#{creator.discriminator} ({creator.id}): {e}")

        # Send the log file to the logging channel
        await logging_channel.send(file=log_file)
        await message.channel.delete()






       













    async def create_ticket_log(channel):
        # Get the ticket creator's ID from the channel's topic
        creator_id = int(channel.topic)

        # Get the creator's user object
        creator = await channel.guild.fetch_member(creator_id)

        # Get the channel's messages
        messages = await channel.history(limit=None).flatten()

        # Create the log file
        log_file_name = f"ticket_log_{channel.id}.txt"
        log_file_path = os.path.join("logs", log_file_name)

        with open(log_file_path, "w") as log_file:
            # Write the ticket information to the file
            log_file.write(f"Ticket created by: {creator.display_name} ({creator.id})\n")
            log_file.write(f"Creation time: {channel.created_at}\n")
            log_file.write(f"Closed by: {channel.guild.me.display_name} ({channel.guild.me.id})\n")
            log_file.write(f"Closing time: {datetime.datetime.now(datetime.timezone.utc)}\n\n")

            # Write the ticket messages to the file
            for message in messages:
                author = message.author.display_name
                timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S %Z")
                content = message.clean_content

                log_file.write(f"{timestamp} - {author}: {content}\n")












        
def setup(bot : commands.Bot):
    bot.add_cog(tickets(bot))
