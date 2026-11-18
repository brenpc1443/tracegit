"""Etapa 2: clona cada candidato y extrae con PyDriller los commits que cumplen los filtros.

Salidas:
  data/raw/crudo.jsonl          un commit por línea (ignorado por git: se publica en Hugging Face)
  dataset/registro_repos.csv    por repo: commits contados, aceptados y motivos de descarte (versionado)
Se puede cortar y retomar: los repos ya registrados se saltan.

Uso:  python dataset/minar.py [--objetivo 4000] [--objetivo-es 1200] [--max-repos N] [--conservar-clones]
"""
import argparse
import csv
import json
import os
import random
import shutil
import stat
import statistics
import subprocess
import time
from collections import Counter

from pydriller import Repository

from comun import (CACHE_CLONES, CORTE, CRUDO, DIR_DATASET, MAX_CHARS_DIFF_ARCHIVO, MAX_CHARS_DIFF_TOTAL,
                   MAX_COMMITS_REPO, MAX_EJEMPLOS_REPO, MIN_COMMITS_REPO, MIN_EJEMPLOS_REPO, SEMILLA,
                   archivo_excluido, es_bot, limpiar_mensaje, mensaje_valido)
from idioma import detectar

REGISTRO = DIR_DATASET / "registro_repos.csv"
CAMPOS_REG = ["repo", "licencia", "lenguaje", "origen", "estado", "commits_antes_corte", "candidatos",
              "aceptados", "es", "en", "mediana_lineas_repo", "motivos", "segundos"]


def git(*args, cwd=None, timeout=300):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout)


def borrar(ruta):
    """rmtree robusto en Windows: los objetos de .git son de solo lectura."""
    def quitar_solo_lectura(func, p, _):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    if ruta.exists():
        shutil.rmtree(ruta, onerror=quitar_solo_lectura)


def ya_registrados():
    if not REGISTRO.exists():
        return set()
    with open(REGISTRO, encoding="utf-8") as f:
        return {r["repo"] for r in csv.DictReader(f)}


def registrar(fila):
    nuevo = not REGISTRO.exists()
    with open(REGISTRO, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_REG)
        if nuevo:
            w.writeheader()
        w.writerow(fila)


def intercalar(candidatos):
    """Orden de proceso: primero los de consultas en español y luego los generales; dentro de cada bloque,
    turnos entre (lenguaje, licencia). Sin esto, el orden de las consultas (Python y MIT primero) haría que el
    dataset fuera casi solo Python/MIT (visto en el minado del 18-11-2026)."""
    from itertools import zip_longest
    ordenados = []
    for bloque in (True, False):
        colas = {}
        for c in candidatos:
            if c["origen"].startswith("es:") == bloque:
                colas.setdefault((c["lenguaje"], c["licencia"]), []).append(c)
        for ronda in zip_longest(*colas.values()):
            ordenados.extend(c for c in ronda if c is not None)
    return ordenados


def copiado_del_diff(msg, archivos):
    """True si el asunto del mensaje es una línea añadida o borrada del diff (el autor pegó código)."""
    asunto = msg.split("\n", 1)[0].strip()
    if len(asunto) < 8:
        return False
    for a in archivos:
        for linea in a["diff"].splitlines():
            if linea[:1] in "+-" and linea[1:].strip() == asunto:
                return True
    return False


