import discord from discord.ext import commands from discord import app_commands from discord.ui import View, Button import random import asyncio import os import re from datetime import datetime, timedelta, timezone from dotenv import load_dotenv

load_dotenv() TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default() intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents) giveaways = {}  # Stores giveaway data by message_id

def parse_duration(duration_str): units = { "s": 1, "sec": 1, "second": 1, "seconds": 1, "m": 60, "min": 60, "minute": 60, "minutes": 60, "h": 3600, "hour": 3600, "hours": 3600, "d": 86400, "day": 86400, "days": 86400, "w": 604800, "week": 604800, "weeks": 604800, "mo": 2592000, "month": 2592000, "months": 2592000, "y": 31536000, "year": 31536000, "years": 31536000 } pattern = r"(\d+)([a-zA-Z]+)" matches = re.findall(pattern, duration_str) if not matches: return None total_seconds = 0 for value, unit in matches: unit = unit.lower() if unit in units: total_seconds += int(value) * units[unit] else: return None return total_seconds

class GiveawayButton(Button): def init(self, message_id: int): super().init( label="Giveaway", style=discord.ButtonStyle.danger, custom_id=f"giveaway_{message_id}" ) self.message_id = message_id

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

    await update_embed(interaction.channel, self.message_id)

class GiveawayView(View): def init(self, message_id: int): super().init(timeout=None) self.add_item(GiveawayButton(message_id))

@bot.event async def on_ready(): print(f"Logged in as {bot.user}") try: synced = await bot.tree.sync() print(f"Synced {len(synced)} slash command(s).") except Exception as e: print(f"Failed to sync commands: {e}")

async def update_embed(channel, message_id): giveaway = giveaways.get(message_id) if not giveaway: return try: msg = await channel.fetch_message(message_id) end_time = giveaway["end_time"] winners = giveaway["winners"] prize = giveaway["prize"] host = giveaway["host"] image_url = giveaway["image"] participants = len(giveaway["participants"])

embed = discord.Embed(
        title=prize,
        description=(
            f"Click the button below to join!

\n" f"Hosted By: {host.mention}\n" f"Ends: <t:{end_time}:R>\n" f"{winners} winner(s) • {participants} participants" ), color=discord.Color.red() ) if image_url: embed.set_image(url=image_url) await msg.edit(embed=embed, view=GiveawayView(message_id)) except: pass

@bot.tree.command(name="giveaway", description="Start a giveaway") @app_commands.describe( duration="e.g. 1d2h or 3m10s", winners="Number of winners", prize="Prize name", image="Image URL to use" ) async def giveaway(interaction: discord.Interaction, duration: str, winners: int, prize: str, image: str = None): seconds = parse_duration(duration) if seconds is None: await interaction.response.send_message("Invalid duration format.", ephemeral=True) return

end_time = int((datetime.now(timezone.utc) + timedelta(seconds=seconds)).timestamp())
host = interaction.user

embed = discord.Embed(
    title=prize,
    description=(
        f"Click the button below to join!

\n" f"Hosted By: {host.mention}\n" f"Ends: <t:{end_time}:R>\n" f"{winners} winner(s) • 0 participants" ), color=discord.Color.red() ) if image: embed.set_image(url=image)

msg = await interaction.channel.send(embed=embed, view=GiveawayView(0))
giveaways[msg.id] = {
    "participants": set(),
    "winners": winners,
    "prize": prize,
    "host": host,
    "end_time": end_time,
    "ended": False,
    "image": image
}
await msg.edit(view=GiveawayView(msg.id))
await interaction.response.send_message("Giveaway started!", ephemeral=True)
await asyncio.sleep(seconds)
await end_giveaway_by_id(msg.id, interaction.channel)

async def end_giveaway_by_id(message_id: int, channel): giveaway = giveaways.get(message_id) if not giveaway or giveaway["ended"]: return giveaway["ended"] = True

participants = list(giveaway["participants"])
if not participants:
    await channel.send("No one joined the giveaway.")
    return

winner_count = min(giveaway["winners"], len(participants))
winners = random.sample(participants, winner_count)
prize = giveaway["prize"]

for winner_id in winners:
    await channel.send(f"<:GiftifyTada:1098640605065777313> Congratulations, <@{winner_id}>! You have won the giveaway of prize **{prize}**.")

@bot.tree.command(name="reroll", description="Reroll a giveaway") @app_commands.describe(message_id="Giveaway message ID to reroll") async def reroll(interaction: discord.Interaction, message_id: str): try: msg_id = int(message_id) giveaway = giveaways.get(msg_id) if not giveaway or not giveaway["ended"]: await interaction.response.send_message("Giveaway not found or not ended.", ephemeral=True) return

participants = list(giveaway["participants"])
    if not participants:
        await interaction.response.send_message("No participants to reroll.", ephemeral=True)
        return

    winner_count = min(giveaway["winners"], len(participants))
    new_winners = random.sample(participants, winner_count)
    prize = giveaway["prize"]

    for winner_id in new_winners:
        await interaction.channel.send(f"<:GiftifyTada:1098640605065777313> Congratulations, <@{winner_id}>! You have won the giveaway of prize **{prize}**.")

    await interaction.response.send_message("Reroll complete.", ephemeral=True)
except Exception as e:
    await interaction.response.send_message(f"Error: {e}", ephemeral=True)

if name == "main": bot.run(TOKEN)

