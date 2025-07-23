import discord from discord.ext import commands from discord import app_commands from discord.ui import View, Button import random import asyncio import os import re from datetime import datetime, timedelta, timezone from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default() intents.message_content = True intents.guilds = True intents.members = True intents.messages = True intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)

giveaways = {}

def parse_duration(duration): pattern = r"(?:(\d+)\sy(?:ear)?s?)?\s(?:(\d+)\smo(?:nth)?s?)?\s(?:(\d+)\sw(?:eek)?s?)?\s(?:(\d+)\sd(?:ay)?s?)?\s(?:(\d+)\sh(?:our)?s?)?\s(?:(\d+)\s*m(?:inute|in)?s?)?" match = re.match(pattern, duration.lower()) if not match: return None

years, months, weeks, days, hours, minutes = map(lambda x: int(x) if x else 0, match.groups())
return timedelta(days=days + weeks * 7 + months * 30 + years * 365, hours=hours, minutes=minutes)

class GiveawayButton(Button): def init(self, giveaway_id, emoji): super().init(label="Giveaway", style=discord.ButtonStyle.danger, emoji=emoji) self.giveaway_id = giveaway_id

async def callback(self, interaction: discord.Interaction):
    giveaway = giveaways.get(self.giveaway_id)
    if not giveaway:
        return await interaction.response.send_message("Giveaway not found.", ephemeral=True)

    if interaction.user.id in giveaway['participants']:
        giveaway['participants'].remove(interaction.user.id)
    else:
        giveaway['participants'].append(interaction.user.id)

    await interaction.response.send_message("You are now entered in the giveaway!", ephemeral=True)

    embed = giveaway['embed']
    embed.set_footer(text=f"Participants: {len(giveaway['participants'])}")
    await giveaway['message'].edit(embed=embed)

@bot.tree.command(name="giveaway") @app_commands.describe(duration="Duration like '1d2h', '2 weeks'", prize="Prize name", image="Image URL", emoji="Custom emoji") async def giveaway_command(interaction: discord.Interaction, duration: str, prize: str, image: str = None, emoji: str = "🎉"): delta = parse_duration(duration) if not delta: await interaction.response.send_message("Invalid duration.", ephemeral=True) return

end_time = datetime.now(timezone.utc) + delta

embed = discord.Embed(title="🎁 Giveaway!", description=f"**Prize:** {prize}\nEnds <t:{int(end_time.timestamp())}:R>", color=0xFF0000)
if image:
    embed.set_image(url=image)
embed.set_footer(text=f"Participants: 0")

view = View()
giveaway_id = str(interaction.id)
button = GiveawayButton(giveaway_id, emoji)
view.add_item(button)

message = await interaction.channel.send(embed=embed, view=view)
await interaction.response.send_message("Giveaway started!", ephemeral=True)

giveaways[giveaway_id] = {
    'end_time': end_time,
    'participants': [],
    'message': message,
    'embed': embed,
    'prize': prize,
    'channel': interaction.channel,
    'author': interaction.user.id,
    'button': button
}

await asyncio.sleep(delta.total_seconds())
await end_giveaway(giveaway_id)

async def end_giveaway(giveaway_id): giveaway = giveaways.get(giveaway_id) if not giveaway: return

participants = giveaway['participants']
prize = giveaway['prize']

if not participants:
    await giveaway['channel'].send("No valid entries. Giveaway cancelled.")
else:
    winner = random.choice(participants)
    await giveaway['channel'].send(f"<:GiftifyTada:1098640605065777313> Congratulations, <@{winner}>! You have won the giveaway of prize **{prize}**.")

try:
    await giveaway['message'].delete()
except:
    pass

giveaways.pop(giveaway_id, None)

@bot.tree.command(name="reroll") @app_commands.describe(message_id="Giveaway message ID", winners="Number of winners") async def reroll(interaction: discord.Interaction, message_id: str, winners: int = 1): giveaway = next((g for g in giveaways.values() if g['message'].id == int(message_id)), None) if not giveaway: await interaction.response.send_message("Giveaway not found.", ephemeral=True) return

participants = giveaway['participants'][:]
if len(participants) < winners:
    await interaction.response.send_message("Not enough participants to reroll.", ephemeral=True)
    return

new_winners = random.sample(participants, winners)
winners_mentions = ", ".join(f"<@{user}>" for user in new_winners)
await giveaway['channel'].send(f"New winner(s): {winners_mentions}!")
await interaction.response.send_message("Rerolled successfully.", ephemeral=True)

@bot.tree.command(name="end") @app_commands.describe(message_id="Giveaway message ID") async def end(interaction: discord.Interaction, message_id: str): giveaway = next((k for k, v in giveaways.items() if v['message'].id == int(message_id)), None) if not giveaway: await interaction.response.send_message("Giveaway not found.", ephemeral=True) return await end_giveaway(giveaway) await interaction.response.send_message("Giveaway ended.", ephemeral=True)

@bot.tree.command(name="cancel") @app_commands.describe(message_id="Giveaway message ID") async def cancel(interaction: discord.Interaction, message_id: str): for k, v in giveaways.items(): if v['message'].id == int(message_id): if interaction.user.id != v['author']: await interaction.response.send_message("Only the giveaway creator can cancel.", ephemeral=True) return await v['message'].delete() giveaways.pop(k) await interaction.response.send_message("Giveaway cancelled.", ephemeral=True) return await interaction.response.send_message("Giveaway not found.", ephemeral=True)

@bot.event async def on_ready(): print(f"Logged in as {bot.user}") try: synced = await bot.tree.sync() print(f"Synced {len(synced)} command(s)") except Exception as e: print(e)

bot.run(os.getenv("DISCORD_TOKEN"))

