# ExpenseGram Deployment Guide

This guide details the steps to set up, configure, and host the **ExpenseGram** Telegram bot on a DigitalOcean Droplet using Docker Compose.

---

## 1. Prerequisites

1. **DigitalOcean Droplet**: A basic $4/mo or $6/mo droplet (Ubuntu 22.04 LTS or 24.04 LTS) is more than sufficient.
2. **Docker & Docker Compose**: Installed on your Droplet. (DigitalOcean has a "Docker" 1-Click App in the Marketplace that sets this up automatically).
3. **Telegram Bot Token**: Generated from [@BotFather](https://t.me/BotFather).

---

## 2. Setting Up the Files on the Droplet

1. SSH into your droplet:
   ```bash
   ssh root@your_droplet_ip
   ```
2. Create a folder for the application:
   ```bash
   mkdir -p ~/expensegram
   cd ~/expensegram
   ```
3. Copy or clone your files (`main.py`, `database.py`, `parser.py`, `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `pyproject.toml`, `uv.lock`) into that folder.

---

## 3. Configuring Environment Variables

1. Inside your application directory, create a `.env` file:
   ```bash
   nano .env
   ```
2. Add your Telegram Bot Token:
   ```env
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
   ```
   *(Note: Leave `TELEGRAM_OWNER_ID` blank initially!)*

---

## 4. Bootstrapping and Restricting Bot Access (Owner Setup)

Because this bot is single-user, it has a secure lock feature:

1. Build and run the container:
   ```bash
   docker compose up -d --build
   ```
2. Open your Telegram app and search for your bot. Click **Start** (or send `/start`).
3. Because `TELEGRAM_OWNER_ID` is empty, the bot will reply with:
   > Your Telegram User ID is: `123456789`
   > Please set `TELEGRAM_OWNER_ID=123456789` in your `.env` file to authorize yourself.
4. Go back to your terminal, stop the bot, and edit `.env`:
   ```bash
   nano .env
   ```
5. Add the line:
   ```env
   TELEGRAM_OWNER_ID=123456789
   ```
6. Rebuild and restart the container:
   ```bash
   docker compose up -d --build
   ```
7. Send `/start` again. The bot is now locked to you, and any message sent by other users will be ignored.

---

## 5. Operations & Logs

### View Container Logs
To monitor parsing and check for unauthorized access attempts:
```bash
docker compose logs -f
```

### Stop/Start the Bot
* **Stop**: `docker compose down`
* **Start**: `docker compose up -d`
* **Restart**: `docker compose restart`

### Database Backups
All transactions are stored in a local SQLite file mapped to `./data/expenses.db`. To backup this file:
```bash
cp ./data/expenses.db ./data/expenses_backup_$(date +%F).db
```
You can also use the `/export` command directly inside Telegram to download a CSV backup.

---

## 6. Continuous Integration & Deployment (CI/CD)

A GitHub Actions workflow is set up in [.github/workflows/ci-cd.yml](file://.github/workflows/ci-cd.yml). On every push to `main`:
1. **CI**: Lints and formats the codebase using `ruff`, and runs tests with `pytest`.
2. **CD**: Connects to the Droplet via SSH, pulls the latest code from GitHub, rebuilds the Docker container, and cleans up old images.

### Step 1: Configure Repository Secrets on GitHub
Go to your repository on GitHub, navigate to **Settings** -> **Secrets and variables** -> **Actions** -> **New repository secret**, and add:
- `SSH_HOST`: The IP address of your DigitalOcean Droplet.
- `SSH_USER`: The SSH username (usually `root`).
- `SSH_KEY`: The **private SSH key** corresponding to a public key authorized on the Droplet (the contents of your local `~/.ssh/id_rsa` or `~/.ssh/id_ed25519`).
- `SSH_PORT` *(Optional)*: Set this if your Droplet's SSH port is not the default `22`.

### Step 2: Authorize the Droplet to Pull from GitHub
Since your repository may be private, the Droplet needs authorization to run `git pull`.

#### Option A: Using SSH Deploy Keys (Recommended & Secure)
1. **Generate a new SSH key** on your Droplet:
   ```bash
   ssh-keygen -t ed25519 -C "expensegram-droplet-deploy"
   ```
   *(Press enter to save to the default path and skip passphrase)*
2. **Copy the public key**:
   ```bash
   cat ~/.ssh/id_ed25519.pub
   ```
3. **Add it to GitHub**:
   Go to your repository -> **Settings** -> **Deploy keys** -> **Add deploy key**. Paste the public key and check **Allow write access** if needed (not required for read-only pull).
4. **Update the Git Remote URL** on your Droplet to use SSH:
   ```bash
   cd ~/expensegram
   git remote set-url origin git@github.com:stefanobspn/ExpenseGram.git
   ```

#### Option B: Using a Personal Access Token (PAT)
1. **Generate a PAT** on GitHub with `read` permissions for the repository.
2. **Update the Git Remote URL** on your Droplet to include the token:
   ```bash
   cd ~/expensegram
   git remote set-url origin https://YOUR_PAT_TOKEN@github.com/stefanobspn/ExpenseGram.git
   ```

