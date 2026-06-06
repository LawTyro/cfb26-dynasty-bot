@echo off

cd /d C:\Users\natha\Documents\GitHub\cfb26-dynasty-bot

git pull

call .venv\Scripts\activate

pip install -r requirements.txt

python bot.py

pause