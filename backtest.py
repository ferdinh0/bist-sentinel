import pandas as pd
import numpy as np
import yfinance as yf

from data.bist import get_bist100_symbols, get_stock_data
from data.indicators import add_indicators
from strategy.scorer import score_stock


# =========================================================
# AYARLAR
# =========================================================

PERIOD = "3y"
TEST_LIMIT = None
STEP = 5

HORIZONS = [5, 10, 20]
TARGETS = [3, 5, 8]


# =========================================================
# SKOR BANDI
# =========================================================

def get_score_bucket(score):

    if score >= 100:
        return "100+"

    elif score >= 90:
        return "90-99"

    elif score >= 80:
        return "80-89"

    elif score >= 70:
        return "70-79"

    else:
        return "<70"


# =========================================================
# OVEREXTENSION BANDI
# =========================================================

def get_distance_bucket(distance):

    if pd.isna(distance):
        return "Bilinmiyor"

    if distance < 2:
        return "<2%"

    elif distance < 5:
        return "2-5%"

    elif distance < 10:
        return "5-10%"

    elif distance < 15:
        return "10-15%"

    else:
        return "15%+"


# =========================================================
# COMPONENT BANDI
# =========================================================

def get_component_bucket(score, maximum):

    ratio = score / maximum if maximum else 0

    if ratio < 0.34:
        return "Düşük"

    elif ratio < 0.67:
        return "Orta"

    else:
        return "Yüksek"


# =========================================================
# BIST100 BENCHMARK
# =========================================================

def get_benchmark_data():

    print()
    print("📊 BIST100 benchmark verisi indiriliyor...")

    tickers = [
        "XU100.IS",
        "^XU100",
    ]

    for ticker in tickers:

        try:

            benchmark = yf.download(
                ticker,
                period=PERIOD,
                interval="1d",
                progress=False,
                auto_adjust=False,
            )

            if benchmark is None or benchmark.empty:
                continue

            if isinstance(
                benchmark.columns,
                pd.MultiIndex
            ):

                benchmark.columns = (
                    benchmark.columns
                    .get_level_values(0)
                )

            if "Close" not in benchmark.columns:
                continue

            benchmark = benchmark[
                ["Close"]
            ].copy()

            benchmark["Close"] = pd.to_numeric(
                benchmark["Close"],
                errors="coerce"
            )

            benchmark = benchmark.dropna()

            if benchmark.empty:
                continue

            benchmark.index = pd.to_datetime(
                benchmark.index
            )

            if getattr(
                benchmark.index,
                "tz",
                None
            ) is not None:

                benchmark.index = (
                    benchmark.index
                    .tz_localize(None)
                )

            print(
                f"✅ BIST100 benchmark bulundu: "
                f"{ticker} | "
                f"{len(benchmark)} gün"
            )

            return benchmark

        except Exception as e:

            print(
                f"⚠️ {ticker} benchmark hatası: {e}"
            )

    print(
        "❌ BIST100 benchmark verisi alınamadı."
    )

    return None


# =========================================================
# BIST100 GETİRİSİ
# =========================================================

def get_benchmark_return(
    benchmark,
    date,
    horizon,
):

    if benchmark is None or benchmark.empty:
        return np.nan

    try:

        signal_date = pd.Timestamp(date)

        if signal_date.tzinfo is not None:

            signal_date = (
                signal_date
                .tz_localize(None)
            )

        benchmark_dates = pd.DatetimeIndex(
            benchmark.index
        )

        # Hisse getirisi signal gününün kapanışından
        # i + horizon gününe göre hesaplandığı için benchmark da
        # aynı mantıkla signal tarihine hizalanır.
        eligible_dates = benchmark_dates[
            benchmark_dates <= signal_date
        ]

        if len(eligible_dates) == 0:
            return np.nan

        entry_date = eligible_dates[-1]

        entry_pos = benchmark_dates.get_loc(entry_date)
        exit_pos = entry_pos + horizon

        if exit_pos >= len(benchmark_dates):
            return np.nan

        exit_date = benchmark_dates[exit_pos]

        entry_price = float(
            benchmark.loc[
                entry_date,
                "Close"
            ]
        )

        exit_price = float(
            benchmark.loc[
                exit_date,
                "Close"
            ]
        )

        if entry_price <= 0:
            return np.nan

        return (
            (
                exit_price
                - entry_price
            )
            / entry_price
        ) * 100

    except Exception:

        return np.nan


