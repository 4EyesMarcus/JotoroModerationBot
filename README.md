JoJo Moderation bot is a Discord bot that automatically detects and handles messages containing profanity. It keeps track of user offenses and applies timeouts or bans based on the number of offenses. Mainly used for streamer/youtube communities.

**Features:**

Automatic detection of profanity in messages
Keeps track of user offenses and applies timeouts or bans based on the number of offenses
Whitelist system for words that shouldn't trigger offenses
Mute role integration for timeouts
Ability to reset warnings for a specified member
Ticket system for users to request support and get their issues resolved by staff

**Setup:**

Clone the repository
Install the required packages using pip install -r requirements.txt
Create a bot on the Discord Developer Portal and obtain its token
Add the bot to your server using the invite link generated in the Developer Portal
Edit the config.json file with your bot token and desired settings
Run python bot.py to start the bot

**Usage:**

The bot will automatically detect and handle messages containing profanity. Offenses are tracked and timeouts or bans are applied based on the number of offenses.
To reset warnings for a specified member, use the /resetwarnings command. By default, the command resets warnings for the command user.
To open a support ticket, use the /ticket command. Staff can close tickets using the /close command.

**Code:**

The main code for the bot is in bot.py.
The check_message function checks each message for profanity and handles it appropriately.
The resetwarnings function is a slash command that resets warnings for a specified member.
The Ticket class in tickets.py handles the ticket system and includes methods for opening and closing tickets.

In addition, Jotoro Moderation includes the following commands:

**General and Setup Commands**

/help — Displays the available commands and setup information.

/setup — Configures the server’s muted role, banned-word settings, banned-link settings, and changelog channel.

/setup_status — Displays the current moderation, moderation-log, and ticket-system configuration.

/setup_tickets — Creates and configures the private ticket category, ticket logging channel, and initial support role.

**Moderation Commands**

/ban — Bans a member from the server.

/kick — Kicks a member from the server.

/purge — Deletes up to 100 recent messages.

/mute — Applies the server’s configured muted role to a member.

/unmute — Removes a member’s muted role or active Discord timeout.

/clear_mute — Removes a member’s active mute and resets their AutoMod warnings while preserving their historical mute count.

/warnings — Displays a member’s active warnings, mute history, current mute status, and remaining timeout.

/muted_members — Lists all members currently muted through a role or Discord timeout.

/resetwarnings — Resets a member’s active AutoMod warnings without deleting their mute history.

/set_muted_role — Changes the role Jotoro uses when muting members.

/set_modlog_channel — Selects the channel where moderation actions are recorded.

/test_modlog — Sends a test entry to verify that the configured moderation log channel is working.

**Banned Words and Link Commands**

/list_banned — Lists the banned words currently active in the server.

/list_whitelisted — Lists the server’s whitelisted words.

/add_word — Adds a custom word to the server’s banned-word list.

/remove_word — Removes a custom word from the server’s banned-word list.

/whitelist — Adds or removes a word from the server’s whitelist.

/ban_link — Adds a link to the server’s blocked-link list. Messages containing the blocked link are automatically removed.

/list_banned_links — Lists all links currently blocked by the server.

**Ticket Commands**

/newticket — Creates a private support ticket under the server’s configured ticket category.

/close — Closes the current ticket, creates a transcript, sends it to the ticket logging channel, and deletes the ticket channel.

/support_roles — Displays the roles currently authorized to access support tickets.

/add_support_role — Adds a role to the server’s ticket-support team.

/remove_support_role — Removes a role from the server’s ticket-support team.

**Updates and Support**

/set_changelog_channel — Changes the channel where Jotoro posts bot updates.

/sendreport — Sends a bug report, feature request, or support message to the bot owner.

Twitch Notification Commands

These commands are present in the bot, although Twitch notifications are still being finalized:

/setnotificationchannel — Selects the server’s Twitch notification channel and optional mention role.

/addtwitchchannel — Adds a Twitch streamer to the server’s notification list.

/removetwitchchannel — Removes a Twitch streamer from the server’s notification list.

/listtwitchchannels — Lists the Twitch channels currently followed by the server.
