"""Métricas de especialización y análisis de sesgo D1 (PLAN.md §6 y §6.1). Se ejecuta en local, sin GPU.

Entrada: las predicciones de notebooks/02_generacion_evaluacion.ipynb (dataset privado brenpc/tracegit-predicciones)
y el test de la v1.1 del dataset (revisión fijada). Salida: eval/resultados/especializacion_<etiqueta>_<fecha>.json
y .md (tablas para el informe).

Métricas por ejemplo:
  rouge_l          F1 de la subsecuencia común más larga, sobre palabras Unicode en minúsculas (implementación
                   propia: el tokenizador de rouge-score borra las tildes y la ñ).
  exactitud_ids    de los identificadores que menciona la respuesta, proporción que aparece en el diff.
                   Sin identificadores: no cuenta (NaN).
                   El diff de la instrucción está recortado, así que también el mensaje humano "falla" a veces:
                   la fila "humano" de las tablas es la referencia de ese techo.
  inventa_id       1 si menciona al menos un identificador que no está en el diff (alucinación).
  idioma_correcto  1 si la respuesta está en el idioma del commit (mismo detector que el dataset).
  plantilla_web    1 si la respuesta es una plantilla de la web de GitHub ("Add files via upload"...).
BLEU: sacrebleu corpus BLEU 13a por condición y por grupo.

Intervalos al 95 %: bootstrap por repositorio (1000 remuestreos, semilla 42). Los ejemplos de un mismo
repositorio no son independientes y el test tiene 12 repositorios, así que los intervalos son anchos a propósito.
Sesgo D1: fairlearn MetricFrame por idioma (es/en) y por estilo de repositorio; brecha = diferencia entre grupos.

Uso:  python eval/metricas_especializacion.py [--revision-pred SHA] [--etiqueta test_v1.1]
"""
import argparse
import json
import math
import re
import sys
import warnings
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import sacrebleu
from fairlearn.metrics import MetricFrame
from huggingface_hub import HfApi, hf_hub_download

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "dataset"))
sys.path.insert(0, str(RAIZ / "dataset" / "v1_1"))
from depurar import es_plantilla_web  # noqa: E402
from idioma import detectar  # noqa: E402

DATASET = dict(repo="brenpc/tracegit-commits", revision="42eed230d333d04b7ad196032a6fe1d88524e323",
               archivo="v1.1/test.jsonl")
REPO_PRED = "brenpc/tracegit-predicciones"
N_BOOT, SEMILLA = 1000, 42
METRICAS = ["rouge_l", "exactitud_ids", "inventa_id", "idioma_correcto", "plantilla_web"]
GRUPOS = ["idioma", "estilo_repo"]

# ---------------------------------------------------------------- métricas por ejemplo
RE_PALABRA = re.compile(r"\w+", re.UNICODE)


def palabras(t):
    return RE_PALABRA.findall(t.lower())


def rouge_l(pred, ref):
    a, b = palabras(pred), palabras(ref)
    if not a or not b:
        return 0.0
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0]
        for j, y in enumerate(b):
            cur.append(prev[j] + 1 if x == y else max(prev[j + 1], cur[j]))
        prev = cur
    lcs = prev[-1]
    if lcs == 0:
        return 0.0
    p, r = lcs / len(a), lcs / len(b)
    return 2 * p * r / (p + r)


RE_BACKTICK = re.compile(r"`([^`\n]{1,80})`")
RE_ID = re.compile(
    r"(?<![\w.])(?:[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+"   # punteado: modulo.func, app.js
    r"|[a-z]+[A-Z][A-Za-z0-9]*"                                         # camelCase
    r"|[A-Z][a-z0-9]+[A-Z][A-Za-z0-9]*"                                 # PascalCase compuesto
    r"|[A-Za-z0-9]+_[A-Za-z0-9_]+)"                                     # snake_case
    r"(?:\(\))?")
NO_ID = {"e.g", "i.e", "etc", "vs", "p.ej"}


def identificadores(texto):
    ids = set()
    for m in RE_BACKTICK.findall(texto):
        m = m.strip().strip("'\"").removesuffix("()")
        if m and " " not in m:
            ids.add(m)
    for m in RE_ID.findall(texto):
        m = m.removesuffix("()").rstrip(".")
        if m.lower() not in NO_ID and len(m) > 2:
            ids.add(m)
    return ids


