import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "buscador"))

import perfilado as P

PERFIL_MINIMO = {
    "criterios_busqueda": {
        "smmlv_2026_cop": 1750905,
        "piso_salarial_cop_mes": 3501810,
        "modalidad": ["Remoto", "Híbrido"],
        "ciudad_presencial": "Cali",
        "idioma_vacante": ["Español"],
    },
    "habilidades": {
        "lenguajes": ["Python", "SQL"],
        "cloud_devops": ["AWS", "Docker"],
        "bases_de_datos": ["PostgreSQL"],
        "herramientas": ["Git"],
    },
    "perfiles_objetivo": [
        {"id": "dev", "prioridad": 1,
         "cargos_objetivo": ["Desarrollador Full Stack", "Ingeniero de Software"],
         "keywords": ["microservicios"]},
        {"id": "noc", "prioridad": 2,
         "cargos_objetivo": ["Ingeniero NOC"], "keywords": ["monitoreo"]},
    ],
}


def test_lee_el_piso_del_perfil():
    c = P.Criterios(PERFIL_MINIMO)
    assert c.piso_remoto == 3501810


def test_calcula_el_piso_por_defecto_si_no_lo_declara():
    """Sin piso declarado: dos salarios minimos, no cero."""
    c = P.Criterios({"criterios_busqueda": {"smmlv_2026_cop": 1000000}})
    assert c.piso_remoto == 2000000


def test_el_piso_presencial_es_mas_alto_que_el_remoto():
    """Una presencial cuesta transporte y tiempo: tiene que pagar mas."""
    c = P.Criterios(PERFIL_MINIMO)
    assert c.piso_presencial > c.piso_remoto


def test_lee_las_modalidades():
    c = P.Criterios(PERFIL_MINIMO)
    assert c.acepta_remoto and c.acepta_hibrido
    assert not c.acepta_presencial


def test_sin_ciudad_no_se_buscan_locales():
    c = P.Criterios({"criterios_busqueda": {"modalidad": ["Remoto"]}})
    assert c.ciudad is None


# ------------------------------------------------------------------- pesos

def test_los_pesos_salen_del_perfil():
    pesos = P.pesos_de_habilidades(PERFIL_MINIMO)
    assert "python" in pesos and "aws" in pesos and "postgresql" in pesos


def test_el_lenguaje_pesa_mas_que_la_base_de_datos():
    pesos = P.pesos_de_habilidades(PERFIL_MINIMO)
    assert pesos["python"] > pesos["postgresql"]


def test_lo_demasiado_generico_no_puntua():
    """'git' aparece en casi todo aviso: puntuarlo solo sube el ruido."""
    assert "git" not in P.pesos_de_habilidades(PERFIL_MINIMO)


def test_la_prioridad_del_perfil_manda_en_las_keywords():
    pesos = P.pesos_de_habilidades(PERFIL_MINIMO)
    assert pesos["microservicios"] > pesos["monitoreo"]


def test_otro_perfil_produce_otros_pesos():
    """La prueba que importa: el sistema deja de describir a una sola persona."""
    otro = {"habilidades": {"lenguajes": ["Java", "Kotlin"]}, "perfiles_objetivo": []}
    pesos = P.pesos_de_habilidades(otro)
    assert "java" in pesos and "kotlin" in pesos
    assert "python" not in pesos


# --------------------------------------------------------------- terminos

def test_los_terminos_salen_de_los_cargos_objetivo():
    t = P.terminos_de_busqueda(PERFIL_MINIMO)
    assert "Desarrollador Full Stack" in t


def test_los_terminos_respetan_la_prioridad():
    t = P.terminos_de_busqueda(PERFIL_MINIMO)
    assert t.index("Desarrollador Full Stack") < t.index("Ingeniero NOC")


def test_los_terminos_se_recortan():
    """Pedirle cuarenta terminos a un portal da esperas y 429, no mejores datos."""
    assert len(P.terminos_de_busqueda(PERFIL_MINIMO, maximo=1)) == 1


