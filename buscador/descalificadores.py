# -*- coding: utf-8 -*-
"""
Descalificadores: lo que hace imposible una vacante, sin importar el encaje.

Un aviso puede coincidir perfecto en stack y aun asi estar cerrado. Pedir C1 de
ingles a alguien con B1, o exigir residencia en Chile a alguien en Colombia, no
son "menos puntos": son un no.

El buscador los trataba como si fueran puntaje, y por eso cuatro de seis vacantes
recomendadas resultaron imposibles al abrirlas. La correccion es de orden: **el
descalificador se evalua antes de puntuar**, y su respuesta es binaria.

    aviso ──> descalificadores ──> [descartado, con motivo]
                    │
                    └──> puntuacion de encaje

Cada funcion devuelve el motivo como texto, o None si no descalifica. Devolver el
motivo y no solo True importa: sin el, un descarte es indistinguible de un fallo
del adaptador, y ya perdimos noventa vacantes por no notar esa diferencia.
"""

from __future__ import annotations

import re
import unicodedata


def sin_tildes(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s or "")
                   if unicodedata.category(c) != "Mn").lower()


# ------------------------------------------------------------------- idioma
#
# Niveles del marco comun europeo por encima de lo que la persona sostiene, y
# las formas en que un aviso pide ingles de trabajo sin nombrar un nivel.
_NIVELES = {"a1": 1, "a2": 2, "b1": 3, "b2": 4, "c1": 5, "c2": 6}

RE_NIVEL_MCER = re.compile(r"\b([abc][12])\b", re.I)

#: Formas de exigir ingles de trabajo sin dar un nivel. Todas implican sostener
#: una conversacion, que es justo lo que un B1 no garantiza.
RE_INGLES_DE_TRABAJO = re.compile(
    r"requiere postular en ingl[eé]s|"
    r"ingl[eé]s\s+(avanzado|fluido|fluidez|profesional|conversacional|nativo|de negocios)|"
    r"(advanced|fluent|proficient|professional|business|native)\s+english|"
    r"english\s+(level\s+)?(c1|c2|advanced|fluent|proficiency|required|is required)|"
    r"must\s+(be\s+)?(fluent|proficient)\s+in\s+english|"
    r"dominio\s+(del\s+)?ingl[eé]s",
    re.I,
)


def exige_ingles(texto: str, nivel_persona: str = "b1") -> str | None:
    """Motivo si el aviso exige mas ingles del que la persona sostiene.

    Se mira el nivel MCER declarado y, aparte, las formulas que piden ingles de
    trabajo sin nombrar nivel. La segunda via es la que se escapaba: un aviso que
    dice "Requiere postular en Ingles" nunca escribe "C1".
    """
    t = texto or ""
    mio = _NIVELES.get(nivel_persona.lower(), 3)

    for m in RE_NIVEL_MCER.finditer(t):
        nivel = m.group(1).lower()
        if _NIVELES.get(nivel, 0) > mio:
            # Un B2 suelto puede referirse a otra cosa; se exige que el entorno
            # hable de ingles para no descartar por una coincidencia tonta.
            ventana = sin_tildes(t[max(0, m.start() - 90):m.end() + 90])
            if "ingles" in ventana or "english" in ventana:
                return "exige ingles %s y la persona declara %s" % (
                    nivel.upper(), nivel_persona.upper())

    if RE_INGLES_DE_TRABAJO.search(t):
        return "exige ingles de trabajo (avanzado, fluido o postular en ingles)"
    return None


# ---------------------------------------------------------------- geografia
#
# Un aviso puede restringir por pais de dos formas: nombrando los paises
# admitidos, o prohibiendo trabajar desde fuera de uno.
RE_SOLO_DESDE = re.compile(
    r"(?:no\s+es\s+posible|no\s+se\s+puede|no\s+puedes?)[^.]{0,40}"
    r"(?:desde\s+fuera\s+de|fuera\s+de)\s+([a-zA-Záéíóúñ ]{3,20})",
    re.I,
)

RE_DEBES_RESIDIR = re.compile(
    r"(?:debes?|deber[aá]s?|necesitas?|must)\s+(?:residir|vivir|estar|reside|live)"
    r"[^.]{0,120}",
    re.I,
)

RE_SOLO_PARA = re.compile(
    r"(?:solo|s[oó]lo|[uú]nicamente|exclusivamente)\s+(?:para|en|residentes\s+de)\s+"
    r"([a-zA-Záéíóúñ ]{3,20})",
    re.I,
)


def restringe_pais(texto: str, pais_persona: str = "colombia") -> str | None:
    """Motivo si el aviso excluye el pais de la persona.

    La regla es conservadora: solo descarta cuando el aviso enumera paises y el
    de la persona **no** esta entre ellos. Un aviso que no dice nada no descarta,
    porque el silencio no es una prohibicion.
    """
    t = texto or ""
    mio = sin_tildes(pais_persona)

    m = RE_SOLO_DESDE.search(t)
    if m:
        pais = sin_tildes(m.group(1)).strip()
        if pais and mio not in pais and pais not in mio:
            return "no permite trabajar desde fuera de %s" % m.group(1).strip()

    for patron in (RE_DEBES_RESIDIR, RE_SOLO_PARA):
        m = patron.search(t)
        if m:
            frase = sin_tildes(m.group(0))
            # Si la frase enumera paises y el nuestro no aparece, descarta.
            paises = re.findall(
                r"\b(colombia|chile|argentina|peru|mexico|espana|uruguay|"
                r"ecuador|bolivia|panama|costa rica|brasil|venezuela|"
                r"estados unidos|usa|united states|canada)\b", frase)
            if paises and mio not in paises:
                return "restringe a %s" % ", ".join(sorted(set(paises)))
    return None


