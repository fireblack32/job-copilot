import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from copiloto import handoff as h
from copiloto import preguntas as q


def test_enviar_es_de_la_persona():
    a = h.crear("enviar", "BC DevOps")
    assert a.es_de_la_persona
    assert a.bloquea


def test_buscar_es_del_copiloto():
    assert not h.crear("buscar").es_de_la_persona


def test_paso_desconocido_cae_en_la_persona():
    """La regla de oro: si no lo reconocemos, no lo improvisamos."""
    a = h.crear("un_paso_que_nadie_previo")
    assert a.es_de_la_persona
    assert a.bloquea
    assert a.tipo.clave == "desconocida"


def test_no_se_puede_enviar_con_un_bloqueante_pendiente():
    acciones = [h.crear("llenar"), h.crear("oauth", enlace="https://x/y")]
    assert not h.puede_enviarse(acciones)


def test_se_puede_enviar_cuando_lo_bloqueante_esta_listo():
    a = h.crear("oauth")
    a.estado = h.Estado.LISTA
    assert h.puede_enviarse([h.crear("llenar"), a])


def test_prueba_tecnica_es_de_la_persona_pero_no_bloquea_el_envio():
    a = h.crear("prueba_tecnica")
    assert a.es_de_la_persona
    assert not a.bloquea


def test_detecta_captcha_y_oauth_en_una_pagina():
    txt = "Conecta tu GitHub para continuar. No soy un robot."
    claves = h.detectar(txt)
    assert "oauth" in claves and "captcha" in claves


def test_detecta_terminos_con_tildes():
    assert "terminos" in h.detectar("Aceptar cookies y Política de Privacidad")


def test_pagina_normal_no_genera_acciones_humanas():
    assert h.detectar("Buscamos desarrollador Python con experiencia") == []


def test_resumen_cuenta_bien():
    acciones = [h.crear("buscar"), h.crear("llenar"),
                h.crear("enviar"), h.crear("captcha")]
    r = h.resumen(acciones)
    assert r == {"total": 4, "del_copiloto": 2, "de_la_persona": 2,
                 "pendientes": 2, "bloqueantes": 2}


# ------------------------------------------------------------- cuestionario

def test_cuestionario_de_perfil_arranca_incompleto():
    c = q.para_perfil()
    assert not c.completo
    assert any(p.clave == "pretension_cop" for p in c.pendientes())


def test_lo_opcional_no_bloquea():
    respuestas = {p.clave: "x" for p in q.PERFIL if p.requerida}
    c = q.para_perfil(respuestas)
    assert c.completo


def test_pregunta_por_tecnologia_ofrece_el_nivel_honesto():
    p = q.sobre_tecnologia("Kubernetes")
    assert "Kubernetes" in p.texto
    assert "No la he usado" in p.opciones
    assert "La use en produccion y respondo por ella" in p.opciones


def test_cuestionario_de_vacante_solo_pregunta_lo_que_falta():
    c = q.para_vacante(["Ollama", "Qdrant"])
    assert len(c.preguntas) == 2


# ------------------------------------------------------------- formulario

from copiloto import formulario as f


def test_el_formulario_incluye_el_enlace_para_ir_a_autorizar():
    a = h.crear("oauth", "FortIA", enlace="https://www.getonbrd.com/webpros/edit")
    html = f.render([a], q.para_perfil())
    assert "https://www.getonbrd.com/webpros/edit" in html
    assert "Ir a hacerlo" in html


def test_el_formulario_explica_por_que_no_lo_hace_el_copiloto():
    html = f.render([h.crear("captcha", "X")], q.para_perfil())
    assert "distinguir personas de programas" in html


def test_las_acciones_del_copiloto_no_aparecen_en_el_formulario():
    """El formulario es la lista de la persona, no el registro de todo."""
    html = f.render([h.crear("buscar"), h.crear("adaptar_cv")], q.para_perfil())
    assert "Nada pendiente por ahora" in html


def test_las_preguntas_de_perfil_se_renderizan():
    html = f.render([], q.para_perfil())
    assert "Pretension salarial mensual" in html
    assert "obligatorio" in html


def test_las_opciones_de_nivel_llegan_al_html():
    c = q.para_vacante(["Kubernetes"])
    html = f.render([], c)
    assert "No la he usado" in html
    assert "respondo por ella" in html


def test_el_html_escapa_lo_que_venga_del_portal():
    """El titulo de una vacante es texto de un tercero, no codigo."""
    a = h.crear("enviar", '<script>alert(1)</script>')
    html = f.render([a], q.para_perfil())
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
