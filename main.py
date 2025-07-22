import discord from discord.ext import commands, tasks from discord import app_commands import asyncio import re from datetime import datetime, timedelta import random import os

intents = discord.Intents.default() intents.message_content = True tree = app_commands.CommandTree(commands.Bot(command_prefix="!", intents=intents)) bot = commands.Bot(command_prefix="!", intents=intents)

In-memory giveaway storage

giveaways = {}

Duration parser: 1d2h30m10s -> timedelta

def parse_duration(duration_str): time_units = { "s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800, "mo": 2592000, "y": 31536000 } pattern = r"(\d+)(s|m|h|d|w|mo|y)" matches = re.findall(pattern, duration_str) if not matches: return None total_seconds = sum(int(value) * time_units[unit] for value, unit in matches) return timedelta(seconds=total_seconds)

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

        # Update or add participants count
        new_desc = re.sub(r"\*\*Participants:\*\* \d+", f"**Participants:** {len(giveaway['participants'])}", embed.description or "")
        if "**Participants:**" not in new_desc:
            new_desc += f"\n**Participants:** {len(giveaway['participants'])}"

        updated_embed = embed.copy()
        updated_embed.description = new_desc

        await message.edit(embed=updated_embed, view=self)
    except Exception as e:
        print(f"Failed to update giveaway message: {e}")

async def end_giveaway(message_id, channel): giveaway = giveaways.get(message_id) if not giveaway or giveaway["ended"]: return

giveaway["ended"] = True
participants = list(giveaway["participants"])
winners = random.sample(participants, min(giveaway["winners"], len(participants))) if participants else []

try:
    message = await channel.fetch_message(message_id)
    embed = message.embeds[0]
    embed.color = discord.Color.dark_gray()
    embed.title = "🎉 Giveaway Ended!"
    embed.description = (
        f"**This giveaway has ended!**\n"
        f"Hosted By: <@{giveaway['host']}>\n"
        f"Winners: {', '.join(f'<@{w}>' for w in winners) if winners else 'None'}\n"
        f"Ended: <t:{int(datetime.utcnow().timestamp())}:R> (<t:{int(datetime.utcnow().timestamp())}:f>)\n"
        f"**Participants:** {len(participants)}"
    )
    await message.edit(embed=embed, view=None)

    # DM winners
    for winner_id in winners:
        try:
            user = await bot.fetch_user(winner_id)
            dm_embed = discord.Embed(
                title="🎊 Congratulations!",
                description=f"You won the giveaway for **{giveaway['prize']}**!",
                color=discord.Color.gold()
            )
            dm_embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/1029/1029183.png")
            dm_embed.add_field(name="Ended At", value=f"<t:{int(datetime.utcnow().timestamp())}:F>")
            dm_embed.set_footer(text="Enjoy your prize! 🥳")
            await user.send(content=f"Congratulations <@{winner_id}>! 🎉", embed=dm_embed)
        except:
            print(f"Failed to DM user {winner_id}")

except Exception as e:
    print(f"Failed to edit giveaway end: {e}")

@tree.command(name="giveaway") @app_commands.describe(duration="e.g. 1d2h30m", winners="Number of winners", prize="Giveaway prize") async def giveaway(interaction: discord.Interaction, duration: str, winners: int, prize: str): delta = parse_duration(duration) if not delta: await interaction.response.send_message("❌ Invalid duration format.", ephemeral=True) return

end_time = datetime.utcnow() + delta
timestamp = int(end_time.timestamp())

embed = discord.Embed(
    title=prize,
    description=(
        "Click the giveaway button to join the giveaway!\n"
        f"Hosted By: <@{interaction.user.id}>\n"
        f"Ends: <t:{timestamp}:R> (<t:{timestamp}:f>)"
    ),
    color=discord.Color.red()
)

view = GiveawayButton(None)
message = await interaction.channel.send(embed=embed, view=view)

view.message_id = message.id
giveaways[message.id] = {
    "host": interaction.user.id,
    "winners": winners,
    "prize": prize,
    "end_time": end_time,
    "participants": set(),
    "ended": False
}

await interaction.response.send_message(f"🎉 Giveaway started for **{prize}**!", ephemeral=True)

await asyncio.sleep(delta.total_seconds())
await end_giveaway(message.id, interaction.channel)

@tree.command(name="endgiveaway") @app_commands.describe(message_id="Giveaway message ID") async def endgiveaway(interaction: discord.Interaction, message_id: str): try: message_id = int(message_id) await end_giveaway(message_id, interaction.channel) await interaction.response.send_message("✅ Giveaway ended manually.", ephemeral=True) except: await interaction.response.send_message("❌ Failed to end giveaway.", ephemeral=True)

@tree.command(name="reroll") @app_commands.describe(message_id="Giveaway message ID") async def reroll(interaction: discord.Interaction, message_id: str): giveaway = giveaways.get(int(message_id)) if not giveaway or not giveaway["ended"]: await interaction.response.send_message("❌ Invalid or ongoing giveaway.", ephemeral=True) return

participants = list(giveaway["participants"])
winners = random.sample(participants, min(giveaway["winners"], len(participants))) if participants else []

await interaction.channel.send(f"🔁 Rerolled winners: {', '.join(f'<@{w}>' for w in winners) if winners else 'None'}")

@bot.event async def on_ready(): await tree.sync() print(f"✅ Logged in as {bot.user}")

bot.run(os.getenv("DISCORD_TOKEN"))

