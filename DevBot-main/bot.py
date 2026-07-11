import os
import nextcord
from nextcord.ext import commands

intents = nextcord.Intents.all()

bot = commands.Bot(command_prefix="/", intents=intents)

extensions = ["moderation"]
commands_synced = False


if __name__ == "__main__":
    for extension in extensions:
        print(f"Loading {extension}")
        bot.load_extension(extension)


@bot.event
async def on_ready():
    global commands_synced

    print("Bot Online")

    await bot.change_presence(
        activity=nextcord.Activity(
            type=nextcord.ActivityType.listening, name="/help for commands"
        )
    )

    if not commands_synced:
        await bot.sync_all_application_commands(
            register_new=True, update_known=True, delete_unknown=True
        )
        commands_synced = True
        print("Slash commands synchronized successfully.")


token = os.environ.get("DISCORD_TOKEN")

if not token:
    raise RuntimeError(
        "DISCORD_TOKEN environment variable is not set. Please add it as a secret."
    )

bot.run(token)
