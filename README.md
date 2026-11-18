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

## Ejecución

En construcción. Las instrucciones reproducibles (versiones fijadas en `requirements.txt`) se
agregan con el código.

## Licencia

Código bajo licencia MIT (ver `LICENSE`).

## Ética

Aviso: los informes son generados por IA y **no son un dictamen de autoría**. Los datos personales
de git (nombres y correos) se seudonimizan antes de cualquier modelo (Ley N.° 29733).
