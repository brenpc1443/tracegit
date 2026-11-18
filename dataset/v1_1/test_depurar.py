"""Pruebas de los filtros de la v1.1.   Uso:  python -m pytest dataset/v1_1/test_depurar.py"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from depurar import depurar, es_plantilla_web  # noqa: E402


def test_plantillas_web_de_github():
    for m in ["Add files via upload", "Create README.md", "Update src/app.js", "Delete org.eclipse.wst.common.component",
              "Rename main.py to app.py", "  Update index.html  "]:
        assert es_plantilla_web(m), m


def test_mensajes_humanos_parecidos_no_son_plantilla():
    for m in ["add files via upload of the logo", "delete wemake-python-styleguide", "Add connection to POS",
              "rename IDE to editor", "Update README.md with install steps", "Update dependencies",
              "Create login view", "add timestamp to logs"]:
        assert not es_plantilla_web(m), m


def _ej(repo, msg, sha, split="train"):
    return {"split": split, "messages": [{"role": "assistant", "content": msg}], "meta": {"repo": repo, "sha": sha}}


def test_tope_de_mensajes_identicos_y_repos_pequenos():
    filas = [_ej("a/x", "still working on ci", f"s{i}") for i in range(6)]
    filas += [_ej("a/x", f"mensaje distinto {i}", f"d{i}") for i in range(4)]
    filas += [_ej("b/y", "Add files via upload", "u0")] + [_ej("b/y", f"cambio {i}", f"c{i}") for i in range(3)]
    vivos, descartes, _ = depurar(filas, random.Random(42))
    assert descartes["mensaje_repetido_en_repo"] == 4
    assert descartes["plantilla_web_github"] == 1
    assert descartes["repo_con_pocos_tras_depurar"] == 3          # b/y queda con 3 < 5
    assert sum(1 for f in vivos if f["messages"][-1]["content"] == "still working on ci") == 2
    assert {f["meta"]["repo"] for f in vivos} == {"a/x"}


def test_reproducible():
    filas = [_ej("a/x", "igual", f"s{i}") for i in range(10)] + [_ej("a/x", f"otro {i}", f"o{i}") for i in range(5)]
    a = [f["meta"]["sha"] for f in depurar(filas, random.Random(42))[0]]
    b = [f["meta"]["sha"] for f in depurar(list(filas), random.Random(42))[0]]
    assert a == b


if __name__ == "__main__":
    for nombre, prueba in list(globals().items()):
        if nombre.startswith("test_"):
            prueba()
    print("todas las pruebas de la v1.1 pasan")
