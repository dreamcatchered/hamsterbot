import asyncio
import threading
from bot import main as bot_main
from web_app import app
from config import WEB_HOST, WEB_PORT

def run_web():
    app.run(host=WEB_HOST, port=WEB_PORT, debug=False, use_reloader=False)

def run_bot():
    bot_main()

if __name__ == "__main__":
    print("🐹 запуск бота и веб-сервера...")
    print(f"📱 telegram бот запускается...")
    print(f"🌐 веб-сервер будет доступен на порту {WEB_PORT}")
    print(f"🔗 публичный адрес: https://tunnel4.dreampartners.online")
    
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()
    
    print("✅ веб-сервер запущен")
    print("✅ запуск telegram бота...")
    
    run_bot()
