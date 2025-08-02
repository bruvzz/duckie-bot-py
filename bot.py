# at top: imports remain the same
import os
import sys
import asyncio
import logging
from datetime import datetime, timezone

import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv

# --- Load env ---
load_dotenv()
TOKEN = os.getenv("TOKEN")
CHANNEL_ID = int(os.getenv("NOTIFY_CHANNEL_ID", ""))
EVERYONE_PING = "@everyone"

# --- Logging ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger("bot")

# --- Intents ---
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.messages = True
intents.message_content = True

# --- State ---
current_windows_hash: str | None = None
future_windows_hash: str | None = None


def is_ignored_error(exc: Exception) -> bool:
    text = str(exc)
    patterns = ["Error: read ECONNRESET", "-4077", "stream_base_commons:217:20"]
    return any(p in text for p in patterns)


def handle_loop_exception(loop, context):
    exception = context.get("exception")
    if exception and is_ignored_error(exception):
        logger.info("WSS Error: Client Lost Connection and Connection Reset")
        return
    logger.error("\n=== UNHANDLED EXCEPTION IN LOOP ===")
    logger.error(f"Context: {context}")
    logger.error("=== END ===")


def global_excepthook(exc_type, exc_value, exc_traceback):
    if exc_value and is_ignored_error(exc_value):
        return
    logger.error("\n=== UNCAUGHT EXCEPTION ===")
    logger.error("Exception:", exc_info=(exc_type, exc_value, exc_traceback))
    logger.error("=== END ===")


sys.excepthook = global_excepthook


# --- Bot subclass to hook into setup ---
class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents, application_id=None)

    async def setup_hook(self):
        # This runs inside the event loop before login is complete.
        loop = asyncio.get_running_loop()
        loop.set_exception_handler(handle_loop_exception)
        # Sync slash commands on startup (optional)
        try:
            await self.tree.sync()
            logger.info("Slash commands synced.")
        except Exception as e:
            logger.warning(f"Slash command sync failed: {e}")

        # Kick off background monitor once the loop is running
        self.loop.create_task(monitor_hash_updates_loop())


bot = MyBot()

# --- UI Views (same as before) ---
class VersionButtonView(discord.ui.View):
    def __init__(self, hash_str: str, *, timeout: float | None = None):
        super().__init__(timeout=timeout)
        url = f"https://rdd.weao.xyz/?channel=LIVE&binaryType=WindowsPlayer&version={hash_str}"
        self.add_item(discord.ui.Button(label=hash_str, url=url, style=discord.ButtonStyle.link))


class FutureBuildView(discord.ui.View):
    def __init__(self, future_hash: str, *, timeout: float | None = None):
        super().__init__(timeout=timeout)
        download_url = f"https://rdd.weao.xyz/?channel=LIVE&binaryType=WindowsPlayer&version={future_hash}"
        self.add_item(
            discord.ui.Button(
                label=future_hash,
                style=discord.ButtonStyle.secondary,
                disabled=True,
            )
        )
        self.add_item(
            discord.ui.Button(label="Download", url=download_url, style=discord.ButtonStyle.link)
        )


# --- Helpers ---
async def fetch_json(url: str) -> dict | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"HTTP {resp.status} from {url}")
                return await resp.json()
    except Exception as e:
        logger.error(f"Error fetching {url}: {e}", exc_info=True)
        return None


def color_from_hex(hex_str: str) -> discord.Colour:
    return discord.Colour(int(hex_str.lstrip("#"), 16))


