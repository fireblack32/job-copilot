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
