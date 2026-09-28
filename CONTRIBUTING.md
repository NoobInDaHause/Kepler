# Contributing to Kepler

Thanks for your interest in contributing to **Kepler**! 🤖

Kepler is an actively developed open-source Discord bot, and contributions, suggestions, bug reports, and improvements are welcome.

---

## 🧪 Development Version

The main repository contains the **development version** of Kepler.

This means the repository may contain:

* unfinished features
* experimental changes
* bugs
* breaking changes
* code that has not yet been included in a stable release

Stable versions are distributed through **GitHub Releases**.

---

## 🛠️ Setting Up the Development Environment

### 1. Fork the Repository

Fork the upstream Martin repository to your own GitHub account.

Then clone your fork:

```bash
git clone https://github.com/NoobInDaHause/Martin.git Kepler
cd Kepler
```

### 2. Configure Kepler

Rename the example configuration files:

```text
.env.example       → .env
config.json.example → config.json
```

Configure them for your development environment.

**Never commit private credentials, tokens, or other sensitive information.**

### 3. Start Kepler

Use the startup script for your operating system.

#### Windows

```text
start_bot.bat
```

#### Linux

```bash
./start_bot.sh
```

Using the startup scripts is preferred over manually starting the bot because they provide the intended development environment for Kepler.

---

## 📁 Project Organization

Kepler uses a modular architecture.

### `cogs/`

Contains the bot's individual features and commands.

When adding a new bot feature, it will generally belong in its own Cog.

### `keplerbot/`

Contains the core implementation of the bot.

Core functionality that is shared across the project should generally remain here rather than being duplicated between Cogs.

### `utilities/`

Contains reusable utilities and helper functionality used throughout the project.

### `cogs_data/`

Contains persistent data used by individual Cogs.

Database-related changes should follow the existing data-management patterns used by the project.

---

## 🐍 Coding Style

Kepler is written in Python and uses type hints throughout the codebase.

When contributing:

* Follow the existing code style.
* Prefer clear and descriptive names.
* Add type hints where appropriate.
* Avoid unnecessary duplication.
* Keep features modular.
* Reuse existing utilities when possible.
* Keep asynchronous code asynchronous.
* Avoid introducing unnecessary dependencies.

Kepler uses **Black Formatter** for checks.

---

## 🧩 Adding a New Feature

When adding a new feature:

1. Determine whether the feature belongs in an existing Cog or should have its own Cog.
2. Keep feature-specific code contained within the appropriate module.
3. Use the existing database/data-management system when persistent data is required.
4. Add appropriate error handling.
5. Test the feature before submitting the changes.
6. Make sure existing functionality still works.

---

## 🔀 Pull Requests

Before opening a Pull Request:

1. Make sure your branch contains only the changes related to your contribution.
2. Test your changes.
3. Check for linting or other development errors.
4. Write a clear commit message.
5. Explain what your Pull Request changes.
6. Mention any known limitations or unfinished parts.

Keep Pull Requests focused when possible. Smaller, focused changes are easier to review and maintain.

---

## 🐛 Bug Reports

When reporting a bug, include as much useful information as possible:

* What happened?
* What did you expect to happen?
* How can the problem be reproduced?
* What version of Kepler are you using?
* What operating system are you using?
* Relevant error messages or logs.

**Never include your Discord bot token or other private credentials in a bug report.**

---

## 💡 Suggestions

Suggestions are welcome.

When proposing a feature, explain:

* What the feature would do.
* Why it would be useful.
* How you expect it to work.
* Any potential problems or limitations you can think of.

---

## 📜 Releases

Contributors should keep in mind that the repository represents the **development version** of Kepler.

Changes merged into the development repository do not necessarily become part of a stable release immediately.

Stable versions are published separately through **GitHub Releases**.

---

## 📄 License

By contributing to Kepler, you agree that your contributions will be distributed under the project's license.
