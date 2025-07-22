import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
import random
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
giveaways = {}  # Stores giveaway data by message_id

class GiveawayButton(Button):
    def __init__(self, message_id: int):
        super().__init__(
            label="🎉 Join / Leave Giveaway",
            style=discord.ButtonStyle.danger,
            custom_id=f"giveaway_{message_id}"
        )
        self.message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        giveaway = giveaways.get(self.message_id)

        if not giveaway:
            await interaction.response.send_message("❌ This giveaway has ended or doesn't exist.", ephemeral=True)
            return

        if user.id in giveaway["participants"]:
            giveaway["participants"].remove(user.id)
            await interaction.response.send_message("❌ You left the giveaway.", ephemeral=True)
        else:
            giveaway["participants"].add(user.id)
            await interaction.response.send_message("✅ You joined the giveaway!", ephemeral=True)

class GiveawayView(View):
    def __init__(self, message_id: int):
        super().__init__(timeout=None)
        self.add_item(GiveawayButton(message_id))

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash command(s).")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")

@bot.tree.command(name="giveaway", description="Start a giveaway")
@app_commands.describe(duration="Time in seconds", winners="Number of winners", prize="Giveaway prize")
async def giveaway(interaction: discord.Interaction, duration: int, winners: int, prize: str):
    embed = discord.Embed(
        title="🎉 New Giveaway!",
        description=f"**Prize:** {prize}\n**Winners:** {winners}\n⏳ Ends in: {duration} seconds\nClick the button to enter!",
        color=discord.Color.red()
    )
    msg = await interaction.channel.send(embed=embed, view=GiveawayView(0))  # temp ID

    giveaways[msg.id] = {"participants": set(), "winners": winners}
    await msg.edit(view=GiveawayView(msg.id))  # real ID now
    await interaction.response.send_message("✅ Giveaway started!", ephemeral=True)

    await asyncio.sleep(duration)
    await end_giveaway_by_id(msg.id, interaction.channel)

async def end_giveaway_by_id(message_id: int, channel):
    giveaway = giveaways.pop(message_id, None)
    if not giveaway:
        await channel.send("⚠️ Giveaway not found or already ended.")
        return

    participants = list(giveaway["participants"])
    winner_count = giveaway["winners"]

    if not participants:
        await channel.send("😢 No one joined the giveaway.")
        return

    if len(participants) < winner_count:
        winner_count = len(participants)

    winners = random.sample(participants, winner_count)
    winner_mentions = ", ".join(f"<@{uid}>" for uid in winners)

    await channel.send(f"🎉 Giveaway ended! Congratulations to: {winner_mentions}")

@bot.tree.command(name="endgiveaway", description="End a giveaway manually by message ID")
@app_commands.describe(message_id="Message ID of the giveaway")
async def endgiveaway(interaction: discord.Interaction, message_id: str):
    try:
        msg_id = int(message_id)
        await end_giveaway_by_id(msg_id, interaction.channel)
        await interaction.response.send_message("✅ Giveaway ended manually.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="reroll", description="Reroll the giveaway winners")
@app_commands.describe(message_id="Message ID of the giveaway")
async def reroll(interaction: discord.Interaction, message_id: str):
    try:
        msg_id = int(message_id)
        giveaway = giveaways.get(msg_id)
        if not giveaway:
            await interaction.response.send_message("❌ Giveaway not found or already ended.", ephemeral=True)
            return

        participants = list(giveaway["participants"])
        winner_count = giveaway["winners"]

        if len(participants) == 0:
            await interaction.response.send_message("😢 No participants to reroll.", ephemeral=True)
            return

        if len(participants) < winner_count:
            winner_count = len(participants)

        new_winners = random.sample(participants, winner_count)
        winner_mentions = ", ".join(f"<@{uid}>" for uid in new_winners)
        await interaction.response.send_message(f"🔁 Rerolled winners: {winner_mentions}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

# Run the bot
if __name__ == "__main__":
    bot.run(TOKEN)
