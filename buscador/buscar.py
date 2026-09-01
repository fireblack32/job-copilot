# -*- coding: utf-8 -*-
"""
Buscador multi-portal: recolecta, normaliza, filtra y puntua vacantes
contra el perfil maestro.

    python buscar.py [--fuentes a,b,c] [--trm 3124]

Escribe  resultados/crudo.json  y  resultados/ranking.json .
"""
import argparse, io, json, os, re, sys, unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fuentes
import fuentes_co
import fuentes_cali

# Torre, elempleo y Computrabajo usan los adaptadores corregidos de fuentes_co
fuentes.ADAPTADORES.update({
    "torre": fuentes_co.torre,
    "elempleo": fuentes_co.elempleo,
    "computrabajo": fuentes_co.computrabajo,
    # Presencial e hibrido en Cali: estos NO filtran por remoto.
    "computrabajo-cali": fuentes_cali.computrabajo_cali,
    "elempleo-cali": fuentes_cali.elempleo_cali,
})

AQUI = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(AQUI, "..", "resultados")
PERFIL = os.environ.get("PERFIL_MAESTRO", os.path.join(AQUI, "..", "perfil-maestro.json"))

SMMLV_2026 = 1750905
PISO_COP = 2 * SMMLV_2026          # 3.501.810, piso para vacantes remotas

# Piso para Cali. Es mas alto que el remoto a proposito: una vacante presencial
# cuesta transporte y unas dos horas de desplazamiento al dia, asi que tiene que
# pagar mas que una remota para valer lo mismo.
PISO_CALI = 4_000_000
HORAS_MES = 160

# ------------------------------------------------------------------- utilidad
def sin_tildes(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "")
                   if unicodedata.category(c) != "Mn").lower()


# Tasas a COP. Se refrescan al arrancar; estos son el respaldo si la API falla.
TASAS_COP = {"COP": 1.0, "USD": 3134.8, "EUR": 3623.2, "INR": 32.8, "MXN": 183.9,
             "ARS": 2.1, "CLP": 3.4, "PEN": 930.2, "BRL": 602.1, "UYU": 78.0,
             "CRC": 7.0, "GBP": 4200.0, "CAD": 2270.0}

# Un salario mensual fuera de esta banda es dato sucio del portal, no una oferta real.
COP_MES_MIN = 500_000
COP_MES_MAX = 80_000_000


def refrescar_tasas():
    """Trae tasas reales. Sin esto, INR y MXN se leen como si fueran dolares."""
    import urllib.request
    try:
        req = urllib.request.Request("https://open.er-api.com/v6/latest/COP",
                                     headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=25) as r:
            rates = json.loads(r.read().decode("utf-8"))["rates"]
        for m in list(TASAS_COP):
            if m in rates and rates[m]:
                TASAS_COP[m] = 1.0 / rates[m]
        TASAS_COP["COP"] = 1.0
        return True
    except Exception as e:
        print("  aviso: no se pudieron refrescar tasas (%s); se usan las de respaldo" % e)
        return False


def a_cop_mes(sal, moneda, periodo):
    """Normaliza a COP/mes. None si la moneda es desconocida o el dato es absurdo."""
    if not sal or sal <= 0:
        return None
    m = (moneda or "").upper().strip()
    if m not in TASAS_COP:
        return None          # moneda desconocida: no adivinar
    cop = float(sal) * TASAS_COP[m]
    if periodo == "ano":
        cop /= 12.0
    elif periodo == "hora":
        cop *= HORAS_MES
    elif periodo != "mes":
        return None          # periodicidad no declarada: no asumir
    return cop if COP_MES_MIN < cop < COP_MES_MAX else None


# ------------------------------------------------------ filtros de exclusion
ENGLISH_DURO = [
    r"ingl[eé]s\s*(nivel\s*)?(b2|c1|c2)", r"ingl[eé]s\s+(avanzado|fluido|nativo|conversacional)",
    r"(advanced|fluent|proficient|native|professional|excellent)\s+(written\s+and\s+spoken\s+)?english",
    r"english\s*(level\s*)?(b2|c1|c2)", r"english\s+(is\s+)?(required|mandatory|fluency)",
    r"100%\s*(en|in)\s*(ingl[eé]s|english)", r"\(english\)", r"dominio\s+(del\s+)?ingl[eé]s",
    r"fluency\s+in\s+english", r"strong\s+english",
]

# Un aviso escrito integramente en ingles implica proceso en ingles.
MARCADORES_ES = ["experiencia", "conocimiento", "desarrollo", "empresa", "equipo",
                 "requisitos", "trabajo", "años", "para", "con", "que", "nuestro"]
MARCADORES_EN = ["experience", "requirements", "you will", "we are", "the team",
                 "years", "with", "that", "our", "role"]


