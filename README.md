# 🤖 Kepler

**Kepler** is an open-source Discord bot written in **Python** using [`discord.py`](https://github.com/Rapptz/discord.py).

Kepler is designed around a modular architecture, making it easier to add features, commands, and services as the project continues to grow.

> ⚠️ **The repository contains the development version of Kepler.**
>
> For normal use, download a **stable release** from the [Releases](../../releases) page instead.

---

## 📦 Development vs Stable

### 🧪 Development Version

The GitHub repository contains the **latest development version** of Kepler.

It may contain:

* unfinished features
* experimental changes
* bugs
* breaking changes
* changes that have not yet been included in a stable release

The development version is mainly intended for **development, testing, and contributing**.

### ✅ Stable Releases

Stable versions are published through **GitHub Releases**.

If you simply want to run Kepler, download a stable release instead of cloning the development repository.

---

## 🚀 Getting Started

### 1. Create a Discord Bot

Before running Kepler, you need to create a Discord application and bot.

1. Open the [Discord Developer Portal](https://discord.com/developers/applications).
2. Click **New Application**.
3. Give your application a name.
4. Open the **Bot** section.
5. Click **Add Bot**.
6. Copy the bot's **Token** and keep it private.

> 🔐 **Never share your bot token or commit it to GitHub.**
>
> If your token is exposed, regenerate it from the Discord Developer Portal.

### 2. Invite the Bot

Open the **Installation** section of your Discord application and configure the installation settings.

Make sure the bot has the permissions required by the features you intend to use.

You can then use the generated installation link to add Kepler to your server.

### 3. Configure Kepler

Rename the example configuration files:

```text
.env.example       → .env
config.json.example → config.json
```

Open both files and configure them according to your setup.

> ⚠️ Keep `.env` and other files containing private credentials out of version control.

### 4. Start Kepler

Kepler provides startup scripts for both Windows and Linux.

#### Windows

Run:

```text
start_bot.bat
```

#### Linux

Run:

```bash
./start_bot.sh
```

The startup scripts are the **recommended way to start Kepler**.

---

## 🖥️ Hosting Kepler

Kepler needs Python 3.10 or newer and a reliable internet connection. It connects to Discord over an outbound connection, so you do not need to open or forward inbound ports. Keep the project directory writable: Kepler stores its SQLite databases in `cogs_data/` and writes `logs.log` in the project directory.

For a continuously available bot, use an always-on Windows or Linux VM. A personal computer works too, but Kepler is offline whenever the device is off, asleep, or disconnected from the internet.

### Disclaimer

Kepler can be hosted with pterodactyl or anything similar but I will not provide support for you if you wish to do so.
It is recommended that you use linux for hosting kepler though you would require a bit of linux knowledge but the internet is always around for you to search things up.

### Windows

Run `start_bot.bat` from the project. It creates a virtual environment and installs the required packages the first time it runs. On a Windows VM, you can use Task Scheduler to start the bot at startup or user logon; set **Start in** to the Kepler project directory.

The batch script pauses after Kepler exits, and only automatically restarts it for its designated restart code. For unattended recovery from other exits, use a Windows service manager configured to restart the bot, or restart it manually after checking `logs.log`.

### Linux VM

Run `bash start_bot.sh` from the project directory to start Kepler. For automatic startup and for the restart command to work and recovery on a VM with `systemd`, create a service file at `/etc/systemd/system/kepler.service`:

```bash
sudo nano /etc/systemd/system/kepler.service
```

Then paste this code:

```ini
[Unit]
Description=Kepler Discord bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=<YOUR_LINUX_USERNAME>
WorkingDirectory=<THE_PATH_TO_YOUR_BOT>
ExecStart=bash start_bot.sh

[Install]
WantedBy=multi-user.target
```

Make sure the `kepler` account can read the project and write to it, replace the enclosed with `<>`and then enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable kepler
sudo systemctl start kepler
```

View service output with `sudo journalctl -u kepler -f`. The startup script handles Kepler's designated restart code; `systemd` restarts the service if it exits with an error.

### Personal devices

Use the platform's startup script as above. Keep the device awake and connected to the internet while you want the bot online; laptops and phones may suspend background work or disconnect on battery or mobile networks. This is suitable for testing or light use, but less reliable than an always-on VM.

### Updates and backups

Keep `.env` private and restrict access to it; it contains the bot token. Back up `config.json` and `cogs_data/` regularly, preferably while Kepler is stopped. Before updating the code or dependencies, stop Kepler and make a backup so you can restore its configuration and database files if needed.

---

## ✨ Features

* ⚡ Slash commands
* 🧩 Modular Cog architecture
* 🛡️ Moderation system
* 🚫 Blacklist system
* 🔐 Owner-only functionality
* 💾 SQLite-based persistent data
* ⚙️ Configurable settings
* 🔄 Automated development checks
* 📦 Stable versioned releases

More features are being developed.

---

## 🛠️ Built With

* 🐍 **Python**
* 🤖 **discord.py**
* 💾 **SQLite**
* ⚡ **asyncio**
* 🔍 **Ruff**
* 🛡️ **CodeQL**
* 🔄 **GitHub Actions**

---

## 🤝 Contributing

Want to help develop Kepler?

Check out **[CONTRIBUTING.md](CONTRIBUTING.md)** for development and contribution guidelines.

---

## 📜 Releases

Stable versions of Kepler are distributed through **GitHub Releases**.

The repository itself should be considered the **development version**, while releases represent versions intended for normal use.

---

## 👤 Author

Created and maintained by **NoobInDaHause**.

---

<p align="center">
  <b>Kepler</b><br>
  Built one feature at a time. 🤖
</p>
