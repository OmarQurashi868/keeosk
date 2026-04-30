import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import asyncio

TOKEN = os.getenv("TOKEN")
DATA_FILE = os.getenv("DATA_FILE", "/data/data.json")

# ── Data helpers ─────────────────────────────────────────────────────────────

def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"categories": {}}

def save_data(data: dict):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ── Bot setup ─────────────────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="\x00", intents=intents)  # null prefix = no text commands

# ── Permission check ──────────────────────────────────────────────────────────

def has_manage_roles(interaction: discord.Interaction) -> bool:
    return interaction.user.guild_permissions.manage_roles

# ── Role resolution ───────────────────────────────────────────────────────────

def get_roles_between(guild: discord.Guild, top_id: int, bottom_id: int) -> list[discord.Role]:
    """
    Return all roles whose position is BETWEEN top_role and bottom_role (exclusive).
    top_role must have a higher position number than bottom_role.
    """
    top_role    = guild.get_role(top_id)
    bottom_role = guild.get_role(bottom_id)
    if not top_role or not bottom_role:
        return []
    high = max(top_role.position, bottom_role.position)
    low  = min(top_role.position, bottom_role.position)
    return [r for r in guild.roles if low < r.position < high]

# ── Embed + UI builders ───────────────────────────────────────────────────────

def build_embed(category_name: str, roles: list[discord.Role], select_type: str) -> discord.Embed:
    desc_lines = [f"{'Pick one role' if select_type == 'single' else 'Pick any roles'} from the list below.\n"]
    for r in roles:
        desc_lines.append(r.mention)
    embed = discord.Embed(
        title=f"🏷️  {category_name}",
        description="\n".join(desc_lines),
        colour=discord.Colour.blurple(),
    )
    embed.set_footer(text=f"Mode: {'Single-select' if select_type == 'single' else 'Multi-select'}")
    return embed


class RoleButton(discord.ui.Button):
    def __init__(self, role: discord.Role, category_key: str, select_type: str):
        super().__init__(
            label=role.name,
            custom_id=f"role:{category_key}:{role.id}",
            style=discord.ButtonStyle.secondary,
        )
        self.role_id      = role.id
        self.category_key = category_key
        self.select_type  = select_type

    async def callback(self, interaction: discord.Interaction):
        await handle_role_toggle(
            interaction,
            self.category_key,
            self.role_id,
            self.select_type,
        )


class RoleSelect(discord.ui.Select):
    def __init__(self, roles: list[discord.Role], category_key: str, select_type: str):
        options = [
            discord.SelectOption(label=r.name, value=str(r.id))
            for r in roles[:25]  # Discord limit
        ]
        super().__init__(
            placeholder="Choose a role…",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"roleselect:{category_key}",
        )
        self.category_key = category_key
        self.select_type  = select_type

    async def callback(self, interaction: discord.Interaction):
        await handle_role_toggle(
            interaction,
            self.category_key,
            int(self.values[0]),
            self.select_type,
        )


def build_view(roles: list[discord.Role], category_key: str, select_type: str) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    if select_type == "single":
        view.add_item(RoleSelect(roles, category_key, select_type))
    else:
        for role in roles[:25]:  # Discord allows max 25 buttons per message (5 rows × 5)
            view.add_item(RoleButton(role, category_key, select_type))
    return view


# ── Role toggle logic ─────────────────────────────────────────────────────────

async def handle_role_toggle(
    interaction: discord.Interaction,
    category_key: str,
    role_id: int,
    select_type: str,
):
    await interaction.response.defer(ephemeral=True)

    data  = load_data()
    guild = interaction.guild
    cat   = data["categories"].get(category_key)
    if not cat:
        await interaction.followup.send("❌ Category no longer exists.", ephemeral=True)
        return

    roles_in_cat = get_roles_between(guild, cat["top_role_id"], cat["bottom_role_id"])
    role_ids_in_cat = {r.id for r in roles_in_cat}

    target_role = guild.get_role(role_id)
    if not target_role or role_id not in role_ids_in_cat:
        await interaction.followup.send("❌ That role is no longer part of this category.", ephemeral=True)
        return

    member = interaction.user

    if select_type == "single":
        # Remove all other category roles first
        roles_to_remove = [r for r in member.roles if r.id in role_ids_in_cat and r.id != role_id]
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove, reason="Self-role: single-select swap")

        if target_role in member.roles:
            await member.remove_roles(target_role, reason="Self-role: deselect")
            await interaction.followup.send(f"✅ Removed **{target_role.name}**.", ephemeral=True)
        else:
            await member.add_roles(target_role, reason="Self-role: select")
            await interaction.followup.send(f"✅ You now have **{target_role.name}**.", ephemeral=True)
    else:
        if target_role in member.roles:
            await member.remove_roles(target_role, reason="Self-role: toggle off")
            await interaction.followup.send(f"✅ Removed **{target_role.name}**.", ephemeral=True)
        else:
            await member.add_roles(target_role, reason="Self-role: toggle on")
            await interaction.followup.send(f"✅ Added **{target_role.name}**.", ephemeral=True)


