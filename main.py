import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
import random
import asyncio
import os
import re
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
giveaways = {}

def parse_duration(duration_str):
    units = {
        "s": 1, "m": 60, "h": 3600, "d": 86400,
        "w": 604800, "mo": 2592000, "y": 31536000
    }
    pattern = r"(\d+)(s|m|h|d|w|mo|y)"
    matches = re.findall(pattern, duration_str)
    if not matches:
        return None
    return sum(int(value) * units[unit] for value, unit in matches)

class JoinButton(Button):
    def __init__(self, message_id: int):
        super().__init__(label="Join", style=discord.ButtonStyle.green, custom_id=f"join_{message_id}")
        self.message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        giveaway = giveaways.get(self.message_id)
        if not giveaway or giveaway["ended"]:
            await interaction.response.send_message("This giveaway has ended or doesn't exist.", ephemeral=True)
            return

        if user.id in giveaway["participants"]:
            giveaway["participants"].remove(user.id)
            await interaction.response.send_message("You left the giveaway.", ephemeral=True)
        else:
            giveaway["participants"].add(user.id)
            await interaction.response.send_message("You joined the giveaway!", ephemeral=True)

        await giveaway["message"].edit(view=GiveawayView(self.message_id))

class ParticipantButton(Button):
    def __init__(self, message_id: int):
        super().__init__(label="Participants", style=discord.ButtonStyle.blurple, custom_id=f"participants_{message_id}")
        self.message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        giveaway = giveaways.get(self.message_id)
        if not giveaway:
            await interaction.response.send_message("Giveaway not found.", ephemeral=True)
            return

        users = [f"<@{uid}>" for uid in giveaway["participants"]]
        participants_text = "\n".join(users) if users else "No participants yet."
        await interaction.response.send_message(f"**Participants:**\n{participants_text}", ephemeral=True)

class GiveawayView(View):
    def __init__(self, message_id: int):
        super().__init__(timeout=None)
        self.add_item(JoinButton(message_id))
        self.add_item(ParticipantButton(message_id))

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s).")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

@bot.tree.command(name="giveaway", description="Start a giveaway")
@app_commands.describe(
    duration="e.g. 1d2h30m10s",
    winners="Number of winners",
    prize="Prize name"
)
async def giveaway(interaction: discord.Interaction, duration: str, winners: int, prize: str):
    seconds = parse_duration(duration.lower())
    if seconds is None:
        await interaction.response.send_message("Invalid duration format. Use like `1d2h30m10s` or `5m`.", ephemeral=True)
        return

    end_time = int((datetime.now(timezone.utc) + timedelta(seconds=seconds)).timestamp())
    host = interaction.user.mention

    embed = discord.Embed(
        title="Giveaway",
        description=(
            f"**Prize:** {prize}\n"
            f"**Ends in:** <t:{end_time}:R>\n"
            f"**Hosted by:** {host}\n"
            f"**Winners:** {winners}"
        ),
        color=discord.Color.purple()
    )

    msg = await interaction.channel.send(embed=embed, view=GiveawayView(0))
    giveaways[msg.id] = {
        "participants": set(),
        "winners": winners,
        "prize": prize,
        "host": interaction.user,
        "end_time": end_time,
        "ended": False,
        "message": msg
    }

    await msg.edit(view=GiveawayView(msg.id))
    await interaction.response.send_message("Giveaway started!", ephemeral=True)

    async def update_embed():
        while not giveaways[msg.id]["ended"]:
            await asyncio.sleep(10)
            embed.description = (
                f"**Prize:** {prize}\n"
                f"**Ends in:** <t:{end_time}:R>\n"
                f"**Hosted by:** {host}\n"
                f"**Winners:** {winners}"
            )
            await msg.edit(embed=embed)

    bot.loop.create_task(update_embed())
    await asyncio.sleep(seconds)
    await end_giveaway_by_id(msg.id, interaction.channel)

async def end_giveaway_by_id(message_id: int, channel):
    giveaway = giveaways.get(message_id)
    if not giveaway or giveaway["ended"]:
        return

    giveaway["ended"] = True
    participants = list(giveaway["participants"])
    prize = giveaway["prize"]
    host = giveaway["host"]
    end_time = int(datetime.now(timezone.utc).timestamp())
    winner_count = giveaway["winners"]

    if not participants:
        embed = discord.Embed(
            title="Giveaway Ended",
            description=f"**Hosted by:** {host.mention}\nNo participants joined.\n**Ended:** <t:{end_time}:F>",
            color=discord.Color.dark_gray()
        )
        await channel.send(embed=embed)
        return

    if len(participants) < winner_count:
        winner_count = len(participants)

    winners = random.sample(participants, winner_count)
    mentions = ", ".join(f"<@{uid}>" for uid in winners)

    embed = discord.Embed(
        title="Giveaway Ended",
        description=f"**Hosted by:** {host.mention}\n**Winners:** {mentions}\n**Ended:** <t:{end_time}:F>",
        color=discord.Color.dark_gray()
    )
    await channel.send(embed=embed)

@bot.tree.command(name="reroll", description="Reroll a giveaway")
@app_commands.describe(message_id="Giveaway message ID to reroll")
async def reroll(interaction: discord.Interaction, message_id: str):
    try:
        msg_id = int(message_id)
        giveaway = giveaways.get(msg_id)
        if not giveaway or not giveaway["ended"]:
            await interaction.response.send_message("Giveaway not found or not ended yet.", ephemeral
