# Phase25 Final Risk Register

| risk | status | impact | mitigation | future_action |
| --- | --- | --- | --- | --- |
| confundir WaveCount con estrategia | open_controlled | alto | Documentar que no genera edge ni senales. | Mantener en memoria/TFG como analisis estructural. |
| convertir scoring en senal | blocked | alto | can_generate_signal=false en toda la matriz. | No conectar a Telegram/MT5/backtests. |
| sobreajustar prominencia | controlled | medio | 2.5.9 queda diagnostic-only; 2.5.6 no cambia. | Solo revisar si se abre expansion descriptiva. |
| rescatar conteos pequenos por metrica robusta | blocked | alto | Robust prominence no cambia buckets. | Mantener watchlist/exclusion si visualmente son pequenos. |
| extrapolar Metals sin evidencia suficiente | controlled | medio | Metals supported with warning. | Estratificar futuras muestras y revisar casos pequenos. |
| comparar scores entre grupos sin normalizar | controlled | medio | Reportar por grupo y no comparar score bruto como equivalente perfecto. | Usar percentiles solo como diagnostico. |
| usar ABC aislado | blocked | alto | ABC queda experimental/contextual con padre requerido. | Redisenar correcciones si se quiere fortalecer ABC. |
| usar H1/H4 como base principal | blocked | medio | H1/H4 queda auxiliary_only. | Usarlo solo como zoom/subestructura. |
| usar EWO/EMA/HTF como reglas duras | blocked | alto | Se mantienen como soft_context. | No endurecer sin fase metodologica especifica. |
| llevar WaveCount a live/MT5 demasiado pronto | blocked | alto | No live-ready; prominencia visual es offline. | Investigar ventanas causales solo si se abre trabajo live futuro. |