# =========================================================
# İŞLEM SİMÜLASYONU
# =========================================================

def simulate_trade(
    df,
    entry_index,
    entry_price,
    stop_price,
):

    results = {}

    if (
        entry_price <= 0
        or pd.isna(stop_price)
        or stop_price <= 0
    ):
        return results

    end_index = min(
        entry_index + max(HORIZONS),
        len(df) - 1
    )

    for target in TARGETS:

        target_price = (
            entry_price
            * (1 + target / 100)
        )

        outcome = "TIMEOUT"
        exit_day = None
        exit_price = None

        for j in range(
            entry_index + 1,
            end_index + 1
        ):

            high = float(
                df["High"].iloc[j]
            )

            low = float(
                df["Low"].iloc[j]
            )

            hit_stop = (
                low <= stop_price
            )

            hit_target = (
                high >= target_price
            )

            # Aynı mumda hem hedef hem stop
            # görülürse konservatif olarak STOP.
            if hit_stop and hit_target:

                outcome = "STOP"
                exit_day = j - entry_index
                exit_price = stop_price
                break

            if hit_stop:

                outcome = "STOP"
                exit_day = j - entry_index
                exit_price = stop_price
                break

            if hit_target:

                outcome = "TARGET"
                exit_day = j - entry_index
                exit_price = target_price
                break

        if outcome == "TARGET":

            pnl = float(target)

        elif outcome == "STOP":

            pnl = (
                (
                    exit_price
                    - entry_price
                )
                / entry_price
            ) * 100

        else:

            final_price = float(
                df["Close"].iloc[end_index]
            )

            pnl = (
                (
                    final_price
                    - entry_price
                )
                / entry_price
            ) * 100

        results[target] = {
            "outcome": outcome,
            "exit_day": exit_day,
            "pnl": pnl,
        }

    return results


# =========================================================
# ANA
# =========================================================

