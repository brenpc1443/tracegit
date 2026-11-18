"""Configuración y utilidades compartidas del minador (PLAN.md §1.2)."""
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------- rutas
RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "data"                      # ignorado por git (salvo lo que se copie a dataset/)
CRUDO = DATOS / "raw"
PROCESADO = DATOS / "processed"
FINAL = DATOS / "final"
# Los clones van a D: (C: tiene poco espacio). Se puede cambiar con la variable de entorno.
CACHE_CLONES = Path(os.environ.get("TRACEGIT_CACHE", "D:/tracegit_cache"))
DIR_DATASET = Path(__file__).resolve().parent   # aquí se versionan candidatos, registro y card

# ---------------------------------------------------------------- criterios del dataset
CORTE = datetime(2022, 11, 30, tzinfo=timezone.utc)   # antes de ChatGPT: respuestas humanas
LICENCIAS = ["mit", "apache-2.0", "bsd-2-clause", "bsd-3-clause"]
LENGUAJES = ["python", "javascript", "typescript", "java"]
MIN_COMMITS_REPO, MAX_COMMITS_REPO = 20, 500            # proyectos de tamaño "curso"
MIN_EJEMPLOS_REPO = 5                                   # menos que esto: el repo no aporta
MAX_EJEMPLOS_REPO = 60                                  # tope por repo: diversidad
MAX_CHARS_DIFF_TOTAL = 40_000                           # más que esto: refactor masivo, se descarta
MAX_CHARS_DIFF_ARCHIVO = 6_000                          # recorte previo; el fino es por tokens
MAX_RESP_CHARS = 512
MAX_TOKENS_INSTRUCCION = 1024
SEMILLA = 42
PROPORCION = {"train": 0.8, "validation": 0.1, "test": 0.1}

SYSTEM = ("Eres un asistente que describe cambios de código. Dado un diff de git, escribe un mensaje de commit "
          "claro y fiel al cambio, sin inventar identificadores.")

TOKENIZER = {"repo": "google/gemma-4-E2B-it", "revision": "4adf15748de9e1a0097b6274cee9c15836c41c37"}

# ---------------------------------------------------------------- filtros de commits
PATRON_BOT = re.compile(r"\[bot\]|dependabot|renovate|github-actions|greenkeeper|snyk-bot|pre-commit-ci|"
                        r"allcontributors|semantic-release|imgbot|codecov|travis", re.I)

GENERICOS = {"update", "updates", "updated", "fix", "fixes", "fixed", "wip", "typo", "typos", "cleanup",
             "changes", "change", "minor", "minor changes", "minor fix", "minor fixes", "small fix", "test",
             "tests", "commit", "first commit", "initial commit", "init", "readme", "update readme",
             "update readme.md", "actualizacion", "actualización", "cambios", "arreglo", "arreglos", "prueba",
             "primer commit", "commit inicial", "subida", "avance", "avances", "version", "versión"}

ARCHIVOS_EXCLUIDOS = re.compile(
    r"(^|/)(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|poetry\.lock|Pipfile\.lock|composer\.lock|"
    r"Gemfile\.lock|Cargo\.lock|npm-shrinkwrap\.json|gradle\.lockfile)$"
    r"|\.min\.(js|css)$|\.map$|\.bundle\.js$|\.lock$"
    r"|(^|/)(dist|build|out|node_modules|vendor|target|\.idea|\.vscode|__pycache__|coverage|\.next)/"
    r"|\.(png|jpe?g|gif|ico|svg|webp|bmp|pdf|zip|gz|tar|jar|war|class|pyc|so|dll|exe|bin|woff2?|ttf|eot|"
    r"mp3|mp4|wav|ogg|db|sqlite3?|pkl|h5|onnx|pt|ipynb)$",
    re.I,
)


def es_bot(nombre: str, correo: str) -> bool:
    return bool(PATRON_BOT.search(nombre or "") or PATRON_BOT.search(correo or ""))


def archivo_excluido(ruta: str) -> bool:
    return bool(ARCHIVOS_EXCLUIDOS.search(ruta.replace("\\", "/")))


# ---------------------------------------------------------------- limpieza de texto (D2 y calidad)
RE_TRAILER = re.compile(r"^\s*(signed-off-by|co-authored-by|reviewed-by|acked-by|tested-by|reported-by|"
                        r"suggested-by|cc|change-id|git-svn-id)\s*:.*$", re.I | re.M)
RE_CORREO = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
RE_MENCION = re.compile(r"(?<![\w.])@[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})\b")
RE_URL_CREDENCIAL = re.compile(r"""https?://[^\s/@]+:[^\s/@]+@[^\s"'<>]+|https?://[^\s"'<>]*[?&]"""
                               r"""(?:token|key|access_token|api_key|apikey|secret|sig|signature)=[^\s"'<>]+""",
                               re.I)
