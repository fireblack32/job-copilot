# -*- coding: utf-8 -*-
"""
Las preguntas que ninguna hoja de vida responde.

Este catalogo sale de observar que decidio de verdad las postulaciones reales.
Nada de esto estaba en los PDF del CV: salio de preguntar. Mientras siga saliendo
de una conversacion, el sistema solo sirve para quien pueda conversar con el.

Hay dos clases de pregunta, y conviene no mezclarlas:

- **De perfil**: se responden una vez y valen para todas las postulaciones
  (disponibilidad, pretension, tipo de contrato que se acepta).
- **De vacante**: dependen de lo que pida el aviso concreto, y casi siempre son
  sobre el nivel real en una tecnologia. Son las que evitan afirmar de mas.

La distincion importa porque la primera clase se pregunta al dar de alta a la
persona y la segunda solo cuando hace falta, para no interrogar a nadie sin motivo.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Pregunta:
    clave: str
    texto: str
    ayuda: str = ""
    #: "texto", "numero", "opcion", "si_no"
    tipo: str = "texto"
    opciones: tuple[str, ...] = ()
    requerida: bool = True


# ------------------------------------------------------------ de perfil
PERFIL = [
    Pregunta(
        "pretension_cop", "Pretension salarial mensual en pesos",
        "El piso desde el que vale la pena moverte. Se compara con lo que publica "
        "cada vacante; si publican una banda mas alta, se pide dentro de su banda.",
        tipo="numero",
    ),
    Pregunta(
        "disponibilidad_semanas", "En cuantas semanas podrias arrancar",
        "Cuenta preaviso, compromisos y vacaciones ya agendadas. Es mejor decir "
        "ocho y cumplir que decir cuatro y no poder.",
        tipo="numero",
    ),
    Pregunta(
        "tipo_contrato", "Que vinculaciones aceptas",
        "Un contrato laboral trae prestaciones; uno por prestacion de servicios no, "
        "y la seguridad social corre por tu cuenta.",
        tipo="opcion",
        opciones=("Solo laboral con prestaciones",
                  "Laboral y prestacion de servicios",
                  "Solo prestacion de servicios / contractor"),
    ),
    Pregunta(
        "modalidad", "Que modalidades te sirven",
        "Si aceptas presencial o hibrido, decinos en que ciudad y en que zona.",
        tipo="opcion",
        opciones=("Solo remoto", "Remoto e hibrido", "Remoto, hibrido y presencial"),
    ),
    Pregunta(
        "ciudad_zona", "Ciudad y zona preferida si aceptas presencial",
        "Sirve para descartar lo que te obligaria a cruzar la ciudad a diario.",
        requerida=False,
    ),
    Pregunta(
        "idiomas", "En que idiomas puedes trabajar y a que nivel",
        "Se honesto con el nivel de conversacion: un aviso que pide reuniones en "
        "ingles se filtra si no lo sostienes.",
    ),
    Pregunta(
        "no_negociables", "Que no estas dispuesto a aceptar",
        "Turnos de noche, viajes, disponibilidad los fines de semana, lo que sea.",
        requerida=False,
    ),
]

# ------------------------------------------------------------ de vacante
#
# Se hacen solo cuando el aviso pide algo que no consta en el perfil. La respuesta
# decide como se redacta, y sobre todo evita afirmar lo que no es cierto.
NIVELES = (
    "No la he usado",
    "La estudie o hice un proyecto propio",
    "La use en un trabajo, con supervision",
    "La use en produccion y respondo por ella",
)


def sobre_tecnologia(nombre: str) -> Pregunta:
    return Pregunta(
        clave="nivel_" + nombre.lower().replace(" ", "_"),
        texto="Cual es tu nivel real con %s" % nombre,
        ayuda="Esta vacante la pide y no consta en tu perfil. La respuesta define "
              "que se puede afirmar: si es un proyecto propio, se dice que es un "
              "proyecto propio.",
        tipo="opcion",
        opciones=NIVELES,
    )


def sobre_experiencia(nombre: str) -> Pregunta:
    return Pregunta(
        clave="anios_" + nombre.lower().replace(" ", "_"),
        texto="Cuantos anios llevas trabajando con %s" % nombre,
        ayuda="Cuenta solo trabajo real, no cursos.",
        tipo="numero",
        requerida=False,
    )


@dataclass
class Cuestionario:
    """Preguntas pendientes para una persona, con lo que ya respondio."""

    preguntas: list[Pregunta] = field(default_factory=list)
    respuestas: dict[str, object] = field(default_factory=dict)

    def pendientes(self) -> list[Pregunta]:
        return [p for p in self.preguntas
                if p.requerida and not str(self.respuestas.get(p.clave, "")).strip()]

    @property
    def completo(self) -> bool:
        return not self.pendientes()


def para_perfil(respuestas: dict | None = None) -> Cuestionario:
    return Cuestionario(list(PERFIL), dict(respuestas or {}))


def para_vacante(tecnologias_faltantes: list[str],
                 respuestas: dict | None = None) -> Cuestionario:
    """Cuestionario corto para lo que una vacante pide y el perfil no cubre."""
    preguntas = [sobre_tecnologia(t) for t in tecnologias_faltantes]
    return Cuestionario(preguntas, dict(respuestas or {}))
