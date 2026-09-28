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
