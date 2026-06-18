# WaveCount Fase 2.4.2 - auditoria de contexto/calidad

Fecha: 2026-05-23

## Alcance

Se cruza la galeria Fase 2.4 con el cierre visual Fase 2.3.4.
No se cambian conteos, pivotes, grados, EMAs/EWO, estrategias ni backtests.

## Resultados H4/D1

- Casos H4/D1 revisados: 54.
- Casos donde el contexto puede ser regla blanda: 6.
- Casos donde el contexto ayuda pero necesita validacion manual futura: 6.
- Casos que el contexto no debe rescatar: 24.

## Lectura

- EMAs 50/150 aportan mas como contexto de regimen y ambiguedad que como filtro duro.
- D1/HTF ayuda a distinguir impulso alineado, correccion contra regimen y transicion, pero puede llegar tarde.
- EWO 5-35 es util para momentum de onda 3 y perdida/divergencia de onda 5, pero no debe cambiar conteos cerrados.
- ABC sigue experimental en la vista integrada: no debe usarse para reglas Fase 2.5 hasta una seleccion limpia.
- Fase 2.4 no rescata conteos excluidos en 2.3.4.

## Control auxiliar

- Casos auxiliares H1/M30 revisados: 54.
- Casos M30 dentro del control auxiliar: 2.
- H1/H4 puede refinar lectura; M30/H1 queda como microestructura o banco de fallos.

## Decision

H4/D1 Fase 2.4 queda cerrada como capa de contexto diagnostico.
Tiene sentido pasar despues a Fase 2.5 solo con reglas blandas, no con filtros duros.

## Validacion

- Tiempo de ejecucion: 7.85s.
- Las tablas CSV tienen indices Markdown para abrir imagenes rapidamente.
