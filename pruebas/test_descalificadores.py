import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "buscador"))
import descalificadores as D

PERFIL = {
    "idiomas": [{"idioma": "Inglés", "nivel": "B1 - intermedio"}],
    "personal": {"ciudad": "Cali, Colombia"},
    "certificaciones": [{"nombre": "Scrum Foundation Professional Certification"}],
}


# ---- los cuatro casos reales que se colaron y costaron tiempo

def test_niuro_c1_ingles():
    assert D.exige_ingles("C1 English level or higher. Solid Python.", "b1")


def test_alluxi_requiere_postular_en_ingles():
    assert D.exige_ingles("Requiere postular en Inglés. Buscamos full stack.", "b1")


def test_alluxi_ingles_profesional():
    assert D.exige_ingles("Inglés profesional escrito y hablado, capaz de sostener llamadas", "b1")


def test_usercode_solo_chile():
    txt = "No es posible realizar teletrabajo desde fuera de Chile por reglas de seguridad."
    assert D.restringe_pais(txt, "colombia")


def test_cali_software_iso27001():
    txt = "Ingeniero de Sistemas con énfasis en desarrollo Web y con Certificación ISO 27001 vigente"
    assert D.exige_certificacion(txt, ["Scrum Foundation"])


# ---- lo que NO debe descartar

def test_improving_incluye_colombia():
    txt = "Debes residir en Chile, Argentina, Perú o Colombia para postular."
    assert D.restringe_pais(txt, "colombia") is None


def test_b1_no_descarta_a_un_b1():
    assert D.exige_ingles("Inglés B1 deseable", "b1") is None


def test_ingles_b2_para_alguien_b2():
    assert D.exige_ingles("Inglés B2 requerido", "b2") is None


def test_el_silencio_no_restringe():
    """Un aviso que no dice nada de pais no descarta: el silencio no prohibe."""
    assert D.restringe_pais("Buscamos desarrollador Python remoto", "colombia") is None


def test_b2_suelto_sin_contexto_de_idioma_no_descarta():
    """'B2' puede ser un codigo de producto; sin la palabra ingles cerca, no cuenta."""
    assert D.exige_ingles("Manejo de formato B2 en facturación electrónica", "b1") is None


def test_certificacion_que_si_tiene_no_descarta():
    txt = "Se requiere Certificación PMP vigente"
    assert D.exige_certificacion(txt, ["PMP"]) is None


# ---- la fachada

def test_la_fachada_lee_el_nivel_del_perfil():
    assert D.descalifica("C1 English level required", PERFIL)
    assert D.descalifica("Buscamos desarrollador Python con React", PERFIL) is None


def test_la_fachada_devuelve_el_motivo_no_solo_true():
    """Sin motivo, un descarte es indistinguible de un adaptador roto."""
    motivo = D.descalifica("No es posible trabajar desde fuera de Chile", PERFIL)
    assert isinstance(motivo, str) and "Chile" in motivo


# ---- la ciudad de una vacante con presencia

def test_una_hibrida_en_otra_ciudad_queda_fuera():
    """Por esta rendija entraron PROCIBERNETICA, Kibernum y Accenture."""
    m = D.exige_otra_ciudad("hibrido", "Bogota, D.C.", "", "Cali")
    assert m and "bogota" in m


def test_una_hibrida_en_la_ciudad_de_la_persona_se_queda():
    assert D.exige_otra_ciudad("hibrido", "Valle del Cauca Cali", "", "Cali") is None


def test_una_remota_no_se_descarta_por_donde_este_la_empresa():
    """NTT DATA publica desde Bogota vacantes 100% remotas."""
    assert D.exige_otra_ciudad("remoto", "Bogota, D.C.", "", "Cali") is None


def test_si_la_ubicacion_no_nombra_ciudad_se_mira_el_texto():
    """'Colombia' no esta vacia y sin embargo no dice donde es."""
    m = D.exige_otra_ciudad("hibrido", "Colombia",
                            "Modalidad hibrida en Bogota", "Cali")
    assert m and "bogota" in m


