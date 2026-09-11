# -*- coding: utf-8 -*-
"""
Deriva la configuracion de busqueda desde el perfil de la persona.

Hasta ahora el buscador tenia los criterios escritos en el codigo: el piso
salarial, la ciudad, las palabras que puntuan y los terminos con que se consulta
cada portal. Todo eso describe a **una** persona, asi que el sistema solo servia
para esa persona. Y lo curioso es que el perfil ya traia esos datos: estaban
duplicados, y la copia que mandaba era la del codigo.

Aqui se invierte: el perfil es la fuente y el codigo solo lee. Probar con otra
hoja de vida pasa a ser cambiar un archivo, no editar constantes.

    perfil.json ──> criterios (pisos, ciudad, modalidades, idioma)
                ──> pesos de habilidades (que suma puntos y cuanto)
                ──> terminos de busqueda (que se le pregunta a cada portal)

Lo que no se puede derivar tiene un valor por defecto explicito y documentado,
para que quien lea el resultado sepa que fue una decision y no un descuido.
"""

from __future__ import annotations

import re
import unicodedata

#: Piso por defecto si el perfil no declara ninguno: dos salarios minimos.
#: Se deja visible aqui y no escondido en el codigo del filtro.
SMMLV_2026_COP = 1_750_905

#: Peso por familia de habilidad. Una tecnologia del stack principal vale mas
#: que una herramienta de apoyo, porque encontrarla en un aviso dice mas sobre
#: si la vacante encaja.
PESOS_POR_FAMILIA = {
    "lenguajes": 5,
    "frontend": 5,
    "backend": 5,
    "ia": 6,
    # Trabajar CON agentes de IA, no solo integrar modelos: Claude, IA
    # generativa, agentes. Pesa lo mismo que `ia` porque es la direccion en la
    # que el perfil quiere crecer; sin esta entrada caia al peso por defecto (3)
    # y una vacante que pedia Claude puntuaba como una que pedia Git.
    "desarrollo_asistido_ia": 6,
    # Automatizacion de procesos a secas: RPA, integraciones, batch, planta.
    # Vivia dentro de `ia` y ahi pesaba 6; se saco para que no marque como IA
    # avisos que no la piden, y conserva el mismo peso para no bajar del
    # tablero siete vacantes de automatizacion que si encajan.
    "automatizacion": 6,
    "bases_de_datos": 3,
    "cloud_devops": 4,
    # Dos nombres para la misma familia: el codigo decia `redes_telecom` y el
    # perfil dice `telecomunicaciones`. No coincidian, asi que DWDM, NMS,
    # SPECTRUM y fibra optica caian al peso por defecto (3) en vez del 5 que se
    # pretendia, y una vacante de NOC puntuaba por debajo de una de desarrollo
    # que la mencionara de pasada.
    "redes_telecom": 5,
    "telecomunicaciones": 5,
    "industrial": 4,
    "metodologias": 2,
    "herramientas": 2,
}
PESO_POR_DEFECTO = 3

#: Familias cuyas habilidades marcan una vacante como "pide IA". Es una marca y
#: no un filtro: filtrar por ella dejaria fuera los carriles de NOC e industrial
#: enteros, que casi nunca la mencionan.
FAMILIAS_IA = ("ia", "desarrollo_asistido_ia")

#: Palabras demasiado genericas para puntuar: aparecen en casi cualquier aviso
#: y solo suben el ruido. Se excluyen aunque esten en el perfil.
DEMASIADO_GENERICAS = {
    "html", "css", "git", "office", "microsoft office", "ingenieria",
    "tecnologia de la informacion", "apis restful", "api rest",
}


def sin_tildes(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s or "")
                   if unicodedata.category(c) != "Mn").lower()


