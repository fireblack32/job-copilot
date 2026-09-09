import sys, os, json, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from copiloto import bitacora as b
from copiloto import tablero as t
from copiloto.registrar import urls_en


V1 = {"fuente": "getonbrd", "id": "9911", "titulo": "Desarrollador Backend Python",
      "empresa": "BC Tecnologia", "url": "https://getonbrd.com/jobs/back-9911",
      "pts": 40, "via": "remota"}
V2 = {"fuente": "computrabajo-cali", "id": "ABC", "titulo": "Data Engineer",
      "empresa": "DROPI", "url": "https://co.computrabajo.com/of/abc",
      "pts": 31, "via": "cali", "zona": "sur"}


# ------------------------------------------------------------------ identidad
def test_la_clave_usa_fuente_e_id():
    assert b.clave(V1) == "getonbrd:9911"


def test_sin_id_la_clave_cae_a_la_url_sin_parametros():
    v = {"fuente": "torre", "url": "https://torre.co/of/7?utm_source=mail#lc=1"}
    assert b.clave(v) == "torre:https://torre.co/of/7"


def test_la_huella_ignora_el_ruido_del_titulo():
    """'(Remoto)' y 'Bogota' no distinguen un puesto de otro."""
    a = {"empresa": "BC Tecnologia", "titulo": "Desarrollador Backend Python (Remoto)"}
    c = {"empresa": "bc tecnologia", "titulo": "Desarrollador Backend Python - Bogota"}
    assert b.huella(a) == b.huella(c)


def test_sin_empresa_no_hay_huella():
    """Si no, un cargo generico de una empresa bloquearia el de todas."""
    assert b.huella({"titulo": "Desarrollador Backend"}) == ""


# -------------------------------------------------------------------- memoria
def test_una_vacante_enviada_no_vuelve_a_ofrecerse():
    bit = b.Bitacora()
    bit.registrar(V1, quien=b.Quien.PERSONA, fecha="2026-09-02")
    motivo = bit.cerrada(V1)
    assert motivo and "vos" in motivo


def test_el_mismo_puesto_en_otro_portal_tambien_queda_cerrado():
    """El caso que mas dano hace: mandarle dos veces el CV a la misma empresa."""
    bit = b.Bitacora()
    bit.registrar(V1)
    gemela = {**V1, "fuente": "torre", "id": "otro", "url": "https://torre.co/x"}
    motivo = bit.cerrada(gemela)
    assert motivo and "getonbrd" in motivo


def test_una_vacante_distinta_sigue_abierta():
    bit = b.Bitacora()
    bit.registrar(V1)
    assert bit.cerrada(V2) is None


def test_en_curso_no_cierra_la_vacante():
    """Sacarla del tablero no es lo mismo que haberla postulado."""
    bit = b.Bitacora()
    bit.registrar(V1, estado=b.Estado.EN_CURSO)
    assert bit.cerrada(V1) is None


def test_descartada_dice_por_que():
    bit = b.Bitacora()
    bit.registrar(V1, estado=b.Estado.DESCARTADA, nota="pide C1 de ingles")
    assert "C1" in bit.cerrada(V1)


def test_registrar_dos_veces_no_duplica():
    bit = b.Bitacora()
    bit.registrar(V1)
    bit.registrar(V1, estado=b.Estado.DESCARTADA)
    assert len(bit) == 1


# --------------------------------------------------------------- persistencia
def test_sobrevive_al_disco():
    d = tempfile.mkdtemp()
    ruta = os.path.join(d, "bitacora.json")
    bit = b.Bitacora(ruta)
    bit.registrar(V1, quien=b.Quien.PERSONA)
    bit.guardar()
    otra = b.Bitacora(ruta)
    assert otra.cerrada(V1)
    assert otra.resumen()["por_la_persona"] == 1


