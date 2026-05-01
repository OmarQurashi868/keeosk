# Keeosk

A simple Discord bot for creating **self-role panels** using buttons or dropdowns, based on role ranges.

100% vibe-coded.

---

## 🚀 Run with Docker

### Pull image

```bash
docker pull ghcr.io/omarqurashi868/keeosk:latest
```

### Run (bind mount)

```bash
docker run -d \
  --name keeosk \
  -e TOKEN=YOUR_BOT_TOKEN \
  -v /etc/keeosk-bot/data:/data \
  ghcr.io/omarqurashi868/keeosk
```

> If `data.json` does not exist, it will be created automatically.

---

## 🐳 Docker Compose

```yaml
version: "3.9"

services:
  keeosk:
    image: ghcr.io/omarqurashi868/keeosk
    container_name: keeosk
    restart: unless-stopped
    environment:
      - TOKEN=YOUR_BOT_TOKEN
    volumes:
      - /etc/keeosk-bot/data:/data
```

Run:

```bash
docker compose up -d
```

> `data.json` will be created automatically on first run.

---
 
## ⚙️ Usage
 
All commands require the **Manage Roles** permission.
 
* `/add-category` — Create a new self-role panel
  * `name` — display name for the category
  * `channel` — where the panel message is posted
  * `top_limit` / `bottom_limit` — roles that define the range (exclusive boundaries)
  * `select_type` — **Multi-select** (toggle buttons) or **Single-select** (dropdown)
 
* `/edit-category` — Modify an existing category (all fields except `name` are optional)
 
* `/remove-category` — Delete a category and its panel message
 
* `/list-categories` — Show all categories configured in this server
 
* `/refresh-category` — Manually force a category's message to re-render
 
> Role panels also **auto-update** whenever roles are created, deleted, or reordered (with a 5-second debounce to avoid rate limits).
 
---
 

## 🔐 Requirements

* Bot permissions:

  * Manage Roles
  * Send Messages
* Bot role must be **above assignable roles**
