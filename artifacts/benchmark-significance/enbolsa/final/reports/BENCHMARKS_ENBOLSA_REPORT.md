# Informe final canonico de benchmarks ENBOLSA

## 1. Objetivo

El objetivo de esta fase del TFG es comparar las dos variantes principales de
la linea ENBOLSA, `enbolsa:fib_limit` y `enbolsa:macd_breakout`, frente a un
conjunto de benchmarks clasicos e independientes de la estructura `W1/W2`.

La finalidad de la comparacion no es optimizar ex post una estrategia concreta,
sino evaluar si la propuesta ENBOLSA aporta una ventaja observable frente a
reglas sencillas y reproducibles de seguimiento de tendencia, reversion a la
media y reentrada tras pullback.

Las estrategias evaluadas son las siguientes:

- ENBOLSA:
  - `enbolsa:fib_limit`
  - `enbolsa:macd_breakout`
- Benchmarks:
  - `benchmark:rsi_3tf_mean_reversion`
  - `benchmark:rsi_3tf_momentum_reentry`
  - `benchmark:ma_cross_3tf_trend`
  - `benchmark:bb_3tf_pullback_reentry`

El benchmark contextual `sp500_buy_hold` se conserva como referencia externa
para indices, pero no se mezcla con la comparacion operativa principal.

## 2. Diseno experimental y comparabilidad

La comparacion se ha ejecutado con la misma infraestructura operativa utilizada
en ENBOLSA:

- mismo universo de activos;
- mismos grupos (`Forex Majors`, `Metals`, `Index`);
- mismas parejas temporales (`M30:H1`, `H1:H4`, `H4:D1`);
- mismo capital inicial por bloque (`initial_capital = 10000`);
- mismo modelo de sizing monetario por stop;
- mismo tratamiento de spread, comisiones y formato de `trade_log`.

Este punto es especialmente importante, ya que evita favorecer a los
benchmarks mediante una capa operativa distinta de la empleada en la linea
ENBOLSA.

Ademas, la comparacion mantiene la misma convencion de ejecucion a cierre de
vela LTF utilizada en la capa operativa comparada. Esta decision preserva la
simetria entre ENBOLSA y benchmarks, aunque debe interpretarse como una
hipotesis de backtest ligeramente mas optimista que una ejecucion estricta en
la apertura de la vela siguiente.

## 3. Semantica de las metricas

Cada combinacion `group x tf_pair` se simula como una cuenta independiente. Por
tanto, las metricas de cartera, como `Return%`, `Sharpe`, `Sortino`, `MaxDD%`
o `Calmar`, solo son metodologicamente validas a nivel de bloque individual.

En consecuencia, la salida final diferencia tres niveles de analisis:

1. `block_metrics.csv`
   - tabla canonica por `strategy x group x tf_pair`;
   - es la referencia correcta para metricas de cartera y drawdown.
2. `aggregate_by_*.csv`
   - agregaciones entre bloques independientes;
   - resumen distribuciones de resultados entre bloques, pero no representan
     una unica curva de equity.
3. `trade_pool_*.csv`
   - resumen el conjunto de operaciones agregadas;
   - son utiles para estudiar frecuencia operativa, `PF`, `Expectancy`,
     `AvgR` y `ExpectancyR`, pero no deben interpretarse como metricas de una
     sola cartera consolidada.

Esta separacion corrige expresamente el problema de pseudo-cartera detectado en
versiones anteriores del workstream.

## 4. Tratamiento de la pareja temporal H4:D1

La pareja `H4:D1` se ha incluido en la comparacion final. Sin embargo, debe
interpretarse como una variante degradada de dos timeframes y no como un stack
3TF completo, ya que en la infraestructura disponible no existe un timeframe
superior real equivalente a `W1`.

Por ello:

- `TFStackEffective = H4,D1`
- `H4D1Mode = degraded_2tf_h4_d1`

Esta decision se mantiene explicitamente etiquetada en tablas y artefactos para
evitar una lectura incorrecta de los resultados.

## 5. Resultados globales agregados entre bloques

La Tabla 1 resume los resultados agregados por estrategia. Estas cifras no
deben leerse como el rendimiento de una sola cartera global, sino como el
comportamiento medio y mediano de cada estrategia a traves de los nueve bloques
independientes evaluados.