def metricas_ejemplo(pred, ref, instruccion, idioma):
    ids = identificadores(pred)
    instr = instruccion.lower()
    presentes = [i for i in ids if i.lower() in instr]      # sin distinguir mayúsculas: "Launch.JSON"
    return {
        "rouge_l": rouge_l(pred, ref),
        "exactitud_ids": len(presentes) / len(ids) if ids else math.nan,
        "inventa_id": float(len(presentes) < len(ids)),
        "idioma_correcto": float(bool(pred.strip()) and detectar(pred)[0] == idioma),
        "plantilla_web": float(es_plantilla_web(pred)),
        "palabras": len(palabras(pred)),
    }


# ---------------------------------------------------------------- agregación con bootstrap por repositorio
def media(x):
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    return float(x.mean()) if len(x) else math.nan


def bootstrap_repos(df, estadistico, rng):
    """IC 95 % remuestreando repositorios completos. estadistico(df) -> float."""
    repos = df["repo"].unique()
    por_repo = {r: df[df["repo"] == r] for r in repos}
    vals = []
    for _ in range(N_BOOT):
        muestra = pd.concat([por_repo[r] for r in rng.choice(repos, len(repos), replace=True)])
        v = estadistico(muestra)
        if not math.isnan(v):
            vals.append(v)
    if len(vals) < N_BOOT * 0.5:
        return [math.nan, math.nan]
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


def bleu(df):
    if df.empty:
        return math.nan
    return sacrebleu.corpus_bleu(df["prediccion"].tolist(), [df["referencia"].tolist()]).score


