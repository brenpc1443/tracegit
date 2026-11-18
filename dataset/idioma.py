"""Detección del idioma del mensaje de commit (necesaria para la métrica de equidad D1).

lingua-language-detector 2.1.1 (Apache-2.0), pensado para textos cortos como los mensajes de commit.
Regla (elegida con 28 casos de prueba el 18-11-2026: 25/28 aciertos; los errores son mensajes
ambiguos de dos palabras):
  1. Se quitan rutas y números (no aportan al idioma).
  2. Si el idioma más probable no es es/en y su confianza es >= 0,6, el mensaje es "otro".
  3. Si no, se decide solo entre español e inglés; la confianza es p(ganador) / (p(es) + p(en)).
Los mensajes con confianza < 0,7 se reasignan después al idioma mayoritario de su repositorio
(limpiar.py), y la confianza queda guardada para filtrar en el análisis de sesgo.
"""
import re

from lingua import Language, LanguageDetectorBuilder

_IDIOMAS = [Language.ENGLISH, Language.SPANISH, Language.PORTUGUESE, Language.FRENCH, Language.GERMAN,
            Language.ITALIAN, Language.DUTCH, Language.RUSSIAN, Language.CHINESE, Language.JAPANESE,
            Language.KOREAN, Language.TURKISH, Language.INDONESIAN]
_DETECTOR = LanguageDetectorBuilder.from_languages(*_IDIOMAS).with_preloaded_language_models().build()
_RUIDO = re.compile(r"`[^`]*`|\S*[/\\]\S*|\d+")
UMBRAL_OTRO = 0.6
UMBRAL_AMBIGUO = 0.7


def detectar(texto: str) -> tuple[str, float]:
    """Devuelve (código, confianza). Código: 'es', 'en' u 'otro'."""
    limpio = _RUIDO.sub(" ", texto)
    if not re.search(r"[^\W\d_]{2,}", limpio):
        return "otro", 0.0
    vals = {v.language: v.value for v in _DETECTOR.compute_language_confidence_values(limpio)}
    if not vals:
        return "otro", 0.0
    top = max(vals, key=vals.get)
    if top not in (Language.ENGLISH, Language.SPANISH) and vals[top] >= UMBRAL_OTRO:
        return "otro", vals[top]
    es, en = vals.get(Language.SPANISH, 0.0), vals.get(Language.ENGLISH, 0.0)
    return ("es" if es > en else "en"), max(es, en) / (es + en + 1e-12)
