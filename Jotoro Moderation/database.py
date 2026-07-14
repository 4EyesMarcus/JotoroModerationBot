import os
from typing import Optional

import aiosqlite


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "jotoro.db")


async def _column_exists(
    database: aiosqlite.Connection,
    table_name: str,
    column_name: str,
) -> bool:
    async with database.execute(
        f"PRAGMA table_info({table_name})"
    ) as cursor:
        rows = await cursor.fetchall()

    return any(row[1] == column_name for row in rows)


async def _add_column_if_missing(
    database: aiosqlite.Connection,
    table_name: str,
    column_name: str,
    column_definition: str,
) -> None:
    if not await _column_exists(database, table_name, column_name):
        await database.execute(
            f"""
            ALTER TABLE {table_name}
            ADD COLUMN {column_name} {column_definition}
            """
        )

        print(
            f"[DATABASE] Added column "
            f"{table_name}.{column_name}"
        )


async def initialize_database() -> None:
    async with aiosqlite.connect(DATABASE_PATH) as database:
        await database.execute("PRAGMA journal_mode=WAL")
        await database.execute("PRAGMA busy_timeout=5000")
        await database.execute("PRAGMA foreign_keys=ON")

        await database.execute("""
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER PRIMARY KEY,
                muted_role_id INTEGER,
                ticket_category_id INTEGER,
                ticket_log_channel_id INTEGER,
                twitch_notification_channel_id INTEGER,
                twitch_mention_role_id INTEGER,
                changelog_channel_id INTEGER,
                use_default_words INTEGER NOT NULL DEFAULT 1,
                use_default_links INTEGER NOT NULL DEFAULT 1,
                setup_completed INTEGER NOT NULL DEFAULT 0
            )
        """)

        # These migrations update an existing jotoro.db without deleting it.
        # Every expected guild_settings column is checked because older
        # versions of the database may be missing more than one field.
        await _add_column_if_missing(
            database,
            "guild_settings",
            "muted_role_id",
            "INTEGER",
        )

        await _add_column_if_missing(
            database,
            "guild_settings",
            "ticket_category_id",
            "INTEGER",
        )

        await _add_column_if_missing(
            database,
            "guild_settings",
            "ticket_log_channel_id",
            "INTEGER",
        )

        await _add_column_if_missing(
            database,
            "guild_settings",
            "twitch_notification_channel_id",
            "INTEGER",
        )

        await _add_column_if_missing(
            database,
            "guild_settings",
            "twitch_mention_role_id",
            "INTEGER",
        )

        await _add_column_if_missing(
            database,
            "guild_settings",
            "changelog_channel_id",
            "INTEGER",
        )

        await _add_column_if_missing(
            database,
            "guild_settings",
            "use_default_words",
            "INTEGER NOT NULL DEFAULT 1",
        )

        await _add_column_if_missing(
            database,
            "guild_settings",
            "use_default_links",
            "INTEGER NOT NULL DEFAULT 1",
        )

        await _add_column_if_missing(
            database,
            "guild_settings",
            "setup_completed",
            "INTEGER NOT NULL DEFAULT 0",
        )

        await database.execute("""
            CREATE TABLE IF NOT EXISTS warnings (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                offenses INTEGER NOT NULL DEFAULT 0,
                timeout_end_time REAL,
                PRIMARY KEY (guild_id, user_id)
            )
        """)

        await database.execute("""
            CREATE TABLE IF NOT EXISTS banned_links (
                guild_id INTEGER NOT NULL,
                link TEXT NOT NULL COLLATE NOCASE,
                PRIMARY KEY (guild_id, link)
            )
        """)

        await database.execute("""
            CREATE TABLE IF NOT EXISTS custom_banned_words (
                guild_id INTEGER NOT NULL,
                word TEXT NOT NULL COLLATE NOCASE,
                PRIMARY KEY (guild_id, word)
            )
        """)

        await database.execute("""
            CREATE TABLE IF NOT EXISTS whitelisted_words (
                guild_id INTEGER NOT NULL,
                word TEXT NOT NULL COLLATE NOCASE,
                PRIMARY KEY (guild_id, word)
            )
        """)
        await database.execute("""
            CREATE TABLE IF NOT EXISTS support_roles (
                guild_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL,
                PRIMARY KEY (guild_id, role_id)
            )
        """)

        await database.execute("""
            CREATE TABLE IF NOT EXISTS open_tickets (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
        await database.commit()

    print(f"[DATABASE] Ready: {DATABASE_PATH}")


# ---------------------------------------------------------
# GUILD SETUP AND SETTINGS
# ---------------------------------------------------------

async def save_initial_setup(
    guild_id: int,
    muted_role_id: int,
    changelog_channel_id: int,
    use_default_words: bool,
    use_default_links: bool,
) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as database:
        await database.execute("""
            INSERT INTO guild_settings (
                guild_id,
                muted_role_id,
                changelog_channel_id,
                use_default_words,
                use_default_links,
                setup_completed
            )
            VALUES (?, ?, ?, ?, ?, 1)
            ON CONFLICT(guild_id) DO UPDATE SET
                muted_role_id = excluded.muted_role_id,
                changelog_channel_id = excluded.changelog_channel_id,
                use_default_words = excluded.use_default_words,
                use_default_links = excluded.use_default_links,
                setup_completed = 1
        """, (
            guild_id,
            muted_role_id,
            changelog_channel_id,
            int(use_default_words),
            int(use_default_links),
        ))

        await database.commit()


async def get_setup_status(
    guild_id: int,
) -> Optional[tuple[int, int, bool, bool, bool]]:
    async with aiosqlite.connect(DATABASE_PATH) as database:
        async with database.execute("""
            SELECT
                muted_role_id,
                changelog_channel_id,
                use_default_words,
                use_default_links,
                setup_completed
            FROM guild_settings
            WHERE guild_id = ?
        """, (guild_id,)) as cursor:
            row = await cursor.fetchone()

    if row is None:
        return None

    return (
        row[0],
        row[1],
        bool(row[2]),
        bool(row[3]),
        bool(row[4]),
    )


async def is_setup_complete(guild_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as database:
        async with database.execute("""
            SELECT setup_completed
            FROM guild_settings
            WHERE guild_id = ?
        """, (guild_id,)) as cursor:
            row = await cursor.fetchone()

    return bool(row[0]) if row else False


async def get_moderation_preferences(
    guild_id: int,
) -> tuple[bool, bool]:
    async with aiosqlite.connect(DATABASE_PATH) as database:
        async with database.execute("""
            SELECT use_default_words, use_default_links
            FROM guild_settings
            WHERE guild_id = ?
        """, (guild_id,)) as cursor:
            row = await cursor.fetchone()

    if row is None:
        return True, True

    return bool(row[0]), bool(row[1])


# ---------------------------------------------------------
# MUTED ROLE
# ---------------------------------------------------------

async def set_muted_role(guild_id: int, role_id: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as database:
        await database.execute("""
            INSERT INTO guild_settings (
                guild_id,
                muted_role_id
            )
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                muted_role_id = excluded.muted_role_id
        """, (guild_id, role_id))

        await database.commit()


async def get_muted_role(guild_id: int) -> Optional[int]:
    async with aiosqlite.connect(DATABASE_PATH) as database:
        async with database.execute("""
            SELECT muted_role_id
            FROM guild_settings
            WHERE guild_id = ?
        """, (guild_id,)) as cursor:
            row = await cursor.fetchone()

    return row[0] if row else None


# ---------------------------------------------------------
# WARNINGS
# ---------------------------------------------------------

async def get_warning_count(guild_id: int, user_id: int) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as database:
        async with database.execute("""
            SELECT offenses
            FROM warnings
            WHERE guild_id = ? AND user_id = ?
        """, (guild_id, user_id)) as cursor:
            row = await cursor.fetchone()

    return int(row[0]) if row else 0


async def set_warning_count(
    guild_id: int,
    user_id: int,
    offenses: int,
    timeout_end_time: Optional[float] = None,
) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as database:
        await database.execute("""
            INSERT INTO warnings (
                guild_id,
                user_id,
                offenses,
                timeout_end_time
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET
                offenses = excluded.offenses,
                timeout_end_time = excluded.timeout_end_time
        """, (
            guild_id,
            user_id,
            offenses,
            timeout_end_time,
        ))

        await database.commit()


async def reset_warning_count(
    guild_id: int,
    user_id: int,
) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as database:
        cursor = await database.execute("""
            DELETE FROM warnings
            WHERE guild_id = ? AND user_id = ?
        """, (guild_id, user_id))

        await database.commit()
        return cursor.rowcount > 0


# ---------------------------------------------------------
# BANNED LINKS
# ---------------------------------------------------------

async def ensure_default_banned_links(
    guild_id: int,
    links: list[str],
) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as database:
        await database.executemany("""
            INSERT OR IGNORE INTO banned_links (
                guild_id,
                link
            )
            VALUES (?, ?)
        """, [
            (guild_id, link.strip())
            for link in links
            if link.strip()
        ])

        await database.commit()


async def clear_banned_links(guild_id: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as database:
        await database.execute("""
            DELETE FROM banned_links
            WHERE guild_id = ?
        """, (guild_id,))

        await database.commit()


async def add_banned_link(
    guild_id: int,
    link: str,
) -> bool:
    normalized_link = link.strip()

    if not normalized_link:
        return False

    async with aiosqlite.connect(DATABASE_PATH) as database:
        cursor = await database.execute("""
            INSERT OR IGNORE INTO banned_links (
                guild_id,
                link
            )
            VALUES (?, ?)
        """, (guild_id, normalized_link))

        await database.commit()
        return cursor.rowcount > 0


async def get_banned_links(guild_id: int) -> list[str]:
    async with aiosqlite.connect(DATABASE_PATH) as database:
        async with database.execute("""
            SELECT link
            FROM banned_links
            WHERE guild_id = ?
            ORDER BY link
        """, (guild_id,)) as cursor:
            rows = await cursor.fetchall()

    return [row[0] for row in rows]


# ---------------------------------------------------------
# CUSTOM BANNED WORDS
# ---------------------------------------------------------

async def add_custom_banned_word(
    guild_id: int,
    word: str,
) -> bool:
    normalized_word = word.strip().lower()

    if not normalized_word:
        return False

    async with aiosqlite.connect(DATABASE_PATH) as database:
        cursor = await database.execute("""
            INSERT OR IGNORE INTO custom_banned_words (
                guild_id,
                word
            )
            VALUES (?, ?)
        """, (guild_id, normalized_word))

        await database.commit()
        return cursor.rowcount > 0


async def remove_custom_banned_word(
    guild_id: int,
    word: str,
) -> bool:
    normalized_word = word.strip().lower()

    async with aiosqlite.connect(DATABASE_PATH) as database:
        cursor = await database.execute("""
            DELETE FROM custom_banned_words
            WHERE guild_id = ?
              AND word = ? COLLATE NOCASE
        """, (guild_id, normalized_word))

        await database.commit()
        return cursor.rowcount > 0


async def get_custom_banned_words(
    guild_id: int,
) -> list[str]:
    async with aiosqlite.connect(DATABASE_PATH) as database:
        async with database.execute("""
            SELECT word
            FROM custom_banned_words
            WHERE guild_id = ?
            ORDER BY word
        """, (guild_id,)) as cursor:
            rows = await cursor.fetchall()

    return [row[0] for row in rows]


# ---------------------------------------------------------
# WHITELISTED WORDS
# ---------------------------------------------------------

async def add_whitelisted_word(
    guild_id: int,
    word: str,
) -> bool:
    normalized_word = word.strip().lower()

    if not normalized_word:
        return False

    async with aiosqlite.connect(DATABASE_PATH) as database:
        cursor = await database.execute("""
            INSERT OR IGNORE INTO whitelisted_words (
                guild_id,
                word
            )
            VALUES (?, ?)
        """, (guild_id, normalized_word))

        await database.commit()
        return cursor.rowcount > 0


async def remove_whitelisted_word(
    guild_id: int,
    word: str,
) -> bool:
    normalized_word = word.strip().lower()

    async with aiosqlite.connect(DATABASE_PATH) as database:
        cursor = await database.execute("""
            DELETE FROM whitelisted_words
            WHERE guild_id = ?
              AND word = ? COLLATE NOCASE
        """, (guild_id, normalized_word))

        await database.commit()
        return cursor.rowcount > 0


async def get_whitelisted_words(
    guild_id: int,
) -> list[str]:
    async with aiosqlite.connect(DATABASE_PATH) as database:
        async with database.execute("""
            SELECT word
            FROM whitelisted_words
            WHERE guild_id = ?
            ORDER BY word
        """, (guild_id,)) as cursor:
            rows = await cursor.fetchall()

    return [row[0] for row in rows]


# ---------------------------------------------------------
# CHANGELOG CHANNELS
# ---------------------------------------------------------

async def set_changelog_channel(
    guild_id: int,
    channel_id: int,
) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as database:
        await database.execute("""
            INSERT INTO guild_settings (
                guild_id,
                changelog_channel_id
            )
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                changelog_channel_id = excluded.changelog_channel_id
        """, (guild_id, channel_id))

        await database.commit()


async def get_all_changelog_channels() -> list[tuple[int, int]]:
    async with aiosqlite.connect(DATABASE_PATH) as database:
        async with database.execute("""
            SELECT guild_id, changelog_channel_id
            FROM guild_settings
            WHERE changelog_channel_id IS NOT NULL
        """) as cursor:
            rows = await cursor.fetchall()

    return [
        (int(guild_id), int(channel_id))
        for guild_id, channel_id in rows
    ]

# ---------------------------------------------------------
# Ticket System
# ---------------------------------------------------------

async def set_ticket_settings(
    guild_id: int,
    category_id: int,
    logging_channel_id: int,
) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as database:
        await database.execute("""
            INSERT INTO guild_settings (
                guild_id,
                ticket_category_id,
                ticket_log_channel_id
            )
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                ticket_category_id = excluded.ticket_category_id,
                ticket_log_channel_id = excluded.ticket_log_channel_id
        """, (guild_id, category_id, logging_channel_id))
        await database.commit()


async def get_ticket_settings(
    guild_id: int,
) -> Optional[tuple[int, int]]:
    async with aiosqlite.connect(DATABASE_PATH) as database:
        async with database.execute("""
            SELECT ticket_category_id, ticket_log_channel_id
            FROM guild_settings
            WHERE guild_id = ?
        """, (guild_id,)) as cursor:
            row = await cursor.fetchone()

    if row is None or row[0] is None:
        return None

    return row[0], row[1]


async def add_support_role(guild_id: int, role_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as database:
        cursor = await database.execute("""
            INSERT OR IGNORE INTO support_roles (guild_id, role_id)
            VALUES (?, ?)
        """, (guild_id, role_id))
        await database.commit()
        return cursor.rowcount > 0


async def remove_support_role(guild_id: int, role_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as database:
        cursor = await database.execute("""
            DELETE FROM support_roles
            WHERE guild_id = ? AND role_id = ?
        """, (guild_id, role_id))
        await database.commit()
        return cursor.rowcount > 0


async def get_support_role_ids(guild_id: int) -> list[int]:
    async with aiosqlite.connect(DATABASE_PATH) as database:
        async with database.execute("""
            SELECT role_id
            FROM support_roles
            WHERE guild_id = ?
            ORDER BY role_id
        """, (guild_id,)) as cursor:
            rows = await cursor.fetchall()

    return [int(row[0]) for row in rows]


async def add_open_ticket(
    guild_id: int,
    user_id: int,
    channel_id: int,
) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as database:
        await database.execute("""
            INSERT INTO open_tickets (guild_id, user_id, channel_id)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET
                channel_id = excluded.channel_id
        """, (guild_id, user_id, channel_id))
        await database.commit()


async def get_open_ticket_channel_id(
    guild_id: int,
    user_id: int,
) -> Optional[int]:
    async with aiosqlite.connect(DATABASE_PATH) as database:
        async with database.execute("""
            SELECT channel_id
            FROM open_tickets
            WHERE guild_id = ? AND user_id = ?
        """, (guild_id, user_id)) as cursor:
            row = await cursor.fetchone()

    return int(row[0]) if row else None


async def remove_open_ticket(
    guild_id: int,
    user_id: int,
) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as database:
        cursor = await database.execute("""
            DELETE FROM open_tickets
            WHERE guild_id = ? AND user_id = ?
        """, (guild_id, user_id))
        await database.commit()
        return cursor.rowcount > 0