| Estrategia | Bloques | Trades | NetProfit total | Mean Return % | Median Return % | Positive Block Rate % | Median PF | Median AvgR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `benchmark:bb_3tf_pullback_reentry` | 9 | 22302 | -57249.61 | -63.61 | -58.88 | 11.1 | 0.90 | -0.069 |
| `benchmark:ma_cross_3tf_trend` | 9 | 13588 | -17334.66 | -19.26 | -73.74 | 22.2 | 0.90 | -0.085 |
| `benchmark:rsi_3tf_mean_reversion` | 9 | 5012 | -37382.91 | -41.54 | -26.75 | 0.0 | 0.86 | -0.083 |
| `benchmark:rsi_3tf_momentum_reentry` | 9 | 12976 | -54653.65 | -60.72 | -77.80 | 11.1 | 0.84 | -0.088 |
| `enbolsa:fib_limit` | 9 | 39910 | -15898.16 | -17.66 | -33.36 | 44.4 | 0.96 | -0.007 |
| `enbolsa:macd_breakout` | 9 | 20216 | 177422.03 | 197.14 | 36.28 | 88.9 | 1.08 | 0.075 |

Desde una perspectiva global, se observan tres conclusiones principales:

1. `enbolsa:macd_breakout` es la unica estrategia con beneficio agregado
   claramente positivo, mediana de retorno positiva y una tasa de bloques
   positivos muy elevada (`88.9%`).
2. `enbolsa:fib_limit` no alcanza un rendimiento global positivo, pero se
   comporta mejor que la mayoria de benchmarks simples y mantiene una mediana de
   `AvgR` cercana al equilibrio.
3. Los benchmarks presentan, en conjunto, un comportamiento debil. El unico
   caso con alguna senal positiva relevante es `ma_cross_3tf_trend`, pero esa
   mejora se concentra en un subconjunto especifico de bloques y no se sostiene
   en la mediana global.

Conviene introducir, no obstante, una cautela metodologica importante en la
lectura de los bloques ENBOLSA mas extremos. Una auditoria especifica del
bloque `enbolsa:macd_breakout / Forex Majors / H1:H4` confirma que su
`Return% = 1405.24` se reconstruye exactamente desde su propio `trade_log` y no
procede del antiguo problema de pseudo-cartera entre bloques. Sin embargo, ese
resultado se obtiene bajo un modelo de portfolio multi-simbolo sin cap
explicito de riesgo abierto agregado: en los picos del bloque se alcanzan hasta
`14` setups simultaneos y alrededor de `13.6%` del balance en riesgo abierto.
Por tanto, la cifra debe interpretarse como resultado del modelo operativo
actual y no como evidencia de una cartera que trabaje siempre con un riesgo
total cercano al `1%`.

## 6. Resultados por grupo

Los resultados por grupo permiten matizar el comportamiento anterior.

### 6.1 Forex Majors

En `Forex Majors`, la superioridad relativa de `enbolsa:macd_breakout` es clara.
La estrategia alcanza un `Mean Return%` del `473.16%`, aunque con una dispersion
muy elevada, y una mediana de `21.62%`. El resto de estrategias, incluida
`fib_limit`, presenta resultados agregados claramente negativos.

Este comportamiento sugiere que, dentro del universo de divisas principales, la
logica de ruptura y continuidad de `macd_breakout` se adapta mejor que las
estrategias benchmark de reversion, reentrada RSI, medias o Bollinger.

### 6.2 Index

En `Index`, `enbolsa:macd_breakout` vuelve a destacar, con `100%` de bloques
positivos y un `Mean Return%` de `86.14%`. `enbolsa:fib_limit` queda cerca del
equilibrio agregado (`-0.28%`), aunque con una fuerte heterogeneidad entre
bloques, ya que uno de ellos es claramente favorable (`H4:D1`) y otro muy
desfavorable (`M30:H1`).

Los benchmarks siguen siendo en general negativos. El unico resultado positivo
aislado aparece en `rsi_3tf_momentum_reentry` dentro de `H4:D1`, pero no es
suficiente para revertir el balance del grupo.

### 6.3 Metals

`Metals` es el grupo mas equilibrado. Ambas estrategias ENBOLSA son positivas:

- `enbolsa:fib_limit`: `Mean Return% = 22.45%`
- `enbolsa:macd_breakout`: `Mean Return% = 32.11%`

