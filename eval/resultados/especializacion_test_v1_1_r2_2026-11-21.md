# Especialización y sesgo D1 · test_v1.1_r2 · 2026-11-21

Dataset `brenpc/tracegit-commits@42eed230d333d04b7ad196032a6fe1d88524e323:v1.1/test.jsonl` · predicciones `brenpc/tracegit-predicciones@435beff3b8bebccc1ed00edaf4eba94411aabd89` · 375 ejemplos de 12 repositorios · IC 95 %: 1000 remuestreos por repositorio, semilla 42.

## 1. Global

| condición | ROUGE-L | BLEU | exactitud de ids | inventa id (%) | idioma correcto (%) | plantilla web (%) | palabras | truncadas (%) |
|---|---|---|---|---|---|---|---|---|
| humano | — | — | 0.726 [0.631, 0.830] | 5.3 [3.0, 7.9] | 97.6 [96.0, 99.0] | 0.0 [0.0, 0.0] | 8.7 [6.5, 10.6] | 0.0 [0.0, 0.0] |
| base | 0.058 [0.045, 0.075] | 0.29 [0.09, 0.50] | 0.983 [0.976, 0.990] | 7.7 [4.3, 11.2] | 49.9 [37.2, 66.3] | 0.0 [0.0, 0.0] | 46.1 [40.9, 51.3] | 30.1 [20.7, 39.8] |
| v1 | 0.080 [0.053, 0.118] | 0.70 [0.23, 1.65] | 1.000 [1.000, 1.000] | 0.0 [0.0, 0.0] | 50.9 [34.6, 74.0] | 32.0 [19.6, 43.9] | 4.9 [4.5, 5.4] | 0.8 [0.2, 1.8] |

`humano` es el mensaje real tomado como respuesta: sirve de referencia para identificadores e idioma.
La exactitud de identificadores se calcula solo sobre las respuestas que mencionan alguno.

## 2. Diferencia contra el modelo base (pareada)

| comparación | ROUGE-L | BLEU | exactitud de ids | inventa id (pp) | idioma correcto (pp) | plantilla web (pp) |
|---|---|---|---|---|---|---|
| v1-base | 0.022 [-0.005, 0.057] | 0.41 [-0.03, 1.33] | 0.004 [0.000, 0.008] | -7.7 [-11.3, -4.5] | 1.1 [-8.5, 13.2] | 32.0 [19.8, 43.3] |

## 3. Sesgo D1: desagregación por grupo

### Por idioma

| condición | métrica | en (n) | es (n) | brecha [IC 95 %] |
|---|---|---|---|---|
| base | rouge_l | 0.066 (99) | 0.055 (276) | en-es: 0.011 [-0.018, 0.046] |
| base | exactitud_ids | 0.986 (99) | 0.982 (276) | en-es: 0.004 [-0.012, 0.018] |
| base | idioma_correcto | 0.758 (99) | 0.406 (276) | en-es: 0.352 [-0.001, 0.603] |
| base | inventa_id | 0.061 (99) | 0.083 (276) | en-es: -0.022 [-0.076, 0.036] |
| base | bleu | 0.15 (99) | 0.33 (276) | — |
| v1 | rouge_l | 0.1 (99) | 0.072 (276) | en-es: 0.028 [-0.040, 0.071] |
| v1 | exactitud_ids | 1.0 (99) | 1.0 (276) | en-es: 0.000 [0.000, 0.000] |
| v1 | idioma_correcto | 0.838 (99) | 0.391 (276) | en-es: 0.447 [0.115, 0.702] |
| v1 | inventa_id | 0.0 (99) | 0.0 (276) | en-es: 0.000 [0.000, 0.000] |
| v1 | bleu | 0.58 (99) | 0.71 (276) | — |

### Por estilo repo

| condición | métrica | commits_grandes (n) | commits_pequenos (n) | brecha [IC 95 %] |
|---|---|---|---|---|
| base | rouge_l | 0.048 (242) | 0.075 (133) | commits_grandes-commits_pequenos: -0.027 [-0.059, 0.004] |
| base | exactitud_ids | 0.985 (242) | 0.979 (133) | commits_grandes-commits_pequenos: 0.006 [-0.007, 0.023] |
| base | idioma_correcto | 0.479 (242) | 0.534 (133) | commits_grandes-commits_pequenos: -0.055 [-0.394, 0.221] |
| base | inventa_id | 0.079 (242) | 0.075 (133) | commits_grandes-commits_pequenos: 0.004 [-0.058, 0.057] |
| base | bleu | 0.22 (242) | 0.42 (133) | — |
| v1 | rouge_l | 0.093 (242) | 0.056 (133) | commits_grandes-commits_pequenos: 0.037 [-0.013, 0.101] |
| v1 | exactitud_ids | 1.0 (242) | 1.0 (133) | commits_grandes-commits_pequenos: 0.000 [0.000, 0.000] |
| v1 | idioma_correcto | 0.5 (242) | 0.526 (133) | commits_grandes-commits_pequenos: -0.026 [-0.468, 0.364] |
| v1 | inventa_id | 0.0 (242) | 0.0 (133) | commits_grandes-commits_pequenos: 0.000 [0.000, 0.000] |
| v1 | bleu | 0.87 (242) | 0.42 (133) | — |

## 4. Grupo peor por idioma (ROUGE-L)

- base: **es** (brecha no significativa al 95 %)
- v1: **es** (brecha no significativa al 95 %)
