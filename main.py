import discord from discord.ext import commands, tasks from discord import app_commands from discord.ui import View, Button import random import asyncio import os import re from datetime import datetime, timedelta, timezone from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default() intents.message_content = True intents.guilds = True intents.members = True intents.messages = True intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents) tree = bot.tree

active_giveaways = {}

class GiveawayButton(Button): def init(self, message_id): super().init(label="Giveaway", style=discord.ButtonStyle.danger, emoji="🎉") self.message_id = message_id

async def callback(self, interaction: discord.Interaction):
    if interaction.user.id in active_giveaways[self.message_id]['participants']:
        await interaction.response.send_message("You already joined!", ephemeral=True)
        return

    active_giveaways[self.message_id]['participants'].add(interaction.user.id)
    embed = interaction.message.embeds[0]
    embed.set_footer(text=f"{len(active_giveaways[self.message_id]['participants'])} Users joined the giveaway")
    await interaction.message.edit(embed=embed)
    await interaction.response.send_message("You've joined the giveaway!", ephemeral=True)

class GiveawayView(View): def init(self, message_id): super().init(timeout=None) self.add_item(GiveawayButton(message_id))

@tree.command(name="giveaway", description="Start a giveaway") @app_commands.describe(prize="Giveaway prize", duration="Duration like 1d2h3m", winners="Number of winners", image="Image URL", emoji="Button emoji") async def giveaway_command(interaction: discord.Interaction, prize: str, duration: str, winners: int, image: str = None, emoji: str = "🎉"): end_time = parse_duration(duration) if end_time is None: await interaction.response.send_message("Invalid duration format.", ephemeral=True) return

now = datetime.now(timezone.utc)
delta = end_time - now

embed = discord.Embed(title="🎉 Giveaway 🎉", description=f"**Prize:** {prize}\n**Hosted by:** {interaction.user.mention}", color=discord.Color.red())
embed.set_footer(text="0 Users joined the giveaway")
embed.timestamp = end_time
if image:
    embed.set_image(url=image)

view = GiveawayView(None)
view.clear_items()
button = GiveawayButton(None)
button.emoji = emoji
view.add_item(button)

message = await interaction.channel.send(embed=embed, view=view)
button.message_id = message.id
view = GiveawayView(message.id)
await message.edit(view=view)

active_giveaways[message.id] = {
    'end_time': end_time,
    'prize': prize,
    'winners': winners,
    'participants': set(),
    'channel_id': interaction.channel.id
}

await interaction.response.send_message(f"Giveaway started for **{prize}**!", ephemeral=True)
bot.loop.create_task(end_giveaway_after(message.id, delta))

async def end_giveaway_after(message_id, delay): await asyncio.sleep(delay.total_seconds()) await end_giveaway(message_id)

async def end_giveaway(message_id): data = active_giveaways.get(message_id) if not data: return

channel = bot.get_channel(data['channel_id'])
try:
    message = await channel.fetch_message(message_id)
except:
    return

participants = list(data['participants'])
if not participants:
    await channel.send("No one joined the giveaway.")
else:
    winners = random.sample(participants, min(len(participants), data['winners']))
    winner_mentions = ', '.join(f"<@{uid}>" for uid in winners)
    await channel.send(f"<:GiftifyTada:1098640605065777313> Congratulations, {winner_mentions}! You have won the giveaway of prize **{data['prize']}**.")

del active_giveaways[message_id]
await message.edit(view=None)

@tree.command(name="end", description="End a giveaway early") async def end_command(interaction: discord.Interaction, message_id: str): try: message_id = int(message_id) await end_giveaway(message_id) await interaction.response.send_message("Giveaway ended.", ephemeral=True) except: await interaction.response.send_message("Failed to end giveaway.", ephemeral=True)

@tree.command(name="cancel", description="Cancel a giveaway") async def cancel_command(interaction: discord.Interaction, message_id: str): try: message_id = int(message_id) data = active_giveaways.pop(message_id, None) if not data: await interaction.response.send_message("No such giveaway.", ephemeral=True) return

channel = bot.get_channel(data['channel_id'])
    message = await channel.fetch_message(message_id)
    await message.delete()
    await interaction.response.send_message("Giveaway cancelled and deleted.", ephemeral=True)
except:
    await interaction.response.send_message("Failed to cancel giveaway.", ephemeral=True)

@tree.command(name="reroll", description="Reroll winners") async def reroll_command(interaction: discord.Interaction, message_id: str, number_of_winners: int = 1): try: message_id = int(message_id) data = active_giveaways.get(message_id) if not data: await interaction.response.send_message("Giveaway not found or already ended.", ephemeral=True) return

participants = list(data['participants'])
    if len(participants) < number_of_winners:
        await interaction.response.send_message("Not enough participants.", ephemeral=True)
        return

    winners = random.sample(participants, number_of_winners)
    winner_mentions = ', '.join(f"<@{uid}>" for uid in winners)
    await interaction.response.send_message(f"Rerolled Winners: {winner_mentions}", ephemeral=False)
except:
    await interaction.response.send_message("Failed to reroll.", ephemeral=True)

def parse_duration(duration_str): now = datetime.now(timezone.utc) regex = r"(?:(\d+)\sy(?:ear)?s?|mo(?:nth)?s?|w(?:eek)?s?|d(?:ay)?s?|h(?:our)?s?|m(?:in(?:ute)?)?s?|s(?:ec(?:ond)?)?)" pattern = re.findall(r"(\d+)\s(y|mo|w|d|h|m|min|s)", duration_str.lower()) if not pattern: return None

total = timedelta()
for value, unit in pattern:
    value = int(value)
    if unit == "y": total += timedelta(days=365 * value)
    elif unit == "mo": total += timedelta(days=30 * value)
    elif unit == "w": total += timedelta(weeks=value)
    elif unit == "d": total += timedelta(days=value)
    elif unit == "h": total += timedelta(hours=value)
    elif unit in ("m", "min"): total += timedelta(minutes=value)
    elif unit == "s": total += timedelta(seconds=value)

return now + total

@bot.event async def on_ready(): await tree.sync() print(f"Logged in as {bot.user}")

bot.run(os.getenv("TOKEN"))

