"""Dataset v1.1: depuración de la v1 sin rehacer el minado (docs/DEPURACION_V1_1.md).

Lee la v1 (data/final/{split}.jsonl, solo lectura) y escribe la v1.1 en data/v1_1/. Los splits no cambian
de dueño: un ejemplo sigue en el split en que estaba, así que la v1 y la v1.1 son comparables.

Filtros nuevos, en orden:
  1. plantilla_web_github: mensajes que GitHub escribe por defecto al editar desde la web
     ("Add files via upload", "Create README.md", "Update src/app.js", "Delete x", "Rename a to b").
     No los escribió una persona y el adaptador v1 aprendió a repetirlos.
  2. mensaje_repetido_en_repo: como máximo MAX_IDENTICOS_REPO mensajes idénticos (sin distinguir
     mayúsculas) por repositorio; se conservan al azar con la semilla 42.
  3. repo_con_pocos_tras_depurar: se quitan los repositorios que quedan con menos de MIN_EJEMPLOS_REPO.

Uso:  python dataset/v1_1/depurar.py
"""
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from comun import DATOS, FINAL, MIN_EJEMPLOS_REPO, SEMILLA  # noqa: E402

VERSION = "v1.1"
SALIDA = DATOS / "v1_1"
DIR_V11 = Path(__file__).resolve().parent
SPLITS = ("train", "validation", "test")
MAX_IDENTICOS_REPO = 2

# Mensajes por defecto de la edición web de GitHub: verbo con mayúscula + una sola ruta con extensión o carpeta.
RE_PLANTILLA_WEB = re.compile(
    r"^(?:Add files via upload"
    r"|(?:Create|Update|Delete) \S*[./]\S*"
    r"|Rename \S*[./]\S* to \S*[./]\S*)$")


def es_plantilla_web(msg: str) -> bool:
    return bool(RE_PLANTILLA_WEB.match(msg.strip()))


def clave_mensaje(msg: str) -> str:
    return " ".join(msg.lower().split())


def depurar(filas, rng):
    """filas: lista de ejemplos (con 'split'). Devuelve (conservados, descartes, ejemplos_descartados)."""
    descartes, quitados = Counter(), []

    vivos = []
    for f in filas:
        if es_plantilla_web(f["messages"][-1]["content"]):
            descartes["plantilla_web_github"] += 1; quitados.append(("plantilla_web_github", f))
        else:
            vivos.append(f)

    grupos = defaultdict(list)
    for f in vivos:
        grupos[(f["meta"]["repo"], clave_mensaje(f["messages"][-1]["content"]))].append(f)
    vivos = []
    for clave in sorted(grupos):                      # orden fijo: reproducible
        g = grupos[clave]
        if len(g) > MAX_IDENTICOS_REPO:
            g = sorted(g, key=lambda x: x["meta"]["sha"])
            rng.shuffle(g)
            for f in g[MAX_IDENTICOS_REPO:]:
                descartes["mensaje_repetido_en_repo"] += 1; quitados.append(("mensaje_repetido_en_repo", f))
            g = g[:MAX_IDENTICOS_REPO]
        vivos.extend(g)

    por_repo = Counter(f["meta"]["repo"] for f in vivos)
    pequenos = {r for r, n in por_repo.items() if n < MIN_EJEMPLOS_REPO}
    conservados = []
    for f in vivos:
        if f["meta"]["repo"] in pequenos:
            descartes["repo_con_pocos_tras_depurar"] += 1; quitados.append(("repo_con_pocos_tras_depurar", f))
        else:
            conservados.append(f)
    return conservados, descartes, quitados


def resumen_split(filas):
    m = [f["meta"] for f in filas]
    return {"ejemplos": len(filas), "repos": len({x["repo"] for x in m}),
            "duenos": len({x["repo"].split("/")[0] for x in m}),
            "idioma": dict(Counter(x["idioma"] for x in m).most_common()),
            "lenguaje": dict(Counter(x["lenguaje"] for x in m).most_common()),
            "licencia": dict(Counter(x["licencia"] for x in m).most_common()),
            "estilo_repo": dict(Counter(x["estilo_repo"] for x in m).most_common())}


def main():
    filas = []
    for s in SPLITS:
        with open(FINAL / f"{s}.jsonl", encoding="utf-8") as fh:
            for linea in fh:
                f = json.loads(linea); f["split"] = s; filas.append(f)
    # El orden de entrada se fija por SHA para que el resultado no dependa del orden de los archivos.
    filas.sort(key=lambda f: (f["split"], f["meta"]["repo"], f["meta"]["sha"]))

    conservados, descartes, quitados = depurar(filas, random.Random(SEMILLA))

    SALIDA.mkdir(parents=True, exist_ok=True)
    for s in SPLITS:
        with open(SALIDA / f"{s}.jsonl", "w", encoding="utf-8", newline="\n") as fh:
            for f in (x for x in conservados if x["split"] == s):
                fh.write(json.dumps({"messages": f["messages"], "meta": f["meta"]}, ensure_ascii=False) + "\n")

    antes = Counter(f["split"] for f in filas)
    stats = {
        "version": VERSION, "base": "v1 (brenpc/tracegit-commits@8b5d79317fca720262bdb5334ed25e12442ef040)",
        "max_identicos_por_repo": MAX_IDENTICOS_REPO, "min_ejemplos_repo": MIN_EJEMPLOS_REPO, "semilla": SEMILLA,
        "descartes": dict(descartes),
        "descartes_por_split": {s: dict(Counter(m for m, f in quitados if f["split"] == s)) for s in SPLITS},
        "ejemplos_v1": {s: antes[s] for s in SPLITS},
        "por_split": {s: resumen_split([f for f in conservados if f["split"] == s]) for s in SPLITS},
        "repos_eliminados": sorted({f["meta"]["repo"] for m, f in quitados if m == "repo_con_pocos_tras_depurar"}),
        "mensajes_mas_descartados": [[m, n] for m, n in Counter(
            f["messages"][-1]["content"].strip() for _, f in quitados).most_common(10)],
    }
    with open(DIR_V11 / "estadisticas.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(stats, fh, ensure_ascii=False, indent=2)
    print(json.dumps({k: stats[k] for k in ("descartes", "ejemplos_v1")}, ensure_ascii=False))
    print({s: stats["por_split"][s]["ejemplos"] for s in SPLITS})


if __name__ == "__main__":
    main()
