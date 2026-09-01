# -*- coding: utf-8 -*-
"""
Adaptadores para vacantes presenciales e hibridas en Cali.

Los adaptadores de `fuentes_co.py` descartan todo lo que no sea remoto, que era
justo lo que se buscaba antes. Aqui pasa lo contrario: interesa lo presencial y
lo hibrido, siempre que este en Cali, y ademas hay que capturar dos datos que el
buscador remoto nunca necesito:

- **La modalidad real** (remoto / hibrido / presencial). El titulo miente a
  menudo; la descripcion suele decir la verdad.
- **La zona de la ciudad.** Se prefiere el sur, y para eso hace falta mirar
  barrios y referencias, porque casi ninguna oferta dice "sur" con esa palabra.
"""
import re
import time

from fuentes import _get, _strip
from fuentes_co import _ld_blocks, job_posting

# Barrios, comunas y referencias del sur de Cali. Es una lista de literales a
# proposito: inferir la zona desde una direccion sin geocodificar produce mas
# errores que aciertos, y aqui un falso positivo manda a cruzar la ciudad todos
# los dias.
SUR_CALI = [
    "ciudad jardin", "pance", "valle del lili", "ciudad universitaria", "caney",
    "limonar", "capri", "el ingenio", "canaveralejo", "melendez", "napoles",
    "bochalema", "alferez real", "el refugio", "tequendama", "pampalinda",
    "san fernando", "holguines", "unicentro", "jardin plaza", "cosmocentro",
    "la hacienda", "autopista sur", "calle 5", "carrera 100", "carrera 98",
    "canasgordas", "los cristales", "sur de cali", "zona sur",
    "comuna 17", "comuna 22", "comuna 19",
]

# El norte y el centro se marcan para poder ordenar, no para descartar: una
# oferta muy buena en el norte sigue siendo una oferta.
NORTE_CENTRO_CALI = [
    "chipichape", "granada", "versalles", "menga", "la flora", "san nicolas",
    "centenario", "el penon", "santa monica", "salomia", "calima", "yumbo",
    "comuna 2", "comuna 4", "norte de cali",
]

RE_HIBRIDO = re.compile(r"h[ií]brid", re.I)
RE_REMOTO = re.compile(r"remot|teletrabajo|home\s*office|desde casa", re.I)
RE_PRESENCIAL = re.compile(r"presencial|en sitio|on\s*site|100%\s*oficina", re.I)

#: Senales de contrato laboral colombiano con prestaciones. Sin esto, una oferta
#: por prestacion de servicios se cuela como si trajera salud y pension.
RE_PRESTACIONES = re.compile(
    r"prestaciones de ley|prestaciones sociales|t[eé]rmino indefinido|"
    r"t[eé]rmino fijo|contrato laboral|todas las prestaciones|"
    r"\beps\b|\barl\b|caja de compensaci[oó]n|cesant[ií]as|prima de servicios|"
    r"seguridad social|salud y pensi[oó]n",
    re.I,
)

#: Contratos que NO traen prestaciones, aunque el aviso hable de "beneficios".
RE_SIN_PRESTACIONES = re.compile(
    r"prestaci[oó]n de servicios|contrato civil|por honorarios|"
    r"cuenta de cobro|freelance|independiente",
    re.I,
)


def clasificar_modalidad(texto, titulo=""):
    """Devuelve 'remoto', 'hibrido' o 'presencial'.

    El hibrido gana sobre los otros dos: un aviso que dice "hibrido, 2 dias
    remoto" es hibrido, no remoto, y confundirlos es justo lo que hace aparecer
    vacantes que en realidad exigen presentarse en otra ciudad.
    """
    campo = (titulo or "") + " " + (texto or "")
    if RE_HIBRIDO.search(campo):
        return "hibrido"
    if RE_PRESENCIAL.search(campo):
        return "presencial"
    if RE_REMOTO.search(campo):
        return "remoto"
    # Un aviso local que no declara nada es, en la practica, presencial.
    return "presencial"


def zona_cali(texto):
    """'sur', 'norte_centro' o None. None significa que el aviso no lo dice."""
    t = (texto or "").lower()
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u")):
        t = t.replace(a, b)
    for barrio in SUR_CALI:
        if barrio in t:
            return "sur"
    for barrio in NORTE_CENTRO_CALI:
        if barrio in t:
            return "norte_centro"
    return None


def tiene_prestaciones(texto):
    """True / False / None. None es 'el aviso no lo dice', que no es lo mismo que no.

    Se devuelve None en vez de False a proposito: descartar por silencio dejaria
    fuera media bolsa de empleo colombiana, donde el contrato laboral se da por
    supuesto y no se escribe.
    """
    if not texto:
        return None
    if RE_SIN_PRESTACIONES.search(texto) and not RE_PRESTACIONES.search(texto):
        return False
    if RE_PRESTACIONES.search(texto):
        return True
    return None


def _direccion(jp):
    """Saca la direccion del JobPosting, que llega como dict o como lista."""
    if not jp:
        return ""
    addr = jp.get("jobLocation") or {}
    if isinstance(addr, list):
        addr = addr[0] if addr else {}
    a = (addr.get("address") or {}) if isinstance(addr, dict) else {}
    if not isinstance(a, dict):
        return ""
    partes = [a.get("streetAddress"), a.get("addressLocality"), a.get("addressRegion")]
    return " ".join(str(p) for p in partes if p)


