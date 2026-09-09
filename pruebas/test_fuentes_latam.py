# -*- coding: utf-8 -*-
"""El resto de LATAM: mismo motor de Computrabajo, distinto pais y moneda."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "buscador"))

import fuentes_latam as L


def test_estan_los_ocho_paises_que_respondieron():
    """Probados uno por uno contra el portal el 7-sept: los ocho devolvieron
    pagina llena con el mismo marcado que Colombia."""
    assert set(L.PAISES) == {"mx", "cl", "ar", "pe", "pa", "cr", "uy", "ec"}


def test_espana_no_esta_y_es_a_proposito():
    """computrabajo.es responde 200 pero devuelve la misma pagina generica de
    33 KB para cualquier busqueda: no publica los avisos en el HTML."""
    assert "es" not in L.PAISES


def test_cada_pais_declara_su_moneda():
    """Sin moneda, un sueldo mexicano de 40.000 se leeria como 40.000 pesos
    colombianos, que es la clase de error que ya paso con las rupias de Torre."""
    for codigo, (dominio, moneda, pais) in L.PAISES.items():
        assert dominio.endswith("computrabajo.com"), codigo
        assert moneda and len(moneda) == 3, codigo
        assert pais, codigo


def test_panama_y_ecuador_usan_dolares():
    """Los dos estan dolarizados; ponerles moneda local seria inventar una tasa."""
    assert L.PAISES["pa"][1] == "USD"
    assert L.PAISES["ec"][1] == "USD"


def test_hay_un_adaptador_registrado_por_pais():
    assert len(L.ADAPTADORES) == len(L.PAISES)
    for codigo in L.PAISES:
        assert "computrabajo-" + codigo in L.ADAPTADORES
        assert callable(L.ADAPTADORES["computrabajo-" + codigo])


def test_los_adaptadores_no_comparten_el_pais():
    """Un `for` que crea closures sin capturar la variable devuelve ocho
    adaptadores del mismo pais. Es el error clasico de este patron."""
    nombres = {fn.__name__ for fn in L.ADAPTADORES.values()}
    assert len(nombres) == len(L.PAISES)


# --------------------------- solo remotas de verdad, no hibridas en otro pais

def test_una_hibrida_en_otro_pais_no_es_remota():
    """El fallo real: la criba del listado marcaba 'remoto' cualquier aviso que
    mencionara 'hibrido'. De 62 vacantes internacionales solo 4 eran remotas;
    las otras 58 pedian mudarse a Ciudad de Mexico, Santiago, Lima o Iquique."""
    texto = ("Service Delivery Manager Senior. Modalidad hibrida, 3 dias en "
             "oficina en Benito Juarez, Ciudad de Mexico. Buscamos profesional "
             "con experiencia en gestion de servicios de TI.")
    assert L.clasificar_modalidad(texto, "Service Delivery Manager Senior") != "remoto"


def test_una_presencial_en_otro_pais_no_es_remota():
    texto = ("Ingeniero de Redes y Telecomunicaciones para trabajo presencial "
             "en nuestras instalaciones de Iquique. Se requiere disponibilidad "
             "para asistir a la oficina todos los dias.")
    assert L.clasificar_modalidad(texto, "Ingeniero de Redes") != "remoto"


def test_una_remota_de_verdad_si_pasa():
    texto = ("Desarrollador Full Stack 100% remoto. El equipo trabaja de forma "
             "totalmente remota desde cualquier lugar, sin necesidad de asistir "
             "a oficina. Teletrabajo permanente.")
    assert L.clasificar_modalidad(texto, "Desarrollador Full Stack") == "remoto"