async def notify_current(channel: discord.abc.Messageable, new_current_hash: str):
    global current_windows_hash
    current_windows_hash = new_current_hash

    embed = discord.Embed(
        title="New Roblox Deployment Detected",
        description="All exploits are now patched. Roblox has updated to a new version.",
        color=color_from_hex("#962424"),
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_footer(text="")

    view = VersionButtonView(new_current_hash)
    try:
        await channel.send(content=EVERYONE_PING, embed=embed, view=view)
    except Exception:
        logger.exception("Fallback send for current deployment.")
        await channel.send(content=EVERYONE_PING, embed=embed)


async def notify_future(channel: discord.abc.Messageable, new_future_hash: str):
    global future_windows_hash
    future_windows_hash = new_future_hash

    embed = discord.Embed(
        title="New Roblox Deployment Detected",
        description="**This is a future build and is not out yet.**\nA new version deployment has been released.",
        color=color_from_hex("#965d24"),
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_footer(text="")

    view = FutureBuildView(new_future_hash)
    try:
        await channel.send(content=EVERYONE_PING, embed=embed, view=view)
    except Exception:
        logger.exception("Fallback send for future deployment.")
        await channel.send(content=EVERYONE_PING, embed=embed)


async def monitor_hash_updates_loop():
    global current_windows_hash, future_windows_hash
    while True:
        try:
            current_data, future_data = await asyncio.gather(
                fetch_json("https://weao.xyz/api/versions/current"),
                fetch_json("https://weao.xyz/api/versions/future"),
            )

            new_current_hash = current_data.get("Windows") if current_data else None
            new_future_hash = future_data.get("Windows") if future_data else None

            channel = bot.get_channel(CHANNEL_ID)
            if channel is None:
                logger.warning(f"Channel with ID {CHANNEL_ID} not found.")
            else:
                if new_current_hash and new_current_hash != current_windows_hash:
                    await notify_current(channel, new_current_hash)
                if new_future_hash and new_future_hash != future_windows_hash:
                    await notify_future(channel, new_future_hash)
        except Exception:
            logger.exception("monitor_hash_updates error:")
        await asyncio.sleep(3)


# --- Events ---
@bot.event
async def on_ready():
    global current_windows_hash, future_windows_hash
    logger.info(f"Logged in as {bot.user} ({bot.user.id})")

    try:
        current_data = await fetch_json("https://weao.xyz/api/versions/current")
        future_data = await fetch_json("https://weao.xyz/api/versions/future")
        current_windows_hash = current_data.get("Windows") if current_data else None
        future_windows_hash = future_data.get("Windows") if future_data else None
        logger.info(f"Initial Roblox Windows Current Hash: {current_windows_hash}")
        logger.info(f"Initial Roblox Windows Future Hash: {future_windows_hash}")
    except Exception:
        logger.exception("Error during ready handler:")

    await bot.change_presence(
        activity=discord.Activity(name="with Submarine! /help", type=discord.ActivityType.playing),
        status=discord.Status.idle,
    )


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    is_only_mentioning_bot = bot.user in message.mentions and len(message.mentions) == 1

    if is_only_mentioning_bot:
        try:
            reply = await message.reply(
                f"<@{message.author.id}> - Greetings! Use `/help` if you need any assistance."
            )
            await asyncio.sleep(5)
            try:
                await reply.delete()
            except Exception:
                logger.warning("Failed to delete bot reply.")
        except Exception:
            logger.exception("Error replying to mention.")

    if message.content.lower() == "w.help":
        await message.reply(
            f"<@{message.author.id}> - There will never be prefixes, fuckass boy."
        )

    await bot.process_commands(message)


# --- Diagnostic slash ping command ---
@bot.tree.command(name="ping", description="Check bot latency.")
async def ping(interaction: discord.Interaction):
    start = datetime.now(timezone.utc)
    await interaction.response.defer(ephemeral=True)
    end = datetime.now(timezone.utc)
    bot_latency_ms = int((end - start).total_seconds() * 1000)
    api_latency_ms = int(bot.latency * 1000)
    embed = discord.Embed(
        title="Success",
        description="Here's my current latency statistics:",
        color=discord.Colour.greyple(),
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="Bot Latency", value=f"`{bot_latency_ms}ms`", inline=True)
    embed.add_field(name="API Latency", value=f"`{api_latency_ms}ms`", inline=True)
    embed.set_footer(
        text=f"Requested by {interaction.user}", icon_url=interaction.user.display_avatar.url
    )
    await interaction.edit_original_response(embed=embed)


# --- Entry point ---
async def main():
    if not TOKEN:
        logger.error("Missing TOKEN in environment.")
        sys.exit(1)
    try:
        await bot.start(TOKEN)
    except Exception:
        logger.exception("Failed to start bot.")


if __name__ == "__main__":
    asyncio.run(main())