def _salario(jp, texto):
    """Salario del JSON-LD, con respaldo al primer monto con formato de pesos."""
    sal_min = sal_max = None
    if jp:
        bs = ((jp.get("baseSalary") or {}).get("value")) or {}
        if isinstance(bs, dict):
            sal_min = bs.get("minValue") or bs.get("value")
            sal_max = bs.get("maxValue")
    if not sal_min:
        m = re.search(r"\$\s?([\d\.]{7,})", texto or "")
        if m:
            try:
                sal_min = float(m.group(1).replace(".", ""))
            except ValueError:
                sal_min = None
    return (float(sal_min) if sal_min else None,
            float(sal_max) if sal_max else None)


def _job_posting(html):
    """Delega en el buscador compartido, que sabe entrar en @graph."""
    return job_posting(html)


# --------------------------------------------------------------- Computrabajo
CT_TERMINOS = [
    "desarrollador", "ingeniero-de-sistemas", "soporte-tecnico", "programador",
    "devops", "analista-de-datos", "ingeniero-de-software", "python",
]


def computrabajo_cali(paginas=3, max_detalle=90):
    """Vacantes en Cali. A diferencia del adaptador remoto, NO filtra por remoto."""
    fichas, vistos = [], set()
    for termino in CT_TERMINOS:
        for p in range(1, paginas + 1):
            url = "https://co.computrabajo.com/trabajo-de-%s-en-cali" % termino
            if p > 1:
                url += "?p=%d" % p
            try:
                s = _get(url, timeout=30)
            except Exception as e:
                print("  [ct-cali]", termino, p, "ERR", e)
                break
            arts = re.findall(r"<article[^>]*data-id=.([^'\"]+).[^>]*>(.*?)</article>",
                              s, re.S)
            if not arts:
                break
            for oid, blk in arts:
                if oid in vistos:
                    continue
                vistos.add(oid)
                href = re.search(r'href="(/ofertas-de-trabajo/[^"]+)"', blk)
                tit = re.search(r"<h2[^>]*>\s*<a[^>]*>(.*?)</a>", blk, re.S)
                if href:
                    fichas.append({
                        "id": oid,
                        "url": "https://co.computrabajo.com" + href.group(1),
                        "titulo": _strip(tit.group(1)).strip() if tit else None,
                        "resumen": _strip(blk),
                    })
            time.sleep(0.45)

    out = []
    for f in fichas[:max_detalle]:
        try:
            s = _get(f["url"], timeout=30)
        except Exception:
            continue
        jp = _job_posting(s)
        desc = _strip(jp.get("description")) if jp else _strip(s)[:6000]
        titulo = f["titulo"] or (jp.get("title") if jp else None)
        texto = " ".join([titulo or "", desc, f.get("resumen", "")])
        loc = _direccion(jp)
        sal_min, sal_max = _salario(jp, texto)

        out.append({
            "fuente": "computrabajo-cali", "id": f["id"], "titulo": titulo,
            "empresa": (jp.get("hiringOrganization") or {}).get("name") if jp else None,
            "url": f["url"],
            "modalidad": clasificar_modalidad(texto, titulo),
            "remoto": bool(RE_REMOTO.search(texto)),
            "ubicacion": loc.strip() or "Cali",
            "zona": zona_cali(loc + " " + texto),
            "prestaciones": tiene_prestaciones(texto),
            "sal_min": sal_min, "sal_max": sal_max,
            "moneda": "COP", "periodo": "mes",
            "texto": texto,
            "publicado": jp.get("datePosted") if jp else None,
        })
        time.sleep(0.35)
    return out


# ------------------------------------------------------------------- elempleo
EE_CALI = [
    "https://www.elempleo.com/co/ofertas-empleo/trabajo-en-cali",
    "https://www.elempleo.com/co/ofertas-empleo/ciudad-cali",
    "https://www.elempleo.com/co/ofertas-empleo/trabajo-desarrollador-en-cali",
]


def elempleo_cali(max_detalle=70):
    fichas, vistos = [], set()
    for url in EE_CALI:
        try:
            s = _get(url, timeout=35)
        except Exception as e:
            print("  [ee-cali] listado ERR", e)
            continue
        for blk in _ld_blocks(s):
            if isinstance(blk, dict) and blk.get("@type") == "ItemList":
                for it in blk.get("itemListElement", []):
                    item = it.get("item") or {}
                    oid = item.get("@id")
                    if oid and oid not in vistos:
                        vistos.add(oid)
                        fichas.append({"url": oid, "titulo": item.get("name")})
        time.sleep(0.5)

    out = []
    for f in fichas[:max_detalle]:
        try:
            s = _get(f["url"], timeout=30)
        except Exception:
            continue
        jp = _job_posting(s)
        desc = _strip(jp.get("description")) if jp else ""
        texto = (f["titulo"] or "") + " " + desc
        loc = _direccion(jp)
        sal_min, sal_max = _salario(jp, texto or _strip(s))
        moneda = "COP"
        if jp:
            moneda = (jp.get("baseSalary") or {}).get("currency") or "COP"

        out.append({
            "fuente": "elempleo-cali", "id": f["url"].rsplit("-", 1)[-1],
            "titulo": f["titulo"],
            "empresa": (jp.get("hiringOrganization") or {}).get("name") if jp else None,
            "url": f["url"],
            "modalidad": clasificar_modalidad(texto, f["titulo"]),
            "remoto": bool(RE_REMOTO.search(texto)),
            "ubicacion": loc.strip() or "Cali",
            "zona": zona_cali(loc + " " + texto),
            "prestaciones": tiene_prestaciones(texto),
            "sal_min": sal_min, "sal_max": sal_max,
            "moneda": moneda, "periodo": "mes",
            "texto": texto,
            "publicado": jp.get("datePosted") if jp else None,
        })
        time.sleep(0.4)
    return out
