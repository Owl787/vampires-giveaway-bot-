import discord from discord.ext import commands, tasks from discord import app_commands import asyncio import random import re from datetime import datetime, timedelta, timezone

intents = discord.Intents.default() intents.message_content = True intents.guilds = True intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents) giveaways = {}

Duration parser: 1d2h30m10s -> timedelta

TIME_REGEX = re.compile(r"(\d+)([smhdwmy])")

UNIT_MAP = { 's': 'seconds', 'm': 'minutes', 'h': 'hours', 'd': 'days', 'w': ('days', 7), 'y': ('days', 365) }

def parse_duration(duration_str): total = timedelta() for amount, unit in TIME_REGEX.findall(duration_str.lower()): if unit in ('w', 'y'): unit_name, multiplier = UNIT_MAP[unit] kwargs = {unit_name: int(amount) * multiplier} else: kwargs = {UNIT_MAP[unit]: int(amount)} total += timedelta(**kwargs) return total

class GiveawayButton(discord.ui.View): def init(self, message_id): super().init(timeout=None) self.message_id = message_id

@discord.ui.button(label="🎉 Join Giveaway", style=discord.ButtonStyle.danger)
async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
    user_id = interaction.user.id

    giveaway = giveaways.get(self.message_id)
    if not giveaway or giveaway["ended"]:
        await interaction.response.send_message("❌ This giveaway has ended.", ephemeral=True)
        return

    if user_id in giveaway["participants"]:
        giveaway["participants"].remove(user_id)
        await interaction.response.send_message("🚪 You left the giveaway.", ephemeral=True)
    else:
        giveaway["participants"].add(user_id)
        await interaction.response.send_message("🎉 You entered the giveaway!", ephemeral=True)

    # Update the embed with new participant count
    try:
        message = await interaction.channel.fetch_message(self.message_id)
        embed = message.embeds[0]

        new_desc = re.sub(
            r"\*\*Participants:\*\* \d+",
            f"**Participants:** {len(giveaway['participants'])}",
            embed.description
        )
        if "**Participants:**" not in new_desc:
            new_desc += f"\n**Participants:** {len(giveaway['participants'])}"

        updated_embed = embed.copy()
        updated_embed.description = new_desc

        await message.edit(embed=updated_embed, view=self)
    except Exception as e:
        print(f"Failed to update giveaway message: {e}")

@bot.event async def on_ready(): print(f"Logged in as {bot.user}") try: synced = await bot.tree.sync() print(f"Synced {len(synced)} command(s)") except Exception as e: print(f"Sync error: {e}")

@bot.tree.command(name="giveaway", description="Start a giveaway") @app_commands.describe(duration="e.g. 1d2h30m", prize="The prize to give away", winners="Number of winners") async def giveaway(interaction: discord.Interaction, duration: str, prize: str, winners: int): delta = parse_duration(duration) end_time = datetime.now(timezone.utc) + delta timestamp = int(end_time.timestamp())

embed = discord.Embed(
    title=f"🎁 {prize}",
    description=(
        "Click the giveaway button to join the giveaway!\n"
        f"**Hosted By:** {interaction.user.mention}\n"
        f"**Ends:** <t:{timestamp}:R> (<t:{timestamp}:f>)\n"
        f"**Participants:** 0"
    ),
    color=discord.Color.red()
)
view = GiveawayButton(None)
msg = await interaction.channel.send(embed=embed, view=view)
view.message_id = msg.id

giveaways[msg.id] = {
    "participants": set(),
    "end_time": end_time,
    "prize": prize,
    "host": interaction.user,
    "winners": winners,
    "ended": False
}
await interaction.response.send_message("✅ Giveaway started!", ephemeral=True)

await asyncio.sleep(delta.total_seconds())
await end_giveaway_by_id(msg.id, interaction.channel)

@bot.tree.command(name="reroll", description="Reroll a giveaway by message ID") @app_commands.describe(message_id="The giveaway message ID to reroll") async def reroll(interaction: discord.Interaction, message_id: str): try: msg_id = int(message_id) giveaway = giveaways.get(msg_id) if not giveaway: await interaction.response.send_message("❌ Giveaway not found.", ephemeral=True) return

if not giveaway["ended"]:
        await interaction.response.send_message("❌ Giveaway is still running.", ephemeral=True)
        return

    await end_giveaway_by_id(msg_id, interaction.channel, force_reroll=True)
    await interaction.response.send_message("🔁 Giveaway rerolled!", ephemeral=True)
except Exception as e:
    await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="endgiveaway", description="End a giveaway manually by message ID") @app_commands.describe(message_id="The giveaway message ID to end") async def endgiveaway(interaction: discord.Interaction, message_id: str): try: msg_id = int(message_id) if msg_id not in giveaways: await interaction.response.send_message("❌ Giveaway not found.", ephemeral=True) return

await end_giveaway_by_id(msg_id, interaction.channel, ended_by=interaction.user)
    await interaction.response.send_message("✅ Giveaway ended manually.", ephemeral=True)
except Exception as e:
    await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

async def end_giveaway_by_id(message_id: int, channel, ended_by=None, force_reroll=False): giveaway = giveaways.get(message_id) if not giveaway: return

if not force_reroll and giveaway["ended"]:
    return

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
        description=(
            f"**Hosted By:** {host.mention}\n"
            f"❌ No one joined the giveaway.\n"
            f"**Ended:** <t:{end_time}:R> (<t:{end_time}:f>)"
        ),
        color=discord.Color.dark_gray()
    )
    await channel.send(embed=embed)
    return

if participant_count < winner_count:
    winner_count = participant_count

winners = random.sample(participants, winner_count)
winner_mentions = ", ".join(f"<@{uid}>" for uid in winners)

embed = discord.Embed(
    title="🎁 This giveaway has ended!",
    description=(
        f"**Hosted By:** {host.mention}\n"
        f"**Winners:** {winner_mentions}\n"
        f"**Participants:** {participant_count}\n"
        f"**Ended:** <t:{end_time}:R> (<t:{end_time}:f>)"
    ),
    color=discord.Color.dark_gray()
)
await channel.send(embed=embed)

for winner_id in winners:
    user = await bot.fetch_user(winner_id)
    if user:
        try:
            dm = discord.Embed(
                title="🎉 Congratulations!",
                description=(
                    f"Hey {user.mention}, you won the giveaway!\n\n"
                    f"**Prize:** {prize}\n"
                    f"**Participants:** {participant_count}\n"
                    f"**Time:** <t:{end_time}:F>"
                ),
                color=discord.Color.green()
            )
            dm.set_image(url="https://cdn.discordapp.com/attachments/your_image_here.png")  # Optional image
            await user.send(embed=dm)
        except:
            pass

bot.run("YOUR_BOT_TOKEN")

