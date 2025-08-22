# GTD Python Telegram Bot

Bot that integrates with Nextcloud for implementing GTD system.

## How to run/install
```bash
# move the env.example to .env and populate with appropriate values.
mv env.example .env

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export $(grep -v '^#' .env | xargs)
python gtd_bot.py
```

## Usage
# GTD with Telegram + Nextcloud + Markdown

Commands:
/in <text>
/next <@context> <text>
/wait <text>
/proj <+Project> <text>
/tickler <YYYY-MM-DD> <text>
/list <list>
/done <list> <match>
/weekly
/tickle

## Containerized app
Build via docker compose the Dockerfile

```bash
docker compose build --no-cache

# and run it
docker compose up -d
```

If anything went south, then delete and rebuild
```bash
docker compose down
docker rmi gtd-bot:latest
```
