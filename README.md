# Bot Sandroid (WhatsApp)

A powerful, all-in-one WhatsApp bot integrating AI chat, secure credential storage, and a fully automated attendance system for Indocyber.

## Features

1. **AI Chat (GitHub Models)**
   - Smart AI conversation using `gpt-4o-mini` (or any other free models via GitHub API).
   - Just chat naturally with the bot and it will reply!

2. **Automated Attendance (Indocyber ESS)**
   - Manage your Check-in, Check-out, and Timesheet generation directly from WhatsApp.
   - Set randomized timeranges to automatically simulate human check-in times.
   - Manage multiple locations and users from a single WhatsApp bot.
   - Extract and download weekly/monthly attendance history directly to Excel format.

3. **Login Credential Vault**
   - Securely store and generate passwords and TOTP secrets using Fernet AES encryption.
   - Simple commands to grab your TOTP generated 6-digit codes on the fly.

## Prerequisites

- **Python 3.10+**
- **Node.js** (For running the `open-wa` server)
- **WhatsApp Web Session** running on `open-wa`

## Setup & Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/icksannugrahaa/bot-sandroid.git
   cd bot-sandroid
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment:**
   Copy `.env.example` to `.env` and fill in your details:
   ```bash
   cp .env.example .env
   ```
   **Required Environment Variables:**
   - `OPENWA_BASE_URL` (Your OpenWA API URL)
   - `OPENWA_API_KEY` (Your OpenWA API Key)
   - `GITHUB_TOKEN` (Required for the free AI chat)
   - `ENCRYPTION_KEY` (Generate one using the python snippet in `.env.example`)

4. **Run the Bot:**
   ```bash
   python bot.py
   ```

## Usage

Start chatting with your bot on WhatsApp! Type `help` or `/help` to see all available commands.

### User Management & Attendance
- `/adduser <alias> <username> <password> <imei>`: Add a new user
- `/login <alias>`: Force login / retrieve API token
- `/checkin <alias>`: Perform a manual check-in
- `/checkout <alias>`: Perform a manual check-out
- `/list_history <alias> timesheet`: Download your timesheet as an `.xlsx` file

### Notes & Locations
- `/set_location <alias> <location_name_or_id>`: Set your default office/home base.
- `/set_checkin_timerange <alias> HH:MM HH:MM`: Example: `07:15 07:45`
- `/set_notes <alias> <custom note>`: Set a custom note for your check-in report.

---
Made with 🤖 and ❤️ by Sandroid