class Criterios:
    """Los criterios de busqueda de una persona concreta."""

    def __init__(self, perfil: dict) -> None:
        cb = perfil.get("criterios_busqueda") or {}

        smmlv = cb.get("smmlv_2026_cop") or SMMLV_2026_COP
        self.piso_remoto = cb.get("piso_salarial_cop_mes") or (2 * smmlv)

        #: Piso para vacantes que exigen presencia. Mas alto a proposito: una
        #: presencial cuesta transporte y desplazamiento, asi que tiene que
        #: pagar mas que una remota para valer lo mismo.
        self.piso_presencial = cb.get("piso_salarial_presencial_cop_mes") or int(
            self.piso_remoto * 1.15)

        modalidades = [sin_tildes(m) for m in (cb.get("modalidad") or ["remoto"])]
        self.acepta_remoto = any("remot" in m for m in modalidades)
        self.acepta_hibrido = any("hibrid" in m for m in modalidades)
        self.acepta_presencial = any("presencial" in m for m in modalidades)

        #: Ciudad para las vacantes con presencia. None = no se buscan locales.
        self.ciudad = cb.get("ciudad_presencial")
        self.zonas_preferidas = cb.get("zonas_preferidas") or []

        self.idiomas = [sin_tildes(i) for i in (cb.get("idioma_vacante") or ["espanol"])]
        self.geografias = cb.get("geografias") or []
        self.excluir = cb.get("excluir") or []

    def __repr__(self) -> str:
        return ("Criterios(piso_remoto=%s, piso_presencial=%s, ciudad=%s, "
                "remoto=%s, hibrido=%s, presencial=%s)" % (
                    self.piso_remoto, self.piso_presencial, self.ciudad,
                    self.acepta_remoto, self.acepta_hibrido, self.acepta_presencial))


def pesos_de_habilidades(perfil: dict, extra: dict | None = None) -> dict:
    """Construye el diccionario de puntuacion desde las habilidades del perfil.

    Antes esta tabla estaba escrita a mano y describia a una sola persona. Al
    derivarla, la puntuacion mide encaje con **quien busca**, no con quien
    escribio el codigo.
    """
    pesos: dict[str, int] = {}
    habilidades = perfil.get("habilidades") or {}

    if isinstance(habilidades, dict):
        for familia, lista in habilidades.items():
            peso = PESOS_POR_FAMILIA.get(sin_tildes(familia), PESO_POR_DEFECTO)
            for item in (lista or []):
                clave = sin_tildes(str(item)).strip()
                if not clave or clave in DEMASIADO_GENERICAS:
                    continue
                # Si una habilidad aparece en dos familias, vale la mas alta.
                pesos[clave] = max(pesos.get(clave, 0), peso)

    # Las palabras clave de los perfiles objetivo pesan segun su prioridad: lo
    # que la persona busca primero deberia empujar mas fuerte el ranking.
    for po in perfil.get("perfiles_objetivo") or []:
        prioridad = po.get("prioridad", 3)
        peso = max(6 - prioridad, 2)
        for kw in (po.get("keywords") or []):
            clave = sin_tildes(str(kw)).strip()
            if clave and clave not in DEMASIADO_GENERICAS:
                pesos[clave] = max(pesos.get(clave, 0), peso)

    if extra:
        pesos.update({sin_tildes(k): v for k, v in extra.items()})
    return pesos


def claves_de_familias(perfil: dict, familias=FAMILIAS_IA) -> set[str]:
    """Claves de puntuacion de las habilidades de ciertas familias.

    Mismas claves que produce `pesos_de_habilidades`, asi que se pueden cruzar
    directo con los `hits` de una vacante para saber si pide algo de esa familia.
    """
    habilidades = perfil.get("habilidades") or {}
    if not isinstance(habilidades, dict):
        return set()
    buscadas = {sin_tildes(f) for f in familias}
    claves = set()
    for familia, lista in habilidades.items():
        if sin_tildes(familia) not in buscadas:
            continue
        for item in (lista or []):
            clave = sin_tildes(str(item)).strip()
            if clave and clave not in DEMASIADO_GENERICAS:
                claves.add(clave)
    return claves


