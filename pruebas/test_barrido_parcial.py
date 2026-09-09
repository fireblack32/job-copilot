# -*- coding: utf-8 -*-
"""Un barrido parcial se suma a lo ya recolectado; no lo reemplaza."""
import io, json, os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "buscador"))


def _fusionar(crudo_nuevo, pedidas, todas, ruta_previo):
    """Replica la regla de buscar.py para poder probarla sin salir a la red."""
    if set(pedidas) != set(todas) and os.path.exists(ruta_previo):
        antes = json.load(io.open(ruta_previo, encoding="utf-8"))
        conservados = [r for r in antes if r.get("fuente") not in set(pedidas)]
        return conservados + crudo_nuevo
    return crudo_nuevo


TODAS = ["getonbrd", "torre", "computrabajo-cl"]


def _escribir(filas):
    fd, ruta = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    json.dump(filas, io.open(ruta, "w", encoding="utf-8"), ensure_ascii=False)
    return ruta


def test_un_barrido_parcial_conserva_las_otras_fuentes():
    """El fallo real: relanzar ocho fuentes para probar un arreglo dejo
    crudo.json en 84 KB y el ranking en 4 candidatas, habiendo tenido 2.106
    avisos y 301 candidatas. Se perdieron 25 minutos de barrido sin aviso."""
    previo = _escribir([{"fuente": "getonbrd", "id": "1"},
                        {"fuente": "torre", "id": "2"},
                        {"fuente": "computrabajo-cl", "id": "viejo"}])
    try:
        salida = _fusionar([{"fuente": "computrabajo-cl", "id": "nuevo"}],
                           ["computrabajo-cl"], TODAS, previo)
        fuentes_ = sorted(r["fuente"] for r in salida)
        assert fuentes_ == ["computrabajo-cl", "getonbrd", "torre"]
    finally:
        os.unlink(previo)


def test_lo_recien_barrido_manda_sobre_lo_viejo():
    """De la fuente que si se barrio se descarta lo anterior: sus avisos estan
    frescos y el portal ya bajo los que no siguen publicados."""
    previo = _escribir([{"fuente": "computrabajo-cl", "id": "viejo"}])
    try:
        salida = _fusionar([{"fuente": "computrabajo-cl", "id": "nuevo"}],
                           ["computrabajo-cl"], TODAS, previo)
        assert [r["id"] for r in salida] == ["nuevo"]
    finally:
        os.unlink(previo)


def test_un_barrido_completo_reemplaza_todo():
    """Cuando se barren todas las fuentes no hay nada que conservar."""
    previo = _escribir([{"fuente": "getonbrd", "id": "viejo"}])
    try:
        salida = _fusionar([{"fuente": "getonbrd", "id": "nuevo"}], TODAS, TODAS, previo)
        assert [r["id"] for r in salida] == ["nuevo"]
    finally:
        os.unlink(previo)


def test_sin_archivo_previo_no_falla():
    salida = _fusionar([{"fuente": "torre", "id": "1"}], ["torre"], TODAS,
                       os.path.join(tempfile.gettempdir(), "no-existe-jamas.json"))
    assert len(salida) == 1
