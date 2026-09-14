import time
from datetime import datetime, time as dt_time

from main import main


# =========================================================
# AYARLAR
# =========================================================

SCAN_INTERVAL_MINUTES = 15

MARKET_OPEN = dt_time(
    hour=10,
    minute=0
)

MARKET_CLOSE = dt_time(
    hour=18,
    minute=0
)


# =========================================================
# BIST İŞLEM SAATİ KONTROLÜ
# =========================================================

def is_market_time():

    now = datetime.now()

    # Cumartesi / Pazar
    if now.weekday() >= 5:
        return False

    current_time = now.time()

    return (
        MARKET_OPEN
        <= current_time
        <= MARKET_CLOSE
    )


# =========================================================
# TARAMA
# =========================================================

def run_scan():

    print()
    print("=" * 60)

    print(
        f"🤖 OTOMATİK TARAMA"
    )

    print(
        f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
    )

    print("=" * 60)

    try:

        main()

        print()
        print("✅ Otomatik tarama tamamlandı.")

    except Exception as e:

        print()
        print(
            f"❌ Tarama sırasında hata: {e}"
        )


# =========================================================
# SCHEDULER
# =========================================================

def scheduler():

    print()
    print("🤖 BIST SENTINEL OTOMATİK TARAMA")
    print(
        f"⏱️ Tarama aralığı: "
        f"{SCAN_INTERVAL_MINUTES} dakika"
    )

    print(
        "📅 Pazartesi - Cuma"
    )

    print(
        "🕙 10:00 - 18:00"
    )

    print()
    print(
        "Durdurmak için CTRL + C"
    )

    print("=" * 60)


    last_scan = None


    while True:

        now = datetime.now()


        # -------------------------------------------------
        # PİYASA AÇIK MI?
        # -------------------------------------------------

        if is_market_time():

            current_minute = (
                now.hour * 60
                + now.minute
            )


            # 15 dakikalık zaman dilimi
            slot = (
                current_minute
                // SCAN_INTERVAL_MINUTES
            )


            scan_id = (
                now.date(),
                slot
            )


            # -------------------------------------------------
            # BU DİLİMDE TARAMA YAPILDI MI?
            # -------------------------------------------------

            if scan_id != last_scan:

                run_scan()

                last_scan = scan_id


        else:

            print(
                f"💤 Piyasa kapalı - "
                f"{now.strftime('%d.%m.%Y %H:%M:%S')}"
            )


        # -------------------------------------------------
        # 30 SANİYE KONTROL
        # -------------------------------------------------

        time.sleep(30)


# =========================================================
# BAŞLAT
# =========================================================

if __name__ == "__main__":

    try:

        scheduler()

    except KeyboardInterrupt:

        print()
        print(
            "🛑 Sentinel otomatik tarama durduruldu."
        )