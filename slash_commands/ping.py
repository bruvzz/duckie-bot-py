import discord
from discord import app_commands
from datetime import datetime, timezone

@discord.app_commands.command(name="ping", description="Check bot latency")
async def ping(interaction: discord.Interaction):
    start = datetime.now(timezone.utc)
    await interaction.response.defer(ephemeral=True)
    end = datetime.now(timezone.utc)
    bot_latency_ms = int((end - start).total_seconds() * 1000)
    api_latency_ms = int(interaction.client.latency * 1000)

    embed = discord.Embed(
        title="Success",
        description="Here's my current latency statistics:",
        color=discord.Colour.greyple(),
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="Bot Latency", value=f"`{bot_latency_ms}ms`", inline=True)
    embed.add_field(name="API Latency", value=f"`{api_latency_ms}ms`", inline=True)
    embed.set_footer(
        text=f"Requested by {interaction.user}",
        icon_url=interaction.user.display_avatar.url,
    )
    await interaction.edit_original_response(embed=embed)

command = ping
