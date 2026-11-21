# TraceGit

RAG temporal sobre el historial git de un repositorio: genera un **informe de proceso con evidencia
citada** (cada afirmación cita los commits que la respaldan) y **preguntas orales dirigidas**.
El sistema **no emite un veredicto** humano/IA; la decisión es del docente (*human-in-the-loop*).

Proyecto integrador · ISIA-119 Modelos Generativos de IA · Grupo 3 · 2026-II

## Integrantes

- Brayan Paredes Cabrera
- Rider Rodriguez Ruiz
- Benson Hilario Zavaleta
- Carlos Ahumada Soles

## Modelo

| Rol | Modelo |
|---|---|
| Base alineado (pesos abiertos) | `google/gemma-4-E2B-it @ 4adf15748de9e1a0097b6274cee9c15836c41c37` (Apache 2.0) |
| Especialización | QLoRA (nivel 2 de las bases v3) + RAG |
| Adaptador v1 (privado por ahora) | `brenpc/tracegit-gemma4-e2b-lora-v1 @ 9157fe0c5e22b8ce6a02723d2f6e1c9c23694636` — `notebooks/01_entrenamiento_qlora.ipynb`, registro en `eval/resultados/` |
| Suplente | `Qwen/Qwen3-4B @ 1cfa9a7208912126459214e8b04321603b3df60c` |
| Embeddings | `intfloat/multilingual-e5-small` (local) |

## Estructura

Esta sección se actualiza cada vez que se agrega una carpeta o un archivo. Las versiones nuevas van en archivos o
carpetas nuevas (por ejemplo `dataset/v1_1/`): los de una versión ya publicada no se modifican.

```
tracegit/
├── README.md                     este archivo
├── LICENSE                       MIT
├── dataset/                      construcción del dataset
│   ├── comun.py                  configuración y limpieza compartidas (corte, licencias, filtros, privacidad)
│   ├── idioma.py                 detección de idioma del mensaje (lingua)
│   ├── buscar_repos.py           E1: busca repositorios candidatos con la API de GitHub
│   ├── minar.py                  E2: clona y extrae pares diff → mensaje con PyDriller
│   ├── limpiar.py                E3: deduplica, asigna idioma y estilo, parte por dueño
│   ├── formatear.py              E4: arma la instrucción (≤1024 tokens) en formato de chat
│   ├── generar_card.py           genera la dataset card de la v1
│   ├── test_comun.py             pruebas de limpieza, privacidad e idioma
│   ├── candidatos.csv            procedencia: repositorios encontrados
│   ├── registro_repos.csv        procedencia: qué pasó con cada repositorio y por qué
│   ├── estadisticas_*.json       cifras de la limpieza y del formato (v1)
│   ├── DATASET_CARD.md           dataset card de la v1
│   └── v1_1/                     versión 1.1: depuración de la v1 sin rehacer el minado
│       ├── depurar.py            quita plantillas de la web de GitHub y mensajes repetidos
│       ├── test_depurar.py       pruebas de esos filtros
│       ├── generar_card.py       genera la card de la v1.1
│       ├── estadisticas.json     cifras de la v1.1
│       └── DATASET_CARD.md       dataset card de la v1.1
├── notebooks/                    Colab T4
│   ├── 00_prueba_humo.ipynb      prueba de humo de QLoRA (criterio i)
│   ├── 01_entrenamiento_qlora.ipynb  entrenamiento del adaptador v1
│   ├── 02_generacion_evaluacion.ipynb  primera corrida de generación (fallida: el relleno vació 316/375; se conserva)
│   └── 02b_generacion_evaluacion_sin_relleno.ipynb  respuestas de base y adaptadores sobre el test, sin relleno
├── eval/                         evaluación
│   ├── medir_velocidad_ollama.py criterio (ii): tokens/s en la laptop de la demo
│   ├── metricas_especializacion.py  ROUGE-L, BLEU, identificadores, idioma y sesgo D1 (local, sin GPU)
│   ├── requirements.txt          dependencias de las métricas locales
│   └── resultados/               resultados medidos (JSON con fecha; tablas .md de la evaluación)
└── docs/                         especificaciones
    ├── ALGORITMO_MINADO.md       algoritmo de minado (v1)
    └── DEPURACION_V1_1.md        depuración de la v1.1
```

`data/` (los `.jsonl`) no se versiona en git: está en Hugging Face Hub. Pendientes: `src/tracegit/` (ingesta,
seudonimización, RAG, síntesis y validador).

## Dataset

3925 pares instrucción/respuesta (diff → mensaje de commit humano, anteriores al 30-11-2022), 62 % en español,
divididos por dueño en train 3080 · validation 459 · test 386.

- Hugging Face Hub (privado por ahora): [`brenpc/tracegit-commits`](https://huggingface.co/datasets/brenpc/tracegit-commits)
  - **v1** (raíz) @ `8b5d79317fca720262bdb5334ed25e12442ef040`: con ella se entrenó el adaptador v1.
  - **v1.1** (carpeta `v1.1/`) @ `42eed230d333d04b7ad196032a6fe1d88524e323`: 3704 ejemplos (2903 · 426 · 375), sin
    plantillas de la web de GitHub ni mensajes repetidos. Ver [`docs/DEPURACION_V1_1.md`](docs/DEPURACION_V1_1.md).
- Algoritmo de minado: [`docs/ALGORITMO_MINADO.md`](docs/ALGORITMO_MINADO.md)
- Dataset card con procedencia, filtros y estadísticas: [`dataset/DATASET_CARD.md`](dataset/DATASET_CARD.md)
- Procedencia: `dataset/candidatos.csv` y `dataset/registro_repos.csv`

## Ejecución

En construcción. Las instrucciones reproducibles (versiones fijadas en `requirements.txt`) se
agregan con el código.

## Licencia

Código bajo licencia MIT (ver `LICENSE`).

## Ética

Aviso: los informes son generados por IA y **no son un dictamen de autoría**. Los datos personales
de git (nombres y correos) se seudonimizan antes de cualquier modelo (Ley N.° 29733).
