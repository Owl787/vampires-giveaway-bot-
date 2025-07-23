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

class JoinButton(Button):
    def __init__(self, message_id):
        super().__init__(label="🎉 Join", style=discord.ButtonStyle.blurple, custom_id=f"join_{message_id}")
        self.message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        giveaway = giveaways.get(self.message_id)
        if not giveaway or giveaway["ended"]:
            await interaction.response.send_message("This giveaway has ended.", ephemeral=True)
            return

        user_id = interaction.user.id
        if user_id in giveaway["participants"]:
            giveaway["participants"].remove(user_id)
            await interaction.response.send_message("You left the giveaway.", ephemeral=True)
        else:
            giveaway["participants"].add(user_id)
            await interaction.response.send_message("You joined the giveaway!", ephemeral=True)

        view = GiveawayView(self.message_id)
        await giveaway["message"].edit(view=view)

class ParticipantsButton(Button):
    def __init__(self, message_id, count):
        super().__init__(label=f"{count} Participants", style=discord.ButtonStyle.gray, disabled=True)

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

@bot.tree.command(name="giveaway", description="Start a giveaway like Kiyu")
@app_commands.describe(
    prize="What is the prize?",
    duration="Duration (e.g., 1d, 2h)",
    winners="Number of winners"
)
async def giveaway_command(interaction: discord.Interaction, prize: str, duration: str, winners: int):
    seconds = parse_duration(duration)
    if seconds is None or seconds <= 0:
        await interaction.response.send_message("Invalid duration format.", ephemeral=True)
        return

    end_time = datetime.utcnow() + timedelta(seconds=seconds)

    # Send prize as top message
    await interaction.channel.send(f"**🎁 {prize}**")

    embed = discord.Embed(
        description=(
            f":kiyudot: React with 🎉 to enter\n"
            f":kiyudot: Ends <t:{int(end_time.timestamp())}:R>\n\n"
            f"🎉 {winners} Winner{'s' if winners > 1 else ''}"
        ),
        color=discord.Color.from_str("#2f3136")  # Dark style
    )
    embed.set_thumbnail(url=bot.user.display_avatar.url)

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
    await interaction.response.send_message("✅ Giveaway started!", ephemeral=True)

    await asyncio.sleep(seconds)
    await end_giveaway(message_id)

async def end_giveaway(message_id):
    giveaway = giveaways.get(message_id)
    if not giveaway or giveaway["ended"]:
        return

    giveaway["ended"] = True
    participants = list(giveaway["participants"])
    msg = giveaway["message"]
    channel = msg.channel
    winners = giveaway["winners"]

    if len(participants) < winners:
        result = "❌ Not enough participants to draw a winner."
        winner_ids = []
    else:
        winner_ids = random.sample(participants, winners)
        result = f"🏆 Winner: {', '.join(f'<@{uid}>' for uid in winner_ids)}"

    embed = msg.embeds[0]
    embed.color = discord.Color.green()
    embed.description += f"\n\n{result}"
    embed.set_image(url="https://cdn-icons-png.flaticon.com/512/2583/2583341.png")  # Optional winner image

    await msg.edit(embed=embed, view=None)
    await channel.send(result)
    giveaway["winners_list"] = winner_ids

@bot.tree.command(name="end", description="End a giveaway early")
@app_commands.describe(message_id="Message ID of the giveaway")
async def end_command(interaction: discord.Interaction, message_id: str):
    if message_id not in giveaways:
        await interaction.response.send_message("Giveaway not found.", ephemeral=True)
        return
    if giveaways[message_id]["ended"]:
        await interaction.response.send_message("This giveaway has already ended.", ephemeral=True)
        return

    await end_giveaway(message_id)
    await interaction.response.send_message("Giveaway ended early.", ephemeral=True)

@bot.tree.command(name="reroll", description="Reroll winners for a finished giveaway")
@app_commands.describe(message_id="Message ID of the giveaway")
async def reroll_command(interaction: discord.Interaction, message_id: str):
    giveaway = giveaways.get(message_id)
    if not giveaway or not giveaway["ended"]:
        await interaction.response.send_message("Giveaway not found or not ended yet.", ephemeral=True)
        return

    participants = list(giveaway["participants"])
    winners = giveaway["winners"]

    if len(participants) < winners:
        await interaction.response.send_message("Not enough participants to reroll.", ephemeral=True)
        return

    new_winners = random.sample(participants, winners)
    giveaway["winners_list"] = new_winners
    mentions = ", ".join(f"<@{uid}>" for uid in new_winners)

    embed = giveaway["message"].embeds[0]
    embed.description += f"\n🔁 New winner: {mentions}"
    await giveaway["message"].edit(embed=embed)
    await interaction.response.send_message(f"🔁 Rerolled winner: {mentions}")

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Logged in as {bot.user}")

bot.run(TOKEN)
