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
bot = commands.Bot(command_prefix="!vg ", intents=intents)

giveaways = {}

# Duration Parser
DURATION_MAP = {
    "s": 1, "sec": 1, "second": 1, "seconds": 1,
    "min": 60, "min": 60, "minute": 60, "minutes": 60,
    "h": 3600, "hour": 3600, "hours": 3600,
    "d": 86400, "day": 86400, "days": 86400,
    "w": 604800, "week": 604800, "weeks": 604800,
    "m": 2592000, "months": 2592000,
    "y": 31536000, "year": 31536000, "years": 31536000
}

def parse_duration(duration_str):
    pattern = r"(\d+)([a-zA-Z]+)"
    matches = re.findall(pattern, duration_str)
    if not matches:
        return None
    seconds = 0
    for value, unit in matches:
        unit = unit.lower()
        multiplier = DURATION_MAP.get(unit)
        if not multiplier:
            return None
        seconds += int(value) * multiplier
    return seconds

# Button classes
class JoinButton(Button):
    def __init__(self, message_id):
        super().__init__(label=":tada:Join", style=discord.ButtonStyle.secondary, custom_id=f"join_{message_id}")
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

        view = GiveawayView(self.message_id)
        await giveaway["message"].edit(view=view)

class ParticipantsButton(Button):
    def __init__(self, message_id, count):
        super().__init__(label=f"{count} Participants", style=discord.ButtonStyle.secondary, disabled=True)

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

# Slash command: /vampires giveaway
@bot.tree.command(name="giveaway", description="Start a giveaway")
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.describe(
    prize="Giveaway prize (e.g., $100 Nitro)",
    duration="Duration (e.g., 1d, 2h, 1month)",
    winners="Number of winners"
)
async def vampires_giveaway(interaction: discord.Interaction, prize: str, duration: str, winners: int):
    seconds = parse_duration(duration)
    if not seconds or winners < 1:
        await interaction.response.send_message("Invalid duration or winners count.", ephemeral=True)
        return

    end_time = datetime.utcnow() + timedelta(seconds=seconds)
    timestamp_unix = int(end_time.timestamp())
    emoji = "<:emoji_3:1397732039708643472>"

    embed = discord.Embed(
        title=f"{emoji} {prize}",
        description=f"Ends: <t:{timestamp_unix}:R> (<t:{timestamp_unix}:f>)\nWinners: **{winners}**",
        color=discord.Color.red()
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
        "host": interaction.user.id
    }

    view = GiveawayView(message_id)
    await msg.edit(view=view)
    await interaction.response.send_message("Giveaway started!", ephemeral=True)
    await asyncio.sleep(seconds)
    await end_giveaway(message_id)

# Prefix command: !vg start <prize> <duration> <winners>
@bot.command(name="start")
@commands.has_permissions(manage_guild=True)
async def start_prefix(ctx, prize: str, duration: str, winners: int):
    seconds = parse_duration(duration)
    if not seconds or winners < 1:
        await ctx.send("Invalid duration or winners count.")
        return

    end_time = datetime.utcnow() + timedelta(seconds=seconds)
    timestamp_unix = int(end_time.timestamp())
    emoji = "<:emoji_3:1397732039708643472>"

    embed = discord.Embed(
        title=f"{emoji} {prize}",
        description=f"Ends: <t:{timestamp_unix}:R> (<t:{timestamp_unix}:f>)\nWinners: **{winners}**",
        color=discord.Color.red()
    )
    embed.set_footer(text=f"Hosted by {ctx.author}", icon_url=ctx.author.display_avatar.url)

    view = GiveawayView("temp")
    msg = await ctx.send(embed=embed, view=view)
    message_id = str(msg.id)

    giveaways[message_id] = {
        "prize": prize,
        "end_time": end_time,
        "participants": set(),
        "message": msg,
        "ended": False,
        "winners": winners,
        "host": ctx.author.id
    }

    view = GiveawayView(message_id)
    await msg.edit(view=view)
    await asyncio.sleep(seconds)
    await end_giveaway(message_id)

# End giveaway logic
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

    if len(participants) < winners:
        result = "Not enough participants to select a winner."
    else:
        selected = random.sample(participants, winners)
        mentions = ", ".join(f"<@{uid}>" for uid in selected)
        result = f"🎉 Congratulations {mentions}! You won **{prize}**!"

    embed = msg.embeds[0]
    embed.color = discord.Color.green()
    embed.description += f"\n\n{result}"
    await msg.edit(embed=embed, view=None)
    await channel.send(result)

# Slash: end
@bot.tree.command(name="end", description="End giveaway early")
@app_commands.describe(message_id="Giveaway message ID")
async def end_command(interaction: discord.Interaction, message_id: str):
    giveaway = giveaways.get(message_id)
    if not giveaway:
        await interaction.response.send_message("Giveaway not found.", ephemeral=True)
        return
    if giveaway["ended"]:
        await interaction.response.send_message("Already ended.", ephemeral=True)
        return
    if interaction.user.id != giveaway["host"] and not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("You can't end this giveaway.", ephemeral=True)
        return
    await end_giveaway(message_id)
    await interaction.response.send_message(f"Giveaway {message_id} ended early.", ephemeral=True)

# Prefix: !vg end
@bot.command(name="end")
@commands.has_permissions(manage_guild=True)
async def end_prefix(ctx, message_id: str):
    giveaway = giveaways.get(message_id)
    if not giveaway:
        await ctx.send("Giveaway not found.")
        return
    if giveaway["ended"]:
        await ctx.send("Giveaway already ended.")
        return
    if ctx.author.id != giveaway["host"] and not ctx.author.guild_permissions.manage_guild:
        await ctx.send("You can't end this giveaway.")
        return
    await end_giveaway(message_id)
    await ctx.send(f"Giveaway {message_id} ended early.")

# Slash: reroll
@bot.tree.command(name="reroll", description="Reroll a giveaway")
@app_commands.describe(message_id="Giveaway message ID")
async def reroll_command(interaction: discord.Interaction, message_id: str):
    giveaway = giveaways.get(message_id)
    if not giveaway or not giveaway["ended"]:
        await interaction.response.send_message("Giveaway not found or not ended.", ephemeral=True)
        return

    participants = list(giveaway["participants"])
    winners = giveaway["winners"]

    if len(participants) < winners:
        await interaction.response.send_message("Not enough participants.", ephemeral=True)
        return

    new_winners = random.sample(participants, winners)
    mentions = ", ".join(f"<@{uid}>" for uid in new_winners)
    await interaction.response.send_message(f"🎉 Reroll results: {mentions} won **{giveaway['prize']}**!")

# Prefix: !vg reroll
@bot.command(name="reroll")
@commands.has_permissions(manage_guild=True)
async def reroll_prefix(ctx, message_id: str):
    giveaway = giveaways.get(message_id)
    if not giveaway or not giveaway["ended"]:
        await ctx.send("Giveaway not found or not ended.")
        return

    participants = list(giveaway["participants"])
    winners = giveaway["winners"]

    if len(participants) < winners:
        await ctx.send("Not enough participants to reroll.")
        return

    new_winners = random.sample(participants, winners)
    mentions = ", ".join(f"<@{uid}>" for uid in new_winners)
    await ctx.send(f"🎉 Reroll results: {mentions} won **{giveaway['prize']}**!")

# Bot ready
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user}!")

bot.run(TOKEN)
