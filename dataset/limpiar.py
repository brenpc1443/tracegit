"""Etapa 3: privacidad, idioma, duplicados, estilo de commit y partición por repositorio.

Entrada:  data/raw/crudo.jsonl
Salidas:  data/processed/limpio.jsonl (con el campo "split")
          dataset/estadisticas_limpieza.json (versionado: alimenta la dataset card)

Uso:  python dataset/limpiar.py
"""
import hashlib
import json
import random
import re
import statistics
from collections import Counter, defaultdict

from comun import (CRUDO, DIR_DATASET, MIN_EJEMPLOS_REPO, PROCESADO, PROPORCION, SEMILLA, depurar_privacidad,
                   limpiar_mensaje, mensaje_valido, nfc)
from idioma import UMBRAL_AMBIGUO

MIN_ES_TEST = 100   # PLAN.md §6.1: sin esto la brecha es/en no tiene valor estadístico
MAX_EJEMPLOS_DUENO = 120


def huella_diff(archivos):
    texto = "\n".join(a["diff"] for a in archivos if a["diff"])
    return hashlib.sha256(re.sub(r"\s+", " ", texto).strip().encode("utf-8")).hexdigest()


def particionar(repos_por_grupo, n_por_repo, rng):
    """Asigna cada grupo (dueño) entero a un split; dentro de cada idioma se reparte por número de ejemplos."""
    asignacion = {}
    for grupo, repos in repos_por_grupo.items():
        repos = sorted(repos)
        rng.shuffle(repos)
        total = sum(n_por_repo[r] for r in repos)
        actual = Counter()
        for r in repos:
            deficit = {s: PROPORCION[s] * total - actual[s] for s in PROPORCION}
            s = max(deficit, key=deficit.get)
            asignacion[r] = s
            actual[s] += n_por_repo[r]
    return asignacion


def main():
    contador_priv, descartes = Counter(), Counter()
    ejemplos, vistos = [], set()
    for linea in open(CRUDO / "crudo.jsonl", encoding="utf-8"):
        e = json.loads(linea)
        e["lenguaje"] = e["lenguaje"] or "desconocido"            # GitHub no detectó lenguaje del repo
        e["mensaje"] = limpiar_mensaje(e["mensaje"], contador_priv)   # idempotente: ya venía limpio
        motivo = mensaje_valido(e["mensaje"])
        if motivo:
            descartes[motivo] += 1; continue
        for a in e["archivos"]:
            a["ruta"] = nfc(a["ruta"])
            a["diff"] = depurar_privacidad(nfc(a["diff"]), contador_priv, menciones=False)
        if not any(a["diff"].strip() for a in e["archivos"]):
            descartes["vacio"] += 1; continue
        h = huella_diff(e["archivos"])
        if h in vistos:
            descartes["duplicado_diff"] += 1; continue
        vistos.add(h)
        e["huella_diff"] = h
        ejemplos.append(e)

    # Idioma: los mensajes ambiguos toman el idioma mayoritario de su repositorio
    por_repo = defaultdict(list)
    for e in ejemplos:
        por_repo[e["repo"]].append(e)
    reasignados = 0
    idioma_repo = {}
    for repo, es_ in por_repo.items():
        seguros = Counter(e["idioma"] for e in es_ if e["idioma_confianza"] >= UMBRAL_AMBIGUO)
        mayoritario = seguros.most_common(1)[0][0] if seguros else Counter(e["idioma"] for e in es_).most_common(1)[0][0]
        idioma_repo[repo] = mayoritario
        for e in es_:
            e["idioma_detectado"] = e["idioma"]
            if e["idioma_confianza"] < UMBRAL_AMBIGUO and e["idioma"] != mayoritario:
                e["idioma"] = mayoritario; reasignados += 1

    # Repos que quedaron con muy pocos ejemplos tras deduplicar
    pequenos = {r for r, es_ in por_repo.items() if len(es_) < MIN_EJEMPLOS_REPO}
    descartes["repo_con_pocos_tras_limpiar"] = sum(len(por_repo[r]) for r in pequenos)
    ejemplos = [e for e in ejemplos if e["repo"] not in pequenos]
    for r in pequenos:
        por_repo.pop(r)

    # Estilo de commit del repo (D1): mediana de líneas por commit frente a la mediana de los repos
    medianas = {r: float(es_[0]["mediana_lineas_repo"]) for r, es_ in por_repo.items()
                if es_[0].get("mediana_lineas_repo") not in ("", None)}
    corte_estilo = statistics.median(medianas.values())
    for e in ejemplos:
        m = medianas.get(e["repo"])
        e["estilo_repo"] = "desconocido" if m is None else ("commits_grandes" if m > corte_estilo else "commits_pequenos")

    # Tope por dueño: un autor prolífico no debe dominar el dataset
    rng = random.Random(SEMILLA)
    por_dueno = defaultdict(list)
    for e in ejemplos:
        por_dueno[e["repo"].split("/")[0]].append(e)
    recortados = 0
    for d, es_ in por_dueno.items():
        if len(es_) > MAX_EJEMPLOS_DUENO:
            recortados += len(es_) - MAX_EJEMPLOS_DUENO
            por_dueno[d] = rng.sample(es_, MAX_EJEMPLOS_DUENO)
    ejemplos = [e for es_ in por_dueno.values() for e in es_]
    descartes["tope_por_dueno"] = recortados

    # Partición por DUEÑO (todos sus repos en el mismo split: su estilo no se filtra entre splits),
    # estratificada por el idioma mayoritario de sus ejemplos
    # Estrato = (idioma mayoritario, lenguaje mayoritario) del dueño: así cada split recibe los 4 lenguajes
    estrato = {d: (Counter(e["idioma"] for e in es_).most_common(1)[0][0],
                   Counter(e["lenguaje"] or "desconocido" for e in es_).most_common(1)[0][0])
               for d, es_ in por_dueno.items()}
    grupos = defaultdict(list)
    for d in por_dueno:
        grupos[estrato[d]].append(d)
    asignacion = particionar(grupos, {d: len(v) for d, v in por_dueno.items()}, rng)
    for e in ejemplos:
        e["split"] = asignacion[e["repo"].split("/")[0]]

    PROCESADO.mkdir(parents=True, exist_ok=True)
    with open(PROCESADO / "limpio.jsonl", "w", encoding="utf-8") as f:
        for e in ejemplos:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    resumen = {"ejemplos": len(ejemplos), "repos": len(por_repo), "descartes_en_limpieza": dict(descartes),
               "reemplazos_privacidad": dict(contador_priv), "idioma_reasignado_por_repo": reasignados,
               "corte_estilo_mediana_lineas": corte_estilo, "por_split": {}}
    for s in PROPORCION:
        sub = [e for e in ejemplos if e["split"] == s]
        resumen["por_split"][s] = {
            "ejemplos": len(sub), "repos": len({e["repo"] for e in sub}),
            "duenos": len({e["repo"].split("/")[0] for e in sub}),
            "idioma": dict(Counter(e["idioma"] for e in sub)),
            "lenguaje": dict(Counter(e["lenguaje"] for e in sub)),
            "licencia": dict(Counter(e["licencia"] for e in sub)),
            "estilo_repo": dict(Counter(e["estilo_repo"] for e in sub)),
        }
    es_test = resumen["por_split"]["test"]["idioma"].get("es", 0)
    resumen["aviso"] = None if es_test >= MIN_ES_TEST else f"test tiene {es_test} ejemplos en español (< {MIN_ES_TEST})"
    with open(DIR_DATASET / "estadisticas_limpieza.json", "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)
    print(json.dumps(resumen, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