# ------------------------------------------------------------ vuelta por URL
def test_registrar_por_url_encuentra_la_candidata():
    bit = b.Bitacora()
    hechos, perdidas = bit.registrar_urls(
        ["https://getonbrd.com/jobs/back-9911?ref=tablero"], [V1, V2])
    assert len(hechos) == 1 and not perdidas
    assert bit.cerrada(V1)


def test_una_url_desconocida_se_avisa_y_no_se_anota():
    """Un pegado a medias no debe crear registros fantasma."""
    bit = b.Bitacora()
    hechos, perdidas = bit.registrar_urls(["https://otra.com/x"], [V1])
    assert not hechos and perdidas == ["https://otra.com/x"]
    assert len(bit) == 0


def test_extrae_urls_de_un_pegado_sucio():
    texto = ("Postule a mano a estas 2:\n"
             "https://getonbrd.com/jobs/back-9911\n"
             "https://co.computrabajo.com/of/abc,\n"
             "https://getonbrd.com/jobs/back-9911\n")
    assert urls_en(texto) == ["https://getonbrd.com/jobs/back-9911",
                              "https://co.computrabajo.com/of/abc"]


# -------------------------------------------------------------------- tablero
def test_separar_parte_pendientes_y_cerradas():
    bit = b.Bitacora()
    bit.registrar(V1)
    pend, cerr = b.separar([V1, V2], bit)
    assert [v["id"] for v in pend] == ["ABC"]
    assert cerr[0]["cerrada_porque"]


def test_el_tablero_lleva_el_enlace_de_cada_vacante():
    h = t.render([V1, V2])
    assert V1["url"] in h and V2["url"] in h


def test_las_cerradas_salen_marcadas_y_no_editables():
    bit = b.Bitacora()
    bit.registrar(V1)
    pend, cerr = b.separar([V1, V2], bit)
    h = t.render(pend, cerr)
    assert "checked disabled" in h


def test_el_tablero_agrupa_cali_sur_aparte():
    h = t.render([V1, V2])
    assert "Cali &middot; sur" in h or "Cali · sur" in h


def test_el_salario_se_muestra_como_rango_cuando_lo_hay():
    assert t._plata({"cop_min": 4_000_000, "cop_max": 9_000_000}) == "$4.0M a $9.0M"
    assert t._plata({"cop_min": 4_000_000}) == "$4.0M"
    assert t._plata({}) is None


# ------------------------------------------- la misma empresa con otro sufijo

def test_la_huella_ignora_el_sufijo_societario():
    """El fallo real: se descarto 'Usercode - Desarrollador Full-Stack' por ser
    solo desde Chile, y volvio como 'Usercode SpA' al primer puesto del tablero
    cuando el adaptador empezo a traer el nombre completo de la empresa."""
    corta = {"empresa": "Usercode", "titulo": "Desarrollador Full-Stack"}
    larga = {"empresa": "Usercode SpA", "titulo": "Desarrollador Full-Stack"}
    assert b.huella(corta) == b.huella(larga)


def test_la_huella_ignora_varios_sufijos():
    base = b.huella({"empresa": "Makers Solutions", "titulo": "Dev"})
    for nombre in ("Makers Solutions S.A.S", "Makers Solutions LTDA",
                   "Makers Solutions Inc", "Makers Solutions S.A."):
        assert b.huella({"empresa": nombre, "titulo": "Dev"}) == base, nombre


def test_no_recorta_un_sufijo_que_es_parte_del_nombre():
    """'Co' dentro de 'Coati' no es sufijo, y 'SA' dentro de 'SAP' tampoco."""
    assert b.huella({"empresa": "Coati", "titulo": "Dev"}) == "coati|dev"
    assert b.huella({"empresa": "SAP", "titulo": "Dev"}) == "sap|dev"


def test_una_empresa_que_es_solo_sufijo_no_queda_vacia():
    assert b.huella({"empresa": "Inc", "titulo": "Dev"}) == "inc|dev"
