"""Genera la dataset card (dataset/DATASET_CARD.md y data/final/README.md para Hugging Face Hub).

Usa las estadísticas versionadas: registro_repos.csv, estadisticas_limpieza.json y estadisticas_formato.json.
Uso:  python dataset/generar_card.py
"""
import csv
import json
from collections import Counter

from comun import (CORTE, DIR_DATASET, FINAL, LENGUAJES, LICENCIAS, MAX_CHARS_DIFF_TOTAL, MAX_COMMITS_REPO,
                   MAX_EJEMPLOS_REPO, MIN_COMMITS_REPO, MIN_EJEMPLOS_REPO, TOKENIZER)


def tabla(filas, cabecera):
    out = ["| " + " | ".join(cabecera) + " |", "|" + "---|" * len(cabecera)]
    out += ["| " + " | ".join(str(c) for c in f) + " |" for f in filas]
    return "\n".join(out)


def main():
    reg = list(csv.DictReader(open(DIR_DATASET / "registro_repos.csv", encoding="utf-8")))
    lim = json.load(open(DIR_DATASET / "estadisticas_limpieza.json", encoding="utf-8"))
    fmt = json.load(open(DIR_DATASET / "estadisticas_formato.json", encoding="utf-8"))

    estados = Counter(r["estado"] if not r["estado"].startswith("error") else "error" for r in reg)
    motivos = Counter()
    for r in reg:
        if r["motivos"]:
            motivos.update(json.loads(r["motivos"]))
    aceptados = [r for r in reg if r["estado"] == "aceptado"]

    splits = ["train", "validation", "test"]
    filas_split = []
    for s in splits:
        p, f = lim["por_split"][s], fmt["por_split"][s]
        filas_split.append([s, p["ejemplos"], p["repos"], p["idioma"].get("es", 0), p["idioma"].get("en", 0),
                            f["tokens_instruccion"]["media"], f["tokens_instruccion"]["p95"],
                            f["tokens_respuesta"]["media"], f["con_diff_recortado"]])
    lenguajes = Counter(); licencias = Counter(); estilos = Counter()
    for s in splits:
        lenguajes.update(lim["por_split"][s]["lenguaje"]); licencias.update(lim["por_split"][s]["licencia"])
        estilos.update(lim["por_split"][s]["estilo_repo"])

    md = f"""---
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

{tabla(filas_split, ["split", "ejemplos", "repos", "es", "en", "tokens instr. (media)", "tokens instr. (p95)", "tokens resp. (media)", "diff recortado"])}

La partición es **por dueño del repositorio**: todos los repositorios de una misma cuenta van al mismo split, así
que ni un repositorio ni el estilo de un autor aparecen en dos splits. Está estratificada por el idioma y el
lenguaje de programación mayoritarios de cada dueño, y cada dueño aporta como máximo 120 ejemplos.

## Procedencia

- **Fuente:** repositorios públicos de GitHub encontrados con la API de búsqueda (`dataset/buscar_repos.py`;
  lista completa en `dataset/candidatos.csv`). Lenguajes: {", ".join(LENGUAJES)}. Licencias: {", ".join(LICENCIAS)}
  (licencia detectada por GitHub, `spdx_id`). Sin forks.
- **Ventana temporal:** solo commits con fecha de autor **y** de *committer* anteriores al
  **{CORTE.date().isoformat()}** (lanzamiento de ChatGPT), para que la respuesta sea humana.
- **Tamaño del repositorio:** de {MIN_COMMITS_REPO} a {MAX_COMMITS_REPO} commits sin merge antes del corte
  (proyectos tipo curso). Como máximo {MAX_EJEMPLOS_REPO} ejemplos por repositorio (muestra aleatoria, semilla 42)
  y como mínimo {MIN_EJEMPLOS_REPO}.
- **Repositorios procesados:** {len(reg)} ({", ".join(f"{k}: {v}" for k, v in estados.most_common())}).
  Detalle por repositorio en `dataset/registro_repos.csv`.

Licencias en el dataset final: {", ".join(f"{k} ({v})" for k, v in licencias.most_common())}.
Lenguajes: {", ".join(f"{k} ({v})" for k, v in lenguajes.most_common())}.

## Filtros

Commits descartados durante el minado (solo en repositorios dentro del rango de tamaño):

{tabla(motivos.most_common(), ["motivo", "commits"])}

Descartes en la limpieza: {", ".join(f"{k}: {v}" for k, v in lim["descartes_en_limpieza"].items()) or "ninguno"}.

- Sin merges ni reverts; sin commits de bots (dependabot, renovate, github-actions, etc.).
- Mensajes con menos de 3 palabras o genéricos (`update`, `fix`, `wip`, `cambios`...) descartados.
- Archivos excluidos del diff (aparecen en las estadísticas como `[omitido]`): lockfiles, minificados, mapas,
  carpetas generadas (`dist/`, `build/`, `node_modules/`...), binarios, imágenes y notebooks.
- Diffs de más de {MAX_CHARS_DIFF_TOTAL:,} caracteres descartados (refactors masivos).
- Duplicados exactos eliminados por la huella SHA-256 del diff normalizado.
- Texto normalizado a Unicode NFC.

## Privacidad (Ley N.° 29733)

- **Minimización:** el dataset no guarda autor, *committer* ni correos.
- Se eliminan los *trailers* `Signed-off-by`, `Co-authored-by` y similares.
- Reemplazos aplicados en mensajes y diffs: {", ".join(f"{k}: {v}" for k, v in lim["reemplazos_privacidad"].items()) or "ninguno"}.
  Los correos pasan a `<correo>`, las @menciones a `@usuario` y las claves o *tokens* detectados a `<secreto>`.
- Se quitan de la respuesta las referencias a PR e *issues* (`#123`, `GH-12`, enlaces), que no se pueden deducir
  del diff.

## Formato

Cada línea de `{{train,validation,test}}.jsonl` tiene `messages` (system, user y assistant) y `meta`
(repositorio, licencia, SHA, fecha, idioma, confianza del idioma, lenguaje, estilo del repositorio, líneas
cambiadas y tokens). La instrucción se recorta a {fmt["max_tokens_instruccion"]} tokens del tokenizer de
`{TOKENIZER["repo"]}@{TOKENIZER["revision"][:7]}`; el presupuesto se reparte entre archivos de forma justa.

## Atributos para el análisis de sesgo (D1)

- **Idioma** del mensaje, detectado con `lingua-language-detector` 2.1.1. Los mensajes ambiguos (confianza
  < 0,7) toman el idioma mayoritario de su repositorio ({lim["idioma_reasignado_por_repo"]} reasignados). Se
  guardan el idioma detectado y la confianza.
- **Estilo del repositorio:** `commits_grandes` si la mediana de líneas por commit del repositorio supera
  {lim["corte_estilo_mediana_lineas"]} (la mediana entre repositorios); si no, `commits_pequenos`.
  Distribución: {", ".join(f"{k} ({v})" for k, v in estilos.most_common())}.

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
"""
    (DIR_DATASET / "DATASET_CARD.md").write_text(md, encoding="utf-8")
    FINAL.mkdir(parents=True, exist_ok=True)
    (FINAL / "README.md").write_text(md, encoding="utf-8")
    print("dataset/DATASET_CARD.md y data/final/README.md generados")


if __name__ == "__main__":
    main()
