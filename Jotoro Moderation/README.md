JoJo Moderation bot is a Discord bot that automatically detects and handles messages containing profanity. It keeps track of user offenses and applies timeouts or bans based on the number of offenses. Mainly used for streamer/youtube communities.

Features:

Automatic detection of profanity in messages
Keeps track of user offenses and applies timeouts or bans based on the number of offenses
Whitelist system for words that shouldn't trigger offenses
Mute role integration for timeouts
Ability to reset warnings for a specified member
Ticket system for users to request support and get their issues resolved by staff

Setup:

Clone the repository
Install the required packages using pip install -r requirements.txt
Create a bot on the Discord Developer Portal and obtain its token
Add the bot to your server using the invite link generated in the Developer Portal
Edit the config.json file with your bot token and desired settings
Run python bot.py to start the bot

Usage:

The bot will automatically detect and handle messages containing profanity. Offenses are tracked and timeouts or bans are applied based on the number of offenses.
To reset warnings for a specified member, use the /resetwarnings command. By default, the command resets warnings for the command user.
To open a support ticket, use the /ticket command. Staff can close tickets using the /close command.

Code:

The main code for the bot is in bot.py.
The check_message function checks each message for profanity and handles it appropriately.
The resetwarnings function is a slash command that resets warnings for a specified member.
The Ticket class in tickets.py handles the ticket system and includes methods for opening and closing tickets.

In addition, the bot includes the following commands:

/help - displays all the available commands

/ban - bans a member of the discord

/kick - Kicks a member from the discord

/unban - Unbans a member that was banned

/purge - Delete a specified number of messages

/mute - mute a specific member in discord

/unmute - unmute a specific member in discord

/list_banned - List all profanity words

/list_whitelisted - List all whitelisted words

/add_word - Add a custom word to the profanity list

/remove_word - Remove your custom word from profanity list

/whitelist - remove or add words to the whitelist

/newticket - Makes a new ticket under category ticket

!close - Closes the ticket (Only creator of the ticket can close)

/support_roles - View the support roles for your discord

/add_support_role - Add a support role for your discord

/remove_support_role - Remove a support role from your discord

/set_logging_channel - Set the channel where all ticket logs will go

/ban_link - Bans a link from the discord and erases the link from the message

/set_changelog_channel - Sets the channel for the bot to send updates for it in
