# hamsterbot

Telegram bot that voices hamster images. Send a hamster pic — get it back with a funny voiceover. Built with a web interface for managing the dataset and tracking sessions.

## Features

- **Hamster voicing** — the main feature: send an image, get a voiced hamster back
- Custom Q&A dataset (add/edit via web UI)
- Session progress tracking
- Web admin interface
- Results and statistics

## Stack

![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-000000?style=flat&logo=flask&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=flat&logo=javascript&logoColor=black)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat&logo=sqlite&logoColor=white)

## Setup

```bash
pip install -r requirements.txt
```

Set environment variables:
```env
BOT_TOKEN=your_bot_token
ADMIN_PASSWORD=your_admin_password
```

```bash
python run_bot.py
# Web interface:
python web_app.py
```

## Contact

Telegram: [@dreamcatch_r](https://t.me/dreamcatch_r)
