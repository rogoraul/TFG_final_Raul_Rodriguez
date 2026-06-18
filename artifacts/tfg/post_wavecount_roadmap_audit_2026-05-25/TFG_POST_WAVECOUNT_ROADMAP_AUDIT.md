# TFG Post-WaveCount Roadmap Audit

Auditoria de rumbo tras el cierre metodologico de WaveCount 2.5.x. No implementa funcionalidades, no genera senales, no conecta MT5 y no ejecuta backtests.

## Decision principal

El TFG no debe seguir por inercia abriendo subfases WaveCount. Los bloques tecnicos principales estan lo bastante cerrados para pasar a una fase de arquitectura de memoria y mapa de evidencia.

| next_best_step | why_now | risk_if_skipped |
| --- | --- | --- |
| memory_architecture_and_evidence_map | Los bloques empiricos/metodologicos principales estan cerrados o pausados; seguir abriendo tecnologia aumenta ruido. | Acumular mas fases sin convertir evidencia en memoria defendible. |

## Estado por bloque

| block | status | next_action |
| --- | --- | --- |
| ENBOLSA benchmark/backtest | closed | Usar como eje empirico principal de la memoria; no reabrir salvo bug real. |
| ENBOLSA risk sensitivity | validated | Incluir como cautela metodologica en resultados ENBOLSA. |
| RiskGuard audit | validated | Mantener como apoyo para limitar interpretacion operativa del bloque extremo. |
| RiskGuard operativo | implemented_not_integrated | Dejar como capa preparada; integracion real queda futura salvo que se priorice dashboard/dry-run. |
| Live Signal Watcher | implemented_not_integrated | Mantener read-only; dashboard/Telegram son futuros, no bloquean memoria. |
| Menendez | methodological_only | Pasarlo a memoria como formalizacion alternativa cerrada. |
| WaveCount | methodological_only | Pausar como linea tecnica activa y usarlo como extension exploratoria en memoria. |
| Dashboard | future_only | Dejar post-TFG o abrir solo si el usuario decide priorizar prototipo visual. |
| Telegram | future_only | No hacer todavia. |
| MT5/live | blocked | Bloquear hasta despues de dry-run/shadow/demo con decision explicita. |
| memoria academica | pending | Siguiente hito recomendado: mapa de memoria y artifact-to-chapter. |

## Bloques cerrados

| block | status | reopen_policy |
| --- | --- | --- |
| ENBOLSA benchmark/backtest | closed | No reabrir salvo bug reproducible, contradiccion documental grave o decision explicita del usuario. |
| ENBOLSA risk sensitivity | validated | No reabrir salvo bug reproducible, contradiccion documental grave o decision explicita del usuario. |
| RiskGuard audit | validated | No reabrir salvo bug reproducible, contradiccion documental grave o decision explicita del usuario. |
| Menendez | methodological_only | No reabrir salvo bug reproducible, contradiccion documental grave o decision explicita del usuario. |
| WaveCount | methodological_only | No reabrir salvo bug reproducible, contradiccion documental grave o decision explicita del usuario. |

## Pendientes tecnicos

| technical_item | status | recommended_action |
| --- | --- | --- |
| roadmap cleanup | pending | Actualizar estado post-WaveCount en roadmap. |
| dashboard read-only | future_only | Dejar post-memoria salvo decision explicita. |
| telegram informativo | future_only | No hacer todavia. |
| watcher integration outputs | implemented_not_integrated | No bloquea memoria. |
| RiskGuard live position source | pending | Futuro antes de dry-run, no ahora. |
| Numba/Python parity | pending | Puede abordarse si se quiere reforzar reproducibilidad tecnica. |
| packaging/reproducibility | pending | Hacer junto al mapa de memoria. |
| tests inventory | pending | Documentar antes de entrega. |

## Pendientes academicos

| academic_item | status | next_action | priority |
| --- | --- | --- | --- |
| indice definitivo de memoria | pending | Definir capitulos y subsecciones. | high |
| artifact-to-chapter map | pending | Relacionar tablas/graficos/docs con capitulos. | high |
| resultados ENBOLSA | ready_material | Redactar resultados y cautelas. | high |
| Menendez | ready_material | Redactar como bloque metodologico sin edge. | medium |
| WaveCount | ready_material | Redactar como extension exploratoria no operativa. | medium |
| limitaciones | pending | Consolidar look-ahead, riesgo, live, ABC/WaveCount, Menendez. | high |
| trabajo futuro | pending | Separar futuro realista/post-TFG de alcance del TFG. | medium |
| figuras y tablas finales | pending | Crear shortlist de figuras/tablas para memoria. | high |

## Roadmap post-WaveCount

| horizon | order | roadmap_item | do_not_do |
| --- | --- | --- | --- |
| short_term | 1 | Crear mapa de memoria y artifact-to-chapter. | No redactar aun a ciegas sin mapa. |
| short_term | 2 | Seleccionar tablas/figuras finales ENBOLSA, RiskGuard, Menendez y WaveCount. | No generar nuevas metricas salvo hueco real. |
| short_term | 3 | Limpiar roadmap/estado para que no apunten a fases WaveCount ya cerradas. | No mover carpetas ni reabrir WaveCount. |
| medium_term | 4 | Redactar capitulos tecnicos y resultados. | No vender WaveCount/Menendez como edge. |
| medium_term | 5 | Revisar reproducibilidad minima: comandos, dependencias, tests y artifacts canonicos. | No ejecutar backtests nuevos salvo necesidad documentada. |
| future_post_tfg | 6 | Dashboard read-only, Telegram informativo, DryRunBroker y MT5 shadow/demo. | No hacerlo antes de cerrar memoria si no es requisito. |
| future_post_tfg | 7 | WaveCount 2.6 o expansion historica descriptiva. | No convertirlo en senal. |

## No hacer todavia

| item | reason | policy |
| --- | --- | --- |
| MT5 live/demo/shadow | Falta DryRunBroker, broker adapter y libro vivo validado. | Bloqueado |
| Telegram con comandos de trading | Riesgo operativo y scope creep. | Bloqueado |
| WaveCount como filtro de senales | 2.5.x lo cierra como lectura estructural no operativa. | Bloqueado |
| Backtests WaveCount | No es estrategia ni filtro operativo. | Bloqueado |
| Optimizar ENBOLSA por rentabilidad | Riesgo de sobreajuste fuera del cierre empirico. | Bloqueado |
| Reabrir Menendez para buscar edge | Cierre empirico negativo ya documentado. | No salvo nueva fase explicitamente aprobada |
| Dashboard grande antes de memoria | Puede desviar semanas de trabajo. | Diferir |
| SVM/EWO o IA | Requiere etiquetas y control de leakage. | Futuro experimental |
