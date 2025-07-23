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

giveaways = {}

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

        await giveaway["message"].edit(view=GiveawayView(self.message_id))

# --- Button: Participants ---
class ParticipantsButton(Button):
    def __init__(self, message_id):
        count = len(giveaways.get(message_id, {}).get("participants", []))
        super().__init__(label=f"{count} Participants", style=discord.ButtonStyle.secondary, disabled=True)

# --- View with both buttons ---
class GiveawayView(View):
    def __init__(self, message_id):
        super().__init__(timeout=None)
        self.add_item(JoinButton(message_id))
        self.add_item(ParticipantsButton(message_id))

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

    end_time = datetime.utcnow() + timedelta(seconds=seconds)

    embed = discord.Embed(
        title="🎉 Giveaway 🎉",
        description=f"**{prize}**\n\n• **React with 🎉 to enter!**\n• **Ends in {duration}**\n\n{winners} Winner",
        color=discord.Color.purple()
    )
    embed.set_footer(text=f"Hosted by {interaction.user.name}", icon_url=interaction.user.display_avatar.url)

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
    }

    # Update buttons with real message ID
    view = GiveawayView(message_id)
    await msg.edit(view=view)
    await interaction.response.send_message("Giveaway started!", ephemeral=True)

    # Wait for giveaway end
    await asyncio.sleep(seconds)
    giveaway = giveaways[message_id]
    giveaway["ended"] = True
    participants = list(giveaway["participants"])

    if len(participants) < winners:
        result = "Not enough participants to select a winner."
    else:
        winners_list = random.sample(participants, winners)
        mentions = ", ".join(f"<@{uid}>" for uid in winners_list)
        result = f"🎉 Congratulations {mentions}! You won **{prize}**!"

    embed.color = discord.Color.green()
    embed.description += f"\n\n{result}"
    await msg.edit(embed=embed, view=None)
    await interaction.channel.send(result)

# --- Bot Events ---
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user}!")

bot.run(TOKEN)
