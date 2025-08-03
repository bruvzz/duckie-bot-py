import discord
from discord import app_commands
from datetime import datetime, timezone
import aiohttp

EXPLOITS = [
    {"name": "Zenith", "url": "https://weao.xyz/api/status/exploits/zenith"},
    {"name": "Wave", "url": "https://weao.xyz/api/status/exploits/wave"},
    {"name": "AWP.GG", "url": "https://weao.xyz/api/status/exploits/awp.gg"},
    {"name": "Volcano", "url": "https://weao.xyz/api/status/exploits/volcano"},
    {"name": "Velocity", "url": "https://weao.xyz/api/status/exploits/velocity"},
    {"name": "Swift", "url": "https://weao.xyz/api/status/exploits/swift"},
    {"name": "Seliware", "url": "https://weao.xyz/api/status/exploits/seliware"},
    {"name": "Valex", "url": "https://weao.xyz/api/status/exploits/valex"},
    {"name": "Potassium", "url": "https://weao.xyz/api/status/exploits/potassium"},
    {"name": "Solara", "url": "https://weao.xyz/api/status/exploits/solara"},
    {"name": "Xeno", "url": "https://weao.xyz/api/status/exploits/xeno"},
    {"name": "Bunni.lol", "url": "https://weao.xyz/api/status/exploits/bunni.lol"},
    {"name": "Sirhurt", "url": "https://weao.xyz/api/status/exploits/sirhurt"},
]


async def fetch_exploit_status(session: aiohttp.ClientSession, url: str) -> dict | None:
    try:
        async with session.get(url, timeout=10) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            data["updateStatus"] = "[`🟩`]" if data.get("updateStatus") else "[`🟥`]"
            return data
    except Exception:
        return None


@discord.app_commands.command(name="weao", description="Get the list of Roblox Windows Exploits.")
async def weao(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        async with aiohttp.ClientSession() as session:
            # fetch main version objects
            roblox_resp = await session.get("https://weao.xyz/api/versions/current", timeout=10)
            roblox_obj = await roblox_resp.json() if roblox_resp.status == 200 else {}
            android_resp = await session.get("https://weao.xyz/api/versions/android", timeout=10)
            android_obj = await android_resp.json() if android_resp.status == 200 else {}

            # fetch each exploit status in parallel
            tasks = [
                fetch_exploit_status(session, exploit["url"])
                for exploit in EXPLOITS
            ]
            exploit_data_raw = await asyncio.gather(*tasks)
            exploit_data = []
            for idx, raw in enumerate(exploit_data_raw):
                name = EXPLOITS[idx]["name"]
                if raw:
                    exploit_data.append(
                        {
                            "name": name,
                            "version": raw.get("version", "unknown"),
                            "updatedDate": raw.get("updatedDate", "unknown"),
                            "updateStatus": raw.get("updateStatus", "[`🟥`]"),
                        }
                    )
                else:
                    exploit_data.append(
                        {
                            "name": name,
                            "version": "error",
                            "updatedDate": "error",
                            "updateStatus": "[`🟥`]",
                        }
                    )

            # build description lines
            exploit_descriptions = "\n".join(
                f"{e['updateStatus']} **{e['name']}** | [`{e['version']}`] | [`{e['updatedDate']}`]"
                for e in exploit_data
            )

            # Build embed
            windows_hash = roblox_obj.get("Windows", "unknown")
            windows_date = roblox_obj.get("WindowsDate", "unknown")
            mac_hash = roblox_obj.get("Mac", "unknown")
            mac_date = roblox_obj.get("MacDate", "unknown")
            android_version = android_obj.get("Android", "unknown")
            android_date = android_obj.get("AndroidDate", "unknown")

            description = (
                f"**Windows Hash**: __{windows_hash}__ | [`{windows_date}`]\n"
                f"**Mac Hash**: __{mac_hash}__ | [`{mac_date}`]\n"
                f"**Android Version**: __{android_version}__ | [`{android_date}`]\n\n"
                f"{exploit_descriptions}"
            )

            embed = discord.Embed(
                title="[Current Statuses]",
                description=description,
                color=discord.Colour.greyple(),
                timestamp=datetime.now(timezone.utc),
            )

            # Buttons: disabled version display + download link
            class WeaoView(discord.ui.View):
                def __init__(self, windows_hash: str):
                    super().__init__(timeout=None)
                    # disabled label-style button
                    self.add_item(
                        discord.ui.Button(
                            label=windows_hash,
                            style=discord.ButtonStyle.secondary,
                            custom_id="windows_version_display",
                            disabled=True,
                        )
                    )
                    download_url = (
                        f"https://rdd.weao.xyz/?channel=LIVE&binaryType=WindowsPlayer&version={windows_hash}"
                    )
                    self.add_item(
                        discord.ui.Button(
                            label="Download", url=download_url, style=discord.ButtonStyle.link
                        )
                    )

            view = WeaoView(windows_hash)

            await interaction.edit_original_response(embed=embed, view=view)
    except Exception as error:
        # log to console
        print("Error fetching data:", error)
        try:
            await interaction.edit_original_response(
                content="An error occurred while fetching the data."
            )
        except Exception:
            await interaction.response.send_message(
                "An error occurred while fetching the data.", ephemeral=True
            )


command = weao
