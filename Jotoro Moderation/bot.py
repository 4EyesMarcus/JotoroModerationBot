import os

import nextcord
from nextcord.ext import commands

from database import initialize_database


intents = nextcord.Intents.all()

bot = commands.Bot(
    command_prefix="/",
    intents=intents
)

extensions = [
    "moderation",
    "setup",
    "tickets"
]

commands_synced = False
database_initialized = False


if __name__ == "__main__":
    for extension in extensions:
        print(f"Loading {extension}")
        bot.load_extension(extension)


@bot.event
async def on_ready():
    global commands_synced
    global database_initialized

    print(f"Bot Online as {bot.user}")

    # Initialize SQLite once per bot process.
    if not database_initialized:
        try:
            await initialize_database()
            database_initialized = True
            print("Database initialized successfully.")
        except Exception as error:
            print(
                f"Database initialization failed: "
                f"{type(error).__name__}: {error}"
            )
            return

    await bot.change_presence(
        activity=nextcord.Activity(
            type=nextcord.ActivityType.listening,
            name="/help for commands"
        )
    )

    # Synchronize slash commands once per bot process.
    if not commands_synced:
        try:
            await bot.sync_all_application_commands(
                register_new=True,
                update_known=True,
                delete_unknown=True
            )

            commands_synced = True
            print("Slash commands synchronized successfully.")

        except Exception as error:
            print(
                f"Slash command synchronization failed: "
                f"{type(error).__name__}: {error}"
            )


token = os.environ.get("DISCORD_TOKEN")

if not token:
    raise RuntimeError(
        "DISCORD_TOKEN environment variable is not set. "
        "Please add it as a secret."
    )

bot.run(token)