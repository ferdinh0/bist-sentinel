import threading

from app import app
from scheduler import scheduler
from telegram.bot import bot_loop


def run_web():

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        use_reloader=False,
    )


def run_telegram():

    bot_loop()


def run_scheduler():

    scheduler()


if __name__ == "__main__":

    print()
    print("=" * 60)
    print("🚀 BIST SENTINEL BAŞLATILIYOR")
    print("=" * 60)
    print()

    web_thread = threading.Thread(
        target=run_web,
        daemon=True,
    )

    telegram_thread = threading.Thread(
        target=run_telegram,
        daemon=True,
    )

    scheduler_thread = threading.Thread(
        target=run_scheduler,
        daemon=True,
    )

    web_thread.start()

    print("🌐 Web paneli başlatıldı.")

    telegram_thread.start()

    print("🤖 Telegram botu başlatıldı.")

    scheduler_thread.start()

    print("⏰ Otomatik tarama başlatıldı.")

    print()
    print("=" * 60)
    print("✅ SENTINEL ÇALIŞIYOR")
    print("=" * 60)
    print()
    print("🌐 http://127.0.0.1:5000")
    print("📱 Telegram botu aktif")
    print("⏰ Scheduler aktif")
    print()
    print("Durdurmak için CTRL + C")
    print("=" * 60)

    try:

        while True:
            threading.Event().wait(1)

    except KeyboardInterrupt:

        print()
        print("🛑 Sentinel kapatılıyor...")