# ── Refresh a category message ────────────────────────────────────────────────

async def refresh_category(guild: discord.Guild, category_key: str, cat: dict):
    """Re-fetch roles and update the pinned message for this category."""
    roles = get_roles_between(guild, cat["top_role_id"], cat["bottom_role_id"])

    channel = guild.get_channel(cat["channel_id"])
    if not channel:
        return

    embed = build_embed(cat["name"], roles, cat["select_type"])
    view  = build_view(roles, category_key, cat["select_type"])

    msg_id = cat.get("message_id")
    if msg_id:
        try:
            msg = await channel.fetch_message(msg_id)
            await msg.edit(embed=embed, view=view)
            return
        except discord.NotFound:
            pass

    # Send a fresh message
    msg = await channel.send(embed=embed, view=view)
    data = load_data()
    data["categories"][category_key]["message_id"] = msg.id
    save_data(data)


# ── Slash commands ────────────────────────────────────────────────────────────

@bot.tree.command(name="add-category", description="Create a self-role category between two role boundaries.")
@app_commands.describe(
    name="Display name for this category",
    channel="Channel where the role-picker message will be posted",
    top_limit="Role that marks the TOP boundary (exclusive)",
    bottom_limit="Role that marks the BOTTOM boundary (exclusive)",
    select_type="single – picking one removes others | multi – pick any combination",
)
@app_commands.choices(select_type=[
    app_commands.Choice(name="Multi-select", value="multi"),
    app_commands.Choice(name="Single-select", value="single"),
])
async def add_category(
    interaction: discord.Interaction,
    name: str,
    channel: discord.TextChannel,
    top_limit: discord.Role,
    bottom_limit: discord.Role,
    select_type: app_commands.Choice[str],
):
    if not has_manage_roles(interaction):
        await interaction.response.send_message("❌ You need **Manage Roles** permission.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    roles_between = get_roles_between(interaction.guild, top_limit.id, bottom_limit.id)
    if not roles_between:
        await interaction.followup.send(
            "❌ No roles exist between those two boundaries. Make sure they're not adjacent.",
            ephemeral=True,
        )
        return

    data = load_data()
    # Use a stable key derived from guild + name
    category_key = f"{interaction.guild.id}:{name.lower().replace(' ', '_')}"

    if category_key in data["categories"]:
        await interaction.followup.send(
            f"❌ A category named **{name}** already exists. Use `/edit-category` to modify it.",
            ephemeral=True,
        )
        return

    cat = {
        "name":          name,
        "guild_id":      interaction.guild.id,
        "channel_id":    channel.id,
        "top_role_id":   top_limit.id,
        "bottom_role_id":bottom_limit.id,
        "select_type":   select_type.value,
        "message_id":    None,
    }
    data["categories"][category_key] = cat
    save_data(data)

    await refresh_category(interaction.guild, category_key, cat)

    role_names = ", ".join(r.name for r in roles_between)
    await interaction.followup.send(
        f"✅ Category **{name}** created in {channel.mention}.\n"
        f"Included roles: {role_names}",
        ephemeral=True,
    )


@bot.tree.command(name="remove-category", description="Delete a self-role category and its message.")
@app_commands.describe(name="Name of the category to remove")
async def remove_category(interaction: discord.Interaction, name: str):
    if not has_manage_roles(interaction):
        await interaction.response.send_message("❌ You need **Manage Roles** permission.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    data = load_data()
    category_key = f"{interaction.guild.id}:{name.lower().replace(' ', '_')}"
    cat = data["categories"].pop(category_key, None)
    if not cat:
        await interaction.followup.send(f"❌ No category named **{name}** found.", ephemeral=True)
        return

    save_data(data)

    # Try to delete the pinned message
    if cat.get("message_id"):
        channel = interaction.guild.get_channel(cat["channel_id"])
        if channel:
            try:
                msg = await channel.fetch_message(cat["message_id"])
                await msg.delete()
            except discord.NotFound:
                pass

    await interaction.followup.send(f"✅ Category **{name}** removed.", ephemeral=True)


@bot.tree.command(name="edit-category", description="Change the name, channel, boundaries or type of a category.")
@app_commands.describe(
    name="Current name of the category",
    new_name="New name (leave blank to keep current)",
    channel="New channel (leave blank to keep current)",
    top_limit="New top boundary role (leave blank to keep current)",
    bottom_limit="New bottom boundary role (leave blank to keep current)",
    select_type="Change selection type",
)
@app_commands.choices(select_type=[
    app_commands.Choice(name="Multi-select", value="multi"),
    app_commands.Choice(name="Single-select", value="single"),
    app_commands.Choice(name="(keep current)", value="keep"),
])
async def edit_category(
    interaction: discord.Interaction,
    name: str,
    new_name: str = None,
    channel: discord.TextChannel = None,
    top_limit: discord.Role = None,
    bottom_limit: discord.Role = None,
    select_type: app_commands.Choice[str] = None,
):
    if not has_manage_roles(interaction):
        await interaction.response.send_message("❌ You need **Manage Roles** permission.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    data = load_data()
    category_key = f"{interaction.guild.id}:{name.lower().replace(' ', '_')}"
    cat = data["categories"].get(category_key)
    if not cat:
        await interaction.followup.send(f"❌ No category named **{name}** found.", ephemeral=True)
        return

    if new_name and new_name != name:
        # Move to new key
        data["categories"].pop(category_key)
        category_key = f"{interaction.guild.id}:{new_name.lower().replace(' ', '_')}"
        cat["name"] = new_name

    if channel:
        cat["channel_id"] = channel.id
        cat["message_id"] = None  # force new message in new channel

    if top_limit:
        cat["top_role_id"] = top_limit.id

    if bottom_limit:
        cat["bottom_role_id"] = bottom_limit.id

    if select_type and select_type.value != "keep":
        cat["select_type"] = select_type.value

    data["categories"][category_key] = cat
    save_data(data)

    await refresh_category(interaction.guild, category_key, cat)
    await interaction.followup.send(f"✅ Category **{cat['name']}** updated.", ephemeral=True)


@bot.tree.command(name="list-categories", description="List all self-role categories in this server.")
async def list_categories(interaction: discord.Interaction):
    if not has_manage_roles(interaction):
        await interaction.response.send_message("❌ You need **Manage Roles** permission.", ephemeral=True)
        return

    data  = load_data()
    guild = interaction.guild
    cats  = [c for c in data["categories"].values() if c["guild_id"] == guild.id]

    if not cats:
        await interaction.response.send_message("No categories configured yet.", ephemeral=True)
        return

    embed = discord.Embed(title="Self-role Categories", colour=discord.Colour.blurple())
    for cat in cats:
        roles    = get_roles_between(guild, cat["top_role_id"], cat["bottom_role_id"])
        ch       = guild.get_channel(cat["channel_id"])
        top_r    = guild.get_role(cat["top_role_id"])
        bot_r    = guild.get_role(cat["bottom_role_id"])
        embed.add_field(
            name=cat["name"],
            value=(
                f"Channel: {ch.mention if ch else '❓'}\n"
                f"Bounds: {top_r.name if top_r else '?'} ↕ {bot_r.name if bot_r else '?'}\n"
                f"Roles: {len(roles)} | Type: {cat['select_type']}"
            ),
            inline=False,
        )

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="refresh-category", description="Manually refresh a category's message.")
@app_commands.describe(name="Name of the category to refresh")
async def refresh_category_cmd(interaction: discord.Interaction, name: str):
    if not has_manage_roles(interaction):
        await interaction.response.send_message("❌ You need **Manage Roles** permission.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    data = load_data()
    category_key = f"{interaction.guild.id}:{name.lower().replace(' ', '_')}"
    cat = data["categories"].get(category_key)
    if not cat:
        await interaction.followup.send(f"❌ No category named **{name}** found.", ephemeral=True)
        return

    await refresh_category(interaction.guild, category_key, cat)
    await interaction.followup.send(f"✅ Category **{name}** refreshed.", ephemeral=True)


# ── Auto-refresh on role changes ──────────────────────────────────────────────

async def maybe_refresh_all(guild: discord.Guild):
    """Re-render every category in the guild (called after role hierarchy changes)."""
    data = load_data()
    for key, cat in data["categories"].items():
        if cat["guild_id"] == guild.id:
            await refresh_category(guild, key, cat)


@bot.event
async def on_guild_role_create(role: discord.Role):
    await maybe_refresh_all(role.guild)


@bot.event
async def on_guild_role_delete(role: discord.Role):
    await maybe_refresh_all(role.guild)


@bot.event
async def on_guild_role_update(before: discord.Role, after: discord.Role):
    # Only re-render if the position changed (affects which roles fall between bounds)
    if before.position != after.position or before.name != after.name:
        await maybe_refresh_all(after.guild)


# ── Persistent view re-registration on startup ────────────────────────────────

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")

    data = load_data()
    for key, cat in data["categories"].items():
        guild = bot.get_guild(cat["guild_id"])
        if not guild:
            continue
        roles = get_roles_between(guild, cat["top_role_id"], cat["bottom_role_id"])
        view  = build_view(roles, key, cat["select_type"])
        bot.add_view(view)  # re-register so buttons survive restarts

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s).")
    except Exception as e:
        print(f"Sync error: {e}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("TOKEN environment variable is not set.")
    bot.run(TOKEN)