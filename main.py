import os
import random
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
giveaways = {}  # message_id: {"participants": set, "winners": int}

class GiveawayButton(Button):
    def __init__(self, message_id: int):
        super().__init__(
            style=discord.ButtonStyle.danger,
            label="🎉 Join / Leave Giveaway",
            custom_id=f"giveaway_{message_id}"
        )
        self.message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        giveaway = giveaways.get(self.message_id)

        if not giveaway:
            await interaction.response.send_message("This giveaway has ended or doesn't exist.", ephemeral=True)
            return

        participants = giveaway["participants"]
        if user.id in participants:
            participants.remove(user.id)
            await interaction.response.send_message("You left the giveaway!", ephemeral=True)
        else:
            participants.add(user.id)
            await interaction.response.send_message("You joined the giveaway!", ephemeral=True)

class GiveawayView(View):
    def __init__(self, message_id: int):
        super().__init__(timeout=None)
        self.add_item(GiveawayButton(message_id))

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s).")
    except Exception as e:
        print(e)

@bot.tree.command(name="giveaway", description="Start a giveaway")
@app_commands.describe(duration="Time in seconds", winners="Number of winners", prize="Giveaway prize")
async def giveaway(interaction: discord.Interaction, duration: int, winners: int, prize: str):
    embed = discord.Embed(
        title="🎉 Giveaway Started!",
        description=f"**Prize:** {prize}\n**Winners:** {winners}\nTime: {duration} seconds\nClick the button to join!",
        color=discord.Color.red()
    )
    msg = await interaction.channel.send(embed=embed, view=GiveawayView(0))  # placeholder
    giveaways[msg.id] = {"participants": set(), "winners": winners}
    view = GiveawayView(msg.id)
    await msg.edit(view=view)
    await interaction.response.send_message("Giveaway started!", ephemeral=True)

    await asyncio.sleep(duration)
    await end_giveaway_by_id(msg.id, interaction.channel)

async def end_giveaway_by_id(message_id: int, channel):
    giveaway = giveaways.pop(message_id, None)
    if not giveaway:
        return

    participants = list(giveaway["participants"])
    winner_count = giveaway["winners"]

    if not participants:
        await channel.send("🎉 Giveaway ended but no one joined!")
        return

    if len(participants) < winner_count:
        winner_count = len(participants)

    winners = random.sample(participants, winner_count)
    winner_mentions = [f"<@{uid}>" for uid in winners]
    await channel.send(f"🎉 Giveaway ended! Congratulations to {', '.join(winner_mentions)}!")

@bot.tree.command(name="endgiveaway", description="Force end a giveaway by message ID")
@app_commands.describe(message_id="The ID of the giveaway message to end")
async def endgiveaway(interaction: discord.Interaction, message_id: str):
    try:
        message_id = int(message_id)
        await end_giveaway_by_id(message_id, interaction.channel)
        await interaction.response.send_message("Giveaway ended!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Error: {e}", ephemeral=True)

@bot.tree.command(name="reroll", description="Reroll a giveaway")
@app_commands.describe(message_id="The ID of the giveaway message to reroll")
async def reroll(interaction: discord.Interaction, message_id: str):
    try:
        message_id = int(message_id)
        giveaway = giveaways.get(message_id)
        if not giveaway:
            await interaction.response.send_message("This giveaway has already ended or doesn't exist.", ephemeral=True)
            return

        participants = list(giveaway["participants"])
        winner_count = giveaway["winners"]

        if len(participants) < winner_count:
            winner_count = len(participants)

        winners = random.sample(participants, winner_count)
        winner_mentions = [f"<@{uid}>" for uid in winners]
        await interaction.response.send_message(f"🎉 Rerolled winners: {', '.join(winner_mentions)}")
    except Exception as e:
        await interaction.response.send_message(f"Error: {e}", ephemeral=True)
