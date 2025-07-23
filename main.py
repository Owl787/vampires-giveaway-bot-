import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button

import random
import asyncio
import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)

giveaways = {}

class GiveawayView(View):
    def __init__(self, giveaway_id):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id

        self.join_button = Button(label="Join", emoji="🎁", style=discord.ButtonStyle.success, custom_id="join_button")
        self.participant_count = Button(label="0 Participants", disabled=True, style=discord.ButtonStyle.secondary)

        self.join_button.callback = self.join_button_callback

        self.add_item(self.join_button)
        self.add_item(self.participant_count)

    async def join_button_callback(self, interaction: discord.Interaction):
        data = giveaways.get(self.giveaway_id)
        if not data:
            return await interaction.response.send_message("This giveaway no longer exists.", ephemeral=True)

        user_id = interaction.user.id
        if user_id in data["participants"]:
            return await interaction.response.send_message("You already joined this giveaway!", ephemeral=True)

        data["participants"].add(user_id)
        self.participant_count.label = f"{len(data['participants'])} Participants"
        await interaction.response.edit_message(view=self)

@bot.tree.command(name="giveaway", description="Start a giveaway")
@app_commands.describe(prize="The prize", duration="Duration in minutes", winners="Number of winners")
async def giveaway(interaction: discord.Interaction, prize: str, duration: int, winners: int):
    await interaction.response.defer(ephemeral=True)

    end_time = datetime.now(timezone.utc) + timedelta(minutes=duration)
    giveaway_id = str(random.randint(100000, 999999))
    giveaways[giveaway_id] = {
        "participants": set(),
        "end_time": end_time,
        "winners": winners,
        "prize": prize,
        "host": interaction.user,
    }

    view = GiveawayView(giveaway_id)

    # Send title
    await interaction.channel.send("🎉 **Giveaway** 🎉")

    # Embed message
    embed = discord.Embed(
        description=(
            "<:kiyudot:1310311419878834267> **React** with 🎉 to __enter__!\n"
            f"<:kiyudot:1310311419878834267> **Ends** <t:{int(end_time.timestamp())}:R>\n\n"
            f"{interaction.user.mention} *1 Winner*"
        ),
        color=discord.Color.purple()
    )
    embed.set_thumbnail(url="https://cdn.discordapp.com/embed/avatars/0.png")  # Replace with your bot image

    msg = await interaction.channel.send(embed=embed, view=view)
    await msg.add_reaction("🎉")

    giveaways[giveaway_id]["message_id"] = msg.id
    giveaways[giveaway_id]["channel_id"] = msg.channel.id

    await interaction.followup.send("Giveaway started!", ephemeral=True)

    await asyncio.sleep(duration * 60)
    await end_giveaway(giveaway_id)

async def end_giveaway(giveaway_id):
    data = giveaways.get(giveaway_id)
    if not data:
        return

    channel = bot.get_channel(data["channel_id"])
    message = await channel.fetch_message(data["message_id"])

    participants = list(data["participants"])
    if not participants:
        await channel.send("No participants entered the giveaway.")
    else:
        winners = random.sample(participants, min(data["winners"], len(participants)))
        mentions = ", ".join(f"<@{uid}>" for uid in winners)
        await channel.send(f"🎉 Giveaway Ended! Congratulations {mentions}!\nPrize: **{data['prize']}**")

    giveaways.pop(giveaway_id, None)

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Sync error: {e}")
    print(f"Bot connected as {bot.user}")

bot.run(TOKEN)
