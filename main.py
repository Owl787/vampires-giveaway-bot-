import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
import random
import asyncio
import os
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

giveaways = {}  # Store giveaways by message ID

# Helper to parse duration like '5d'
def parse_duration(duration_str):
    pattern = r"(\d+)([smhd])"
    matches = re.findall(pattern, duration_str)
    if not matches:
        return None
    seconds = 0
    for value, unit in matches:
        value = int(value)
        if unit == "s":
            seconds += value
        elif unit == "m":
            seconds += value * 60
        elif unit == "h":
            seconds += value * 3600
        elif unit == "d":
            seconds += value * 86400
    return seconds

# --- Button: Join ---
class JoinButton(Button):
    def __init__(self, message_id):
        super().__init__(label="🎉 Join", style=discord.ButtonStyle.success, custom_id=f"join_{message_id}")
        self.message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        giveaway = giveaways.get(self.message_id)
        if not giveaway or giveaway["ended"]:
            await interaction.response.send_message("Giveaway ended or not found.", ephemeral=True)
            return

        user_id = interaction.user.id
        if user_id in giveaway["participants"]:
            giveaway["participants"].remove(user_id)
            await interaction.response.send_message("You left the giveaway.", ephemeral=True)
        else:
            giveaway["participants"].add(user_id)
            await interaction.response.send_message("You joined the giveaway!", ephemeral=True)

        # Update the buttons with new participant count
        view = GiveawayView(self.message_id)
        await giveaway["message"].edit(view=view)

# --- Button: Participants ---
class ParticipantsButton(Button):
    def __init__(self, message_id, count):
        super().__init__(label=f"{count} Participants", style=discord.ButtonStyle.secondary, disabled=True)

# --- View with both buttons ---
class GiveawayView(View):
    def __init__(self, message_id):
        super().__init__(timeout=None)
        self.message_id = message_id
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        self.add_item(JoinButton(self.message_id))
        count = len(giveaways.get(self.message_id, {}).get("participants", []))
        self.add_item(ParticipantsButton(self.message_id, count))

# --- Slash command to start giveaway ---
@bot.tree.command(name="giveaway", description="Start a giveaway")
@app_commands.describe(
    prize="Giveaway prize (e.g., $100 Nitro)",
    duration="Duration (e.g., 1d, 2h)",
    winners="Number of winners"
)
async def giveaway_command(interaction: discord.Interaction, prize: str, duration: str, winners: int):
    seconds = parse_duration(duration)
    if seconds is None or seconds <= 0:
        await interaction.response.send_message("Invalid duration format.", ephemeral=True)
        return
    if winners < 1:
        await interaction.response.send_message("Winners must be at least 1.", ephemeral=True)
        return

    end_time = datetime.utcnow() + timedelta(seconds=seconds)
    timestamp_unix = int(end_time.timestamp())

    await interaction.channel.send("🎉 **Giveaway** 🎉")

    embed = discord.Embed(
        description=(
            f"**{prize}**\n"
            f"Ends: <t:{timestamp_unix}:R> (<t:{timestamp_unix}:f>)\n"
            f"Winners: **{winners}**"
        ),
        color=discord.Color.purple()
    )

    embed.set_footer(text=f"Hosted by {interaction.user}", icon_url=interaction.user.display_avatar.url)

    view = GiveawayView("temp")
    msg = await interaction.channel.send(embed=embed, view=view)
    message_id = str(msg.id)

    giveaways[message_id] = {
        "prize": prize,
        "end_time": end_time,
        "participants": set(),
        "message": msg,
        "ended": False,
        "winners": winners,
        "host": interaction.user.id,
    }

    view = GiveawayView(message_id)
    await msg.edit(view=view)
    await interaction.response.send_message("Giveaway started!", ephemeral=True)

    await asyncio.sleep(seconds)
    giveaway = giveaways.get(message_id)
    if giveaway and not giveaway["ended"]:
        await end_giveaway(message_id)

# --- End giveaway function ---
async def end_giveaway(message_id):
    giveaway = giveaways.get(message_id)
    if not giveaway or giveaway["ended"]:
        return

    giveaway["ended"] = True
    participants = list(giveaway["participants"])
    prize = giveaway["prize"]
    winners = giveaway["winners"]
    msg = giveaway["message"]
    channel = msg.channel

    if len(participants) < winners or len(participants) == 0:
        result = "Not enough participants to select a winner."
        winners_list = []
    else:
        winners_list = random.sample(participants, min(winners, len(participants)))
        mentions = ", ".join(f"<@{uid}>" for uid in winners_list)
        result = f"🎉 Congratulations {mentions}! You won **{prize}**!"

    embed = msg.embeds[0]
    embed.color = discord.Color.green()
    embed.description += f"\n\n{result}"

    await msg.edit(embed=embed, view=None)
    await channel.send(result)

    giveaway["winners_list"] = winners_list

# --- Slash command to end giveaway early ---
@bot.tree.command(name="end", description="End an ongoing giveaway early")
@app_commands.describe(message_id="Message ID of the giveaway to end")
async def end_command(interaction: discord.Interaction, message_id: str):
    giveaway = giveaways.get(message_id)
    if not giveaway:
        await interaction.response.send_message("Giveaway not found.", ephemeral=True)
        return
    if giveaway["ended"]:
        await interaction.response.send_message("Giveaway has already ended.", ephemeral=True)
        return

    if interaction.user.id != giveaway["host"] and not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("You do not have permission to end this giveaway.", ephemeral=True)
        return

    await end_giveaway(message_id)
    await interaction.response.send_message(f"Giveaway {message_id} ended early.", ephemeral=True)

# --- Slash command to reroll winners ---
@bot.tree.command(name="reroll", description="Reroll winners for an ended giveaway")
@app_commands.describe(message_id="Message ID of the giveaway to reroll")
async def reroll_command(interaction: discord.Interaction, message_id: str):
    giveaway = giveaways.get(message_id)
    if not giveaway:
        await interaction.response.send_message("Giveaway not found.", ephemeral=True)
        return
    if not giveaway["ended"]:
        await interaction.response.send_message("Giveaway has not ended yet.", ephemeral=True)
        return

    participants = list(giveaway["participants"])
    winners = giveaway["winners"]

    if len(participants) < winners or len(participants) == 0:
        await interaction.response.send_message("Not enough participants to select new winners.", ephemeral=True)
        return

    winners_list = random.sample(participants, min(winners, len(participants)))
    giveaway["winners_list"] = winners_list
    mentions = ", ".join(f"<@{uid}>" for uid in winners_list)
    prize = giveaway["prize"]

    result = f"🎉 Reroll results! Congratulations {mentions}! You won **{prize}**!"
    await interaction.response.send_message(result)

    msg = giveaway["message"]
    embed = msg.embeds[0]
    description = embed.description.split("\n\n")[0]
    embed.description = f"{description}\n\n{result}"
    await msg.edit(embed=embed)

# --- Bot Events ---
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user}!")

bot.run(TOKEN)
