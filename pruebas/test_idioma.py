# -*- coding: utf-8 -*-
"""El filtro de idioma: lo que dejaba pasar avisos en ingles.

Los tres casos de esta prueba se colaron de verdad en un tablero de 265
candidatas: 18 avisos redactados enteros en ingles, 9 que pedian ingles
intermedio-avanzado y 94 de Torre que exigian ingles conversacional.
"""
import io
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "buscador"))
import buscar


@pytest.fixture(autouse=True)
def _restaurar_res():
    """`_depurar_torre` lee el cache de buscar.RES; estas pruebas lo apuntan a
    un temporal. Sin restaurarlo, se lo dejarian cambiado a las demas."""
    original = buscar.RES
    yield
    buscar.RES = original


INGLES = (
    "You will build with context and control, continuous delivery and unique "
    "requests across separate teams. Requirements: experience with distributed "
    "systems. We are a team that values our role in the product. 5 years."
)
ESPANOL = (
    "Buscamos un desarrollador con experiencia en desarrollo de software para "
    "nuestro equipo. Requisitos: 3 años de experiencia, conocimiento de Python "
    "y trabajo con bases de datos. La empresa ofrece contrato a termino indefinido."
)


def test_un_aviso_en_ingles_se_bloquea():
    assert buscar.idioma_bloquea(INGLES) == "aviso redactado en ingles"


def test_un_aviso_en_espanol_no_se_bloquea():
    assert buscar.idioma_bloquea(ESPANOL) is None


def test_las_subcadenas_no_cuentan_como_espanol():
    """`con` vive dentro de context y control, `que` dentro de request, `para`
    dentro de separate. Contando subcadenas, un aviso en ingles acumulaba
    palabras en espanol y la proporcion nunca saltaba."""
    low = "context control continuous request unique separate"
    assert buscar._contar(low, ["con", "que", "para"]) == 0
    assert sum(low.count(w) for w in ["con", "que", "para"]) > 0


def test_el_conteo_ve_la_palabra_suelta():
    assert buscar._contar("trabajo con python para el equipo", ["con", "para"]) == 2


def test_ingles_intermedio_avanzado_se_bloquea():
    for t in ("ingles intermedio-avanzado o avanzado (indispensable)",
              "Ingles intermedio/avanzado (Obligatorio)",
              "ingles intermedio alto"):
        assert buscar.idioma_bloquea(t), t


def test_ingles_intermedio_a_secas_pasa():
    """El perfil declara B2 escrito: un intermedio no lo descalifica."""
    assert buscar.idioma_bloquea("ingles intermedio") is None
    assert buscar.idioma_bloquea("ingles basico") is None


# --------------------------------------------------------------- Torre
def _rank():
    return [
        {"fuente": "torre", "id": "abierto-es"},
        {"fuente": "torre", "id": "en-ingles"},
        {"fuente": "torre", "id": "cerrado"},
        {"fuente": "torre", "id": "sin-dato"},
        {"fuente": "getonbrd", "id": "otra-fuente"},
    ]


CACHE = {
    "abierto-es": {"locale": "es", "idiomas": [["Spanish", "fully-fluent"]],
                   "estado": "open", "ingles": False},
    "en-ingles": {"locale": "en", "idiomas": [["English", "conversational"]],
                  "estado": "open", "ingles": True},
    "cerrado": {"locale": "es", "idiomas": [], "estado": "closed", "ingles": False},
}


def _correr(tmp_path):
    buscar.RES = str(tmp_path)
    io.open(os.path.join(str(tmp_path), buscar.CACHE_TORRE), "w", encoding="utf-8").write(
        json.dumps(CACHE, ensure_ascii=False))
    descartes, motivos = {"idioma": 0}, {}
    quedan = buscar._depurar_torre(_rank(), descartes, motivos, sin_red=True)
    return [r["id"] for r in quedan], descartes, motivos


def test_torre_en_ingles_se_descarta(tmp_path):
    ids, descartes, _ = _correr(tmp_path)
    assert "en-ingles" not in ids
    assert descartes["idioma"] == 2


def test_torre_cerrada_se_descarta(tmp_path):
    ids, _, motivos = _correr(tmp_path)
    assert "cerrado" not in ids
    assert any("cerrado" in m for m in motivos)


def test_sin_dato_no_se_descarta(tmp_path):
    """Un timeout no puede costar una candidata buena."""
    assert "sin-dato" in _correr(tmp_path)[0]


def test_las_otras_fuentes_no_se_tocan(tmp_path):
    assert "otra-fuente" in _correr(tmp_path)[0]


def test_lo_que_esta_en_espanol_y_abierto_se_queda(tmp_path):
    assert "abierto-es" in _correr(tmp_path)[0]
