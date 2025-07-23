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

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree
active_giveaways = {}

def parse_duration(duration_str):
    time_regex = re.findall(r"(\d+)\s*(d|day|m|minute|min|h|hour|w|week|y|year)", duration_str.lower())
    if not time_regex:
        return None
    total_seconds = 0
    for value, unit in time_regex:
        value = int(value)
        if unit in ['d', 'day']:
            total_seconds += value * 86400
        elif unit in ['h', 'hour']:
            total_seconds += value * 3600
        elif unit in ['m', 'minute', 'min']:
            total_seconds += value * 60
        elif unit in ['w', 'week']:
            total_seconds += value * 604800
        elif unit in ['y', 'year']:
            total_seconds += value * 31536000
    return timedelta(seconds=total_seconds)

class GiveawayButton(Button):
    def __init__(self, message_id):
        super().__init__(label="Giveaway", style=discord.ButtonStyle.danger, emoji="<:GiftifyTada:1098640605065777313>")
        self.message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        giveaway = active_giveaways.get(self.message_id)
        if not giveaway:
            await interaction.response.send_message("This giveaway is no longer active.", ephemeral=True)
            return
        user_id = interaction.user.id
        if user_id in giveaway['participants']:
            await interaction.response.send_message("You already joined!", ephemeral=True)
        else:
            giveaway['participants'].append(user_id)
            await interaction.response.send_message(f"You have joined the giveaway! ({len(giveaway['participants'])} participants)", ephemeral=True)
            await giveaway['message'].edit(embed=create_embed(giveaway))

def create_embed(giveaway):
    timestamp = int(giveaway['end_time'].timestamp())
    embed = discord.Embed(
        title="<:GiftifyTada:1098640605065777313> **GIVEAWAY**",
        description=f"""Click the <:GiftifyTada:1098640605065777313> button to join the giveaway!
Hosted By: <@{giveaway['host']}>
Ends: <t:{timestamp}:R> (<t:{timestamp}:f>)""",
        color=discord.Color.red()
    )
    embed.set_image(url=giveaway['image'])
    embed.set_footer(text=f"{len(giveaway['participants'])} participants")
    return embed

@tree.command(name="giveaway", description="Start a giveaway")
@app_commands.describe(duration="Example: 1d2h3m", prize="Giveaway prize", image="Image URL")
async def giveaway(interaction: discord.Interaction, duration: str, prize: str, image: str):
    await interaction.response.defer()
    delta = parse_duration(duration)
    if not delta:
        await interaction.followup.send("Invalid duration format!", ephemeral=True)
        return
    end_time = datetime.now(timezone.utc) + delta
    message = await interaction.channel.send(
        embed=discord.Embed(title="Starting giveaway..."),
        view=None
    )
    giveaway_data = {
        'host': interaction.user.id,
        'end_time': end_time,
        'participants': [],
        'prize': prize,
        'image': image,
        'message': message
    }
    active_giveaways[message.id] = giveaway_data

    button = GiveawayButton(message.id)
    view = View()
    view.add_item(button)
    embed = create_embed(giveaway_data)
    await message.edit(embed=embed, view=view)

    await asyncio.sleep(delta.total_seconds())

    if message.id not in active_giveaways:
        return

    participants = giveaway_data['participants']
    if not participants:
        await message.channel.send("No one joined the giveaway.")
    else:
        winner = random.choice(participants)
        await message.channel.send(f"<:GiftifyTada:1098640605065777313> Congratulations, <@{winner}>! You have won the giveaway of prize **{prize}**.")

    del active_giveaways[message.id]

@tree.command(name="end", description="End a giveaway early")
@app_commands.describe(message_id="The giveaway message ID")
async def end(interaction: discord.Interaction, message_id: str):
    msg_id = int(message_id)
    if msg_id not in active_giveaways:
        await interaction.response.send_message("Giveaway not found!", ephemeral=True)
        return

    giveaway = active_giveaways[msg_id]
    participants = giveaway['participants']
    if not participants:
        await interaction.response.send_message("No participants to choose from.")
    else:
        winner = random.choice(participants)
        await interaction.channel.send(f"<:GiftifyTada:1098640605065777313> Congratulations, <@{winner}>! You have won the giveaway of prize **{giveaway['prize']}**.")

    del active_giveaways[msg_id]
    await interaction.response.send_message("Giveaway ended.", ephemeral=True)

@bot.event
async def on_ready():
    await tree.sync()
    print(f"Bot ready as {bot.user}")

bot.run(os.getenv("TOKEN"))
