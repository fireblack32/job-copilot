# -*- coding: utf-8 -*-
"""
Bitacora de postulaciones: que vacante ya se toco, quien la toco y cuando.

Hasta ahora el estado de las postulaciones vivia en la cabeza de quien llevaba la
sesion. Eso funciona mientras hay una sola persona y una sola conversacion; se
rompe en cuanto la persona postula por su cuenta, o en cuanto la conversacion se
corta y hay que empezar otra. Sin memoria compartida, el copiloto vuelve a
recomendar lo mismo, y postular dos veces a la misma empresa es peor que no
postular: se ve descuidado y esa empresa solo se toca una vez.

    ranking.json  ─┐
                   ├─> tablero (lo que falta por postular)
    bitacora.json ─┘
          ▲
          └── la persona marca lo que postulo a mano

**Identidad de una vacante.** Un aviso se reconoce de dos formas, y hacen falta
las dos:

- `clave` = fuente + id. Exacta, pero se rompe sola: los portales reciclan ids y
  vuelven a publicar el mismo puesto con uno nuevo cada pocas semanas.
- `huella` = empresa + cargo, normalizados. Atrapa el mismo puesto publicado en
  dos portales y el republicado con id nuevo.

La huella descarta igual que la clave, a proposito. El caso que se pierde es una
empresa con dos vacantes distintas de titulo identico; el caso que se evita es
mandarle a la misma empresa la misma hoja de vida dos veces. El segundo hace mas
dano, y ademas se nota.
"""

from __future__ import annotations

import io
import json
import os
import re
import unicodedata
from dataclasses import dataclass, asdict
from datetime import date


class Estado:
    """Estados posibles de una vacante en la bitacora."""

    PENDIENTE = "pendiente"
    ENVIADA = "enviada"
    DESCARTADA = "descartada"
    #: La persona la esta viendo pero todavia no decide. Existe para que una
    #: vacante pueda salir del tablero sin quedar marcada como enviada.
    EN_CURSO = "en_curso"


class Quien:
    COPILOTO = "copiloto"
    PERSONA = "persona"


def sin_tildes(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s or "")
                   if unicodedata.category(c) != "Mn").lower()


#: Ruido que los portales meten en el titulo y que no distingue una vacante de
#: otra. Se quita antes de comparar para que "Dev Backend (Remoto)" y
#: "Dev Backend - remoto" no se vean como dos puestos.
_RUIDO_TITULO = re.compile(
    r"\b(remoto|remote|hibrido|presencial|full\s*time|medio\s*tiempo|"
    r"tiempo\s*completo|urgente|nueva|vacante|oferta|empleo|trabajo|"
    r"bogota|medellin|cali|barranquilla|colombia|latam|m/f|h/m)\b", re.I)


