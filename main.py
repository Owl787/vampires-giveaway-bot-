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

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
giveaways = {}

class JoinButton(Button):
    def __init__(self, msg_id):
        super().__init__(label="🎉 Giveaway", style=discord.ButtonStyle.red)
        self.msg_id = msg_id

    async def callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        if user_id not in giveaways[self.msg_id]['participants']:
            giveaways[self.msg_id]['participants'].append(user_id)
        else:
            giveaways[self.msg_id]['participants'].remove(user_id)

        await interaction.response.defer()
        await update_participants(self.msg_id)

async def update_participants(msg_id):
    data = giveaways[msg_id]
    channel = bot.get_channel(data['channel_id'])
    try:
        message = await channel.fetch_message(msg_id)
    except discord.NotFound:
        return

    embed = message.embeds[0]
    embed.description = (
        "**🎉 GIVEAWAY**\n\n"
        "Click the 🎉 button to join the giveaway!\n\n"
        f"**Prize:** {data['prize']}\n"
        f"**Hosted by:** <@{data['host_id']}>\n"
        f"**Ends:** <t:{data['end_time']}:R> (<t:{data['end_time']}:f>)\n"
        f"👥 **{len(data['participants'])} Participants**\n"
        f"🏆 **{data['winner_count']} Winner(s)**"
    )

    view = View()
    button = JoinButton(msg_id)
    view.add_item(button)

    await message.edit(content=f"👥 **{len(data['participants'])} Participants**", embed=embed, view=view)

async def end_giveaway_by_id(msg_id):
    data = giveaways.get(msg_id)
    if not data or data['ended']:
        return

    data['ended'] = True
    channel = bot.get_channel(data['channel_id'])
    try:
        message = await channel.fetch_message(msg_id)
    except discord.NotFound:
        return

    participants = data['participants']
    if len(participants) < data['winner_count']:
        winners = participants
    else:
        winners = random.sample(participants, data['winner_count'])

    mentions = ", ".join(f"<@{uid}>" for uid in winners)
    embed = message.embeds[0]
    embed.color = discord.Color.green()
    embed.description += f"\n\n🎉 Congratulations, {mentions}! You have won the giveaway of prize **{data['prize']}**."

    for child in message.components[0].children:
        child.disabled = True

    await message.edit(embed=embed, view=message.components[0], content=f"👥 **{len(participants)} Participants**")
    giveaways[msg_id]['winners'] = winners

@bot.tree.command(name="giveaway", description="Start a giveaway")
@app_commands.describe(
    duration="Duration (e.g. 1d2h30m10s)",
    winners="Number of winners",
    prize="The prize for the giveaway"
)
async def giveaway(interaction: discord.Interaction, duration: str, winners: int, prize: str):
    await interaction.response.defer()

    time_units = {
        "d": 86400, "day": 86400,
        "h": 3600, "hour": 3600,
        "m": 60, "minute": 60,
        "s": 1, "second": 1,
        "w": 604800, "week": 604800,
        "mo": 2592000, "month": 2592000,
        "y": 31536000, "year": 31536000
    }

    seconds = 0
    for value, unit in re.findall(r"(\d+)\s*(mo|[a-zA-Z]+)", duration):
        if unit.lower() not in time_units:
            await interaction.followup.send(f"Invalid duration unit: {unit}")
            return
        seconds += int(value) * time_units[unit.lower()]

    end_time = int((datetime.now(timezone.utc) + timedelta(seconds=seconds)).timestamp())

    embed = discord.Embed(
        description=(
            "**🎉 GIVEAWAY**\n\n"
            "Click the 🎉 button to join the giveaway!\n\n"
            f"**Prize:** {prize}\n"
            f"**Hosted by:** {interaction.user.mention}\n"
            f"**Ends:** <t:{end_time}:R> (<t:{end_time}:f>)\n"
            f"👥 **0 Participants**\n"
            f"🏆 **{winners} Winner(s)**"
        ),
        color=discord.Color.red()
    )

    view = View()
    button = JoinButton(None)
    view.add_item(button)

    msg = await interaction.followup.send(embed=embed, view=view, content="👥 **0 Participants**")
    button.msg_id = msg.id

    giveaways[msg.id] = {
        "channel_id": msg.channel.id,
        "host_id": interaction.user.id,
        "participants": [],
        "winner_count": winners,
        "prize": prize,
        "end_time": end_time,
        "ended": False,
        "winners": []
    }

    giveaway_checker.start(msg.id)

@bot.tree.command(name="end", description="End a giveaway manually by message ID")
async def end(interaction: discord.Interaction, message_id: str):
    msg_id = int(message_id)
    if msg_id not in giveaways:
        await interaction.response.send_message("Giveaway not found.")
        return

    await end_giveaway_by_id(msg_id)
    await interaction.response.send_message("Giveaway ended manually.")

@bot.tree.command(name="reroll", description="Reroll a giveaway by message ID")
async def reroll(interaction: discord.Interaction, message_id: str):
    msg_id = int(message_id)
    data = giveaways.get(msg_id)

    if not data or not data['ended']:
        await interaction.response.send_message("Giveaway not found or hasn't ended yet.")
        return

    remaining = list(set(data['participants']) - set(data['winners']))
    if len(remaining) < data['winner_count']:
        new_winners = remaining
    else:
        new_winners = random.sample(remaining, data['winner_count'])

    mentions = ", ".join(f"<@{uid}>" for uid in new_winners)
    channel = bot.get_channel(data['channel_id'])
    message = await channel.fetch_message(msg_id)

    embed = message.embeds[0]
    embed.description += f"\n\n🔁 Rerolled Winners: {mentions}"
    await message.edit(embed=embed)

    giveaways[msg_id]['winners'] = new_winners
    await interaction.response.send_message(f"Rerolled winners: {mentions}")

@tasks.loop(seconds=10)
async def giveaway_checker(msg_id):
    if msg_id not in giveaways:
        giveaway_checker.stop()
        return

    data = giveaways[msg_id]
    if int(datetime.now(timezone.utc).timestamp()) >= data['end_time']:
        await end_giveaway_by_id(msg_id)
        giveaway_checker.stop()

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")
    for msg_id, data in giveaways.items():
        if not data['ended']:
            giveaway_checker.start(msg_id)

bot.run(os.getenv("TOKEN"))