def idioma_bloquea(texto, titulo=""):
    low = sin_tildes((titulo or "") + " " + texto)
    for p in ENGLISH_DURO:
        m = re.search(p, low)
        if m:
            return "requisito: " + m.group(0)[:45]
    es = sum(low.count(w) for w in MARCADORES_ES)
    en = sum(low.count(w) for w in MARCADORES_EN)
    if en > 6 and en > es * 3:
        return "aviso redactado en ingles"
    return None


GEO_EXCLUYE = [
    r"residencia en chile", r"residir en chile", r"vivir en chile", r"radicad[oa]s? en chile",
    r"only.{0,25}(us|usa|united states|canada|europe|uk)\b", r"must (be|reside).{0,30}(us|usa|europe|canada)",
    r"us[- ]based", r"eu[- ]based", r"authorized to work in the (us|united states)",
    r"residencia en (mexico|argentina|peru|españa) ", r"solo (para )?chile",
]
GEO_ACEPTA = [r"latam", r"latinoam", r"america latina", r"colombia", r"anywhere", r"worldwide",
              r"cualquier pais", r"remote_anywhere", r"toda la region"]


# ------------------------------------------------------- puntuacion de encaje
SKILLS = {
    "react": 5, "node": 5, "javascript": 3, "python": 5, "django": 4, "fastapi": 3, "flask": 2,
    "postgres": 3, "mysql": 3, "sql server": 3, "oracle": 2, "nosql": 2, "mongodb": 2, "sql": 2,
    "aws": 4, "azure": 3, "gcp": 3, "google cloud": 3, "docker": 4, "ci/cd": 4, "devops": 3,
    "git": 2, "linux": 2, "api rest": 4, "restful": 4, "microservicio": 2,
    "openai": 6, "llm": 6, "inteligencia artificial": 5, "chatbot": 4, "bot": 3, "rag": 5,
    "agente": 3, "embedding": 4, "machine learning": 2, "prompt": 4,
    "scrum": 2, "agile": 2, "c#": 3, ".net": 3, "php": 2, "c++": 1, "lua": 1, "matlab": 1,
    "noc": 6, "monitoreo": 5, "monitoring": 4, "redes": 4, "network": 3, "fibra": 5, "dwdm": 6,
    "nms": 5, "sla": 4, "ticket": 3, "telecomunicacion": 5, "incidente": 4, "incident": 3,
    "soporte": 3, "infraestructura": 3, "disponibilidad": 4, "plc": 4, "automatizacion": 3,
}
DESCUENTA = ["java ", "spring boot", "kotlin", "golang", "rust", "scala", "ruby on rails",
             "salesforce", "sap ", "abap", "flutter", "swift", "drupal", "magento",
             "sharepoint", "cobol", "mainframe"]

SENIOR_DURO = re.compile(r"\b(staff|principal|head of|director|vp of|arquitect[oa] jefe)\b", re.I)
ANIOS = re.compile(r"(\d{1,2})\s*\+?\s*(?:a[nñ]os|years)")


def puntuar(texto, titulo):
    low = sin_tildes(texto + " " + (titulo or ""))
    hits, pts = [], 0
    for k, w in SKILLS.items():
        if sin_tildes(k) in low:
            pts += w
            hits.append(k)
    contras = [d.strip() for d in DESCUENTA if sin_tildes(d) in low]
    pts -= 2 * len(contras)
    anios = [int(a) for a in ANIOS.findall(low) if int(a) <= 20]
    return pts, hits, contras, (max(anios) if anios else None)