def _normalizar(s: str) -> str:
    s = sin_tildes(s or "")
    s = _RUIDO_TITULO.sub(" ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def clave(vacante: dict) -> str:
    """Identidad exacta: fuente + id del portal.

    Cuando el portal no da id se cae a la URL, que es lo unico que queda. La URL
    es peor identidad porque los portales le cuelgan parametros de seguimiento;
    por eso se corta en el primer '?' y en el primer '#'.
    """
    fuente = sin_tildes(str(vacante.get("fuente") or "sin-fuente"))
    ident = vacante.get("id")
    if not ident:
        url = str(vacante.get("url") or "")
        ident = re.split(r"[?#]", url)[0] or "sin-id"
    return "%s:%s" % (fuente, ident)


def huella(vacante: dict) -> str:
    """Identidad aproximada: empresa + cargo normalizados.

    Es la que atrapa el mismo puesto en dos portales. Devuelve cadena vacia si
    falta la empresa: sin ella la huella seria solo un cargo generico, y
    "Desarrollador Backend" de una empresa bloquearia el de todas las demas.
    """
    empresa = _normalizar(str(vacante.get("empresa") or ""))
    titulo = _normalizar(str(vacante.get("titulo") or ""))
    if not empresa or not titulo:
        return ""
    return "%s|%s" % (empresa, titulo)


@dataclass
class Registro:
    """Lo que se sabe de una vacante ya tocada."""

    clave: str
    huella: str = ""
    estado: str = Estado.PENDIENTE
    quien: str = Quien.COPILOTO
    fecha: str = ""
    titulo: str = ""
    empresa: str = ""
    url: str = ""
    nota: str = ""

    @property
    def cerrada(self) -> bool:
        """True si esta vacante ya no debe volver a ofrecerse."""
        return self.estado in (Estado.ENVIADA, Estado.DESCARTADA)


class Bitacora:
    """Registro persistente de vacantes tocadas, indexado por clave y por huella."""

    def __init__(self, ruta: str | None = None) -> None:
        self.ruta = ruta
        self._por_clave: dict[str, Registro] = {}
        self._por_huella: dict[str, Registro] = {}
        if ruta and os.path.exists(ruta):
            self.cargar()

    # ------------------------------------------------------------- persistencia
    def cargar(self) -> "Bitacora":
        with io.open(self.ruta, encoding="utf-8") as f:
            datos = json.load(f)
        for d in datos.get("registros", []):
            self._indexar(Registro(**d))
        return self

    def guardar(self, ruta: str | None = None) -> str:
        destino = ruta or self.ruta
        registros = sorted(self._por_clave.values(), key=lambda r: (r.fecha, r.clave))
        with io.open(destino, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "registros": [asdict(r) for r in registros]},
                      f, ensure_ascii=False, indent=1)
        return destino

    def _indexar(self, r: Registro) -> Registro:
        self._por_clave[r.clave] = r
        if r.huella:
            self._por_huella[r.huella] = r
        return r

    # ----------------------------------------------------------------- consulta
    def buscar(self, vacante: dict) -> tuple[Registro | None, str]:
        """Devuelve (registro, motivo) del calce, o (None, "") si no hay.

        El motivo importa: 'ya la postulaste vos en Computrabajo' y 'la misma
        empresa y cargo aparecio en otro portal' son cosas distintas para quien
        lee el tablero, y una de las dos puede estar equivocada.
        """
        r = self._por_clave.get(clave(vacante))
        if r:
            return r, "misma vacante"
        h = huella(vacante)
        if h:
            r = self._por_huella.get(h)
            if r:
                return r, "misma empresa y cargo, publicada en %s" % (
                    r.clave.split(":")[0])
        return None, ""

    def cerrada(self, vacante: dict) -> str | None:
        """Motivo por el que esta vacante no debe volver a ofrecerse, o None."""
        r, motivo = self.buscar(vacante)
        if r and r.cerrada:
            quien = "vos" if r.quien == Quien.PERSONA else "el copiloto"
            if r.estado == Estado.DESCARTADA:
                return "descartada: %s" % (r.nota or motivo)
            return "ya postulada por %s (%s)%s" % (
                quien, r.fecha or "sin fecha",
                "" if motivo == "misma vacante" else " - " + motivo)
        return None

    # ------------------------------------------------------------------ escribe
    def registrar(self, vacante: dict, estado: str = Estado.ENVIADA,
                  quien: str = Quien.COPILOTO, nota: str = "",
                  fecha: str | None = None) -> Registro:
        """Anota una vacante. Si ya estaba, actualiza el estado."""
        k = clave(vacante)
        r = self._por_clave.get(k)
        if r is None:
            r = Registro(clave=k, huella=huella(vacante),
                         titulo=str(vacante.get("titulo") or ""),
                         empresa=str(vacante.get("empresa") or ""),
                         url=str(vacante.get("url") or ""))
        r.estado = estado
        r.quien = quien
        r.fecha = fecha or date.today().isoformat()
        if nota:
            r.nota = nota
        return self._indexar(r)

    def registrar_urls(self, urls: list[str], candidatas: list[dict],
                       quien: str = Quien.PERSONA,
                       estado: str = Estado.ENVIADA) -> tuple[list[Registro], list[str]]:
        """Marca por URL. Es la via de vuelta cuando la persona postula sola.

        Devuelve (registradas, no_encontradas). Las no encontradas se devuelven en
        vez de anotarse igual: una URL que no esta en las candidatas suele ser un
        pegado a medias, y anotarla crearia un registro fantasma que nadie podria
        relacionar despues con ninguna vacante.
        """
        indice = {}
        for c in candidatas:
            u = re.split(r"[?#]", str(c.get("url") or ""))[0].rstrip("/")
            if u:
                indice[u] = c
        hechos, perdidas = [], []
        for url in urls:
            u = re.split(r"[?#]", str(url or "").strip())[0].rstrip("/")
            if not u:
                continue
            c = indice.get(u)
            if c is None:
                perdidas.append(url)
                continue
            hechos.append(self.registrar(c, estado=estado, quien=quien))
        return hechos, perdidas

    # ------------------------------------------------------------------ resumen
    def resumen(self) -> dict[str, int]:
        rs = list(self._por_clave.values())
        return {
            "total": len(rs),
            "enviadas": sum(1 for r in rs if r.estado == Estado.ENVIADA),
            "por_el_copiloto": sum(1 for r in rs if r.estado == Estado.ENVIADA
                                   and r.quien == Quien.COPILOTO),
            "por_la_persona": sum(1 for r in rs if r.estado == Estado.ENVIADA
                                  and r.quien == Quien.PERSONA),
            "descartadas": sum(1 for r in rs if r.estado == Estado.DESCARTADA),
            "en_curso": sum(1 for r in rs if r.estado == Estado.EN_CURSO),
        }

    def __len__(self) -> int:
        return len(self._por_clave)


def separar(candidatas: list[dict], bit: Bitacora) -> tuple[list[dict], list[dict]]:
    """Parte las candidatas en (pendientes, ya_cerradas).

    Las cerradas se devuelven en vez de tirarse: el tablero las muestra tachadas,
    y ver que una vacante ya se postulo es informacion, no ruido.
    """
    pendientes, cerradas = [], []
    for c in candidatas:
        motivo = bit.cerrada(c)
        if motivo:
            cerradas.append({**c, "cerrada_porque": motivo})
        else:
            pendientes.append(c)
    return pendientes, cerradas