def r(x, d=3):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(x, d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--etiqueta", default="test_v1.1")
    ap.add_argument("--revision-pred", default=None, help="SHA de brenpc/tracegit-predicciones (por defecto, main)")
    ap.add_argument("--dir-pred", default=None, help="carpeta local con preds_*.jsonl (pruebas, sin el Hub)")
    args = ap.parse_args()
    warnings.filterwarnings("ignore", category=RuntimeWarning)

    if args.dir_pred:
        rev_pred = f"local:{args.dir_pred}"
        archivos = [f"{args.etiqueta}/{p.name}" for p in Path(args.dir_pred).glob("preds_*.jsonl")]
        leer_pred = lambda c: Path(args.dir_pred) / f"preds_{c}.jsonl"  # noqa: E731
    else:
        api = HfApi()
        rev_pred = args.revision_pred or api.dataset_info(REPO_PRED).sha
        archivos = [f for f in api.list_repo_files(REPO_PRED, repo_type="dataset", revision=rev_pred)
                    if f.startswith(f"{args.etiqueta}/preds_") and f.endswith(".jsonl")]
        leer_pred = lambda c: hf_hub_download(REPO_PRED, f"{args.etiqueta}/preds_{c}.jsonl",  # noqa: E731
                                              repo_type="dataset", revision=rev_pred)
    condiciones = sorted((f.split("preds_")[1][:-6] for f in archivos), key=lambda c: (c != "base", c))
    test = [json.loads(l) for l in open(hf_hub_download(DATASET["repo"], DATASET["archivo"], repo_type="dataset",
                                                        revision=DATASET["revision"]), encoding="utf-8")]
    por_sha = {x["meta"]["sha"]: x for x in test}

    filas = []
    for c in ["humano"] + condiciones:
        if c == "humano":            # el mensaje real como respuesta: referencia de identificadores e idioma
            preds = [{"sha": s, "prediccion": x["messages"][-1]["content"], "truncada": False} for s, x in por_sha.items()]
        else:
            preds = [json.loads(l) for l in open(leer_pred(c), encoding="utf-8")]
        for p in preds:
            x = por_sha[p["sha"]]
            m = metricas_ejemplo(p["prediccion"], x["messages"][-1]["content"], x["messages"][1]["content"],
                                 x["meta"]["idioma"])
            filas.append({"condicion": c, "sha": p["sha"], "repo": x["meta"]["repo"], "idioma": x["meta"]["idioma"],
                          "estilo_repo": x["meta"]["estilo_repo"], "lenguaje": x["meta"]["lenguaje"],
                          "prediccion": p["prediccion"], "referencia": x["messages"][-1]["content"],
                          "truncada": float(p.get("truncada", False)), **m})
    df = pd.DataFrame(filas)
    faltan = {c: len(test) - int((df["condicion"] == c).sum()) for c in condiciones}
    assert not any(faltan.values()), f"predicciones incompletas: {faltan}"

    rng = np.random.default_rng(SEMILLA)
    res = {"fecha": date.today().isoformat(), "etiqueta": args.etiqueta,
           "dataset": f"{DATASET['repo']}@{DATASET['revision']}:{DATASET['archivo']}",
           "predicciones": f"{REPO_PRED}@{rev_pred}", "ejemplos": len(test),
           "repos_test": int(df["repo"].nunique()), "bootstrap": f"{N_BOOT} remuestreos por repositorio, semilla {SEMILLA}",
           "global": {}, "diferencias_contra_base": {}, "d1": {}}

    # --- global por condición
    for c in ["humano"] + condiciones:
        d = df[df["condicion"] == c]
        g = {}
        for k in METRICAS + ["palabras", "truncada"]:
            if c == "humano" and k == "rouge_l":
                continue
            g[k] = {"valor": r(media(d[k])), "ic95": [r(v) for v in bootstrap_repos(d, lambda s, k=k: media(s[k]), rng)]}
        if c != "humano":
            g["bleu"] = {"valor": r(bleu(d), 2), "ic95": [r(v, 2) for v in bootstrap_repos(d, bleu, rng)]}
        g["con_identificadores"] = int(d["exactitud_ids"].notna().sum())
        res["global"][c] = g

    # --- diferencia pareada adaptador - base (mismo remuestreo de repositorios para ambos)
    base = df[df["condicion"] == "base"].set_index("sha")
    for c in condiciones:
        if c == "base":
            continue
        a = df[df["condicion"] == c].set_index("sha")
        par = a[["repo"]].copy()
        for k in METRICAS:
            par[k] = a[k] - base.loc[a.index, k]
        par["prediccion"], par["referencia"] = a["prediccion"], a["referencia"]
        dif = {k: {"valor": r(media(par[k])),
                   "ic95": [r(v) for v in bootstrap_repos(par, lambda s, k=k: media(s[k]), rng)]} for k in METRICAS}
        bb = bootstrap_repos(par.assign(p_b=base.loc[a.index, "prediccion"]),
                             lambda s: bleu(s) - bleu(s.assign(prediccion=s["p_b"])), rng)
        dif["bleu"] = {"valor": r(bleu(a) - bleu(base), 2), "ic95": [r(v, 2) for v in bb]}
        res["diferencias_contra_base"][f"{c}-base"] = dif

    # --- D1: desagregación por grupo con fairlearn y brecha con IC
    for c in condiciones:
        d = df[df["condicion"] == c].reset_index(drop=True)
        res["d1"][c] = {}
        for grupo in GRUPOS:
            # Cada métrica ya es un valor por ejemplo: MetricFrame recibe esa columna como y_true y promedia por grupo.
            por_grupo = {k: MetricFrame(metrics=lambda yt, yp: media(yt), y_true=d[k], y_pred=d[k],
                                        sensitive_features=d[grupo]) for k in METRICAS}
            niveles = sorted(d[grupo].unique())
            out = {"n": {g: int((d[grupo] == g).sum()) for g in niveles}, "metricas": {}}
            for k, f in por_grupo.items():
                vals = {g: r(float(f.by_group[g])) for g in niveles}
                if len(niveles) == 2:
                    g1, g2 = niveles
                    ic = bootstrap_repos(d, lambda s, k=k: media(s.loc[s[grupo] == g1, k]) - media(s.loc[s[grupo] == g2, k]), rng)
                    out["metricas"][k] = {"por_grupo": vals, "brecha": f"{g1}-{g2}",
                                          "valor": r(vals[g1] - vals[g2] if None not in (vals[g1], vals[g2]) else math.nan),
                                          "ic95": [r(v) for v in ic], "diferencia_fairlearn": r(float(f.difference()))}
                else:
                    out["metricas"][k] = {"por_grupo": vals, "diferencia_fairlearn": r(float(f.difference()))}
            bl = {g: r(bleu(d[d[grupo] == g]), 2) for g in niveles}
            out["metricas"]["bleu"] = {"por_grupo": bl}
            res["d1"][c][grupo] = out

    # --- grupo peor por idioma para cada adaptador (define la mitigación del v2)
    for c in condiciones:
        m = res["d1"][c]["idioma"]["metricas"]["rouge_l"]
        lo, hi = m["ic95"]
        signif = lo is not None and (lo > 0 or hi < 0)
        peor = min(m["por_grupo"], key=m["por_grupo"].get)
        res["d1"][c]["idioma"]["grupo_peor_rouge_l"] = {"grupo": peor, "brecha_significativa": bool(signif)}

    salida = RAIZ / "eval" / "resultados" / f"especializacion_{args.etiqueta.replace('.', '_')}_{res['fecha']}"
    salida.with_suffix(".json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    salida.with_suffix(".md").write_text(tablas_md(res, condiciones), encoding="utf-8")
    print(tablas_md(res, condiciones))
    print("guardado en", salida.with_suffix(".json"))


def fmt(m, pct=False, d=3):
    if not m or m.get("valor") is None:
        return "—"
    f = (lambda v: f"{100 * v:.1f}") if pct else (lambda v: f"{v:.{d}f}")
    lo, hi = m.get("ic95", [None, None])
    return f(m["valor"]) + (f" [{f(lo)}, {f(hi)}]" if lo is not None else "")


def tablas_md(res, condiciones):
    L = [f"# Especialización y sesgo D1 · {res['etiqueta']} · {res['fecha']}", "",
         f"Dataset `{res['dataset']}` · predicciones `{res['predicciones']}` · {res['ejemplos']} ejemplos de "
         f"{res['repos_test']} repositorios · IC 95 %: {res['bootstrap']}.", "",
         "## 1. Global", "",
         "| condición | ROUGE-L | BLEU | exactitud de ids | inventa id (%) | idioma correcto (%) | plantilla web (%) | palabras | truncadas (%) |",
         "|---|---|---|---|---|---|---|---|---|"]
    for c in ["humano"] + condiciones:
        g = res["global"][c]
        L.append(f"| {c} | {fmt(g.get('rouge_l'))} | {fmt(g.get('bleu'), d=2)} | {fmt(g['exactitud_ids'])} | "
                 f"{fmt(g['inventa_id'], True)} | {fmt(g['idioma_correcto'], True)} | {fmt(g['plantilla_web'], True)} | "
                 f"{fmt(g['palabras'], d=1)} | {fmt(g['truncada'], True)} |")
    L += ["", "`humano` es el mensaje real tomado como respuesta: sirve de referencia para identificadores e idioma.",
          "La exactitud de identificadores se calcula solo sobre las respuestas que mencionan alguno.", "",
          "## 2. Diferencia contra el modelo base (pareada)", "",
          "| comparación | ROUGE-L | BLEU | exactitud de ids | inventa id (pp) | idioma correcto (pp) | plantilla web (pp) |",
          "|---|---|---|---|---|---|---|"]
    for k, d in res["diferencias_contra_base"].items():
        L.append(f"| {k} | {fmt(d['rouge_l'])} | {fmt(d['bleu'], d=2)} | {fmt(d['exactitud_ids'])} | "
                 f"{fmt(d['inventa_id'], True)} | {fmt(d['idioma_correcto'], True)} | {fmt(d['plantilla_web'], True)} |")
    L += ["", "## 3. Sesgo D1: desagregación por grupo", ""]
    for grupo in GRUPOS:
        L += [f"### Por {grupo.replace('_', ' ')}", "",
              "| condición | métrica | " + " | ".join(f"{g} (n)" for g in res["d1"][condiciones[0]][grupo]["n"]) +
              " | brecha [IC 95 %] |", "|---|---|" + "---|" * len(res["d1"][condiciones[0]][grupo]["n"]) + "---|"]
        for c in condiciones:
            o = res["d1"][c][grupo]
            for k in ["rouge_l", "exactitud_ids", "idioma_correcto", "inventa_id", "bleu"]:
                m = o["metricas"][k]
                celdas = " | ".join(f"{m['por_grupo'][g]} ({o['n'][g]})" for g in o["n"])
                brecha = (f"{m['brecha']}: {fmt(m)}" if "brecha" in m else "—")
                L.append(f"| {c} | {k} | {celdas} | {brecha} |")
        L.append("")
    L += ["## 4. Grupo peor por idioma (ROUGE-L)", ""]
    for c in condiciones:
        g = res["d1"][c]["idioma"]["grupo_peor_rouge_l"]
        L.append(f"- {c}: **{g['grupo']}** (brecha {'significativa' if g['brecha_significativa'] else 'no significativa'} al 95 %)")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
