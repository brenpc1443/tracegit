# Algoritmo de minado del dataset

Especificación del proceso que produce el dataset de entrenamiento de TraceGit: pares instrucción/respuesta
en los que la instrucción es un diff de git y la respuesta es el mensaje de commit escrito por una persona.
Corresponde a `PLAN.md` §1.2 y al código de `dataset/`. Las cifras de la corrida del 18-11-2026 están en
`dataset/DATASET_CARD.md`.

## 1. Entradas, salidas y garantías

| | Descripción |
|---|---|
| **Entrada** | API de búsqueda de repositorios de GitHub y clones públicos de los repositorios |
| **Salida** | `data/final/{train,validation,test}.jsonl` (formato de chat + metadatos) y la *dataset card* |
| **Procedencia versionada** | `dataset/candidatos.csv` (qué se encontró), `dataset/registro_repos.csv` (qué pasó con cada repositorio y por qué se descartó cada commit), `dataset/estadisticas_*.json` |

El algoritmo garantiza que cada ejemplo cumple estas condiciones:

1. **Humano:** fecha de autor y de *committer* anteriores al 30-11-2022, sin bots ni merges.
2. **Con licencia permisiva:** MIT, Apache-2.0, BSD-2-Clause o BSD-3-Clause.
3. **Sin datos personales:** no guarda autor ni correo, y los correos, secretos y @menciones se reemplazan.
4. **Respuesta deducible del diff:** no lleva referencias a PR ni *issues*, ni mensajes que sean código copiado.
5. **Instrucción de 1024 tokens como máximo** con el tokenizer de Gemma 4.
6. **Sin fuga entre particiones:** un mismo dueño nunca aparece en dos particiones.

## 2. Vista general

```
E1 buscar_repos.py ──► candidatos.csv ──► E2 minar.py ──► data/raw/crudo.jsonl + registro_repos.csv
                                                              │
     data/final/*.jsonl + card ◄── E4 formatear.py ◄── E3 limpiar.py (data/processed/limpio.jsonl)
```

Cada etapa lee la salida de la anterior, de modo que una se puede repetir sin rehacer las demás. E2 se puede
cortar y retomar: los repositorios que ya están en el registro se saltan.

## 3. Etapa 1: búsqueda de candidatos (`buscar_repos.py`)

```
para cada palabra p en PALABRAS_ES, para cada lenguaje L, para cada licencia K:
    consultar  language:L license:K fork:false size:30..20000 created:2014-01-01..2022-06-30 "p" in:description
para cada lenguaje L, para cada licencia K:
    consultar  language:L license:K fork:false size:30..20000 created:2014-01-01..2022-06-30 stars:2..300
para cada resultado (100 por consulta):
    descartar si ya se vio o si su licencia SPDX no está en LICENCIAS
    guardar repo, url, licencia, lenguaje, estrellas, tamaño, fecha de creación, rama y origen de la consulta
```

- `PALABRAS_ES` = proyecto, universidad, curso, tarea, practica, sistema de, aplicacion. Sirven para encontrar
  proyectos de curso en español, que es el caso de uso. Esta lista no fija el idioma de cada ejemplo: el
  idioma se detecta después, commit por commit.
- 4 lenguajes × 4 licencias × (7 + 1) = 128 consultas, con una pausa de 2,1 s entre una y otra para no pasar
  el límite de 30 por minuto de la API de búsqueda. Si la API responde 403 o 429, el script espera lo que indica
  `Retry-After` o `X-RateLimit-Reset`.
- **No determinismo:** la API de GitHub cambia con el tiempo. Por eso se versiona `candidatos.csv`, y E2 y las
  etapas siguientes son reproducibles a partir de ese archivo.

## 4. Etapa 2: minado (`minar.py`)

### 4.1 Orden de proceso

```
bloques = [candidatos con origen "es:*", candidatos "general"]
en cada bloque: una cola por (lenguaje, licencia); se recorren por turnos (round-robin)
```

Sin el intercalado, el orden de las consultas (Python y MIT primero) producía un dataset casi solo de
Python/MIT. Se detectó en la corrida del 18-11-2026 (sección 8).

### 4.2 Bucle principal

