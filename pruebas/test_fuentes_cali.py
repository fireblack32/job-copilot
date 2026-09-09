# -*- coding: utf-8 -*-
"""El tope de detalles tiene que repartirse entre terminos, no comerselo el primero."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "buscador"))

import fuentes_cali as F


def test_reparte_las_fichas_entre_los_terminos():
    por_termino = {
        "desarrollador": ["d1", "d2", "d3"],
        "telecomunicaciones": ["t1", "t2"],
        "ingeniero-electronico": ["e1"],
    }
    assert F._por_turnos(por_termino) == ["d1", "t1", "e1", "d2", "t2", "d3"]


def test_al_recortar_sobrevive_un_aviso_de_cada_termino():
    """El fallo real: con ~60 fichas por termino y tope 90, el detalle solo se
    bajaba de termino y medio. Los avisos de PLC y fibra optica se recolectaban
    y se tiraban sin abrirlos, y Cali daba menos candidatas tras ampliar."""
    por_termino = {
        "desarrollador": ["d%d" % i for i in range(60)],
        "telecomunicaciones": ["t%d" % i for i in range(60)],
        "ingeniero-electronico": ["e%d" % i for i in range(60)],
    }
    recortado = F._por_turnos(por_termino)[:90]
    assert sum(1 for x in recortado if x.startswith("d")) == 30
    assert sum(1 for x in recortado if x.startswith("t")) == 30
    assert sum(1 for x in recortado if x.startswith("e")) == 30


def test_no_falla_con_terminos_vacios():
    """Un termino que no devolvio nada no debe romper el reparto."""
    assert F._por_turnos({"a": [], "b": ["b1"]}) == ["b1"]
    assert F._por_turnos({}) == []
