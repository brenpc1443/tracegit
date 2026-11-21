# Adaptador v2: mitigación del sesgo D1

Carpeta del **adaptador v2** de TraceGit (21-11-2026). El v1 y sus notebooks (`notebooks/01_…`, `02b_…`) no se
modifican: el v2 va completo en esta carpeta.

| Archivo | Qué hace | Dónde corre |
|---|---|---|
| `01_entrenamiento_qlora_v2.ipynb` | entrena el adaptador v2 y lo publica en `brenpc/tracegit-gemma4-e2b-lora-v2` (privado) | Colab T4, ~1,7 h (estimado) |
| `02_generacion_evaluacion_v2.ipynb` | genera las respuestas de `base`, `v1` y `v2` con el idioma explícito, carpeta `test_v1.1_v2` | Colab T4, ~45 min (estimado) |

Después, en local: `python eval/metricas_especializacion.py --etiqueta test_v1.1_v2`.

## Por qué hace falta un v2

Medición «antes» (`eval/resultados/especializacion_test_v1_1_r2_2026-11-21.md`, test v1.1, 375 ejemplos):

1. **Sesgo por idioma (D1).** El v1 responde en el idioma del commit en el 83,8 % de los ejemplos en inglés y solo
   en el 39,1 % de los ejemplos en español: una brecha de 44,7 pp (IC 95 % de 11,5 a 70,2), la única significativa.
   El grupo desfavorecido es el **español**.
2. **Plantilla de GitHub.** El v1 repite «Add files via upload» en el 32 % del test: lo aprendió del dataset v1, que
   tenía 144 ejemplos así. De los 168 errores de idioma en español, 85 son esa plantilla, que está en inglés.
3. **El prompt no dice el idioma.** El prompt de sistema siempre está en español y no indica en qué idioma responder.
   50 de los 82 repositorios del train mezclan mensajes en español e inglés, así que el diff no basta para saberlo:
   el modelo tiene que adivinar.

## Qué cambia

| | v1 | v2 | Motivo |
|---|---|---|---|
| Dataset | v1 @ 8b5d793, 3080 de train | **v1.1** @ 42eed23, 2903 de train | sin plantillas de la web de GitHub ni mensajes repetidos (punto 2) |
| Idioma de salida | no se indica | **explícito**: al final del prompt de sistema, «Escribe el mensaje de commit en español.» o «… en inglés.» | punto 3; es la mitigación «prompt con idioma explícito» de `PLAN.md` §6.1 |
| Español en el train | natural: 1875 es / 1028 en | **sobremuestreo ×1,5**: 2813 es / 1028 en (3841 en total) | protocolo de `PLAN.md` §6.1: sobremuestrear el grupo que sale peor (punto 1) |
| Épocas | 2 | **1** | en el v1 el mejor checkpoint fue el del paso 200, al final de la 1.ª época; la 2.ª solo subió la pérdida (3,289 → 3,311) |
| LoRA r/alpha/dropout, lr, lote efectivo, semilla, MAX_LEN, cuantización | 16/32/0,05, 2e-4, 16, 42, 1536, NF4 fp16 | **iguales** | para que la diferencia venga de los datos y el prompt |

El sobremuestreo es moderado porque el español ya es el 65 % del train: la causa principal de la brecha no es la
falta de ejemplos en español, sino las plantillas y el prompt sin idioma. El factor queda en la celda 1
(`FACTOR_ES`) y en el registro del entrenamiento.

## Cómo se evalúa (D1 antes y después)

Las tres condiciones de `test_v1.1_v2` llevan el idioma explícito, para separar el efecto de cada cambio:

- `base` (de `test_v1.1_v2`) frente a `base` (de `test_v1.1_r2`): efecto de **solo el prompt**.
- `v1` (de `test_v1.1_v2`) frente a `v1` (de `test_v1.1_r2`): el prompt sobre un adaptador sin reentrenar.
- `v2` (de `test_v1.1_v2`) frente a `v1` (de `test_v1.1_r2`): **antes y después** de la mitigación completa. Es la tabla
  de D1 del informe y de la Matriz EICE.

Criterios de éxito, fijados antes de entrenar:

- la brecha de idioma correcto entre inglés y español baja y su IC 95 % incluye el cero;
- la tasa de «Add files via upload» baja a menos del 1 %;
- el ROUGE-L global no empeora más de 0,01 frente al v1 (margen de `PLAN.md` §6.1);
- la tasa de identificadores inventados sigue por debajo de la del modelo base.

Si no se cumplen, se reporta igual.

## Consecuencia para el sistema

Con el v2, TraceGit debe pasar siempre el idioma de salida en el prompt del paso *map*. Usa el idioma predominante de
los mensajes de commit del repositorio y, si no se puede decidir, el español. Sin esa frase, el adaptador trabaja
fuera de su condición de entrenamiento.