```
total, total_es, por_lenguaje ← contadores leídos de crudo.jsonl (permite retomar)
para cada candidato c en orden:
    si total ≥ OBJETIVO y total_es ≥ OBJETIVO_ES: terminar
    si c ya está en registro_repos.csv: saltar
    si total ≥ OBJETIVO y c no es "es:*": saltar          # cubierto el cupo general, solo se busca español
    si por_lenguaje[c.lenguaje] ≥ 0,30 · OBJETIVO: saltar   # equilibrio entre lenguajes

    clonar c (rama por defecto, sin tags) en D:/tracegit_cache; rehacer el clon si está roto
    n ← commits sin merge anteriores al corte (git rev-list --count --no-merges --before=CORTE HEAD)
    si n ∉ [20, 500]: registrar "fuera_de_rango_commits"; continuar
    ejemplos, lineas ← EXTRAER(c)
    si |ejemplos| < 5: registrar "pocos_ejemplos"; continuar
    si |ejemplos| > 60: ejemplos ← muestra aleatoria de 60 (semilla 42)
    a cada ejemplo: mediana_lineas_repo ← mediana(lineas)
    añadir ejemplos a crudo.jsonl; actualizar contadores; registrar "aceptado"
    borrar el clon (quitando el atributo de solo lectura de .git en Windows)
```

En la corrida del 18-11-2026 se usaron OBJETIVO = 4000 y OBJETIVO_ES = 1200.

### 4.3 EXTRAER: filtros por commit, en orden

Recorre con PyDriller 2.12 (`only_no_merge=True`, `to=CORTE`) y descarta el commit en el **primer** filtro que
falla. El motivo se cuenta en el registro.

| # | Filtro | Motivo registrado | Por qué |
|---|---|---|---|
| 1 | `author_date` o `committer_date` ≥ 30-11-2022 | `fecha_posterior_al_corte` | Un *rebase* posterior puede conservar la fecha de autor antigua |
| 2 | Autor o *committer* coincide con el patrón de bots (`[bot]`, dependabot, renovate, github-actions…) | `bot` | La respuesta debe ser humana |
| 3 | El mensaje se limpia con `limpiar_mensaje` (sección 5.1) y pasa por `mensaje_valido` | `mensaje_vacio`, `mensaje_generico`, `mensaje_corto`, `mensaje_parece_codigo`, `mensaje_merge_o_revert` | Una respuesta trivial o que es código no enseña a describir cambios |
| 4 | PyDriller no puede leer los archivos del commit | `error_lectura` | Robustez |
| 5 | Ningún archivo tiene diff útil, porque todos están excluidos o son binarios | `sin_diff_util` | No hay instrucción |
| 6 | La suma de los diffs pasa de 40 000 caracteres | `diff_demasiado_grande` | Refactors masivos: el mensaje no se puede deducir de un diff recortado |
| 7 | El asunto del mensaje es idéntico a una línea `+` o `-` del diff | `mensaje_copiado_del_diff` | El autor pegó código como mensaje |
| 8 | El idioma detectado no es español ni inglés | `idioma_no_es_en` | La métrica D1 compara es y en |

Para cada archivo se guardan la ruta, el tipo de cambio, las líneas `+` y `-`, la marca `excluido` y el diff,
recortado a 6000 caracteres. Los archivos excluidos aparecen en las estadísticas pero no en el diff:
- lockfiles;
- archivos minificados y `.map`;
- `dist/`, `build/`, `node_modules/`, `vendor/`, `target/`, `__pycache__/`…;
- binarios, imágenes, fuentes, modelos y `.ipynb`.

### 4.4 Validez del mensaje (`mensaje_valido`)

- **Genérico:** el asunto o el mensaje completo está en una lista cerrada (`update`, `fix`, `wip`, `typo`,
  `initial commit`, `cambios`, `avance`…).
- **Corto:** menos de 3 palabras de al menos 2 letras, sin contar URLs ni nombres de archivo o rutas
  (`Formato readme.md` cuenta como 1 palabra).