# ------------------------------------------------------------------- ciudad
#
# Una vacante hibrida o presencial exige estar donde queda la oficina. Si esa
# ciudad no es la de la persona, no importa que el aviso diga "remoto" en alguna
# linea: NTT DATA, PROCIBERNETICA y COMWARE entraron como remotas siendo hibridas
# en Bogota, porque el adaptador vio la palabra "remoto" dentro de
# "presencial y remoto".
CIUDADES_CO = re.compile(
    r"\b(bogota|medellin|cali|barranquilla|cartagena|bucaramanga|pereira|"
    r"manizales|cucuta|ibague|santa marta|villavicencio|neiva|armenia|pasto|"
    r"monteria|valledupar|popayan|tunja|sincelejo)\b")


def exige_otra_ciudad(modalidad: str, ubicacion: str = "", texto: str = "",
                      ciudad: str = "cali") -> str | None:
    """Motivo si el aviso pide presencia en una ciudad que no es la de la persona.

    Se mira primero la ubicacion estructurada y solo se cae al texto libre cuando
    no hay ninguna: en el texto, "Bogota" puede ser la sede de la empresa y no el
    sitio del puesto. Es la misma leccion que dejo Mederi.

    No entra en `descalifica()` porque necesita la modalidad ya clasificada, que
    es un campo del adaptador y no algo que se lea del texto. Vive aqui igual
    porque es lo mismo que las demas: no hace la vacante peor, la hace imposible.
    """
    if sin_tildes(modalidad or "") not in ("hibrido", "presencial"):
        return None
    mia = sin_tildes(ciudad or "")
    if not mia:
        return None

    # La ubicacion estructurada manda. Solo si ahi no hay ninguna ciudad se mira
    # el texto: muchos avisos ponen "Colombia" como ubicacion y nombran la ciudad
    # una sola vez en el cuerpo. Caer al texto por "ubicacion vacia" no bastaba,
    # porque "Colombia" no esta vacia y sin embargo no dice donde es.
    ciudades = set(CIUDADES_CO.findall(sin_tildes(ubicacion or "")))
    if not ciudades:
        ciudades = set(CIUDADES_CO.findall(sin_tildes(texto or "")))
    # El silencio no descarta: media bolsa colombiana no nombra la ciudad.
    if not ciudades or mia in ciudades:
        return None
    return "%s en %s y la persona esta en %s" % (
        sin_tildes(modalidad), ", ".join(sorted(ciudades)), mia)


# ------------------------------------------------------------- certificaciones
RE_CERT_OBLIGATORIA = re.compile(
    r"certificaci[oó]n\s+(?:iso\s*\d{4,5}|pmp|cissp|ccna|ccnp)\s*(?:vigente|obligatoria|requerida)",
    re.I,
)


def exige_certificacion(texto: str, certificaciones: list[str] | None = None) -> str | None:
    """Motivo si el aviso exige una certificacion vigente que la persona no tiene."""
    m = RE_CERT_OBLIGATORIA.search(texto or "")
    if not m:
        return None
    exigida = sin_tildes(m.group(0))
    for c in (certificaciones or []):
        if sin_tildes(c) in exigida:
            return None
    return "exige %s" % m.group(0).strip()


# ------------------------------------------------------------------- fachada
def descalifica(texto: str, perfil: dict | None = None) -> str | None:
    """Devuelve el primer motivo de descarte, o None si la vacante es viable.

    Se llama **antes** de puntuar. Devolver el motivo permite contar los descartes
    por causa y notar cuando una fuente empieza a descartarse entera, que es la
    senal de que un adaptador se rompio.
    """
    perfil = perfil or {}
    idiomas = perfil.get("idiomas") or []
    nivel = "b1"
    for i in idiomas:
        if isinstance(i, dict) and "ingl" in sin_tildes(str(i.get("idioma", ""))):
            m = RE_NIVEL_MCER.search(str(i.get("nivel", "")))
            if m:
                nivel = m.group(1).lower()

    pais = sin_tildes((perfil.get("personal") or {}).get("ciudad", "")) or "colombia"
    pais = "colombia" if "colombia" in pais or "cali" in pais else pais

    certs = [c.get("nombre", "") if isinstance(c, dict) else str(c)
             for c in (perfil.get("certificaciones") or [])]

    for comprobar in (
        lambda: exige_ingles(texto, nivel),
        lambda: restringe_pais(texto, pais),
        lambda: exige_certificacion(texto, certs),
    ):
        motivo = comprobar()
        if motivo:
            return motivo
    return None