# ----------------------------------------------------------------- ciudad

def test_la_ciudad_usa_limite_de_palabra():
    """El fallo real: 'cali' dentro de 'calidad' colo una vacante de Bogota."""
    pat = P.patron_ciudad("Cali")
    assert pat.search("cali, valle del cauca")
    assert not pat.search("calidad de la informacion")


def test_sin_ciudad_no_hay_patron():
    assert P.patron_ciudad(None) is None


# ------------------------------------------- terminos por perfil y por portal

PERFIL_TRES_CARRERAS = {
    "habilidades": {
        # El perfil real usa esta clave; el codigo tenia escrita `redes_telecom`.
        "telecomunicaciones": ["DWDM", "NMS"],
        "industrial": ["PLC"],
    },
    "perfiles_objetivo": [
        {"id": "desarrollo", "prioridad": 1,
         "cargos_objetivo": ["Desarrollador Full Stack", "Ingeniero de Software",
                             "Desarrollador Backend", "Desarrollador Python",
                             "AI Engineer"],
         "terminos_portal": {"slug": ["desarrollador", "programador"],
                             "texto": ["react", "node.js"]}},
        {"id": "telecomunicaciones", "prioridad": 2,
         "cargos_objetivo": ["Ingeniero NOC", "Analista NOC"],
         "terminos_portal": {"slug": ["telecomunicaciones"],
                             "texto": ["fibra optica"]}},
        {"id": "industrial", "prioridad": 3,
         "cargos_objetivo": ["Ingeniero de Mantenimiento", "Especialista en PLC"],
         "terminos_portal": {"slug": ["ingeniero-electronico"],
                             "texto": ["scada"]}},
    ],
}


def test_el_recorte_no_borra_un_perfil_entero():
    """El fallo real: con nueve cargos de desarrollo y tope 12, el perfil
    industrial no llegaba a entrar y no se buscaba ni una vacante de PLC."""
    t = P.terminos_de_busqueda(PERFIL_TRES_CARRERAS, maximo=3)
    assert t == ["Desarrollador Full Stack", "Ingeniero NOC",
                 "Ingeniero de Mantenimiento"]


def test_todos_los_perfiles_aportan_terminos_de_portal():
    slugs = P.terminos_portal(PERFIL_TRES_CARRERAS, "slug")
    assert "desarrollador" in slugs
    assert "telecomunicaciones" in slugs
    assert "ingeniero-electronico" in slugs


def test_las_dos_formas_no_se_mezclan():
    """Computrabajo arma la URL con el termino; Torre lo recibe como texto."""
    assert "react" not in P.terminos_portal(PERFIL_TRES_CARRERAS, "slug")
    assert "desarrollador" not in P.terminos_portal(PERFIL_TRES_CARRERAS, "texto")


def test_sin_terminos_declarados_cae_a_los_cargos():
    """Un perfil sin `terminos_portal` no deja al portal sin consultar."""
    perfil = {"perfiles_objetivo": [
        {"id": "x", "prioridad": 1, "cargos_objetivo": ["Ingeniero de Automatización"]}]}
    assert P.terminos_portal(perfil, "slug") == ["ingeniero-de-automatizacion"]


def test_el_slug_quita_tildes_y_signos():
    assert P.a_slug("Ingeniero Electrónico / Automatización") == \
        "ingeniero-electronico-automatizacion"


def test_las_habilidades_de_telecom_pesan_como_las_de_desarrollo():
    """Con la clave desalineada, DWDM y NMS caian al peso por defecto (3) y una
    vacante de NOC puntuaba menos que una de desarrollo que la nombrara al pasar."""
    pesos = P.pesos_de_habilidades(PERFIL_TRES_CARRERAS)
    assert pesos["dwdm"] == P.PESOS_POR_FAMILIA["telecomunicaciones"]
    assert pesos["dwdm"] > P.PESO_POR_DEFECTO