- **Parece código:** el asunto tiene 3 o más caracteres de `={};|&^$\` y estos suman más del 6 % de su
  longitud, o el asunto empieza por `RUN`, `import`, `from`, `const`, `let`, `var`, `def` o `return`. Las
  comillas y los paréntesis no cuentan, porque aparecen en prosa normal (`Add "login" button (frontend)`).
- **Merge o revert:** el asunto empieza por `merge branch`, `merge pull request`, `merge remote-tracking` o
  `revert "`.

## 5. Etapa 3: limpieza y partición (`limpiar.py`)

### 5.1 Limpieza de texto

**Mensaje** (`limpiar_mensaje`), en este orden:
1. Normalización NFC.
2. Se quitan los *trailers* (`Signed-off-by`, `Co-authored-by`, `Reviewed-by`, `Change-Id`…).
3. Se quitan las referencias que no se deducen del diff: URLs de *issues* o PR, `(#123)`, `owner/repo#45`,
   `GH-12` y los verbos de cierre que quedan colgando al final de una línea (`..., closes`). Esta regla salió de
   la prueba de humo, en la que el modelo inventó un número de PR.
4. `depurar_privacidad` (ver abajo), con @menciones → `@usuario`.
5. Se ordenan los espacios y la puntuación huérfana, y el mensaje se recorta a 512 caracteres, en el límite de
   una palabra.

**Diff:** NFC y `depurar_privacidad` **sin** el reemplazo de @menciones, porque en código `@property` y
`@Override` son decoradores y anotaciones, no personas.

**`depurar_privacidad`** reemplaza:
- claves privadas PEM, claves de AWS, GitHub, OpenAI, Google y Slack, y JWT → `<secreto>`;
- asignaciones `password|secret|api_key|token… = "valor"` → el valor pasa a `<secreto>`;
- URLs con credenciales o con `?token=` → `<url>`;
- correos → `<correo>`.

Cuenta cada reemplazo para la *dataset card*.

### 5.2 Duplicados

`huella = SHA-256(diffs concatenados con los espacios normalizados)`. Se conserva la primera aparición de cada
huella, lo que elimina, por ejemplo, el código copiado entre repositorios o los forks no marcados como tales.

### 5.3 Idioma

`detectar` (en `idioma.py`, con lingua-language-detector 2.1.1):
1. Quita los bloques entre comillas invertidas, las rutas y los números.
2. Calcula la confianza en 13 idiomas frecuentes en GitHub.
3. Si el más probable no es es ni en, y su confianza es de 0,6 o más, el idioma es `otro` y el commit se
   descarta en E2.
4. Si no, decide entre es y en, con confianza = p(ganador) / (p(es) + p(en)).

La regla se eligió con 28 casos de prueba: acierta 25. Los 3 errores son mensajes de dos palabras.

En E3, los mensajes con confianza menor de 0,7 toman el **idioma mayoritario de su repositorio** (calculado
con los mensajes de confianza ≥ 0,7). Se guardan el idioma detectado original y la confianza, para poder
filtrar en el análisis de sesgo.

### 5.4 Estilo de commit (atributo de D1)

`estilo_repo = commits_grandes` si la mediana de líneas por commit del repositorio, calculada sobre **todos**
sus commits anteriores al corte, supera la mediana de esas medianas entre los repositorios aceptados. Si no,
`commits_pequenos`.

### 5.5 Topes y partición

```
descartar los repositorios que quedaron con menos de 5 ejemplos
por dueño (la cuenta antes de "/"): si tiene más de 120 ejemplos, muestra aleatoria de 120 (semilla 42)
estrato(dueño) = (idioma mayoritario, lenguaje mayoritario) de sus ejemplos
para cada estrato:
    barajar los dueños (semilla 42)
    para cada dueño: asignarlo al split con mayor déficit = 0,8·N | 0,1·N | 0,1·N − ejemplos ya asignados
avisar si test tiene menos de 100 ejemplos en español
```

La partición es por **dueño** y no por repositorio porque un mismo autor puede tener varios repositorios, y su
estilo de redacción se filtraría de entrenamiento a prueba.

## 6. Etapa 4: formato (`formatear.py`)