def test_la_ubicacion_estructurada_manda_sobre_el_texto():
    """La leccion de Mederi: el texto nombra sedes, la ubicacion nombra el puesto."""
    assert D.exige_otra_ciudad("presencial", "Cali",
                               "tenemos oficinas en Bogota y Medellin", "Cali") is None


def test_el_silencio_sobre_la_ciudad_no_descarta():
    assert D.exige_otra_ciudad("presencial", "", "Buscamos desarrollador", "Cali") is None


def test_calidad_no_cuenta_como_cali():
    """Sin limite de palabra, 'cali' aparece dentro de 'calidad'."""
    m = D.exige_otra_ciudad("hibrido", "", "control de calidad en Bogota", "Cali")
    assert m and "bogota" in m


# ------------------------------------- ingles pedido con palabras intercaladas

def test_detecta_ingles_fluido_con_palabras_en_medio():
    """El fallo real: 'fluent english' se detectaba y 'fluent written english'
    no. Se colo la vacante mejor puntuada de un barrido (52 pts, $8M)."""
    assert D.exige_ingles("Fluent written English and daily overlap with US hours")


def test_detecta_las_formulas_sin_nivel():
    for frase in ("Strong written and verbal English",
                  "English fluency is a must",
                  "Excellent communication skills in English",
                  "Professional working proficiency in English"):
        assert D.exige_ingles(frase), frase


def test_no_descarta_por_nombrar_el_idioma_al_pasar():
    """Un aviso en espanol que menciona ingles como deseable no se descarta."""
    assert D.exige_ingles("Deseable: ingles basico. El equipo trabaja en espanol.") is None
    assert D.exige_ingles("Documentacion tecnica en ingles y espanol") is None


# ----------------------------------------------- avisos en un tercer idioma

FRANCES = """Developpeur fullstack confirme H/F. Nous recherchons pour notre
entreprise un developpeur avec de l'experience sur C#, .Net et Angular. Vous
serez integre dans une equipe agile. Votre profil: formation superieure, des
competences solides en developpement web. Le poste est base a Lyon, avec un
salaire selon experience. Les missions incluent la conception et le
developpement des applications pour les clients."""

PORTUGUES = """Vaga para desenvolvedor backend. Voce vai atuar com uma equipe
agil no desenvolvimento de APIs. Requisitos: conhecimento em Python e SQL,
experiencia com nuvem. Desejavel conhecimento em Docker. O trabalho e remoto
para todo o Brasil, com atuacao em projetos dos nossos clientes."""

ESPANOL = """Buscamos un desarrollador full stack con experiencia en React y
Node.js para trabajar con nuestro equipo en proyectos de clientes. Requisitos:
conocimiento de SQL, Docker y nube. El trabajo es remoto para toda Colombia,
con un salario segun experiencia. Las funciones incluyen el desarrollo y el
mantenimiento de aplicaciones web para los usuarios."""


def test_descarta_un_aviso_en_frances():
    """El fallo real: por arbeitnow.fr entro un aviso de Lyon en frances con 50
    puntos, quinto en el tablero. El filtro solo miraba ingles."""
    assert D.otro_idioma(FRANCES) == "el aviso esta en frances"


def test_descarta_un_aviso_en_portugues():
    assert D.otro_idioma(PORTUGUES) == "el aviso esta en portugues"


def test_no_descarta_un_aviso_en_espanol():
    """El espanol comparte palabras con el italiano y el portugues; el umbral
    tiene que ser lo bastante alto para no descartar lo que si sirve."""
    assert D.otro_idioma(ESPANOL) is None


def test_no_juzga_textos_muy_cortos():
    """Torre expone ~300 caracteres; contar marcadores ahi es adivinar."""
    assert D.otro_idioma("Nous recherchons un developpeur") is None
