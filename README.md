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

```
dataset/     minador de commits (PyDriller), limpieza, dataset card
notebooks/   entrenamiento QLoRA y evaluación (Colab T4)
src/tracegit ingesta, rasgos, seudonimización, RAG, síntesis, verificador
eval/        métricas: especialización, retrieval, citas, sesgos (D1)
docs/        plan, Matriz EICE, model card y dataset card
```

## Dataset

3925 pares instrucción/respuesta (diff → mensaje de commit humano, anteriores al 30-11-2022), 62 % en español,
divididos por dueño en train 3080 · validation 459 · test 386.

- Hugging Face Hub (privado por ahora): [`brenpc/tracegit-commits`](https://huggingface.co/datasets/brenpc/tracegit-commits)
  @ `8b5d79317fca720262bdb5334ed25e12442ef040`
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