```
tokenizer ← tokenizer.json de google/gemma-4-E2B-it @ 4adf157 (se descarga una vez a D:/tracegit_cache)
para cada ejemplo:
    cabecera ← "Archivos y estadísticas:" + una línea por archivo "TIPO ruta (+a -b) [omitido]" + "Diff:"
        hasta 30 archivos; si la cabecera pasa de 256 tokens (1/4 del presupuesto), se listan menos
        y se añade "... y N archivos más"
    libre ← 1024 − tokens(cabecera)
    bloques ← "--- ruta\n" + diff de cada archivo con diff; como máximo libre / 108 bloques
    presupuesto ← libre − 12 · |bloques|                    # 12 tokens por bloque para la marca de recorte
    c* ← el mayor c tal que Σ min(tokens(bloque_i), c) ≤ presupuesto   (búsqueda binaria; reparto justo)
    cada bloque se recorta a c* tokens y se marca "[... diff recortado]"
    salida: messages = [system, user = cabecera + bloques, assistant = mensaje], meta = {...}
se comprueba que ninguna instrucción pase de 1024 tokens (+8 de margen de redondeo)
```

El reparto justo evita que un archivo grande deje sin espacio a los demás: los archivos chicos entran enteros y
los grandes se recortan al mismo tope.

## 7. Parámetros

| Parámetro | Valor | Justificación |
|---|---|---|
| Corte temporal | 30-11-2022 | Lanzamiento de ChatGPT: la respuesta debe ser humana |
| Licencias | MIT, Apache-2.0, BSD-2/3 | Permiten reutilizar el contenido con atribución |
| Commits por repositorio | 20–500 | Tamaño de un proyecto de curso, que es el caso de uso |
| Ejemplos por repositorio / por dueño | 5–60 / ≤ 120 | Diversidad: ningún autor domina el dataset |
| Tope por lenguaje | 30 % del objetivo | Equilibrio entre Python, Java, JS y TS |
| Diff total | ≤ 40 000 caracteres | Descarta refactors masivos |
| Respuesta | ≤ 512 caracteres | `PLAN.md` §1.2 |
| Instrucción | ≤ 1024 tokens | Cabe en la secuencia de 1536 de la T4 (`PLAN.md` §4.3) |
| Umbrales de idioma | otro ≥ 0,6; ambiguo < 0,7 | Elegidos con casos de prueba (sección 5.3) |
| Semilla | 42 | Reproducibilidad |

## 8. Corrida del 18-11-2026 (registro honesto)

1. Una prueba con 5 repositorios mostró mensajes que eran código y mensajes que eran solo una URL. Se agregaron
   los filtros 3 (parece código y palabras sin URL) y 7 (copiado del diff), y se descartó esa prueba.
2. En Windows, `shutil.rmtree` no borraba los objetos de solo lectura de `.git`, y los clones a medio borrar
   daban "fuera de rango" falsos. Se corrigió el borrado y se reinició desde cero.
3. Con unos 1000 ejemplos minados se vio que todos eran Python/MIT, por el orden de las consultas. Se detuvo
   la corrida, se comprobó que el archivo crudo estaba íntegro (1055 ejemplos, ninguno huérfano) y se reanudó
   con el orden intercalado y el tope por lenguaje. **Los primeros 1055 ejemplos se minaron con el orden
   original:** por eso Python es el lenguaje con más ejemplos.
4. En la limpieza se vio que el reemplazo de @menciones alteraba decoradores y anotaciones en los diffs. Desde
   entonces solo se aplica a los mensajes. El archivo crudo guarda los diffs sin tocar, así que no hubo que
   volver a minar.
5. Resultado: 258 repositorios procesados, 114 aceptados y **3925 ejemplos** (62 % en español).

## 9. Cómo reproducirlo

```
pip install pydriller==2.12 lingua-language-detector==2.1.1 tokenizers requests numpy
python dataset/test_comun.py                    # pruebas de limpieza e idioma
python dataset/buscar_repos.py                  # opcional: regenera candidatos.csv (no determinista)
python dataset/minar.py --objetivo 4000 --objetivo-es 1200
python dataset/limpiar.py
python dataset/formatear.py
python dataset/generar_card.py
```

Variable de entorno opcional: `TRACEGIT_CACHE` (por defecto `D:/tracegit_cache`) para la carpeta de clones.
El token de GitHub sale de `GITHUB_TOKEN` o de `gh auth token`.
