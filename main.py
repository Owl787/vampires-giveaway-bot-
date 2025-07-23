import discord
from discord.ext import commands, tasks
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
    matches = re.findall(r'(\d+)([a-zA-Z]+)', duration_str)
    total_duration = timedelta()
    for amount, unit in matches:
        amount = int(amount)
        if unit in ['d', 'day', 'days']:
            total_duration += timedelta(days=amount)
        elif unit in ['h', 'hour', 'hours']:
            total_duration += timedelta(hours=amount)
        elif unit in ['m', 'min', 'minute', 'minutes']:
            total_duration += timedelta(minutes=amount)
        elif unit in ['w', 'week', 'weeks']:
            total_duration += timedelta(weeks=amount)
        elif unit in ['y', 'year', 'years']:
            total_duration += timedelta(days=365 * amount)
    return total_duration

class GiveawayButton(Button):
    def __init__(self, message_id):
        super().__init__(label="Giveaway", style=discord.ButtonStyle.danger, emoji="🎉")
        self.message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        giveaway = active_giveaways.get(self.message_id)
        if giveaway is None:
            return await interaction.response.send_message("This giveaway has ended.", ephemeral=True)

        if interaction.user.id in giveaway['participants']:
            return await interaction.response.send_message("You already joined!", ephemeral=True)

        giveaway['participants'].append(interaction.user.id)

        # Update participant count
        embed = giveaway['message'].embeds[0]
        embed.set_footer(text=f"{len(giveaway['participants'])} users joined the giveaway")
        await giveaway['message'].edit(embed=embed)

        await interaction.response.send_message("You've entered the giveaway!", ephemeral=True)

class GiveawayView(View):
    def __init__(self, message_id):
        super().__init__(timeout=None)
        self.add_item(GiveawayButton(message_id))

@tree.command(name="giveaway", description="Start a giveaway")
@app_commands.describe(duration="e.g. 1d2h, 30min, 2w", prize="Prize name", winners="Number of winners", image="Image URL")
async def giveaway(interaction: discord.Interaction, duration: str, prize: str, winners: int, image: str = None):
    delta = parse_duration(duration)
    if delta.total_seconds() == 0:
        await interaction.response.send_message("Invalid duration.", ephemeral=True)
        return

    end_time = datetime.now(timezone.utc) + delta

    embed = discord.Embed(title="🎉 Giveaway 🎉", description=f"**Prize:** {prize}", color=0xFF0000)
    embed.add_field(name="Ends At", value=f"<t:{int(end_time.timestamp())}:R>", inline=True)
    embed.set_footer(text="0 users joined the giveaway")

    if image:
        embed.set_image(url=image)

    view = GiveawayView(str(interaction.id))
    message = await interaction.channel.send(embed=embed, view=view)

    active_giveaways[str(interaction.id)] = {
        "message": message,
        "prize": prize,
        "winners": winners,
        "participants": [],
        "end_time": end_time,
        "channel": interaction.channel,
        "creator": interaction.user.id
    }

    await interaction.response.send_message(f"Giveaway started in {interaction.channel.mention}!", ephemeral=True)

    await asyncio.sleep(delta.total_seconds())

    giveaway = active_giveaways.pop(str(interaction.id), None)
    if not giveaway:
        return

    participants = giveaway['participants']
    if not participants:
        await giveaway['channel'].send("No one joined the giveaway.")
        return

    selected_winners = random.sample(participants, min(winners, len(participants)))

    mentions = "\n".join([f"<@{user_id}>" for user_id in selected_winners])
    await giveaway['channel'].send(
        f"<:GiftifyTada:1098640605065777313> Congratulations, {mentions}! You have won the giveaway of prize **{prize}**."
    )

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")
    await tree.sync()

bot.run(os.getenv("DISCORD_TOKEN"))
