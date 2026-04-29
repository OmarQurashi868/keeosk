import discord
from discord import app_commands
from discord.ext import commands
import json
import os

TOKEN = os.getenv("TOKEN")
DATA_FILE = os.getenv("DATA_FILE", "/data/data.json")

intents = discord.Intents.default()
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix=None, intents=intents)
tree = bot.tree


# ------------------ DATA ------------------

def load_data():
    # ensure directory exists
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)

    # auto-create file if missing
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump({}, f)
        return {}

    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_data(data):
    # ensure directory exists
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)

    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


def get_roles_between(guild, top_id, bottom_id):
    top = guild.get_role(top_id)
    bottom = guild.get_role(bottom_id)

    if not top or not bottom:
        return []

    high = max(top.position, bottom.position)
    low = min(top.position, bottom.position)

    roles = [
        r for r in guild.roles
        if low <= r.position <= high and not r.managed
    ]

    return roles


# ------------------ UI ------------------

class RoleButton(discord.ui.Button):
    def __init__(self, role_id):
        super().__init__(label="...", style=discord.ButtonStyle.secondary)
        self.role_id = role_id

    async def callback(self, interaction: discord.Interaction):
        role = interaction.guild.get_role(self.role_id)
        member = interaction.user

        if not role:
            return await interaction.response.send_message("Role missing.", ephemeral=True)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"Removed {role.name}", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"Added {role.name}", ephemeral=True)


class RoleView(discord.ui.View):
    def __init__(self, role_ids, guild):
        super().__init__(timeout=None)

        for rid in role_ids[:25]:
            role = guild.get_role(rid)
            if role:
                btn = RoleButton(rid)
                btn.label = role.name
                self.add_item(btn)


class RoleDropdown(discord.ui.Select):
    def __init__(self, role_ids, guild):
        self.role_ids = role_ids

        options = []
        for rid in role_ids[:25]:
            role = guild.get_role(rid)
            if role:
                options.append(discord.SelectOption(label=role.name, value=str(rid)))

        super().__init__(placeholder="Select a role...", options=options)

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user

        selected = guild.get_role(int(self.values[0]))

        # remove ONLY roles from this category
        for rid in self.role_ids:
            role = guild.get_role(rid)
            if role and role in member.roles:
                await member.remove_roles(role)

        if selected:
            await member.add_roles(selected)

        await interaction.response.send_message(
            f"Selected {selected.name}", ephemeral=True
        )


class DropdownView(discord.ui.View):
    def __init__(self, role_ids, guild):
        super().__init__(timeout=None)
        self.add_item(RoleDropdown(role_ids, guild))


# ------------------ CORE ------------------

async def build_category(guild, name, cfg):
    roles = get_roles_between(guild, cfg["top"], cfg["bottom"])
    role_ids = [r.id for r in roles]

    cfg["roles"] = role_ids  # store for tracking

    embed = discord.Embed(
        title=name,
        description="Select your roles below",
        color=discord.Color.blurple()
    )

    if cfg["mode"] == "dropdown":
        view = DropdownView(role_ids, guild)
    else:
        view = RoleView(role_ids, guild)

    return embed, view


async def update_all_categories(guild):
    data = load_data()
    changed = False

    for name, cfg in data.items():
        channel = guild.get_channel(cfg["channel"])
        if not channel:
            continue

        try:
            msg = await channel.fetch_message(cfg["message"])
        except:
            continue

        embed, view = await build_category(guild, name, cfg)
        await msg.edit(embed=embed, view=view)
        changed = True

    if changed:
        save_data(data)


# ------------------ COMMANDS ------------------

@tree.command(name="add_category")
async def add_category(interaction: discord.Interaction,
                       name: str,
                       top_role: discord.Role,
                       bottom_role: discord.Role,
                       channel: discord.TextChannel,
                       mode: str):

    if not interaction.user.guild_permissions.manage_roles:
        return await interaction.response.send_message("Need Manage Roles permission.", ephemeral=True)

    data = load_data()

    cfg = {
        "top": top_role.id,
        "bottom": bottom_role.id,
        "channel": channel.id,
        "message": None,
        "mode": mode,
        "roles": []
    }

    embed, view = await build_category(interaction.guild, name, cfg)
    msg = await channel.send(embed=embed, view=view)

    cfg["message"] = msg.id
    data[name] = cfg

    save_data(data)

    await interaction.response.send_message(f"Created `{name}`", ephemeral=True)


@tree.command(name="refresh")
async def refresh(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_roles:
        return await interaction.response.send_message("Need Manage Roles permission.", ephemeral=True)

    await update_all_categories(interaction.guild)
    await interaction.response.send_message("Refreshed.", ephemeral=True)


# ------------------ AUTO UPDATE EVENTS ------------------

@bot.event
async def on_guild_role_create(role):
    await update_all_categories(role.guild)


@bot.event
async def on_guild_role_delete(role):
    await update_all_categories(role.guild)


@bot.event
async def on_guild_role_update(before, after):
    if before.position != after.position or before.name != after.name:
        await update_all_categories(after.guild)


# ------------------ READY ------------------

@bot.event
async def on_ready():
    await tree.sync()
    print(f"Logged in as {bot.user}")


bot.run(TOKEN)