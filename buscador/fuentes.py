# -*- coding: utf-8 -*-
"""
Adaptadores de portales de empleo.

Cada adaptador devuelve una lista de dicts con el esquema unificado:

    fuente        str   identificador del portal
    id            str   id nativo en ese portal
    titulo        str
    empresa       str | None
    url           str
    remoto        bool | None
    ubicacion     str   texto libre de pais/ciudad
    sal_min       float | None   en la moneda nativa
    sal_max       float | None
    moneda        str | None     'USD' | 'COP' | ...
    periodo       str | None     'mes' | 'ano' | 'hora'
    texto         str   descripcion concatenada, para filtrar por idioma y skills
    publicado     str | None     ISO o texto

Solo se usan APIs publicas y paginas publicas de listado. No se automatiza
ninguna postulacion desde aqui.
"""
import json, re, html, time, urllib.request, urllib.error

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def _get(url, data=None, headers=None, timeout=40):
    h = {"User-Agent": UA, "Accept": "application/json, text/html;q=0.9"}
    if headers:
        h.update(headers)
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def _json(url, data=None, headers=None):
    return json.loads(_get(url, data, headers))


def _strip(h):
    """Texto visible de un fragmento HTML.

    Quitar solo las etiquetas no basta: el contenido de <style> y <script> queda
    dentro y se cuela como si fuera texto del aviso. Eso hacia que la puntuacion
    corriera sobre CSS —"bottom" contiene "bot"— y que un aviso sin descripcion
    utilizable pareciera tener senales que no tenia.
    """
    if not h:
        return ""
    h = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1\s*>", " ", h)
    return html.unescape(re.sub(r"<[^>]+>", " ", h))


# --------------------------------------------------------------- Get on Board
GOB_CATS = ["programming", "sysadmin-devops-qa", "machine-learning-ai",
            "data-science-analytics", "technical-support", "cybersecurity"]


#: Nombre de empresa por id, para no pedir dos veces la misma. Get on Board
#: publica varias vacantes por empresa, asi que la cache ahorra la mayoria de
#: las llamadas.
_GOB_EMPRESAS = {}


def gob_empresa(cid):
    """Nombre de la empresa a partir del id que trae el listado.

    El listado solo devuelve ``company: {data: {id: 4161}}`` -- un numero, sin
    nombre-- y el detalle de la vacante exige autenticacion (401). Por eso el
    tablero mostraba "Empresa no declarada" en mas de cien filas, y no se podia
    decidir a cual postular sin abrir cada enlace.

    El endpoint publico de empresas si responde y trae el nombre.
    """
    if cid in _GOB_EMPRESAS:
        return _GOB_EMPRESAS[cid]
    nombre = None
    try:
        d = _json("https://www.getonbrd.com/api/v0/companies/%s" % cid)
        nombre = ((d.get("data") or {}).get("attributes") or {}).get("name")
    except Exception:
        pass          # sin nombre se sigue: es un dato de apoyo, no un requisito
    _GOB_EMPRESAS[cid] = nombre
    time.sleep(0.2)
    return nombre


def getonbrd(max_pages=8):
    out = []
    for cat in GOB_CATS:
        page = 1
        while page <= max_pages:
            try:
                d = _json(f"https://www.getonbrd.com/api/v0/categories/{cat}/jobs?per_page=50&page={page}")
            except Exception as e:
                print("  [getonbrd]", cat, "p", page, "ERR", e)
                break
            for r in d.get("data", []):
                a = r["attributes"]
                cid = ((a.get("company") or {}).get("data") or {}).get("id")
                out.append({
                    "fuente": "getonbrd", "id": r["id"], "titulo": a.get("title"),
                    "empresa": gob_empresa(cid) if cid else None,
                    "url": "https://www.getonbrd.com/jobs/" + r["id"],
                    "remoto": bool(a.get("remote")),
                    "ubicacion": ", ".join(a.get("countries") or []) + " | " + str(a.get("remote_modality")),
                    "sal_min": a.get("min_salary"), "sal_max": a.get("max_salary"),
                    "moneda": "USD" if a.get("min_salary") else None, "periodo": "mes",
                    "texto": " ".join(_strip(a.get(k)) for k in
                                      ("title", "description", "functions", "desirable", "projects")),
                    "publicado": a.get("published_at"),
                })
            meta = d.get("meta", {})
            if page >= meta.get("total_pages", 1):
                break
            page += 1
            time.sleep(0.25)
    return out


