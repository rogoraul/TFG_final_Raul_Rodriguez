from __future__ import annotations

import pandas as pd

from backtests.menendez.menendez_pipeline import construir_screener_rows, ejecutar_suite_experimental_menendez


def _load_latest_rows(symbols=None, variant_name="faithful_strict", **kwargs):
    suite = ejecutar_suite_experimental_menendez(
        symbols=symbols,
        variant_names=[variant_name],
        verbose=False,
        **kwargs,
    )
    variant_bundle = suite["variants"].get(variant_name, {})
    return variant_bundle.get("screener_rows", pd.DataFrame())


def create_dash_app(symbols=None, variant_name="faithful_strict", title="Menendez Screener", **kwargs):
    try:
        from dash import Dash, Input, Output, dash_table, dcc, html
    except ImportError as exc:
        raise RuntimeError(
            "Dash no esta instalado. Anade `dash` al entorno para usar el screener."
        ) from exc

    app = Dash(__name__)
    app.title = title

    def _rows_to_records():
        df = _load_latest_rows(symbols=symbols, variant_name=variant_name, **kwargs)
        if df.empty:
            return []
        df = df.copy()
        for column_name in ("timestamp",):
            if column_name in df.columns:
                df[column_name] = pd.to_datetime(df[column_name], errors="coerce").astype(str)
        return df.to_dict("records")

    columns = [
        {"name": "symbol", "id": "symbol"},
        {"name": "timestamp", "id": "timestamp"},
        {"name": "setup_state", "id": "setup_state"},
        {"name": "last_passed_stage", "id": "last_passed_stage"},
        {"name": "entry_ready", "id": "entry_ready"},
        {"name": "reason_block", "id": "reason_block"},
        {"name": "dir", "id": "dir"},
        {"name": "entry", "id": "entry"},
        {"name": "sl", "id": "sl"},
        {"name": "tp", "id": "tp"},
        {"name": "rr", "id": "rr"},
        {"name": "h4_attractor_dir", "id": "h4_attractor_dir"},
    ]

    app.layout = html.Div(
        style={
            "padding": "24px",
            "fontFamily": "Georgia, Cambria, 'Times New Roman', serif",
            "background": "linear-gradient(135deg, #f4efe3 0%, #d8e7ee 100%)",
            "minHeight": "100vh",
        },
        children=[
            html.H1(title, style={"marginBottom": "8px"}),
            html.P(
                f"Variante activa: {variant_name}. La tabla reutiliza directamente el pipeline Menendez.",
                style={"marginTop": "0", "marginBottom": "20px"},
            ),
            dcc.Interval(id="refresh-interval", interval=60_000, n_intervals=0),
            dash_table.DataTable(
                id="menendez-screener-table",
                columns=columns,
                data=_rows_to_records(),
                sort_action="native",
                filter_action="native",
                page_size=25,
                style_table={"overflowX": "auto", "backgroundColor": "#ffffffcc"},
                style_cell={"padding": "8px", "fontSize": "13px", "textAlign": "left"},
                style_header={"backgroundColor": "#203040", "color": "white", "fontWeight": "bold"},
            ),
        ],
    )

    @app.callback(Output("menendez-screener-table", "data"), Input("refresh-interval", "n_intervals"))
    def _refresh_table(_):
        return _rows_to_records()

    return app
