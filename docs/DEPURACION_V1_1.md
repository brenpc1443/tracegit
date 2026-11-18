# Depuración del dataset: versión 1.1

Complemento de [`ALGORITMO_MINADO.md`](ALGORITMO_MINADO.md), que sigue describiendo la v1 sin cambios. La v1.1
**no rehace el minado**: lee la salida de la v1 y le aplica tres filtros más. Código en `dataset/v1_1/`.

## 1. Motivo

El adaptador v1 (`brenpc/tracegit-gemma4-e2b-lora-v1@9157fe0`) contestó "Add files via upload" en 2 de los 5
ejemplos de la comprobación rápida (`notebooks/01_entrenamiento_qlora.ipynb`, celda 10). Al revisar la v1:

- **153 ejemplos** (145 en train, el 4,7 %) eran mensajes que **GitHub escribe por defecto** al subir o editar
  archivos desde su web. No los redacta una persona. Pasaron el filtro de la v1 porque tienen 3 palabras o más.
- **Mensajes idénticos** repetidos dentro de un mismo repositorio: `still working on travis ci` aparecía 31 veces
  y ocupaba el 6,8 % de validación, lo que sesga `eval_loss` hacia un solo repositorio.

## 2. Algoritmo

```
ENTRADA  data/final/{train,validation,test}.jsonl   (v1, solo lectura)
ordenar por (split, repo, sha)                       # el resultado no depende del orden de lectura
para cada ejemplo:
    si el mensaje es plantilla web de GitHub         → descartar (plantilla_web_github)
agrupar por (repo, mensaje en minúsculas y espacios normalizados)
para cada grupo con más de 2 ejemplos:
    barajar con semilla 42, conservar 2              → el resto: mensaje_repetido_en_repo
para cada repo con menos de 5 ejemplos               → descartar (repo_con_pocos_tras_depurar)
SALIDA   data/v1_1/{train,validation,test}.jsonl, dataset/v1_1/estadisticas.json
```

**Plantilla web de GitHub:** el mensaje completo es `Add files via upload`, o `Create`/`Update`/`Delete <ruta>`,
o `Rename <ruta> to <ruta>`. El verbo va con mayúscula, como lo escribe GitHub, y la ruta es una sola palabra con
punto o barra. Un mensaje con más texto (`Update README.md with install steps`) o en minúsculas
(`delete wemake-python-styleguide`) se considera humano y se conserva. Los casos están en `test_depurar.py`.

**La partición no cambia:** cada ejemplo sigue en el split que tenía en la v1. Así se mantiene la separación
por dueño, y el adaptador v1 y el v2 se pueden comparar sobre el mismo test.

## 3. Resultado (18-11-2026)

| | train | validation | test | total |
|---|---|---|---|---|
| v1 | 3080 | 459 | 386 | 3925 |
| plantilla_web_github | −145 | 0 | −8 | −153 |
| mensaje_repetido_en_repo | −26 | −33 | −1 | −60 |
| repo_con_pocos_tras_depurar | −6 | 0 | −2 | −8 |
| **v1.1** | **2903** | **426** | **375** | **3704** |

- Idioma en train: es 1875 / en 1028 (65 % español). Test: es 276 / en 99.
- Repositorios eliminados: `CarlosUSO/Proyecto`, `alejandrorueda/spaceapp`, `lAleRojasl/qrnet`.
- Publicado en `brenpc/tracegit-commits`, carpeta `v1.1/`, revisión
  `42eed230d333d04b7ad196032a6fe1d88524e323`. La v1 sigue en la raíz y en la revisión `8b5d793`.
- Detalle completo: `dataset/v1_1/estadisticas.json` y `dataset/v1_1/DATASET_CARD.md`.

## 4. Cómo reproducirlo

```bash
python dataset/v1_1/test_depurar.py    # o: python -m pytest dataset/v1_1/test_depurar.py
python dataset/v1_1/depurar.py         # requiere data/final/ de la v1
python dataset/v1_1/generar_card.py
```
