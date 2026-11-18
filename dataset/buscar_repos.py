"""Etapa 1: busca repositorios candidatos con la API de búsqueda de GitHub.

Salida: dataset/candidatos.csv (versionado: es la procedencia del dataset).
Primero van las consultas pensadas para encontrar repositorios en español; luego las generales.

Uso:  python dataset/buscar_repos.py
Token: variable GITHUB_TOKEN o, si no existe, `gh auth token` (GitHub CLI).
"""
import csv
import os
import shutil
import subprocess
import sys
import time

import requests

from comun import DIR_DATASET, LENGUAJES, LICENCIAS

GH_PORTABLE = r"C:\Users\HP\tools\gh\bin\gh.exe"
API = "https://api.github.com/search/repositories"
# Filtros comunes: repos propios (no forks), tamaño moderado y creados antes del corte.
BASE = "language:{leng} license:{lic} fork:false size:30..20000 created:2014-01-01..2022-06-30"
# Palabras frecuentes en descripciones de proyectos de curso en español.
PALABRAS_ES = ["proyecto", "universidad", "curso", "tarea", "practica", "sistema de", "aplicacion"]
POR_CONSULTA = 100


def token() -> str:
    if os.environ.get("GITHUB_TOKEN"):
        return os.environ["GITHUB_TOKEN"]
    gh = shutil.which("gh") or GH_PORTABLE
    return subprocess.run([gh, "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()


def consultas():
    for palabra in PALABRAS_ES:
        for leng in LENGUAJES:
            for lic in LICENCIAS:
                yield f"es:{palabra}", f'{BASE.format(leng=leng, lic=lic)} "{palabra}" in:description'
    for leng in LENGUAJES:
        for lic in LICENCIAS:
            yield "general", f"{BASE.format(leng=leng, lic=lic)} stars:2..300"


def main():
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token()}", "Accept": "application/vnd.github+json",
                      "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "tracegit-minador"})
    vistos, filas = set(), []
    lista = list(consultas())
    for i, (origen, q) in enumerate(lista, 1):
        while True:
            r = s.get(API, params={"q": q, "per_page": POR_CONSULTA, "page": 1})
            if r.status_code in (403, 429):          # límite de la API de búsqueda: 30 por minuto
                espera = int(r.headers.get("Retry-After", 0)) or max(
                    5, int(r.headers.get("X-RateLimit-Reset", time.time() + 60)) - int(time.time()) + 1)
                print(f"  límite de la API, espero {espera}s"); time.sleep(espera); continue
            r.raise_for_status(); break
        nuevos = 0
        for it in r.json().get("items", []):
            lic = (it.get("license") or {}).get("spdx_id") or ""
            if it["full_name"] in vistos or lic.lower() not in LICENCIAS:
                continue
            vistos.add(it["full_name"]); nuevos += 1
            filas.append({"repo": it["full_name"], "url": it["clone_url"], "licencia": lic,
                          "lenguaje": it.get("language") or "", "estrellas": it["stargazers_count"],
                          "tamano_kb": it["size"], "creado": it["created_at"][:10],
                          "rama": it.get("default_branch") or "", "origen": origen})
        print(f"[{i}/{len(lista)}] {origen:18} +{nuevos:3}  total {len(filas)}")
        time.sleep(2.1)                               # se mantiene bajo 30 consultas/minuto

    destino = DIR_DATASET / "candidatos.csv"
    with open(destino, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
        w.writeheader(); w.writerows(filas)
    print(f"{len(filas)} candidatos en {destino}")


if __name__ == "__main__":
    sys.exit(main())