# ---------------------------------------------------------------------- Torre
TORRE_QUERIES = ["react", "node.js", "python", "full stack", "devops",
                 "javascript", "backend", "cloud", "inteligencia artificial", "soporte"]


def torre(size=100):
    out, vistos = [], set()
    for q in TORRE_QUERIES:
        try:
            d = _json(f"https://search.torre.co/opportunities/_search/?size={size}&aggregate=false&offset=0",
                      data={"skill/role": {"text": q, "experience": "potential-to-develop"},
                            "remote": {"term": True}})
        except Exception as e:
            print("  [torre]", q, "ERR", e)
            continue
        for r in d.get("results", []):
            if r["id"] in vistos:
                continue
            vistos.add(r["id"])
            comp = (r.get("compensation") or {}).get("data") or {}
            orgs = r.get("organizations") or []
            per = {"monthly": "mes", "yearly": "ano", "hourly": "hora"}.get(comp.get("periodicity"))
            out.append({
                "fuente": "torre", "id": r["id"], "titulo": r.get("objective"),
                "empresa": orgs[0]["name"] if orgs else None,
                "url": "https://torre.ai/post/" + r["id"],
                "remoto": bool(r.get("remote")),
                "ubicacion": (r.get("place") or {}).get("locationType") or "",
                "sal_min": comp.get("minAmount") or None, "sal_max": comp.get("maxAmount") or None,
                "moneda": comp.get("currency"), "periodo": per,
                "texto": " ".join(str(x) for x in [r.get("objective"), r.get("tagline")] +
                                  [s.get("name") for s in (r.get("skills") or [])]),
                "publicado": r.get("created"),
            })
        time.sleep(0.4)
    return out


# --------------------------------------------------------------- Computrabajo
def computrabajo(paginas=6):
    """Lee las paginas publicas de listado de Computrabajo Colombia."""
    out = []
    base = "https://co.computrabajo.com/trabajo-de-{}?p={}"
    for termino in ["desarrollador", "ingeniero-de-sistemas", "soporte-tecnico"]:
        for p in range(1, paginas + 1):
            try:
                s = _get(base.format(termino, p), timeout=30)
            except Exception as e:
                print("  [computrabajo]", termino, p, "ERR", e)
                break
            arts = re.findall(r"<article[^>]*data-id='([^']+)'[^>]*>(.*?)</article>", s, re.S)
            if not arts:
                break
            for oid, blk in arts:
                tit = re.search(r'<a[^>]*class="js-o-link[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', blk, re.S)
                emp = re.search(r'<a[^>]*class="[^"]*it-blank[^"]*"[^>]*>(.*?)</a>', blk, re.S)
                sal = re.search(r"\$\s?([\d\.\,]+)", _strip(blk))
                out.append({
                    "fuente": "computrabajo", "id": oid,
                    "titulo": _strip(tit.group(2)).strip() if tit else None,
                    "empresa": _strip(emp.group(1)).strip() if emp else None,
                    "url": "https://co.computrabajo.com" + tit.group(1) if tit else None,
                    "remoto": bool(re.search(r"remoto|teletrabajo|h[ií]brido", blk, re.I)),
                    "ubicacion": "Colombia",
                    "sal_min": float(sal.group(1).replace(".", "").replace(",", "")) if sal else None,
                    "sal_max": None, "moneda": "COP" if sal else None, "periodo": "mes",
                    "texto": _strip(blk), "publicado": None,
                })
            time.sleep(0.6)
    return out


# ------------------------------------------------------------------- elempleo
def elempleo(paginas=5):
    out = []
    for p in range(1, paginas + 1):
        try:
            s = _get(f"https://www.elempleo.com/co/ofertas-empleo/?PageIndex={p}", timeout=30)
        except Exception as e:
            print("  [elempleo] p", p, "ERR", e)
            break
        blks = re.split(r'class="result-item', s)[1:]
        if not blks:
            break
        for blk in blks:
            tit = re.search(r'<a[^>]*href="(/co/ofertas-trabajo/[^"]+)"[^>]*>(?:\s*)([^<]{6,120})', blk)
            if not tit:
                continue
            txt = _strip(blk[:3000])
            sal = re.search(r"\$\s?([\d\.]{7,})", txt)
            out.append({
                "fuente": "elempleo", "id": tit.group(1).rsplit("/", 1)[-1],
                "titulo": html.unescape(tit.group(2)).strip(), "empresa": None,
                "url": "https://www.elempleo.com" + tit.group(1),
                "remoto": bool(re.search(r"remoto|teletrabajo", txt, re.I)),
                "ubicacion": "Colombia",
                "sal_min": float(sal.group(1).replace(".", "")) if sal else None,
                "sal_max": None, "moneda": "COP" if sal else None, "periodo": "mes",
                "texto": txt, "publicado": None,
            })
        time.sleep(0.6)
    return out


