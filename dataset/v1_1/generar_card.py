"""Genera dataset/v1_1/DATASET_CARD.md (y data/v1_1/README.md para Hugging Face Hub) desde estadisticas.json.

La card de la v1 (dataset/DATASET_CARD.md) sigue siendo la referencia de procedencia, filtros del minado y
privacidad; esta solo documenta lo que cambia en la v1.1.
Uso:  python dataset/v1_1/generar_card.py
"""
import json
from pathlib import Path

DIR_V11 = Path(__file__).resolve().parent
SALIDA = DIR_V11.parent.parent / "data" / "v1_1"
SPLITS = ("train", "validation", "test")


def main():
    s = json.load(open(DIR_V11 / "estadisticas.json", encoding="utf-8"))
    filas = []
    for k in SPLITS:
        p = s["por_split"][k]
        filas.append(f"| {k} | {s['ejemplos_v1'][k]} | {p['ejemplos']} | {p['repos']} | {p['duenos']} | "
                     f"{p['idioma'].get('es', 0)} | {p['idioma'].get('en', 0)} |")
    desc = "\n".join(f"| {k} | " + " | ".join(str(s['descartes_por_split'][x].get(k, 0)) for x in SPLITS) +
                     f" | {v} |" for k, v in s["descartes"].items())
    top = "\n".join(f"| {m} | {n} |" for m, n in s["mensajes_mas_descartados"])
    total = sum(s["por_split"][k]["ejemplos"] for k in SPLITS)

    md = f"""# TraceGit commits humanos — versión 1.1

Depuración de la v1 (`{s['base']}`) **sin rehacer el minado**: mismos repositorios, misma partición por dueño
(ningún ejemplo cambia de split) y mismo formato. Procedencia, filtros del minado, privacidad y atributos de
sesgo: card de la v1 (`dataset/DATASET_CARD.md`, en la raíz de este repositorio de Hugging Face).

Archivos: `v1.1/{{train,validation,test}}.jsonl`. Código: `dataset/v1_1/depurar.py` de
https://github.com/brenpc1443/tracegit; especificación en `docs/DEPURACION_V1_1.md`.

## Por qué

En la comparación rápida del adaptador v1, el modelo respondió "Add files via upload" en 2 de 5 ejemplos. Ese
texto lo escribe GitHub cuando se suben archivos desde su web: no es un mensaje humano, pasó el filtro de
"menos de 3 palabras" y era el 4,7 % de train. También había mensajes idénticos repetidos muchas veces en un
mismo repositorio (un solo mensaje ocupaba 31 de los 459 ejemplos de validación).

## Filtros nuevos (en orden)

1. **Plantilla de la web de GitHub:** `Add files via upload`, y `Create`/`Update`/`Delete <ruta>` o
   `Rename <ruta> to <ruta>` cuando el mensaje es solo eso (verbo con mayúscula y una ruta con extensión o
   carpeta). `Update README.md with install steps` o `delete wemake-python-styleguide` se conservan.
2. **Mensajes repetidos:** como máximo {s['max_identicos_por_repo']} mensajes idénticos (sin distinguir
   mayúsculas) por repositorio, elegidos al azar con la semilla {s['semilla']}.
3. **Repositorios pequeños:** se quitan los que quedan con menos de {s['min_ejemplos_repo']} ejemplos
   ({", ".join(s['repos_eliminados'])}).

## Resultado

| split | v1 | v1.1 | repos | dueños | es | en |
|---|---|---|---|---|---|---|
{chr(10).join(filas)}

Total v1.1: **{total}** ejemplos.

| motivo | train | validation | test | total |
|---|---|---|---|---|
{desc}

Mensajes más descartados:

| mensaje | veces |
|---|---|
{top}

## Uso

```python
from huggingface_hub import hf_hub_download
ruta = hf_hub_download("brenpc/tracegit-commits", "v1.1/train.jsonl", repo_type="dataset", revision="42eed230d333d04b7ad196032a6fe1d88524e323")
```

Para comparar modelos se usa el **test de la v1.1** (sin plantillas), también para el adaptador v1.
"""
    (DIR_V11 / "DATASET_CARD.md").write_text(md, encoding="utf-8")
    SALIDA.mkdir(parents=True, exist_ok=True)
    (SALIDA / "README.md").write_text(md, encoding="utf-8")
    print("dataset/v1_1/DATASET_CARD.md y data/v1_1/README.md generados")


if __name__ == "__main__":
    main()
