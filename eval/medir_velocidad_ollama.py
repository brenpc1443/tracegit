"""Prueba de humo, criterio (ii): tokens/s en la laptop de la demo (PLAN.md §3).

Requisitos: Ollama instalado y el modelo descargado, por ejemplo
    ollama pull gemma4:e2b-it-q4_K_M     (seleccionado)
    ollama pull qwen3:4b-q4_K_M          (suplente)
Etiquetas verificadas en ollama.com el 18-11-2026.

Uso:
    python eval/medir_velocidad_ollama.py gemma4:e2b-it-q4_K_M
Solo usa la biblioteca estándar. Guarda el resultado en eval/resultados/.
"""
import json
import os
import platform
import statistics
import sys
import time
import urllib.request

URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434") + "/api/generate"
UMBRAL_TPS = 3.0
REPETICIONES = 3

# Prompt representativo del paso "map": un diff corto y la petición de describirlo.
PROMPT = """Describe en español, en un mensaje de commit claro, el siguiente cambio:

diff --git a/src/parser.py b/src/parser.py
@@ -10,7 +10,12 @@ def parse_line(line):
-    parts = line.split(",")
-    return parts
+    if not line.strip():
+        raise ValueError("línea vacía")
+    parts = [p.strip() for p in line.split(",")]
+    if len(parts) != 3:
+        raise ValueError(f"se esperaban 3 campos, hay {len(parts)}")
+    return parts
"""


def generar(modelo):
    cuerpo = {"model": modelo, "prompt": PROMPT, "stream": False, "think": False,
              "options": {"num_predict": 128, "temperature": 0, "seed": 42}}
    req = urllib.request.Request(URL, data=json.dumps(cuerpo).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        return json.load(r)


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    modelo = sys.argv[1]
    print(f"Calentando {modelo} (la primera carga no se mide)...")
    generar(modelo)

    corridas = []
    for i in range(REPETICIONES):
        r = generar(modelo)
        tps = r["eval_count"] / (r["eval_duration"] / 1e9)
        prefill = r.get("prompt_eval_count", 0) / max(r.get("prompt_eval_duration", 1) / 1e9, 1e-9)
        corridas.append({"tokens_generados": r["eval_count"], "tokens_s": round(tps, 2),
                         "prefill_tokens_s": round(prefill, 2), "total_s": round(r["total_duration"] / 1e9, 2)})
        print(f"  corrida {i + 1}: {tps:.2f} tokens/s")

    mediana = statistics.median(c["tokens_s"] for c in corridas)
    resultado = {
        "fecha": time.strftime("%Y-%m-%d %H:%M"), "modelo_ollama": modelo,
        "equipo": {"so": platform.platform(), "cpu": platform.processor(), "nucleos_logicos": os.cpu_count()},
        "corridas": corridas, "mediana_tokens_s": mediana,
        "umbral_tokens_s": UMBRAL_TPS, "aprobado_ii": mediana >= UMBRAL_TPS,
        "ultima_salida": r["response"][:300],
    }
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
    print("\nDECISIÓN (ii):", "APROBADO" if resultado["aprobado_ii"] else "FALLA → probar el suplente qwen3:4b-q4_K_M")
    print("Anotar a mano la RAM del equipo y la memoria pico de Ollama (Administrador de tareas).")

    destino = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resultados")
    os.makedirs(destino, exist_ok=True)
    nombre = f"velocidad_{modelo.replace(':', '_').replace('/', '_')}_{time.strftime('%Y%m%d_%H%M')}.json"
    with open(os.path.join(destino, nombre), "w", encoding="utf-8") as f:
        json.dump(resultado, f, indent=2, ensure_ascii=False)
    print("Guardado en eval/resultados/" + nombre)


if __name__ == "__main__":
    main()