# Referencias que no se deducen del diff (hallazgo de la prueba de humo, 18-11-2026)
RE_URL_ISSUE = re.compile(r"https?://(?:www\.)?github\.com/\S+/(?:issues|pull)/\d+\S*", re.I)
# Verbo de cierre que queda colgando al final de una línea ("..., closes" tras quitar "#45")
RE_CIERRE_COLGANTE = re.compile(r"[,;]?\s*\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?|refs?|see|related to)"
                                r"\s*:?\s*$", re.I | re.M)
RE_REF_ISSUE = re.compile(r"\(\s*(?:[\w.-]+/[\w.-]+)?#\d+\s*\)|(?<![\w&])(?:[\w.-]+/[\w.-]+)?#\d+\b|\bGH-\d+\b",
                          re.I)

SECRETOS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),                       # AWS
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),            # GitHub
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{30,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),                 # OpenAI y similares
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),                 # Google
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),          # Slack
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),   # JWT
]
RE_ASIGNACION_SECRETA = re.compile(
    r"""((?:password|passwd|pwd|secret|api_?key|access_?token|auth_?token|client_?secret|private_?key)"""
    r"""\s*[:=]\s*)(["'])([^"'\s]{6,})\2""", re.I)


def nfc(texto: str) -> str:
    return unicodedata.normalize("NFC", texto)


def depurar_privacidad(texto: str, contador: dict | None = None, menciones: bool = True) -> str:
    """Quita correos, credenciales, secretos y @menciones. Cuenta los reemplazos para la dataset card.

    En diffs se usa menciones=False: en código, "@algo" son decoradores de Python o anotaciones de Java.
    """
    def sub(patron, reemplazo, s, clave):
        nuevo, n = patron.subn(reemplazo, s)
        if contador is not None and n:
            contador[clave] = contador.get(clave, 0) + n
        return nuevo
    for p in SECRETOS:
        texto = sub(p, "<secreto>", texto, "secretos")
    texto = sub(RE_ASIGNACION_SECRETA, r"\1\2<secreto>\2", texto, "asignaciones_secretas")
    texto = sub(RE_URL_CREDENCIAL, "<url>", texto, "urls_con_credencial")
    texto = sub(RE_CORREO, "<correo>", texto, "correos")
    if menciones:
        texto = sub(RE_MENCION, "@usuario", texto, "menciones")
    return texto


def limpiar_mensaje(msg: str, contador: dict | None = None) -> str:
    msg = nfc(msg).replace("\r\n", "\n")
    msg = RE_TRAILER.sub("", msg)
    n0 = len(msg)
    msg = RE_URL_ISSUE.sub("", msg)
    msg = RE_REF_ISSUE.sub("", msg)
    msg = RE_CIERRE_COLGANTE.sub("", msg)
    if contador is not None and len(msg) != n0:
        contador["mensajes_con_ref_pr_issue"] = contador.get("mensajes_con_ref_pr_issue", 0) + 1
    msg = depurar_privacidad(msg, contador)
    # orden: espacios sobrantes y puntuación huérfana que dejan las referencias quitadas
    msg = re.sub(r"[ \t]+([,.;:)])", r"\1", msg)
    msg = re.sub(r"\(\s*\)", "", msg)
    msg = re.sub(r"[ \t]{2,}", " ", msg)
    msg = re.sub(r"[ \t]+$", "", msg, flags=re.M)
    msg = re.sub(r"\n{3,}", "\n\n", msg).strip(" \n:-,")
    if len(msg) > MAX_RESP_CHARS:
        corte = msg[:MAX_RESP_CHARS]
        msg = corte[: corte.rfind(" ")] if " " in corte[MAX_RESP_CHARS // 2:] else corte
    return msg.strip()


def mensaje_valido(msg: str) -> str | None:
    """Devuelve el motivo de descarte o None si el mensaje sirve como respuesta."""
    if not msg:
        return "mensaje_vacio"
    asunto = msg.split("\n", 1)[0].strip().lower().rstrip(".!")
    if asunto in GENERICOS or msg.strip().lower().rstrip(".!") in GENERICOS:
        return "mensaje_generico"
    # Palabras reales: sin URLs ni nombres de archivo o rutas (readme.md, src/app.py)
    prosa = re.sub(r"https?://\S+|<url>|\S+\.\w{1,5}\b|\S*[/\\]\S*", " ", msg)
    if len(re.findall(r"[^\W\d_]{2,}", prosa)) < 3:
        return "mensaje_corto"
    asunto_orig = msg.split("\n", 1)[0]
    # Símbolos típicos de código que casi nunca aparecen en prosa (comillas y paréntesis sí aparecen)
    simbolos = sum(ch in "={};|&^$\\" for ch in asunto_orig)
    if simbolos >= 3 and simbolos / max(len(asunto_orig), 1) > 0.06 or re.match(r"^\s*(RUN|import|from|"
                                                                                 r"const|let|var|def|return)\b", asunto_orig):
        return "mensaje_parece_codigo"
    if asunto.startswith(("merge branch", "merge pull request", "merge remote-tracking", "revert \"")):
        return "mensaje_merge_o_revert"
    return None