def main():

    print()
    print("=" * 100)
    print("🧪 BIST SENTINEL V2.4")
    print("🔥 SİNYAL KOMBİNASYON ANALİZİ")
    print("=" * 100)
    print()

    stocks = get_bist100_symbols()

    if TEST_LIMIT:
        stocks = stocks[:TEST_LIMIT]

    print(
        f"📊 Hisse sayısı: {len(stocks)}"
    )

    print(
        f"📅 Veri periyodu: {PERIOD}"
    )

    print(
        f"⏱️ Sinyal aralığı: {STEP} işlem günü"
    )

    benchmark = get_benchmark_data()

    print()

    all_results = []

    # =====================================================
    # HİSSELERİ TARA
    # =====================================================

    for stock_index, symbol in enumerate(
        stocks,
        start=1
    ):

        clean_symbol = symbol.replace(
            ".IS",
            ""
        )

        print(
            f"[{stock_index}/{len(stocks)}] "
            f"{clean_symbol}"
        )

        try:

            df = get_stock_data(
                symbol,
                period=PERIOD,
                interval="1d",
            )

            if df is None or df.empty:

                print("   ❌ Veri yok")
                continue

            df = add_indicators(df)

            df = df.dropna(
                subset=["Close"]
            ).copy()

            if len(df) < 300:

                print(
                    f"   ⚠️ Yetersiz veri: {len(df)}"
                )

                continue

            start_index = 250

            end_index = (
                len(df)
                - max(HORIZONS)
            )

            signal_count = 0

            # =================================================
            # TARİHSEL SİNYALLER
            # =================================================

            for i in range(
                start_index,
                end_index,
                STEP
            ):

                historical_df = df.iloc[
                    :i + 1
                ].copy()

                try:

                    analysis = score_stock(
                        historical_df
                    )

                except Exception as e:

                    print(
                        f"   ⚠️ Skor hatası: {e}"
                    )

                    continue

                score = analysis["total"]

                entry_price = float(
                    df["Close"].iloc[i]
                )

                entry_date = df.index[i]

                stop_price = analysis["stop"]

                if (
                    entry_price <= 0
                    or pd.isna(stop_price)
                    or stop_price <= 0
                ):
                    continue

                # =================================================
                # COMPONENT SKORLARI
                # =================================================

                trend_score = analysis[
                    "trend"
                ][0]

                trend_max = analysis[
                    "trend"
                ][1]

                momentum_score = analysis[
                    "momentum"
                ][0]

                momentum_max = analysis[
                    "momentum"
                ][1]

                volume_score = analysis[
                    "volume"
                ][0]

                volume_max = analysis[
                    "volume"
                ][1]

                risk_score = analysis[
                    "risk"
                ][0]

                risk_max = analysis[
                    "risk"
                ][1]

                sr_score = analysis[
                    "support_resistance"
                ][0]

                sr_max = analysis[
                    "support_resistance"
                ][1]

                formation_score = analysis[
                    "formation"
                ][0]

                formation_max = analysis[
                    "formation"
                ][1]

                # =================================================
                # EMA MESAFELERİ
                # =================================================

                last = historical_df.iloc[-1]

                ema9 = last.get(
                    "EMA9",
                    np.nan
                )

                ema21 = last.get(
                    "EMA21",
                    np.nan
                )

                ema50 = last.get(
                    "EMA50",
                    np.nan
                )

                ema200 = last.get(
                    "EMA200",
                    np.nan
                )

                def distance_from_ema(ema):

                    if (
                        pd.isna(ema)
                        or ema == 0
                    ):
                        return np.nan

                    return (
                        (
                            entry_price
                            - float(ema)
                        )
                        / float(ema)
                    ) * 100

                dist_ema9 = (
                    distance_from_ema(ema9)
                )

                dist_ema21 = (
                    distance_from_ema(ema21)
                )

                dist_ema50 = (
                    distance_from_ema(ema50)
                )

                dist_ema200 = (
                    distance_from_ema(ema200)
                )

                overextension_ema50 = abs(
                    dist_ema50
                )

                overextension_ema200 = abs(
                    dist_ema200
                )

                # =================================================
                # R/R
                # =================================================

                resistance = analysis[
                    "resistance"
                ]

                potential = (
                    (
                        resistance
                        - entry_price
                    )
                    / entry_price
                ) * 100

                stop_distance = (
                    (
                        entry_price
                        - stop_price
                    )
                    / entry_price
                ) * 100

                if stop_distance > 0:

                    rr_ratio = (
                        potential
                        / stop_distance
                    )

                else:

                    rr_ratio = np.nan

                # =================================================
                # SONUÇ KAYDI
                # =================================================

                result = {

                    "symbol":
                        clean_symbol,

                    "date":
                        entry_date,

                    "score":
                        score,

                    "score_bucket":
                        get_score_bucket(
                            score
                        ),

                    # COMPONENTLER
                    "trend_score":
                        trend_score,

                    "trend_bucket":
                        get_component_bucket(
                            trend_score,
                            trend_max
                        ),

                    "momentum_score":
                        momentum_score,

                    "momentum_bucket":
                        get_component_bucket(
                            momentum_score,
                            momentum_max
                        ),

                    "volume_score":
                        volume_score,

                    "volume_bucket":
                        get_component_bucket(
                            volume_score,
                            volume_max
                        ),

                    "risk_score":
                        risk_score,

                    "risk_bucket":
                        get_component_bucket(
                            risk_score,
                            risk_max
                        ),

                    "sr_score":
                        sr_score,

                    "sr_bucket":
                        get_component_bucket(
                            sr_score,
                            sr_max
                        ),

                    "formation_score":
                        formation_score,

                    "formation_bucket":
                        get_component_bucket(
                            formation_score,
                            formation_max
                        ),

                    # EMA
                    "dist_ema9":
                        dist_ema9,

                    "dist_ema21":
                        dist_ema21,

                    "dist_ema50":
                        dist_ema50,

                    "dist_ema200":
                        dist_ema200,

                    "overextension_ema50":
                        overextension_ema50,

                    "overextension_ema200":
                        overextension_ema200,

                    "ema50_distance_bucket":
                        get_distance_bucket(
                            overextension_ema50
                        ),

                    "ema200_distance_bucket":
                        get_distance_bucket(
                            overextension_ema200
                        ),

                    # R/R
                    "entry_price":
                        entry_price,

                    "stop_price":
                        stop_price,

                    "potential_pct":
                        potential,

                    "stop_distance_pct":
                        stop_distance,

                    "rr_ratio":
                        rr_ratio,
                }

                # =================================================
                # GELECEK GETİRİLER
                # =================================================

                for horizon in HORIZONS:

                    future_index = (
                        i + horizon
                    )

                    future_price = float(
                        df["Close"].iloc[
                            future_index
                        ]
                    )

                    stock_return = (
                        (
                            future_price
                            - entry_price
                        )
                        / entry_price
                    ) * 100

                    result[
                        f"return_{horizon}d"
                    ] = stock_return

                    benchmark_return = (
                        get_benchmark_return(
                            benchmark,
                            entry_date,
                            horizon
                        )
                    )

                    result[
                        f"benchmark_{horizon}d"
                    ] = benchmark_return

                    if pd.notna(
                        benchmark_return
                    ):

                        result[
                            f"relative_{horizon}d"
                        ] = (
                            stock_return
                            - benchmark_return
                        )

                    else:

                        result[
                            f"relative_{horizon}d"
                        ] = np.nan

                # =================================================
                # TARGET / STOP
                # =================================================

                trade_results = (
                    simulate_trade(
                        df,
                        i,
                        entry_price,
                        stop_price
                    )
                )

                for target in TARGETS:

                    if target not in trade_results:
                        continue

                    trade = trade_results[
                        target
                    ]

                    result[
                        f"target_{target}_outcome"
                    ] = trade["outcome"]

                    result[
                        f"target_{target}_pnl"
                    ] = trade["pnl"]

                all_results.append(
                    result
                )

                signal_count += 1

            print(
                f"   ✅ {signal_count} sinyal"
            )

        except Exception as e:

            print(
                f"   ❌ {clean_symbol}: {e}"
            )

    # =====================================================
    # DATAFRAME
    # =====================================================

    if not all_results:

        print()
        print("❌ Sonuç oluşmadı.")
        return

    results_df = pd.DataFrame(
        all_results
    )

    # =====================================================
    # KOMBİNASYON FİLTRELERİ
    # =====================================================

    volume_high = (
        results_df[
            "volume_bucket"
        ] == "Yüksek"
    )

    momentum_high = (
        results_df[
            "momentum_bucket"
        ] == "Yüksek"
    )

    sr_high = (
        results_df[
            "sr_bucket"
        ] == "Yüksek"
    )

    trend_high = (
        results_df[
            "trend_score"
        ] >= 20
    )

    rr_2 = (
        results_df[
            "rr_ratio"
        ] >= 2
    )

    rr_3 = (
        results_df[
            "rr_ratio"
        ] >= 3
    )

    # Backtest sonucuna göre EMA50'ye %5'ten fazla uzaklaşmamış
    # sinyalleri ayrıca test ediyoruz. %10 ve %15 de referans olarak kalıyor.
    ema50_lt5 = (
        results_df[
            "overextension_ema50"
        ] < 5
    )

    ema50_lt10 = (
        results_df[
            "overextension_ema50"
        ] < 10
    )

    ema50_lt15 = (
        results_df[
            "overextension_ema50"
        ] < 15
    )

    # =====================================================
    # TEST EDİLECEK SETUPLAR
    # =====================================================

    setups = {

        "BASELINE":
            results_df,

        "A - Hacim yüksek":
            results_df[
                volume_high
            ],

        "B - Hacim + Momentum":
            results_df[
                volume_high
                & momentum_high
            ],

        "C - Hacim + S/R":
            results_df[
                volume_high
                & sr_high
            ],

        "D - Hacim + R/R >=2":
            results_df[
                volume_high
                & rr_2
            ],

        "E - Hacim + R/R >=3":
            results_df[
                volume_high
                & rr_3
            ],

        "F - Hacim + Momentum + S/R":
            results_df[
                volume_high
                & momentum_high
                & sr_high
            ],

        "G - Hacim + Momentum + R/R >=2":
            results_df[
                volume_high
                & momentum_high
                & rr_2
            ],

        "H - Hacim + S/R + R/R >=2":
            results_df[
                volume_high
                & sr_high
                & rr_2
            ],

        "I - Hacim + R/R >=2 + EMA50 <15%":
            results_df[
                volume_high
                & rr_2
                
            ],

        "J - Hacim + Momentum + R/R >=2 + EMA50 <15%":
            results_df[
                volume_high
                & momentum_high
                & rr_2
                
            ],

        "K - Hacim + S/R + R/R >=2 + EMA50 <15%":
            results_df[
                volume_high
                & sr_high
                & rr_2
                
            ],

        "L - Hacim + Momentum + S/R + R/R >=2":
            results_df[
                volume_high
                & momentum_high
                & sr_high
                & rr_2
            ],

        # =====================================================
        # EMA50 MESAFE TESTLERİ
        # =====================================================

        "M - Hacim + EMA50 <5%":
            results_df[
                volume_high
                & ema50_lt5
            ],

        "N - Hacim + EMA50 <10%":
            results_df[
                volume_high
                & ema50_lt10
            ],

        "O - Hacim + EMA50 <15%":
            results_df[
                volume_high
                & ema50_lt15
            ],

        "P - Hacim + EMA50 <5% + Momentum":
            results_df[
                volume_high
                & ema50_lt5
                & momentum_high
            ],

        "Q - Hacim + EMA50 <5% + S/R":
            results_df[
                volume_high
                & ema50_lt5
                & sr_high
            ],

        "R - Hacim + EMA50 <5% + R/R >=2":
            results_df[
                volume_high
                & ema50_lt5
                & rr_2
            ],
    }

    # =====================================================
    # SETUP ANALİZİ
    # =====================================================

    setup_rows = []

    for name, filtered in setups.items():

        if filtered.empty:
            continue

        row = {

            "Setup":
                name,

            "Sinyal":
                len(filtered),
        }

        for horizon in HORIZONS:

            stock_col = (
                f"return_{horizon}d"
            )

            relative_col = (
                f"relative_{horizon}d"
            )

            row[
                f"{horizon}G Ort.%"
            ] = round(
                filtered[
                    stock_col
                ].mean(),
                2
            )

            row[
                f"{horizon}G Rel.%"
            ] = round(
                filtered[
                    relative_col
                ].mean(),
                2
            )

            row[
                f"{horizon}G Rel.Kazanma%"
            ] = round(
                (
                    filtered[
                        relative_col
                    ] > 0
                ).mean() * 100,
                1
            )

        # %5 hedef
        row[
            "%5 Hedef"
        ] = round(
            (
                filtered[
                    "target_5_outcome"
                ] == "TARGET"
            ).mean() * 100,
            1
        )

        # %5 stop
        row[
            "%5 Stop"
        ] = round(
            (
                filtered[
                    "target_5_outcome"
                ] == "STOP"
            ).mean() * 100,
            1
        )

        # Timeout
        row[
            "%5 Timeout"
        ] = round(
            (
                filtered[
                    "target_5_outcome"
                ] == "TIMEOUT"
            ).mean() * 100,
            1
        )

        # Ortalama PnL
        row[
            "%5 Ort.PnL"
        ] = round(
            filtered[
                "target_5_pnl"
            ].mean(),
            2
        )

        setup_rows.append(
            row
        )

    setup_df = pd.DataFrame(
        setup_rows
    )

    # =====================================================
    # SKOR BANDI ANALİZİ
    # =====================================================

    score_rows = []

    for bucket, filtered in results_df.groupby("score_bucket", sort=False):
        if filtered.empty:
            continue

        row = {
            "Skor": bucket,
            "Sinyal": len(filtered),
        }

        for horizon in HORIZONS:
            stock_col = f"return_{horizon}d"
            relative_col = f"relative_{horizon}d"

            row[f"{horizon}G Ort.%"] = round(
                filtered[stock_col].mean(), 2
            )

            row[f"{horizon}G Kazanma%"] = round(
                (filtered[stock_col] > 0).mean() * 100, 1
            )

            row[f"{horizon}G Rel.%"] = round(
                filtered[relative_col].mean(), 2
            )

            row[f"{horizon}G Rel.Kazanma%"] = round(
                (filtered[relative_col] > 0).mean() * 100, 1
            )

        row["%5 Hedef"] = round(
            (
                filtered["target_5_outcome"] == "TARGET"
            ).mean() * 100,
            1
        )

        row["%5 Stop"] = round(
            (
                filtered["target_5_outcome"] == "STOP"
            ).mean() * 100,
            1
        )

        row["%5 Ort.PnL"] = round(
            filtered["target_5_pnl"].mean(),
            2
        )

        score_rows.append(row)

    score_df = pd.DataFrame(score_rows)

    # =====================================================
    # SONUÇLARI YAZDIR
    # =====================================================

    print()
    print("=" * 120)
    print("📊 SKOR BANDI ANALİZİ")
    print("=" * 120)
    print()

    print(
        score_df.to_string(index=False)
    )

    print()
    print("=" * 120)
    print("🔥 SİNYAL KOMBİNASYON ANALİZİ")
    print("=" * 120)
    print()

    print(
        setup_df.to_string(
            index=False
        )
    )

    # =====================================================
    # EN GÜVENİLİR SKOR BANTLARI
    # =====================================================

    print()
    print("=" * 120)
    print("🏆 SKOR BANDI — %5 PnL SIRALAMASI")
    print("=" * 120)
    print()

    score_ranking = (
        score_df[
            score_df["Sinyal"] >= 30
        ]
        .sort_values(
            "%5 Ort.PnL",
            ascending=False
        )
    )

    print(
        score_ranking.to_string(
            index=False
        )
    )

    # =====================================================
    # 5G RELATİF SIRALAMA
    # =====================================================

    print()
    print("=" * 120)
    print("🏆 EN İYİ SETUPLAR — 5G RELATİF")
    print("=" * 120)
    print()

    ranking_5g = (
        setup_df[
            setup_df["Sinyal"] >= 30
        ]
        .sort_values(
            "5G Rel.%",
            ascending=False
        )
    )

    print(
        ranking_5g.to_string(
            index=False
        )
    )

    # =====================================================
    # 10G RELATİF SIRALAMA
    # =====================================================

    print()
    print("=" * 120)
    print("🏆 EN İYİ SETUPLAR — 10G RELATİF")
    print("=" * 120)
    print()

    ranking_10g = (
        setup_df[
            setup_df["Sinyal"] >= 30
        ]
        .sort_values(
            "10G Rel.%",
            ascending=False
        )
    )

    print(
        ranking_10g.to_string(
            index=False
        )
    )

    # =====================================================
    # 20G RELATİF SIRALAMA
    # =====================================================

    print()
    print("=" * 120)
    print("🏆 EN İYİ SETUPLAR — 20G RELATİF")
    print("=" * 120)
    print()

    ranking_20g = (
        setup_df[
            setup_df["Sinyal"] >= 30
        ]
        .sort_values(
            "20G Rel.%",
            ascending=False
        )
    )

    print(
        ranking_20g.to_string(
            index=False
        )
    )

    # =====================================================
    # MUTLAK PNL SIRALAMA
    # =====================================================

    print()
    print("=" * 120)
    print("💰 EN İYİ SETUPLAR — %5 ORTALAMA PNL")
    print("=" * 120)
    print()

    ranking_pnl = (
        setup_df[
            setup_df["Sinyal"] >= 30
        ]
        .sort_values(
            "%5 Ort.PnL",
            ascending=False
        )
    )

    print(
        ranking_pnl.to_string(
            index=False
        )
    )

    # =====================================================
    # CSV
    # =====================================================

    results_df.to_csv(
        "backtest_v25_results.csv",
        index=False,
        encoding="utf-8-sig"
    )

    setup_df.to_csv(
        "backtest_v25_setups.csv",
        index=False,
        encoding="utf-8-sig"
    )

    score_df.to_csv(
        "backtest_v25_score.csv",
        index=False,
        encoding="utf-8-sig"
    )

    print()
    print("=" * 120)
    print("✅ V2.5 TAMAMLANDI")
    print("=" * 120)
    print()
    print("📁 backtest_v25_results.csv")
    print("📁 backtest_v25_setups.csv")
    print("📁 backtest_v25_score.csv")
    print()


if __name__ == "__main__":
    main()