En este grupo aparece el unico benchmark con un comportamiento competitivo:
`ma_cross_3tf_trend`, que alcanza `Mean Return% = 108.87%` y `66.7%` de bloques
positivos. Esto indica que, al menos en metales, una regla clasica de
continuacion por cruce de medias puede capturar tendencias con mayor eficacia
que en otros grupos.

## 7. Resultados por pareja temporal

La desagregacion por `tf_pair` aporta otra capa de interpretacion:

### 7.1 M30:H1

La pareja `M30:H1` es claramente la mas exigente para casi todos los
benchmarks. Todas las estrategias benchmark muestran resultados muy negativos en
media y mediana. `enbolsa:fib_limit` tambien sufre en este contexto
(`Mean Return% = -57.85%`), mientras que `enbolsa:macd_breakout` mantiene un
comportamiento positivo agregado (`58.14%`), aunque mas modesto y con mayor
variabilidad que en `H1:H4`.

### 7.2 H1:H4

`H1:H4` es la pareja temporal mas favorable para `enbolsa:macd_breakout`, con
un `Mean Return%` de `511.97%` y `100%` de bloques positivos. Este resultado
explica una parte sustancial de su ventaja global.

En la misma pareja aparece tambien el mejor bloque benchmark, correspondiente a
`ma_cross_3tf_trend` en `Metals`, aunque el agregado total de esta estrategia
en `H1:H4` sigue mostrando una mediana negativa.

### 7.3 H4:D1

La variante degradada `H4:D1` ofrece el contexto mas favorable para
`enbolsa:fib_limit`, con `Mean Return% = 47.63%` y dos bloques positivos de
tres. Asimismo, suaviza de forma visible las perdidas de varios benchmarks,
aunque solo `bb_3tf_pullback_reentry` y `rsi_3tf_momentum_reentry` consiguen
algun bloque positivo aislado.

En conjunto, estos resultados sugieren que el alargamiento del horizonte
temporal beneficia a las estrategias mas estructurales y reduce parte del ruido
presente en `M30:H1`.

## 8. Apoyo visual de la comparacion

La salida canonica incorpora nuevos graficos destinados a reforzar la lectura
de resultados sin recurrir a una equity global artificial:

- `heatmap_returnpct_por_bloque.png`
- `lineas_r_acumulada_por_trade.png`
- `histograma_densidad_returnpct_por_bloque.png`
- `heatmap_trade_pool_netprofit_activo_estrategia.png`

El grafico de lineas representa la `R` acumulada del `trade-pool` de cada
estrategia, ordenada por numero de trade. En este contexto, `R` se interpreta
como retorno normalizado por riesgo asumido en cada operacion, lo que facilita
la comparacion entre bloques heterogeneos procedentes de distintos grupos de
activos y combinaciones temporales. No debe interpretarse como el retorno
acumulado de una cartera unica ni como una equity curve operable, ya que mezcla
operaciones de bloques independientes. Su utilidad es diagnostica: permite
observar si el rendimiento agregado de cada estrategia progresa de manera
relativamente estable o si depende de un conjunto reducido de rachas
favorables.

Por su parte, el histograma permite visualizar de forma inmediata la
dispersion de los retornos por bloque y comprobar si una estrategia depende de
pocos bloques extremos o si mantiene un comportamiento mas homogeneo.

## 9. Analisis del pool de trades

El pool global de trades refuerza la lectura anterior:

- `enbolsa:macd_breakout` es la unica estrategia con `PF > 1` de forma
  suficientemente clara (`PF = 1.10`) y `ExpectancyR` positiva (`0.075`).
- `enbolsa:fib_limit` queda proxima al equilibrio (`PF = 0.98`), lo que
  coincide con su posicion intermedia en los agregados por bloque.
- Los cuatro benchmarks presentan `PF < 1` y `ExpectancyR` negativa.

Esto no sustituye a las metricas de cartera por bloque, pero si confirma que la
ventaja relativa de `macd_breakout` no depende unicamente de una anomalia en
una metrica aislada.

## 10. Resultados por activo y benchmark contextual

Los resultados por activo quedan exportados en:

- `tables/trade_pool_by_asset.csv`

