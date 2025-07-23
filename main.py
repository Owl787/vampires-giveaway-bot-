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
import discord from discord.ext import commands from discord import app_commands from discord.ui import View, Button import random import asyncio import os import re from datetime import datetime, timedelta, timezone from dotenv import load_dotenv

load_dotenv() TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default() intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents) giveaways = {}  # Stores giveaway data by message_id

def parse_duration(duration_str): units = { "s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800, "mo": 2592000, "y": 31536000 } pattern = r"(\d+)(s|m|h|d|w|mo|y)" matches = re.findall(pattern, duration_str) if not matches: return None

total_seconds = sum(int(value) * units[unit] for value, unit in matches)
return total_seconds

class GiveawayButton(Button): def init(self, message_id: int): super().init( label="🎉 Join the Giveaway!", style=discord.ButtonStyle.danger, custom_id=f"giveaway_{message_id}" ) self.message_id = message_id

async def callback(self, interaction: discord.Interaction):
    user = interaction.user
    giveaway = giveaways.get(self.message_id)

    if not giveaway or giveaway["ended"]:
        await interaction.response.send_message("❌ This giveaway has ended or doesn't exist.", ephemeral=True)
        return

    if user.id in giveaway["participants"]:
        giveaway["participants"].remove(user.id)
        await interaction.response.send_message("❌ You left the giveaway.", ephemeral=True)
    else:
        giveaway["participants"].add(user.id)
        await interaction.response.send_message("✅ You joined the giveaway!", ephemeral=True)

class GiveawayView(View): def init(self, message_id: int): super().init(timeout=None) self.add_item(GiveawayButton(message_id))

@bot.event async def on_ready(): print(f"✅ Logged in as {bot.user}") try: synced = await bot.tree.sync() print(f"✅ Synced {len(synced)} slash command(s).") except Exception as e: print(f"❌ Failed to sync commands: {e}")

@bot.tree.command(name="giveaway", description="Start a giveaway") @app_commands.describe( duration="e.g. 1d2h30m10s", winners="Number of winners", prize="Prize name" ) async def giveaway(interaction: discord.Interaction, duration: str, winners: int, prize: str): seconds = parse_duration(duration.lower()) if seconds is None: await interaction.response.send_message( "❌ Invalid duration format. Use like 1d2h30m10s or 5m.", ephemeral=True ) return

end_time = int((datetime.now(timezone.utc) + timedelta(seconds=seconds)).timestamp())
host = interaction.user.mention

embed = discord.Embed(
    title=f"🎁 {prize}",
    description=(
        f"Click the giveaway button to join the giveaway!\n\n"
        f"**Hosted By:** {host}\n"
        f"**Ends:** <t:{end_time}:R> (<t:{end_time}:f>)"
    ),
    color=discord.Color.red()
)

msg = await interaction.channel.send(embed=embed, view=GiveawayView(0))
giveaways[msg.id] = {
    "participants": set(),
    "winners": winners,
    "prize": prize,
    "host": interaction.user,
    "end_time": end_time,
    "ended": False
}

await msg.edit(view=GiveawayView(msg.id))
await interaction.response.send_message("✅ Giveaway started!", ephemeral=True)

await asyncio.sleep(seconds)
await end_giveaway_by_id(msg.id, interaction.channel)

async def end_giveaway_by_id(message_id: int, channel): giveaway = giveaways.get(message_id) if not giveaway or giveaway["ended"]: return

giveaway["ended"] = True
participants = list(giveaway["participants"])
prize = giveaway["prize"]
host = giveaway["host"]
end_time = int(datetime.now(timezone.utc).timestamp())
winner_count = giveaway["winners"]
participant_count = len(participants)

if participant_count == 0:
    embed = discord.Embed(
        title="🎁 This giveaway has ended!",
        description=f"**Hosted By:** {host.mention}\n❌ No one joined the giveaway.\n**Ended:** <t:{end_time}:R> (<t:{end_time}:f>)",
        color=discord.Color.dark_gray()
    )
    await channel.send(embed=embed)
    return

if winner_count > participant_count:
    winner_count = participant_count

winners = random.sample(participants, winner_count)
winner_mentions = ", ".join(f"<@{uid}>" for uid in winners)

embed = discord.Embed(
    title="🎁 This giveaway has ended!",
    description=(
        f"**Hosted By:** {host.mention}\n"
        f"**Prize:** {prize}\n"
        f"**Participants:** {participant_count}\n"
        f"**Winners:** {winner_mentions}"
    ),
    color=discord.Color.dark_gray()
)
await channel.send(embed=embed)

for winner_id in winners:
    try:
        user = await bot.fetch_user(winner_id)
        if user:
            dm = discord.Embed(
                title="🎉 Congratulations!",
                description=(
                    f"Hey {user.mention}, you won the giveaway!\n\n"
                    f"**Prize:** {prize}\n"
                    f"**Time:** <t:{end_time}:F>"
                ),
                color=discord.Color.green()
            )
            await user.send(embed=dm)
    except:
        pass

(rest of the code remains unchanged)

if name == "main": bot.run(TOKEN)

