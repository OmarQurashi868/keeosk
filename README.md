# Keeosk

A simple Discord bot for creating **self-role panels** using buttons or dropdowns, based on role ranges.

---

## 🚀 Run with Docker

### Pull image

```bash
docker pull ghcr.io/OmarQurashi868/keeosk
```

### Run (bind mount)

```bash
docker run -d \
  --name keeosk \
  -e TOKEN=YOUR_BOT_TOKEN \
  -v /etc/keeosk-bot/data:/data \
  ghcr.io/OmarQurashi868/keeosk
```

> If `data.json` does not exist, it will be created automatically.

---

## 🐳 Docker Compose

```yaml
version: "3.9"

services:
  keeosk:
    image: ghcr.io/OmarQurashi868/keeosk
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

* `/add_category` → Create a role panel

  * Select top + bottom role (range)
  * Choose channel + mode (buttons or dropdown)

* `/refresh` → Manually update panels (auto-updates also enabled)

---

## 🔐 Requirements

* Bot permissions:

  * Manage Roles
  * Send Messages
* Bot role must be **above assignable roles**