Esta tabla permite identificar en que simbolos concretos se concentran las
ganancias y perdidas de cada estrategia. Su uso principal dentro del TFG debe
ser complementario y diagnostico, no sustitutorio del analisis por bloque.

Como referencia externa, el benchmark contextual `sp500_buy_hold` ofrece los
siguientes retornos sobre `US500`:

- `M30:H1`: `138.73%`
- `H1:H4`: `166.98%`
- `H4:D1`: `102.49%`

Estos valores sirven para contextualizar el comportamiento del grupo `Index`,
pero no deben mezclarse con la comparacion operativa principal, ya que no usan
ni la misma logica de entrada/salida ni el mismo tratamiento de riesgo por
operacion.

## 11. Limitaciones

Los resultados anteriores deben interpretarse teniendo presentes las siguientes
limitaciones:

1. No se modela swap.
2. Los benchmarks fueron disenados como referencias clasicas simples, no como
   estrategias optimizadas para maximizar rendimiento.
3. `TotalNetProfit` en tablas agregadas suma cuentas independientes y no
   representa el saldo final de una cartera unica.
4. Algunas estrategias ENBOLSA, especialmente `fib_limit` y `macd_breakout`,
   pueden registrar varias patas operativas asociadas a una misma logica de
   posicion, por lo que el pool de trades no equivale siempre a una lectura
   directa de posiciones completas.
5. Los resultados dependen de la coherencia entre base de datos MySQL,
   metadata de simbolos y cache local del entorno de backtest.
6. La ejecucion a cierre de vela, mantenida para preservar comparabilidad con
   ENBOLSA, constituye una convencion de backtest ligeramente optimista frente
   a una ejecucion estricta en apertura de la vela siguiente.
7. En ENBOLSA, el sizing de bloque funciona como portfolio multi-simbolo sin
   un limite explicito de riesgo abierto agregado. En consecuencia, bloques con
   retornos muy altos pueden estar amplificados por apilamiento simultaneo de
   setups.
8. La entrada `fib_limit` se modela como una orden resting en `0.618`
   ejecutada por toque del rango de la vela. Esta aproximacion es razonable en
   un backtest `OHLCV`, pero no resuelve la secuencia intrabar, la cola ni el
   slippage adicional de un barrido rapido del nivel.

## 12. Conclusiones

La evidencia obtenida en esta comparacion permite extraer tres conclusiones
principales.

En primer lugar, `enbolsa:macd_breakout` muestra una ventaja clara frente a los
benchmarks clasicos considerados. Es la unica estrategia con beneficio agregado
positivo, mediana de retorno positiva, `PF` superior a la unidad en el pool de
trades y una tasa de bloques positivos muy elevada.

En segundo lugar, `enbolsa:fib_limit` presenta un comportamiento mas irregular.
No supera de forma global a `macd_breakout`, pero si ofrece un rendimiento
relativamente mas robusto que la mayoria de benchmarks simples y resulta
especialmente competitivo en `Metals` y en la variante `H4:D1`.

En tercer lugar, los benchmarks clasicos utilizados en este estudio no
consiguen igualar de forma sistematica a ENBOLSA. Aunque `ma_cross_3tf_trend`
destaca localmente en `Metals`, el conjunto benchmark queda, en terminos
globales, por debajo de la propuesta ENBOLSA.

Por tanto, desde una perspectiva academica, la comparacion respalda que la
linea ENBOLSA, y en particular `macd_breakout`, aporta una estructura operativa
con valor diferencial frente a referencias clasicas sencillas, al menos bajo
las condiciones de datos, costes y universo consideradas en este TFG.

## 13. Artefactos canonicos asociados

El informe debe leerse junto con los siguientes artefactos canonicos:

- `final/tables/block_metrics.csv`
- `final/tables/aggregate_by_strategy.csv`
- `final/tables/aggregate_by_group.csv`
- `final/tables/aggregate_by_tf_pair.csv`
- `final/tables/trade_pool_global.csv`
- `final/tables/trade_pool_by_group.csv`
- `final/tables/trade_pool_by_asset.csv`
- `final/tables/sp500_buy_hold_context.csv`
- `final/charts/`
- `final/BENCHMARKS_ENBOLSA_REVIEW.ipynb`

Los directorios `partial-*` se conservan como inputs reproducibles por bloque.
La carpeta `final/` es la unica salida canonica para la memoria del TFG.
