"""Etapa 4: formato de chat con la instrucción recortada a 1024 tokens del tokenizer de Gemma 4.

Entrada:  data/processed/limpio.jsonl
Salidas:  data/final/{train,validation,test}.jsonl  (para Hugging Face Hub)
          dataset/estadisticas_formato.json          (versionado)

Formato de cada línea:
  {"messages": [{"role": "system", ...}, {"role": "user", ...}, {"role": "assistant", ...}],
   "meta": {"repo", "licencia", "sha", "fecha", "idioma", "lenguaje", "estilo_repo", ...}}

Uso:  python dataset/formatear.py
"""
import json
from collections import defaultdict

import numpy as np
import requests
from tokenizers import Tokenizer

from comun import CACHE_CLONES, DIR_DATASET, FINAL, MAX_TOKENS_INSTRUCCION, PROCESADO, PROPORCION, SYSTEM, TOKENIZER

MAX_ARCHIVOS_LISTADOS = 30
RESERVA_MARCAS = 12       # tokens reservados por archivo para cabecera y marca de recorte
MARCA = "\n[... diff recortado]\n"


def cargar_tokenizer():
    ruta = CACHE_CLONES / "tokenizer_gemma4" / f"tokenizer_{TOKENIZER['revision'][:7]}.json"
    if not ruta.exists():
        ruta.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://huggingface.co/{TOKENIZER['repo']}/resolve/{TOKENIZER['revision']}/tokenizer.json"
        r = requests.get(url, timeout=120); r.raise_for_status()
        ruta.write_bytes(r.content)
    return Tokenizer.from_file(str(ruta))


def n_tokens(tok, texto):
    return len(tok.encode(texto, add_special_tokens=False).ids)


def recortar(tok, texto, maximo):
    ids = tok.encode(texto, add_special_tokens=False).ids
    return (texto, False) if len(ids) <= maximo else (tok.decode(ids[:maximo]), True)


def tope_comun(longitudes, presupuesto):
    """Mayor tope c tal que sum(min(L_i, c)) <= presupuesto (reparto justo entre archivos)."""
    if sum(longitudes) <= presupuesto:
        return max(longitudes, default=0)
    lo, hi = 0, max(longitudes)
    while lo < hi:
        c = (lo + hi + 1) // 2
        if sum(min(l, c) for l in longitudes) <= presupuesto:
            lo = c
        else:
            hi = c - 1
    return lo


def instruccion(tok, e):
    archivos = e["archivos"]
    todas = [f"{a['tipo']} {a['ruta']} (+{a['mas']} -{a['menos']})" + (" [omitido]" if a["excluido"] else "")
             for a in archivos]

    def armar(n):
        lineas = todas[:n] + ([f"... y {len(todas) - n} archivos más"] if len(todas) > n else [])
        return "Archivos y estadísticas:\n" + "\n".join(lineas) + "\n\nDiff:\n"

    # La lista de archivos no puede comerse el presupuesto: como máximo la cuarta parte
    n = min(MAX_ARCHIVOS_LISTADOS, len(todas))
    cabecera = armar(n)
    while n > 1 and n_tokens(tok, cabecera) > MAX_TOKENS_INSTRUCCION // 4:
        n -= 1
        cabecera = armar(n)
    con_diff = [a for a in archivos if a["diff"].strip()]
    bloques = [f"--- {a['ruta']}\n{a['diff'].rstrip()}" for a in con_diff]
    libre = MAX_TOKENS_INSTRUCCION - n_tokens(tok, cabecera)
    # Cada archivo con diff debe recibir al menos ~96 tokens; si no alcanza, solo entran los primeros
    max_bloques = max(1, libre // (96 + RESERVA_MARCAS))
    bloques = bloques[:max_bloques]
    presupuesto = libre - RESERVA_MARCAS * len(bloques)
    longitudes = [n_tokens(tok, b) for b in bloques]
    tope = tope_comun(longitudes, max(presupuesto, 0))
    partes, recortado = [], len(bloques) < len(con_diff)
    for b in bloques:
        texto, corto = recortar(tok, b, tope)
        partes.append(texto + (MARCA if corto else "\n"))
        recortado |= corto or any(a.get("diff_recortado") for a in con_diff)
    return cabecera + "".join(partes).rstrip() + "\n", recortado


def main():
    tok = cargar_tokenizer()
    salidas = defaultdict(list)
    for linea in open(PROCESADO / "limpio.jsonl", encoding="utf-8"):
        e = json.loads(linea)
        user, recortado = instruccion(tok, e)
        salidas[e["split"]].append({
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user},
                         {"role": "assistant", "content": e["mensaje"]}],
            "meta": {k: e[k] for k in ("repo", "licencia", "sha", "fecha", "idioma", "idioma_detectado",
                                       "idioma_confianza", "lenguaje", "estilo_repo", "lineas")}
                    | {"diff_recortado": recortado, "tokens_instruccion": n_tokens(tok, user),
                       "tokens_respuesta": n_tokens(tok, e["mensaje"])},
        })

    FINAL.mkdir(parents=True, exist_ok=True)
    resumen = {"tokenizer": f"{TOKENIZER['repo']}@{TOKENIZER['revision']}", "max_tokens_instruccion":
               MAX_TOKENS_INSTRUCCION, "por_split": {}}
    for s in PROPORCION:
        filas = salidas.get(s, [])
        with open(FINAL / f"{s}.jsonl", "w", encoding="utf-8") as f:
            for x in filas:
                f.write(json.dumps(x, ensure_ascii=False) + "\n")
        ti = np.array([x["meta"]["tokens_instruccion"] for x in filas] or [0])
        tr = np.array([x["meta"]["tokens_respuesta"] for x in filas] or [0])
        resumen["por_split"][s] = {
            "ejemplos": len(filas),
            "tokens_instruccion": {"media": int(ti.mean()), "p50": int(np.median(ti)), "p95": int(np.percentile(ti, 95)),
                                   "max": int(ti.max())},
            "tokens_respuesta": {"media": int(tr.mean()), "p95": int(np.percentile(tr, 95)), "max": int(tr.max())},
            "con_diff_recortado": sum(x["meta"]["diff_recortado"] for x in filas),
        }
        assert ti.max() <= MAX_TOKENS_INSTRUCCION + 8, f"{s}: instrucción de {ti.max()} tokens"
    with open(DIR_DATASET / "estadisticas_formato.json", "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)
    print(json.dumps(resumen, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
