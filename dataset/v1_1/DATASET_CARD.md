# TraceGit commits humanos — versión 1.1

Depuración de la v1 (`v1 (brenpc/tracegit-commits@8b5d79317fca720262bdb5334ed25e12442ef040)`) **sin rehacer el minado**: mismos repositorios, misma partición por dueño
(ningún ejemplo cambia de split) y mismo formato. Procedencia, filtros del minado, privacidad y atributos de
sesgo: card de la v1 (`dataset/DATASET_CARD.md`, en la raíz de este repositorio de Hugging Face).

Archivos: `v1.1/{train,validation,test}.jsonl`. Código: `dataset/v1_1/depurar.py` de
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
2. **Mensajes repetidos:** como máximo 2 mensajes idénticos (sin distinguir
   mayúsculas) por repositorio, elegidos al azar con la semilla 42.
3. **Repositorios pequeños:** se quitan los que quedan con menos de 5 ejemplos
   (CarlosUSO/Proyecto, alejandrorueda/spaceapp, lAleRojasl/qrnet).

## Resultado

| split | v1 | v1.1 | repos | dueños | es | en |
|---|---|---|---|---|---|---|
| train | 3080 | 2903 | 82 | 80 | 1875 | 1028 |
| validation | 459 | 426 | 14 | 12 | 226 | 200 |
| test | 386 | 375 | 12 | 12 | 276 | 99 |

Total v1.1: **3704** ejemplos.

| motivo | train | validation | test | total |
|---|---|---|---|---|
| plantilla_web_github | 145 | 0 | 8 | 153 |
| mensaje_repetido_en_repo | 26 | 33 | 1 | 60 |
| repo_con_pocos_tras_depurar | 6 | 0 | 2 | 8 |

Mensajes más descartados:

| mensaje | veces |
|---|---|
| Add files via upload | 152 |
| still working on travis ci | 29 |
| 01/06/2021 - Permisos en BaseActivity | 5 |
| [FIX] openacademy: Finding unitest errors | 4 |
| 30/05/2021 - Actualización funcionalidad restricciones | 3 |
| se actualiza jenkinsfile | 3 |
| Crear perfiles ViewSet | 2 |
| Delete org.eclipse.wst.common.component | 1 |
| logout en template | 1 |
| version para pruebas | 1 |

## Uso

```python
from huggingface_hub import hf_hub_download
ruta = hf_hub_download("brenpc/tracegit-commits", "v1.1/train.jsonl", repo_type="dataset", revision="42eed230d333d04b7ad196032a6fe1d88524e323")
```

Para comparar modelos se usa el **test de la v1.1** (sin plantillas), también para el adaptador v1.
