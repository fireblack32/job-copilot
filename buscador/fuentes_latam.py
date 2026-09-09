# -*- coding: utf-8 -*-
"""Computrabajo fuera de Colombia: el resto de LATAM hispanohablante.

El buscador solo miraba Colombia, y con eso quedaba fuera todo un mercado que
habla el mismo idioma y contrata remoto. Computrabajo opera con el mismo motor
en nueve paises, asi que el adaptador de Colombia sirve tal cual cambiando el
dominio y la moneda.

    mx.computrabajo.com   cl.computrabajo.com   ar.computrabajo.com
    pe.computrabajo.com   pa.computrabajo.com   cr.computrabajo.com
    uy.computrabajo.com   ec.computrabajo.com

**Espana no esta y no es un olvido.** `computrabajo.es` responde 200 pero
devuelve la misma pagina generica de 33 KB para cualquier busqueda: no publica
los avisos en el HTML. InfoJobs devuelve 1,19 MB sin un solo enlace de oferta
reconocible --se arma en el navegador-- y Tecnoempleo responde 403. La via para
Espana no es esta; son las vacantes remotas de empresas espanolas, que si
aparecen por Torre y Get on Board.

A diferencia del adaptador colombiano, aqui **solo se recogen las remotas**. Una
vacante presencial en Lima o en Santiago no le sirve a alguien que vive en Cali,
y ademas suele exigir residencia y documento del pais.
"""

from __future__ import annotations

import re
import time

from fuentes import _get, _strip
from fuentes_cali import clasificar_modalidad
from fuentes_co import job_posting

#: Pais -> (subdominio, moneda local). La moneda importa: sin ella un sueldo
#: mexicano de 40.000 se leeria como si fueran 40.000 pesos colombianos.
PAISES = {
    "mx": ("mx.computrabajo.com", "MXN", "Mexico"),
    "cl": ("cl.computrabajo.com", "CLP", "Chile"),
    "ar": ("ar.computrabajo.com", "ARS", "Argentina"),
    "pe": ("pe.computrabajo.com", "PEN", "Peru"),
    "pa": ("pa.computrabajo.com", "USD", "Panama"),
    "cr": ("cr.computrabajo.com", "CRC", "Costa Rica"),
    "uy": ("uy.computrabajo.com", "UYU", "Uruguay"),
    "ec": ("ec.computrabajo.com", "USD", "Ecuador"),
}

#: Se sobreescribe desde buscar.py con los terminos del perfil.
CT_BUSQUEDAS = ["desarrollador", "ingeniero-de-sistemas", "programador"]

_RE_REMOTO = re.compile(r"remoto|teletrabajo|h[ií]brido|home office", re.I)


def _recolectar(codigo, paginas, max_detalle):
    dominio, moneda, pais = PAISES[codigo]
    base = "https://" + dominio
    por_termino, vistos = {}, set()

    for termino in CT_BUSQUEDAS:
        fichas = por_termino.setdefault(termino, [])
        for p in range(1, paginas + 1):
            url = "%s/trabajo-de-%s" % (base, termino)
            if p > 1:
                url += "?p=%d" % p
            try:
                s = _get(url, timeout=30)
            except Exception as e:
                print("  [ct-%s]" % codigo, termino, p, "ERR", e)
                break
            arts = re.findall(
                r"<article[^>]*data-id=.([^'\"]+).[^>]*>(.*?)</article>", s, re.S)
            if not arts:
                break
            for oid, blk in arts:
                if oid in vistos:
                    continue
                vistos.add(oid)
                href = re.search(r'href="(/ofertas-de-trabajo/[^"]+)"', blk)
                # Criba barata sobre el listado; la buena viene despues, sobre
                # el texto completo del aviso.
                if href and _RE_REMOTO.search(blk):
                    tit = re.search(r"<h2[^>]*>\s*<a[^>]*>(.*?)</a>", blk, re.S)
                    fichas.append({
                        "id": oid,
                        "url": base + href.group(1),
                        "titulo": _strip(tit.group(1)).strip() if tit else None,
                    })
            time.sleep(0.5)

    # Mismo reparto por turnos que en Cali: sin el, el tope de detalles se lo
    # come el primer termino y los perfiles de telecom e industrial no se abren.
    orden = []
    for i in range(max((len(v) for v in por_termino.values()), default=0)):
        for fichas in por_termino.values():
            if i < len(fichas):
                orden.append(fichas[i])

    out = []
    for f in orden[:max_detalle]:
        try:
            s = _get(f["url"], timeout=30)
        except Exception:
            continue
        jp = job_posting(s)
        desc = _strip(jp.get("description")) if jp else _strip(s)[:6000]
        titulo_crudo = f["titulo"] or (jp.get("title") if jp else "") or ""

        # Aqui esta el filtro que importa, y va sobre el texto completo del
        # aviso, no sobre el bloque del listado.
        #
        # La criba del listado da falsos positivos: marca "remoto" cualquier
        # aviso que mencione la palabra "hibrido" en alguna linea. En Colombia
        # eso da igual --una hibrida en Cali es aceptable-- pero aqui no: una
        # hibrida en Santiago o en Ciudad de Mexico exige vivir alli.
        #
        # Sin este filtro, de 62 vacantes internacionales solo 4 eran remotas
        # de verdad; las otras 58 pedian mudarse a Benito Juarez, Las Condes,
        # Lima o Iquique.
        if clasificar_modalidad(titulo_crudo + " " + desc, titulo_crudo) != "remoto":
            time.sleep(0.2)
            continue

        sal_min = sal_max = None
        if jp:
            bs = ((jp.get("baseSalary") or {}).get("value")) or {}
            sal_min = bs.get("minValue") or bs.get("value")
            sal_max = bs.get("maxValue")
        org = (jp.get("hiringOrganization") or {}).get("name") if jp else None
        titulo = f["titulo"] or (jp.get("title") if jp else None)
        out.append({
            "fuente": "computrabajo-" + codigo,
            "id": f["id"], "titulo": titulo, "empresa": org, "url": f["url"],
            "remoto": True, "ubicacion": pais,
            "sal_min": float(sal_min) if sal_min else None,
            "sal_max": float(sal_max) if sal_max else None,
            "moneda": moneda, "periodo": "mes",
            "texto": (titulo or "") + " " + desc,
            "publicado": jp.get("datePosted") if jp else None,
        })
        time.sleep(0.4)
    return out


def adaptador(codigo, paginas=2, max_detalle=40):
    """Devuelve el adaptador de un pais, listo para registrar en ADAPTADORES."""
    def fn():
        return _recolectar(codigo, paginas, max_detalle)
    fn.__name__ = "computrabajo_" + codigo
    return fn


ADAPTADORES = {"computrabajo-" + c: adaptador(c) for c in PAISES}
