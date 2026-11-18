---
language: [es, en]
license: other
license_name: licencias-permisivas-de-origen
license_details: "Cada ejemplo conserva la licencia de su repositorio de origen (MIT, Apache-2.0 o BSD), indicada en meta.licencia junto con el repositorio y el SHA."
task_categories: [text-generation]
tags: [git, commits, code, instruction-tuning, spanish]
pretty_name: TraceGit commits humanos (anteriores a 2022-11-30)
size_categories: [1K<n<10K]
---

# TraceGit: commits humanos para describir cambios de código

Dataset de pares instrucción/respuesta construido por el Grupo 3 de ISIA-119 (2026-II) para especializar con
QLoRA un modelo que **describe cambios de código** (paso *map* de TraceGit). La instrucción es un diff de git
con sus estadísticas; la respuesta es el **mensaje de commit escrito por una persona**.

Código del minador: `dataset/` del repositorio https://github.com/brenpc1443/tracegit. El algoritmo completo
(etapas, filtros en orden, parámetros y registro de la corrida) está en `docs/ALGORITMO_MINADO.md`.

## Resumen

| split | ejemplos | repos | es | en | tokens instr. (media) | tokens instr. (p95) | tokens resp. (media) | diff recortado |
|---|---|---|---|---|---|---|---|---|
| train | 3080 | 86 | 1930 | 1150 | 670 | 1020 | 13 | 1383 |
| validation | 459 | 14 | 227 | 232 | 616 | 1009 | 8 | 168 |
| test | 386 | 13 | 277 | 109 | 687 | 1012 | 12 | 194 |

La partición es **por dueño del repositorio**: todos los repositorios de una misma cuenta van al mismo split, así
que ni un repositorio ni el estilo de un autor aparecen en dos splits. Está estratificada por el idioma y el
lenguaje de programación mayoritarios de cada dueño, y cada dueño aporta como máximo 120 ejemplos.

## Procedencia

- **Fuente:** repositorios públicos de GitHub encontrados con la API de búsqueda (`dataset/buscar_repos.py`;
  lista completa en `dataset/candidatos.csv`). Lenguajes: python, javascript, typescript, java. Licencias: mit, apache-2.0, bsd-2-clause, bsd-3-clause
  (licencia detectada por GitHub, `spdx_id`). Sin forks.
- **Ventana temporal:** solo commits con fecha de autor **y** de *committer* anteriores al
  **2022-11-30** (lanzamiento de ChatGPT), para que la respuesta sea humana.
- **Tamaño del repositorio:** de 20 a 500 commits sin merge antes del corte
  (proyectos tipo curso). Como máximo 60 ejemplos por repositorio (muestra aleatoria, semilla 42)
  y como mínimo 5.
- **Repositorios procesados:** 258 (fuera_de_rango_commits: 135, aceptado: 114, pocos_ejemplos: 8, error: 1).
  Detalle por repositorio en `dataset/registro_repos.csv`.

Licencias en el dataset final: MIT (2396), Apache-2.0 (839), BSD-3-Clause (548), BSD-2-Clause (142).
Lenguajes: Python (1202), Java (1015), JavaScript (846), TypeScript (666), desconocido (196).

## Filtros

Commits descartados durante el minado (solo en repositorios dentro del rango de tamaño):

| motivo | commits |
|---|---|
| mensaje_corto | 2273 |
| mensaje_generico | 564 |
| diff_demasiado_grande | 400 |
| sin_diff_util | 146 |
| bot | 87 |
| idioma_no_es_en | 77 |
| mensaje_vacio | 50 |
| mensaje_merge_o_revert | 34 |
| mensaje_copiado_del_diff | 9 |
| mensaje_parece_codigo | 2 |

Descartes en la limpieza: duplicado_diff: 72, repo_con_pocos_tras_limpiar: 4, tope_por_dueno: 0.

- Sin merges ni reverts; sin commits de bots (dependabot, renovate, github-actions, etc.).
- Mensajes con menos de 3 palabras o genéricos (`update`, `fix`, `wip`, `cambios`...) descartados.
- Archivos excluidos del diff (aparecen en las estadísticas como `[omitido]`): lockfiles, minificados, mapas,
  carpetas generadas (`dist/`, `build/`, `node_modules/`...), binarios, imágenes y notebooks.
- Diffs de más de 40,000 caracteres descartados (refactors masivos).
- Duplicados exactos eliminados por la huella SHA-256 del diff normalizado.
- Texto normalizado a Unicode NFC.

## Privacidad (Ley N.° 29733)

- **Minimización:** el dataset no guarda autor, *committer* ni correos.
- Se eliminan los *trailers* `Signed-off-by`, `Co-authored-by` y similares.
- Reemplazos aplicados en mensajes y diffs: correos: 804, asignaciones_secretas: 103, menciones: 11, urls_con_credencial: 30, secretos: 47, mensajes_con_ref_pr_issue: 2.
  Los correos pasan a `<correo>`, las @menciones a `@usuario` y las claves o *tokens* detectados a `<secreto>`.
- Se quitan de la respuesta las referencias a PR e *issues* (`#123`, `GH-12`, enlaces), que no se pueden deducir
  del diff.

## Formato

Cada línea de `{train,validation,test}.jsonl` tiene `messages` (system, user y assistant) y `meta`
(repositorio, licencia, SHA, fecha, idioma, confianza del idioma, lenguaje, estilo del repositorio, líneas
cambiadas y tokens). La instrucción se recorta a 1024 tokens del tokenizer de
`google/gemma-4-E2B-it@4adf157`; el presupuesto se reparte entre archivos de forma justa.

## Atributos para el análisis de sesgo (D1)

- **Idioma** del mensaje, detectado con `lingua-language-detector` 2.1.1. Los mensajes ambiguos (confianza
  < 0,7) toman el idioma mayoritario de su repositorio (140 reasignados). Se
  guardan el idioma detectado y la confianza.
- **Estilo del repositorio:** `commits_grandes` si la mediana de líneas por commit del repositorio supera
  30.5 (la mediana entre repositorios); si no, `commits_pequenos`.
  Distribución: commits_grandes (1970), commits_pequenos (1955).

## Limitaciones

- La licencia es la que detecta GitHub en el estado actual del repositorio, no en la fecha de cada commit.
- La detección de idioma falla en mensajes muy cortos; los errores observados en la validación fueron mensajes
  de dos palabras.
- El filtro de fecha confía en las fechas de git, que se pueden falsificar; un commit con fecha anterior al corte
  podría tener texto generado por IA.
- Los repositorios en español están infrarrepresentados frente a GitHub en inglés, aunque se buscaron a propósito.
- La búsqueda de GitHub no es aleatoria: favorece los repositorios que su ranking considera relevantes.

## Uso previsto

Ajuste fino (QLoRA) de un modelo que describe cambios de código como paso interno de un sistema que genera
informes de proceso con evidencia citada. **No** sirve para decidir si un código fue escrito por una persona o
por una IA.