# ------------------------------------------------------------------- pipeline
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fuentes", default=",".join(fuentes.ADAPTADORES))
    ap.add_argument("--trm", type=float, default=3124.0)
    ap.add_argument("--min-pts", type=int, default=14)
    args = ap.parse_args()

    refrescar_tasas()
    print("  1 USD = %.0f COP" % TASAS_COP["USD"])
    os.makedirs(RES, exist_ok=True)
    perfil = json.load(io.open(PERFIL, encoding="utf-8"))

    crudo = []
    for nombre in [f.strip() for f in args.fuentes.split(",") if f.strip()]:
        fn = fuentes.ADAPTADORES.get(nombre)
        if not fn:
            print("fuente desconocida:", nombre)
            continue
        print("recolectando", nombre, "...", end=" ", flush=True)
        try:
            filas = fn()
        except Exception as e:
            print("ERROR", e)
            continue
        print(len(filas))
        crudo.extend(filas)

    # deduplicar por (fuente, id) y por (titulo, empresa)
    vistos, dedup = set(), []
    for r in crudo:
        k1 = (r["fuente"], r["id"])
        k2 = (sin_tildes(r.get("titulo")), sin_tildes(r.get("empresa")))
        if k1 in vistos or (r.get("empresa") and k2 in vistos):
            continue
        vistos.add(k1)
        if r.get("empresa"):
            vistos.add(k2)
        dedup.append(r)

    json.dump(dedup, io.open(os.path.join(RES, "crudo.json"), "w", encoding="utf-8"),
              ensure_ascii=False)

    # filtrar y puntuar
    #
    # Hay dos vias de aceptacion, con reglas distintas:
    #
    #   remota  -> en espanol, sin exigencia geografica, piso 2 SMMLV
    #   cali    -> hibrida o presencial en Cali, piso 4.000.000 y con
    #              prestaciones de ley (o al menos sin declarar lo contrario)
    #
    # Mezclarlas en un solo filtro fue lo que antes hacia desaparecer todo lo
    # presencial: la primera condicion descartaba por no ser remoto.
    rank = []
    descartes = {"no_remoto": 0, "idioma": 0, "geo": 0, "salario": 0,
                 "encaje": 0, "senior": 0, "sin_prestaciones": 0, "fuera_de_cali": 0}

    for r in dedup:
        texto = r.get("texto") or ""
        campo_geo = sin_tildes(texto + " " + (r.get("ubicacion") or ""))
        es_fuente_cali = str(r.get("fuente", "")).endswith("-cali")
        modalidad = r.get("modalidad") or ("remoto" if r.get("remoto") else None)

        blo = idioma_bloquea(texto, r.get("titulo"))
        if blo:
            descartes["idioma"] += 1
            continue
        if SENIOR_DURO.search(r.get("titulo") or ""):
            descartes["senior"] += 1
            continue

        cop = a_cop_mes(r.get("sal_min"), r.get("moneda"), r.get("periodo"))
        cop_max = a_cop_mes(r.get("sal_max"), r.get("moneda"), r.get("periodo"))
        techo = cop_max or cop

        if es_fuente_cali:
            # Debe estar en Cali de verdad, no solo venir del listado de Cali.
            if "cali" not in campo_geo:
                descartes["fuera_de_cali"] += 1
                continue
            # Lo 100% remoto que aparece en el listado de Cali ya lo cubre la
            # via remota; aqui interesa lo que obliga a pisar la oficina.
            if modalidad == "remoto":
                descartes["no_remoto"] += 1
                continue
            # Prestaciones: False descarta, None no. El silencio es habitual en
            # la bolsa colombiana y descartar por el dejaria fuera media busqueda.
            if r.get("prestaciones") is False:
                descartes["sin_prestaciones"] += 1
                continue
            if techo is not None and techo < PISO_CALI:
                descartes["salario"] += 1
                continue
            via, piso = "cali", PISO_CALI
        else:
            if r.get("remoto") is False:
                descartes["no_remoto"] += 1
                continue
            if any(re.search(p, campo_geo) for p in GEO_EXCLUYE):
                descartes["geo"] += 1
                continue
            if techo is not None and techo <= PISO_COP:
                descartes["salario"] += 1
                continue
            via, piso = "remota", PISO_COP

        pts, hits, contras, anios = puntuar(texto, r.get("titulo"))
        if pts < args.min_pts:
            descartes["encaje"] += 1
            continue

        zona = r.get("zona")
        rank.append({**r,
                     "via": via,
                     "modalidad": modalidad,
                     "zona": zona,
                     "cop_min": round(cop) if cop else None,
                     "cop_max": round(cop_max) if cop_max else None,
                     "sobre_piso": round(techo / piso, 2) if techo else None,
                     "pts": pts, "hits": hits, "contras": contras, "anios_req": anios,
                     "latam": bool(any(re.search(p, campo_geo) for p in GEO_ACEPTA)),
                     "texto": texto[:4000]})

    # Orden: primero Cali sur (es la preferencia declarada), luego el resto de
    # Cali, luego lo remoto; dentro de cada grupo, por encaje y por salario.
    def clave(r):
        if r["via"] == "cali":
            grupo = 0 if r.get("zona") == "sur" else 1
        else:
            grupo = 2
        return (grupo, not r["latam"], -r["pts"], -(r["cop_max"] or r["cop_min"] or 0))

    rank.sort(key=clave)
    json.dump(rank, io.open(os.path.join(RES, "ranking.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print("\n" + "=" * 74)
    print("recolectadas      :", len(crudo), "| unicas:", len(dedup))
    print("descartes         :", descartes)
    print("CANDIDATAS        :", len(rank), " (LATAM/Colombia:", sum(1 for r in rank if r["latam"]), ")")
    cali = [r for r in rank if r["via"] == "cali"]
    print("  remotas         :", sum(1 for r in rank if r["via"] == "remota"))
    print("  Cali            :", len(cali),
          "| sur:", sum(1 for r in cali if r.get("zona") == "sur"),
          "| hibridas:", sum(1 for r in cali if r.get("modalidad") == "hibrido"))
    print("con salario > piso:", sum(1 for r in rank if r["sobre_piso"]))
    print("=" * 74)
    por_fuente = {}
    for r in rank:
        por_fuente[r["fuente"]] = por_fuente.get(r["fuente"], 0) + 1
    print("por fuente:", por_fuente)


if __name__ == "__main__":
    main()
