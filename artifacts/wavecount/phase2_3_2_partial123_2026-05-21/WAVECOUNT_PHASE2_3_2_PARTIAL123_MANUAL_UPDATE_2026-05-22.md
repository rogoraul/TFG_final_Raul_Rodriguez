# WaveCount Fase 2.3.2 - Actualizacion manual

Fecha: 2026-05-22

Esta actualizacion incorpora la revision manual del usuario sobre los tres parciales clave. No cambia reglas, pivotes, grados, ABC, estrategias ni senales.

## Casos

### partial_123_index_aus200_h1_intermediate_partial123_001

- lectura: No deberia entrar un conteo Elliott: senales cortas, debiles y sin continuacion.
- etiqueta manual: `no_elliott_count_weak_no_continuation`
- rol: `negative_example`
- accion: `do_not_use_as_partial123_positive_case`
- nota: No basta con cuatro pivotes alternantes si el tramo es corto, debil y no deja continuacion hacia 4-5.

### partial_123_forex_audjpy_h1_minor_partial123_007

- lectura: Podria considerarse decente, pero no gusta demasiado porque cuenta ondas en un mercado lateral de correccion.
- etiqueta manual: `ambiguous_partial_in_corrective_range`
- rol: `ambiguous_example`
- accion: `keep_as_ambiguous_not_positive_case`
- nota: Un parcial en rango/correccion lateral puede ser geometricamente plausible, pero no debe usarse como ejemplo positivo claro.

### partial_123_metals_xagusd_h1_minor_partial123_002

- lectura: Mismo problema que 015: no deberia entrar conteo Elliott por debilidad/falta de continuacion. A favor del caso, alrededor del 1 de marzo empezo la guerra de Iran y genero oscilacion drastica de precios.
- etiqueta manual: `no_elliott_count_event_volatility`
- rol: `negative_example_with_event_context`
- accion: `do_not_use_as_partial123_positive_case`
- nota: La volatilidad/evento puede explicar oscilaciones bruscas, pero no convierte una estructura debil en conteo Elliott limpio.

## Decision

015 y 018 quedan como ejemplos negativos de estructuras debiles/sin continuacion. 017 queda como ejemplo ambiguo: puede ser decente geometricamente, pero esta en rango/correccion lateral y no debe usarse como caso positivo claro.