# ------------------------------------------------ agregadores remotos globales
def remotive():
    d = _json("https://remotive.com/api/remote-jobs?category=software-dev&limit=400")
    return [{
        "fuente": "remotive", "id": str(j["id"]), "titulo": j.get("title"),
        "empresa": j.get("company_name"), "url": j.get("url"), "remoto": True,
        "ubicacion": j.get("candidate_required_location") or "",
        "sal_min": None, "sal_max": None, "moneda": None, "periodo": None,
        "texto": _strip(j.get("description")), "publicado": j.get("publication_date"),
    } for j in d.get("jobs", [])]


def jobicy():
    d = _json("https://jobicy.com/api/v2/remote-jobs?count=100&industry=engineering")
    return [{
        "fuente": "jobicy", "id": str(j.get("id")), "titulo": j.get("jobTitle"),
        "empresa": j.get("companyName"), "url": j.get("url"), "remoto": True,
        "ubicacion": j.get("jobGeo") or "",
        "sal_min": j.get("annualSalaryMin"), "sal_max": j.get("annualSalaryMax"),
        "moneda": j.get("salaryCurrency"), "periodo": "ano",
        "texto": _strip(j.get("jobExcerpt")) + " " + _strip(j.get("jobDescription")),
        "publicado": j.get("pubDate"),
    } for j in d.get("jobs", [])]


def himalayas():
    d = _json("https://himalayas.app/jobs/api?limit=200")
    return [{
        "fuente": "himalayas", "id": str(j.get("guid")), "titulo": j.get("title"),
        "empresa": j.get("companyName"), "url": j.get("applicationLink") or j.get("guid"),
        "remoto": True, "ubicacion": ", ".join(j.get("locationRestrictions") or []) or "Worldwide",
        "sal_min": j.get("minSalary"), "sal_max": j.get("maxSalary"),
        "moneda": "USD", "periodo": "ano",
        "texto": _strip(j.get("excerpt")) + " " + _strip(j.get("description")),
        "publicado": j.get("pubDate"),
    } for j in d.get("jobs", [])]


def remoteok():
    d = _json("https://remoteok.com/api")
    out = []
    for j in d:
        if not isinstance(j, dict) or not j.get("position"):
            continue
        out.append({
            "fuente": "remoteok", "id": str(j.get("id")), "titulo": j.get("position"),
            "empresa": j.get("company"), "url": j.get("url"), "remoto": True,
            "ubicacion": j.get("location") or "Worldwide",
            "sal_min": j.get("salary_min"), "sal_max": j.get("salary_max"),
            "moneda": "USD", "periodo": "ano",
            "texto": _strip(j.get("description")) + " " + " ".join(j.get("tags") or []),
            "publicado": j.get("date"),
        })
    return out


def arbeitnow():
    d = _json("https://www.arbeitnow.com/api/job-board-api")
    return [{
        "fuente": "arbeitnow", "id": j.get("slug"), "titulo": j.get("title"),
        "empresa": j.get("company_name"), "url": j.get("url"), "remoto": bool(j.get("remote")),
        "ubicacion": j.get("location") or "",
        "sal_min": None, "sal_max": None, "moneda": None, "periodo": None,
        "texto": _strip(j.get("description")) + " " + " ".join(j.get("tags") or []),
        "publicado": j.get("created_at"),
    } for j in d.get("data", [])]


ADAPTADORES = {
    "getonbrd": getonbrd, "torre": torre, "computrabajo": computrabajo,
    "elempleo": elempleo, "remotive": remotive, "jobicy": jobicy,
    "himalayas": himalayas, "remoteok": remoteok, "arbeitnow": arbeitnow,
}
