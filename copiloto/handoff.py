# -*- coding: utf-8 -*-
"""
Reparto de trabajo entre el copiloto y la persona.

Este modulo existe por una decision de producto, no por una limitacion tecnica:
hay cosas que el copiloto **no debe** hacer aunque pudiera. Autorizar una cuenta,
aceptar unos terminos o mandar una postulacion son actos que comprometen a la
persona, y quien responde por ellos tiene que ser quien los hace.

El reparto se declara aqui una sola vez para que no quede repartido por el codigo
en condiciones sueltas. Cada accion dice quien la hace, por que, y —cuando le toca
a la persona— a donde tiene que ir para hacerla.

Regla de oro: **lo desconocido es de la persona.** Si aparece un paso que este
catalogo no contempla, se le entrega a ella en vez de intentarlo. Un copiloto que
improvisa sobre un formulario que no entiende es peor que uno que se detiene.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Quien(str, Enum):
    COPILOTO = "copiloto"
    PERSONA = "persona"


class Estado(str, Enum):
    PENDIENTE = "pendiente"
    LISTA = "lista"
    NO_APLICA = "no_aplica"


@dataclass(frozen=True)
class TipoAccion:
    """Una clase de accion que puede aparecer en cualquier portal."""

    clave: str
    titulo: str
    quien: Quien
    motivo: str
    #: Si es True, mientras este pendiente no se puede enviar la postulacion.
    bloquea_envio: bool = False
    #: Texto de lo que la persona tiene que hacer, en imperativo y concreto.
    instruccion: str = ""


# --------------------------------------------------------------- el catalogo
#
# Lo que el copiloto hace solo. Ninguna de estas compromete a la persona: son
# lectura, redaccion de borradores o llenado de campos que ella va a revisar.
AUTOMATICAS = [
    TipoAccion("buscar", "Buscar vacantes en los portales", Quien.COPILOTO,
               "Es lectura publica y no compromete a nadie."),
    TipoAccion("puntuar", "Puntuar el encaje con el perfil", Quien.COPILOTO,
               "Calculo sobre datos ya recolectados."),
    TipoAccion("adaptar_cv", "Adaptar la hoja de vida a la vacante", Quien.COPILOTO,
               "Genera un documento que la persona revisa antes de enviar."),
    TipoAccion("redactar", "Redactar las respuestas del formulario", Quien.COPILOTO,
               "Son borradores; quedan en vista previa para revision."),
    TipoAccion("llenar", "Llenar los campos de la postulacion", Quien.COPILOTO,
               "Escribir en el formulario no envia nada."),
    TipoAccion("subir_cv", "Subir la hoja de vida", Quien.COPILOTO,
               "Se verifica despues de subir que el archivo quedo guardado."),
    TipoAccion("verificar", "Verificar que lo escrito quedo guardado", Quien.COPILOTO,
               "Escribir y confirmar son cosas distintas."),
]

# Lo que le toca a la persona. El motivo importa tanto como la accion: es lo que
# se le muestra para que entienda por que no lo hacemos nosotros.
DE_LA_PERSONA = [
    TipoAccion(
        "crear_cuenta", "Crear la cuenta en el portal", Quien.PERSONA,
        "Crear cuentas y elegir contrasenas es algo que solo debe hacer su dueno.",
        bloquea_envio=True,
        instruccion="Registrate con tu correo y guarda la contrasena en tu gestor.",
    ),
    TipoAccion(
        "oauth", "Conectar una cuenta externa (GitHub, LinkedIn, Google)", Quien.PERSONA,
        "Dar acceso a otra cuenta es una autorizacion que va con tus credenciales.",
        bloquea_envio=True,
        instruccion="Entra al portal, pulsa el boton de conectar y autoriza el acceso.",
    ),
    TipoAccion(
        "captcha", "Resolver un CAPTCHA", Quien.PERSONA,
        "Existe justamente para distinguir personas de programas; saltarlo seria enganar al portal.",
        bloquea_envio=True,
        instruccion="Resuelve el CAPTCHA en la pantalla del portal.",
    ),
    TipoAccion(
        "terminos", "Aceptar terminos, cookies o politica de privacidad", Quien.PERSONA,
        "Aceptar un contrato en tu nombre no nos corresponde.",
        bloquea_envio=True,
        instruccion="Lee y acepta si estas de acuerdo.",
    ),
    TipoAccion(
        "enviar", "Enviar la postulacion", Quien.PERSONA,
        "Una postulacion afirma quien eres. Debe salir cuando vos la hayas leido.",
        bloquea_envio=True,
        instruccion="Revisa la vista previa y pulsa enviar si estas conforme.",
    ),
    TipoAccion(
        "prueba_tecnica", "Presentar una prueba tecnica o test cronometrado", Quien.PERSONA,
        "Es una evaluacion de vos; responderla por vos seria falsear el resultado.",
        instruccion="Agenda un momento sin interrupciones y presentala.",
    ),
    TipoAccion(
        "verificar_identidad", "Verificar identidad o subir documentos", Quien.PERSONA,
        "Son documentos personales que no manipulamos.",
        bloquea_envio=True,
        instruccion="Sube el documento que te pida el portal.",
    ),
    TipoAccion(
        "dato_faltante", "Responder un dato que la hoja de vida no dice", Quien.PERSONA,
        "Nadie mas puede saber tu disponibilidad, tu pretension o tu nivel real en algo.",
        bloquea_envio=True,
        instruccion="Responde las preguntas del formulario de perfil.",
    ),
]

CATALOGO = {t.clave: t for t in AUTOMATICAS + DE_LA_PERSONA}

#: Se usa cuando aparece un paso que el catalogo no contempla.
DESCONOCIDA = TipoAccion(
    "desconocida", "Paso no reconocido del portal", Quien.PERSONA,
    "El copiloto no reconocio este paso, y no improvisa sobre formularios que no entiende.",
    bloquea_envio=True,
    instruccion="Revisa que pide el portal y completalo a mano.",
)


@dataclass
class Accion:
    """Una accion concreta dentro de una postulacion concreta."""

    tipo: TipoAccion
    vacante: str = ""
    enlace: str = ""
    detalle: str = ""
    estado: Estado = Estado.PENDIENTE

    @property
    def es_de_la_persona(self) -> bool:
        return self.tipo.quien is Quien.PERSONA

    @property
    def bloquea(self) -> bool:
        return self.tipo.bloquea_envio and self.estado is Estado.PENDIENTE


def crear(clave: str, vacante: str = "", enlace: str = "", detalle: str = "") -> Accion:
    """Crea una accion. Una clave desconocida cae en la persona, no en el copiloto."""
    return Accion(CATALOGO.get(clave, DESCONOCIDA), vacante, enlace, detalle)


def pendientes_de_la_persona(acciones: list[Accion]) -> list[Accion]:
    return [a for a in acciones
            if a.es_de_la_persona and a.estado is Estado.PENDIENTE]


def puede_enviarse(acciones: list[Accion]) -> bool:
    """True solo si nada bloqueante sigue pendiente."""
    return not any(a.bloquea for a in acciones)


def resumen(acciones: list[Accion]) -> dict[str, int]:
    return {
        "total": len(acciones),
        "del_copiloto": sum(1 for a in acciones if not a.es_de_la_persona),
        "de_la_persona": sum(1 for a in acciones if a.es_de_la_persona),
        "pendientes": len(pendientes_de_la_persona(acciones)),
        "bloqueantes": sum(1 for a in acciones if a.bloquea),
    }


# ------------------------------------------------- deteccion desde una pagina
#
# Senales observadas en portales reales. Se amplian con la experiencia; lo que no
# coincide con ninguna cae en DESCONOCIDA, que es de la persona.
SENALES = [
    ("captcha", ["captcha", "recaptcha", "hcaptcha", "no soy un robot"]),
    ("oauth", ["conecta tu github", "conectar con linkedin", "continuar con google",
               "vincular cuenta", "autorizar acceso", "connect github"]),
    ("terminos", ["aceptar cookies", "acepto los terminos", "politica de privacidad",
                  "acepto el tratamiento"]),
    ("verificar_identidad", ["verifica tu identidad", "sube tu documento",
                             "cedula", "documento de identidad"]),
    ("prueba_tecnica", ["prueba tecnica", "test de", "evaluacion tecnica",
                        "assessment", "hackerrank", "codility"]),
    ("crear_cuenta", ["crear cuenta", "registrate", "sign up", "crea tu perfil"]),
]


def detectar(texto_pagina: str) -> list[str]:
    """Devuelve las claves de acciones humanas que aparecen en una pagina."""
    t = (texto_pagina or "").lower()
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u")):
        t = t.replace(a, b)
    encontradas = []
    for clave, marcas in SENALES:
        if any(m in t for m in marcas):
            encontradas.append(clave)
    return encontradas
