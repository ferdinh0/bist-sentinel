from data.bist import (
    get_bist100_symbols,
    get_stock_data,
    load_all_stocks,
)

from data.indicators import add_indicators

from reports.exporter import export_to_csv

from strategy.scorer import score_stock

from telegram.sender import send_message

from telegram.state import should_notify


def main():

    print(
        "🚀 Sentinel BIST Tarama Motoru Başlatılıyor...\n"
    )


    # =====================================================
    # HİSSELER
    # =====================================================

    stocks = get_bist100_symbols()


    print(
        f"📋 Toplam {len(stocks)} hisse taranacak. "
        "Lütfen bekleyin...\n"
    )


    # =====================================================
    # TOPLU VERİ
    # =====================================================

    load_all_stocks(stocks)


    results = []


    # =====================================================
    # ANALİZ
    # =====================================================

    for idx, symbol in enumerate(
        stocks,
        start=1,
    ):

        print(
            f"[{idx}/{len(stocks)}] "
            f"{symbol} analiz ediliyor..."
        )


        try:

            df = get_stock_data(symbol)


            if df is None or df.empty:

                print(
                    "❌ Veri bulunamadı."
                )

                continue


            if len(df) < 50:

                print(
                    "❌ Yetersiz veri."
                )

                continue


            df = add_indicators(df)


            analysis = score_stock(df)


            total = analysis["total"]

            total_max = analysis["max"]


            ratio = (
                total / total_max
                if total_max
                else 0
            )


            # =================================================
            # KARAR
            # =================================================

            if ratio >= 0.70:

                decision = "🟢 GÜÇLÜ AL"

            elif ratio >= 0.50:

                decision = "🟡 İZLE"

            else:

                decision = "🔴 UZAK DUR"


            # =================================================
            # SKORLAR
            # =================================================

            trend_score, trend_max = (
                analysis["trend"]
            )

            momentum_score, momentum_max = (
                analysis["momentum"]
            )

            volume_score, volume_max = (
                analysis["volume"]
            )

            risk_score, risk_max = (
                analysis["risk"]
            )

            formation_score, formation_max = (
                analysis["formation"]
            )


            support = analysis["support"]

            resistance = analysis["resistance"]

            atr_value = analysis["atr"]

            stop_price = analysis["stop"]


            clean_symbol = symbol.replace(
                ".IS",
                "",
            )


            # =================================================
            # TERMINAL
            # =================================================

            print(
                f"\n📈 {clean_symbol}"
            )

            print(
                f"Toplam puan : "
                f"{total}/{total_max}"
            )

            print(
                f"Trend       : "
                f"{trend_score}/{trend_max}"
            )

            print(
                f"Momentum    : "
                f"{momentum_score}/{momentum_max}"
            )

            print(
                f"Hacim       : "
                f"{volume_score}/{volume_max}"
            )

            print(
                f"Risk        : "
                f"{risk_score}/{risk_max}"
            )

            print(
                f"Formasyon   : "
                f"{formation_score}/{formation_max}"
            )

            print(
                f"Destek      : "
                f"{support:.2f}"
            )

            print(
                f"Direnç      : "
                f"{resistance:.2f}"
            )

            print(
                f"ATR         : "
                f"{atr_value:.2f}"
            )

            print(
                f"Stop        : "
                f"{stop_price:.2f}"
            )

            print(
                f"Karar       : "
                f"{decision}"
            )


            # =================================================
            # TELEGRAM SİNYAL KONTROLÜ
            # =================================================

            notify, reason = should_notify(
                clean_symbol,
                decision,
                total,
            )


            if notify:

                if reason == "NEW":

                    title = (
                        "🆕 YENİ SENTINEL SİNYALİ"
                    )

                elif reason == "DECISION_CHANGE":

                    title = (
                        "🚨 SENTINEL SİNYAL DEĞİŞTİ"
                    )

                else:

                    title = (
                        "📊 SENTINEL PUAN DEĞİŞİMİ"
                    )


                message = (

                    f"{title}\n\n"

                    f"📈 {clean_symbol}\n\n"

                    f"Puan: "
                    f"{total}/{total_max}\n"

                    f"Karar: "
                    f"{decision}\n\n"

                    f"🟢 Destek: "
                    f"{support:.2f}\n"

                    f"🔴 Direnç: "
                    f"{resistance:.2f}\n"

                    f"📊 ATR: "
                    f"{atr_value:.2f}\n"

                    f"🛡 Stop: "
                    f"{stop_price:.2f}"
                )


                send_message(message)


                print(
                    "📱 Telegram bildirimi gönderildi."
                )

            else:

                print(
                    "🔕 Değişiklik yok, "
                    "Telegram bildirimi gönderilmedi."
                )


            # =================================================
            # SEBEPLER
            # =================================================

            print(
                "\nSebepler:"
            )


            for comment in analysis["comments"]:

                print(
                    f"✅ {comment}"
                )


            print(
                "\n"
                + "═" * 40
            )


            # =================================================
            # SONUÇ
            # =================================================

            results.append(

                {
                    "symbol": clean_symbol,

                    "total": total,

                    "max": total_max,

                    "trend": (
                        f"{trend_score}/"
                        f"{trend_max}"
                    ),

                    "momentum": (
                        f"{momentum_score}/"
                        f"{momentum_max}"
                    ),

                    "volume": (
                        f"{volume_score}/"
                        f"{volume_max}"
                    ),

                    "risk": (
                        f"{risk_score}/"
                        f"{risk_max}"
                    ),

                    "formation": (
                        f"{formation_score}/"
                        f"{formation_max}"
                    ),

                    "support": round(
                        support,
                        2,
                    ),

                    "resistance": round(
                        resistance,
                        2,
                    ),

                    "atr": round(
                        atr_value,
                        2,
                    ),

                    "stop": round(
                        stop_price,
                        2,
                    ),

                    "decision": decision,
                }
            )


        except Exception as e:

            print(
                f"❌ {symbol} hatası: "
                f"{e}"
            )


    # =====================================================
    # SONUÇLARI SIRALA
    # =====================================================

    if results:

        results_sorted = sorted(

            results,

            key=lambda x: x["total"],

            reverse=True,
        )


        print(
            "\n🏆 EN İYİ HİSSELER\n"
        )


        for rank, item in enumerate(
            results_sorted,
            start=1,
        ):

            print(

                f"{rank}. "
                f"{item['symbol']} - "
                f"{item['total']}/"
                f"{item['max']} - "
                f"{item['decision']}"
            )


        # =================================================
        # CSV
        # =================================================

        csv_file = export_to_csv(
            results_sorted
        )


        if csv_file:

            print(
                f"\n📁 Rapor kaydedildi: "
                f"{csv_file}"
            )


if __name__ == "__main__":

    main()