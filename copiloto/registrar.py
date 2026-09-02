# -*- coding: utf-8 -*-
"""
Registra en la bitacora lo que la persona postulo por su cuenta.

Es la vuelta del circuito del tablero. La persona abre `tablero.html`, postula a
mano, pulsa "Copiar lo que postule" y pega el resultado aqui:

    python -m copiloto.registrar < pegado.txt
    python -m copiloto.registrar https://... https://...

Acepta el pegado tal cual, con la linea de encabezado y la basura que traiga: se
extraen las URLs y se ignora el resto. Pedirle a alguien que limpie un pegado
antes de entregarlo es la clase de friccion que hace que deje de reportar, y una
bitacora que la persona deja de alimentar es peor que no tenerla.

Las URLs que no aparecen en el ranking **no se registran**: se avisan. Una URL
suelta que no calza con ninguna candidata suele ser un pegado a medias, y
anotarla crearia un registro que despues nadie puede relacionar con nada.
"""

from __future__ import annotations

import io
import json
import os
import re
import sys

from copiloto.bitacora import Bitacora, Estado, Quien

AQUI = os.path.dirname(os.path.abspath(__file__))
RANKING = os.path.join(AQUI, "..", "resultados", "ranking.json")
BITACORA = os.path.join(AQUI, "..", "resultados", "bitacora.json")

RE_URL = re.compile(r"https?://[^\s<>\"']+")


def urls_en(texto: str) -> list[str]:
    """Saca las URLs de un pegado, sin duplicados y en el orden en que venian."""
    vistas, out = set(), []
    for u in RE_URL.findall(texto or ""):
        u = u.rstrip(".,;)")
        if u not in vistas:
            vistas.add(u)
            out.append(u)
    return out


def main(argv=None) -> int:
    import argparse

    p = argparse.ArgumentParser(
        description="Anota en la bitacora las vacantes postuladas a mano.")
    p.add_argument("urls", nargs="*", help="URLs; si no hay, se lee de stdin.")
    p.add_argument("--ranking", default=RANKING)
    p.add_argument("--bitacora", default=BITACORA)
    p.add_argument("--quien", default=Quien.PERSONA,
                   choices=[Quien.PERSONA, Quien.COPILOTO])
    p.add_argument("--estado", default=Estado.ENVIADA,
                   choices=[Estado.ENVIADA, Estado.DESCARTADA, Estado.EN_CURSO])
    p.add_argument("--nota", default="")
    a = p.parse_args(argv)

    crudo = " ".join(a.urls) if a.urls else sys.stdin.read()
    urls = urls_en(crudo)
    if not urls:
        print("No se encontro ninguna URL en lo que llego.")
        return 1

    with io.open(a.ranking, encoding="utf-8") as f:
        candidatas = json.load(f)

    bit = Bitacora(a.bitacora)
    hechos, perdidas = bit.registrar_urls(urls, candidatas, quien=a.quien,
                                          estado=a.estado)
    if a.nota:
        for r in hechos:
            r.nota = a.nota
    bit.guardar()

    print("registradas:", len(hechos))
    for r in hechos:
        print("   %-38s %s" % ((r.empresa or "?")[:38], (r.titulo or "?")[:60]))
    if perdidas:
        print("\nno estaban en el ranking (no se registraron):")
        for u in perdidas:
            print("   ", u)
        print("Si son vacantes reales, pasamelas con empresa y cargo y las anoto aparte.")
    print("\nbitacora:", bit.resumen())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
