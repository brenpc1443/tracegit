"""Pruebas de la limpieza y la detección de idioma. Uso: python dataset/test_comun.py"""
from comun import archivo_excluido, depurar_privacidad, limpiar_mensaje, mensaje_valido
from idioma import detectar

MENSAJES = [
    ("Fix typo in App Engine hackiness (#5111)", "Fix typo in App Engine hackiness"),
    ("Fixes #12: crash when parsing empty lines", "Fixes: crash when parsing empty lines"),
    ("Agregar validación de correo juan.perez@gmail.com en el formulario\n\nSigned-off-by: Juan <j@x.com>",
     "Agregar validación de correo <correo> en el formulario"),
    ("Corrige el cálculo del promedio en notas.py, closes owner/repo#45", "Corrige el cálculo del promedio en notas.py"),
    ("thanks @octocat for the report", "thanks @usuario for the report"),
    ("Add GH-42 handler", "Add handler"),
]
for entrada, esperado in MENSAJES:
    obtenido = limpiar_mensaje(entrada)
    assert obtenido == esperado, (entrada, obtenido)

assert mensaje_valido("update") == "mensaje_generico"
assert mensaje_valido("Merge pull request from foo/bar") == "mensaje_merge_o_revert"
assert mensaje_valido("Add parser") == "mensaje_corto"
assert mensaje_valido("Add parser tests") is None
# Mensajes que son código o casi solo una URL / un archivo
for m in ['setuptools = "^50.3.2"', "RUN chmod +x./docker/entrypoint.sh", "(docker rm -f frw_backend || true) && \\",
          '"--log.level=DEBUG"', "Documentación: https://medium.com/x/iaapi-fastapi-template", "Formato readme.md",
          "import numpy as np"]:
    assert mensaje_valido(m) is not None, m
# Prosa legítima con comillas, paréntesis o identificadores
for m in ['Add "login" button (frontend)', "Fix off-by-one error in parse_line()", "Use config.yaml for settings path",
          "Agregado el método calcularPromedio() en la clase Alumno", "Update README with install steps",
          "Handle a == b case in comparator"]:
    assert mensaje_valido(m) is None, m

d = depurar_privacidad('password = "hunter2xyz"\nAKIAABCDEFGHIJKLMNOP\nurl="https://user:pw@host/x"\nmail a@b.co')
assert d == 'password = "<secreto>"\n<secreto>\nurl="<url>"\nmail <correo>', d

codigo = "@property\ndef nombre(self):\n@Override\npublic void run() {} // ana@uni.edu"
assert depurar_privacidad(codigo, menciones=False) == codigo.replace("ana@uni.edu", "<correo>")

for ruta, excl in [("package-lock.json", True), ("src/app.min.js", True), ("dist/main.js", True),
                   ("src/app.py", False), ("docs/img.png", True), ("src/Main.java", False)]:
    assert archivo_excluido(ruta) == excl, ruta

for texto, idioma in [("Añade pruebas unitarias para el módulo de usuarios", "es"),
                      ("Add unit tests for user module", "en"), ("Refactor parseConfig in utils.py", "en"),
                      ("corrige bug", "es"), ("Fehler beim Login behoben", "otro")]:
    assert detectar(texto)[0] == idioma, (texto, detectar(texto))
print("todas las pruebas pasan")
