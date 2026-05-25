# CFB26 Dynasty Advance Bot

A simple Discord bot for College Football 26 dynasties.

## Features

- `!advance`
  - Starts a 4-day countdown
  - Posts daily reminders automatically

- `!canceladvance`
  - Cancels the current countdown

---

# Free Hosting Guide (Render)

## 1. Create a Discord Bot

Go to:

https://discord.com/developers/applications

- Create New Application
- Go to "Bot"
- Reset Token
- Copy the token

Enable:
- MESSAGE CONTENT INTENT

---

## 2. Invite the Bot

OAuth2 → URL Generator

Scopes:
- bot

Bot Permissions:
- Send Messages
- Read Message History
- Add Reactions

Invite it to your server.

---

## 3. Upload to GitHub

Create a new GitHub repo and upload these files.

---

## 4. Deploy on Render (Free)

Go to:

https://render.com/

- New Web Service
- Connect GitHub repo

Settings:
- Runtime: Python
- Build Command:
  pip install -r requirements.txt

- Start Command:
  python bot.py

---

## 5. Add Environment Variable

In Render:

Environment Variables:
- Key: DISCORD_TOKEN
- Value: your bot token

---

## Commands

- `!advance`
- `!canceladvance`

Only admins can run commands.