def terminos_de_busqueda(perfil: dict, maximo: int = 12) -> list[str]:
    """Terminos con que se consulta cada portal, sacados de los cargos objetivo.

    El recorte reparte el cupo **entre perfiles**, no por orden de prioridad.
    Antes cortaba por orden y con eso se perdia el ultimo perfil entero: los
    cargos de desarrollo eran nueve, asi que con `maximo=12` entraban tres de
    telecomunicaciones y **cero de industrial**. La persona tiene tres carreras
    y el buscador solo preguntaba por una.
    """
    perfiles = sorted(perfil.get("perfiles_objetivo") or [],
                      key=lambda p: p.get("prioridad", 99))
    listas = [[str(c).strip() for c in (po.get("cargos_objetivo") or []) if str(c).strip()]
              for po in perfiles]
    return _repartir(listas, maximo)


def _repartir(listas: list[list[str]], maximo: int | None) -> list[str]:
    """Intercala varias listas y recorta, dandole turno a cada una.

    Se toma un elemento de cada lista por vuelta. Asi, si hay que recortar, lo
    que se pierde es la cola de cada perfil y no un perfil completo.
    """
    fuera: list[str] = []
    vistos: set[str] = set()
    for i in range(max((len(l) for l in listas), default=0)):
        for l in listas:
            if i >= len(l):
                continue
            clave = sin_tildes(l[i])
            if clave in vistos:
                continue
            vistos.add(clave)
            fuera.append(l[i])
    return fuera if maximo is None else fuera[:maximo]


def terminos_portal(perfil: dict, forma: str, maximo: int | None = None) -> list[str]:
    """Terminos ya verificados contra un portal, repartidos entre los perfiles.

    Cada perfil objetivo puede declarar `terminos_portal` con dos formas, porque
    los portales no piden lo mismo:

      - ``slug``  -> Computrabajo y elempleo, que arman la URL con el termino
                     (``/trabajo-de-ingeniero-de-telecomunicaciones-en-cali``).
      - ``texto`` -> Torre, que recibe la consulta como texto libre.

    Estan en el perfil y no en el codigo por la misma razon que todo lo demas:
    describen a **quien busca**. Y estan escritos a mano en vez de derivados de
    los cargos porque cada uno se probo contra el portal real; derivarlos daba
    consultas muertas (``ingeniero-noc`` devuelve cero avisos en Computrabajo) o
    ruidosas (``noc`` en Torre devuelve "Medico Veterinario Nocturno").

    Si un perfil no los declara, se cae a los cargos objetivo convertidos a slug,
    que es peor pero no deja al portal sin consultar.
    """
    perfiles = sorted(perfil.get("perfiles_objetivo") or [],
                      key=lambda p: p.get("prioridad", 99))
    listas = []
    for po in perfiles:
        declarados = (po.get("terminos_portal") or {}).get(forma)
        if declarados:
            listas.append([str(t).strip() for t in declarados if str(t).strip()])
        elif forma == "slug":
            listas.append([a_slug(c) for c in (po.get("cargos_objetivo") or []) if a_slug(c)])
        else:
            listas.append([str(c).strip() for c in (po.get("cargos_objetivo") or []) if str(c).strip()])
    return _repartir(listas, maximo)


def a_slug(texto: str) -> str:
    """Convierte un cargo en el segmento de URL que usan los portales colombianos."""
    s = re.sub(r"[^a-z0-9]+", "-", sin_tildes(texto))
    return s.strip("-")


def bloquea_idioma(criterios: Criterios) -> bool:
    """True si la persona solo acepta vacantes en su idioma."""
    return "espanol" in criterios.idiomas and len(criterios.idiomas) == 1


def patron_ciudad(ciudad: str | None):
    """Patron con limite de palabra para la ciudad declarada.

    Con limite de palabra a proposito: buscar "cali" suelto lo encuentra dentro
    de "calidad", y asi se colo una vacante de Bogota como si fuera de Cali.
    """
    if not ciudad:
        return None
    return re.compile(r"\b" + re.escape(sin_tildes(ciudad)) + r"\b")