def extraer(ruta, cand, motivos):
    """Recorre los commits sin merge anteriores al corte y devuelve (ejemplos, lineas_por_commit)."""
    ejemplos, lineas = [], []
    for c in Repository(str(ruta), to=CORTE, only_no_merge=True).traverse_commits():
        if c.author_date >= CORTE or c.committer_date >= CORTE:      # historial reescrito después del corte
            motivos["fecha_posterior_al_corte"] += 1; continue
        lineas.append(c.insertions + c.deletions)
        if es_bot(c.author.name, c.author.email) or es_bot(c.committer.name, c.committer.email):
            motivos["bot"] += 1; continue
        msg = limpiar_mensaje(c.msg)
        motivo = mensaje_valido(msg)
        if motivo:
            motivos[motivo] += 1; continue
        archivos, total = [], 0
        try:
            modificados = c.modified_files
        except Exception:                              # commits corruptos o submódulos raros
            motivos["error_lectura"] += 1; continue
        for mf in modificados:
            ruta_arch = mf.new_path or mf.old_path or mf.filename
            excluido = archivo_excluido(ruta_arch)
            diff = "" if excluido else (mf.diff or "")
            archivos.append({"ruta": ruta_arch.replace("\\", "/"), "tipo": mf.change_type.name,
                             "mas": mf.added_lines, "menos": mf.deleted_lines, "excluido": excluido,
                             "diff": diff[:MAX_CHARS_DIFF_ARCHIVO], "diff_recortado": len(diff) > MAX_CHARS_DIFF_ARCHIVO})
            total += len(diff)
        if not any(a["diff"].strip() for a in archivos):
            motivos["sin_diff_util"] += 1; continue
        if total > MAX_CHARS_DIFF_TOTAL:
            motivos["diff_demasiado_grande"] += 1; continue
        if copiado_del_diff(msg, archivos):
            motivos["mensaje_copiado_del_diff"] += 1; continue
        idioma, conf = detectar(msg)
        if idioma not in ("es", "en"):
            motivos["idioma_no_es_en"] += 1; continue
        ejemplos.append({"repo": cand["repo"], "licencia": cand["licencia"], "lenguaje": cand["lenguaje"],
                         "sha": c.hash, "fecha": c.committer_date.isoformat(), "idioma": idioma,
                         "idioma_confianza": round(conf, 3), "lineas": c.insertions + c.deletions,
                         "mensaje": msg, "archivos": archivos})
    return ejemplos, lineas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--objetivo", type=int, default=4000, help="ejemplos aceptados en total")
    ap.add_argument("--objetivo-es", type=int, default=1200, help="ejemplos en español buscados")
    ap.add_argument("--max-repos", type=int, default=0, help="procesar como mucho N repos (prueba)")
    ap.add_argument("--tope-lenguaje", type=float, default=0.30, help="fracción máxima del objetivo por lenguaje")
    ap.add_argument("--conservar-clones", action="store_true")
    a = ap.parse_args()

    with open(DIR_DATASET / "candidatos.csv", encoding="utf-8") as f:
        candidatos = intercalar(list(csv.DictReader(f)))
    CRUDO.mkdir(parents=True, exist_ok=True); CACHE_CLONES.mkdir(parents=True, exist_ok=True)
    salida = CRUDO / "crudo.jsonl"
    hechos = ya_registrados()

    # Totales acumulados (para retomar)
    total, total_es, por_lenguaje = 0, 0, Counter()
    if salida.exists():
        for linea in open(salida, encoding="utf-8"):
            e = json.loads(linea); total += 1; total_es += e["idioma"] == "es"; por_lenguaje[e["lenguaje"]] += 1
    tope_lenguaje = int(a.tope_lenguaje * a.objetivo)
    rng = random.Random(SEMILLA)
    procesados = 0

    for cand in candidatos:
        if total >= a.objetivo and total_es >= a.objetivo_es:
            break
        if cand["repo"] in hechos:
            continue
        # Cubierto el cupo general, solo se siguen procesando candidatos de consultas en español
        if total >= a.objetivo and not cand["origen"].startswith("es:"):
            continue
        if por_lenguaje[cand["lenguaje"]] >= tope_lenguaje:      # equilibrio entre lenguajes
            continue
        if a.max_repos and procesados >= a.max_repos:
            break
        procesados += 1
        t0 = time.time()
        ruta = CACHE_CLONES / cand["repo"].replace("/", "__")
        fila = {k: "" for k in CAMPOS_REG} | {"repo": cand["repo"], "licencia": cand["licencia"],
                                              "lenguaje": cand["lenguaje"], "origen": cand["origen"]}
        motivos = Counter()
        try:
            if ruta.exists() and git("rev-parse", "--verify", "HEAD", cwd=ruta).returncode != 0:
                borrar(ruta)                              # clon roto o a medio borrar: se rehace
            if not ruta.exists():
                r = git("clone", "--quiet", "--no-tags", "--single-branch", cand["url"], str(ruta), timeout=240)
                if r.returncode != 0:
                    raise RuntimeError("clone: " + r.stderr.strip()[:120])
            n = git("rev-list", "--count", "--no-merges", f"--before={CORTE.isoformat()}", "HEAD", cwd=ruta)
            n = int(n.stdout.strip() or 0)
            fila["commits_antes_corte"] = n
            if not (MIN_COMMITS_REPO <= n <= MAX_COMMITS_REPO):
                fila["estado"] = "fuera_de_rango_commits"
            else:
                ejemplos, lineas = extraer(ruta, cand, motivos)
                fila["candidatos"] = len(ejemplos)
                fila["mediana_lineas_repo"] = statistics.median(lineas) if lineas else ""
                if len(ejemplos) < MIN_EJEMPLOS_REPO:
                    fila["estado"] = "pocos_ejemplos"
                else:
                    if len(ejemplos) > MAX_EJEMPLOS_REPO:
                        ejemplos = rng.sample(ejemplos, MAX_EJEMPLOS_REPO)
                    med = fila["mediana_lineas_repo"]
                    with open(salida, "a", encoding="utf-8") as f:
                        for e in ejemplos:
                            e["mediana_lineas_repo"] = med
                            f.write(json.dumps(e, ensure_ascii=False) + "\n")
                    n_es = sum(e["idioma"] == "es" for e in ejemplos)
                    total += len(ejemplos); total_es += n_es; por_lenguaje[cand["lenguaje"]] += len(ejemplos)
                    fila.update(estado="aceptado", aceptados=len(ejemplos), es=n_es, en=len(ejemplos) - n_es)
        except Exception as ex:                                   # un repo roto no detiene el minado
            fila["estado"] = "error: " + str(ex)[:150].replace("\n", " ")
        finally:
            if not a.conservar_clones:
                try:
                    borrar(ruta)
                except OSError as ex:
                    print(f"  no se pudo borrar {ruta}: {ex}")
        fila["motivos"] = json.dumps(dict(motivos), ensure_ascii=False)
        fila["segundos"] = round(time.time() - t0, 1)
        registrar(fila)
        print(f"{cand['repo'][:45]:45} {fila['estado'][:22]:22} +{fila['aceptados'] or 0:>3} "
              f"| total {total} (es {total_es})", flush=True)

    print(f"Fin: {total} ejemplos ({total_es} en español) en {salida}")


if __name__ == "__main__":
    main()
