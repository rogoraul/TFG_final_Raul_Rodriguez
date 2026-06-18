# =======================================================================
# TABLA DE STATS POR ACTIVO (coloreada)
# =======================================================================

import numpy as np
import pandas as pd


def mostrar_stats_por_activo(pf):
    """
    Muestra una tabla coloreada con las stats de cada activo.
    """
    symbols = pf.trades.count().index.tolist()

    rows = []
    for sym in symbols:
        try:
            trades = pf.trades.records_readable
            sym_trades = trades[trades["Column"] == sym]

            n_trades = len(sym_trades)
            if n_trades == 0:
                continue

            wins = sym_trades[sym_trades["PnL"] > 0]
            losses = sym_trades[sym_trades["PnL"] <= 0]

            wr = len(wins) / n_trades * 100
            avg_win = wins["Return"].mean() * 100 if len(wins) > 0 else 0
            avg_loss = losses["Return"].mean() * 100 if len(losses) > 0 else 0
            total_pnl = sym_trades["PnL"].sum()
            rr_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0
            pf_ratio = abs(wins["PnL"].sum() / losses["PnL"].sum()) if losses["PnL"].sum() != 0 else np.inf

            rows.append({
                "Activo": sym,
                "Trades": n_trades,
                "Wins": len(wins),
                "Losses": len(losses),
                "Win Rate %": round(wr, 1),
                "Avg Win %": round(avg_win, 2),
                "Avg Loss %": round(avg_loss, 2),
                "R:R": round(rr_ratio, 2),
                "Profit Factor": round(pf_ratio, 2),
                "PnL Total": round(total_pnl, 2),
            })
        except Exception:
            continue

    df_stats = pd.DataFrame(rows).sort_values("PnL Total", ascending=False)
    df_stats = df_stats.reset_index(drop=True)

    total_trades = df_stats["Trades"].sum()
    total_wins = df_stats["Wins"].sum()
    total_wr = total_wins / total_trades * 100 if total_trades > 0 else 0
    total_pnl = df_stats["PnL Total"].sum()

    print(
        f"\n{len(df_stats)} activos | {total_trades} trades | "
        f"WR: {total_wr:.1f}% | PnL Total: ${total_pnl:,.2f}\n"
    )

    def colorear(row):
        styles = [""] * len(row)

        wr = row["Win Rate %"]
        if wr >= 35:
            styles[4] = "background-color: #2d5a27; color: white"
        elif wr < 20:
            styles[4] = "background-color: #5a2727; color: white"

        pnl = row["PnL Total"]
        if pnl > 0:
            styles[9] = "background-color: #1a4a1a; color: #90ee90"
        else:
            styles[9] = "background-color: #4a1a1a; color: #ee9090"

        pf = row["Profit Factor"]
        if pf >= 1.5:
            styles[8] = "background-color: #2d5a27; color: white"
        elif pf < 1.0:
            styles[8] = "background-color: #5a2727; color: white"

        return styles

    return df_stats.style.apply(colorear, axis=1).format({
        "Win Rate %": "{:.1f}",
        "Avg Win %": "{:+.2f}",
        "Avg Loss %": "{:+.2f}",
        "R:R": "{:.2f}",
        "Profit Factor": "{:.2f}",
        "PnL Total": "${:,.2f}",
    })
