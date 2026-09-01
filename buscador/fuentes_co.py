# -*- coding: utf-8 -*-
"""
Adaptadores corregidos para las fuentes hispanohablantes: Torre, elempleo y
Computrabajo. Se separan de fuentes.py porque los tres necesitan una segunda
pasada sobre la pagina de detalle para obtener descripcion y salario, que es
donde vive el dato que realmente filtra.
"""
import json, re, time
from fuentes import _get, _json, _strip

# ---------------------------------------------------------------------- Torre
# La API rechaza size > 20; se pagina con offset.
TORRE_QUERIES = ["react", "node.js", "python", "full stack", "devops", "javascript",
                 "backend", "cloud developer", "inteligencia artificial", "soporte tecnico",
                 "django", "aws"]


def torre(paginas=4, size=20):
    out, vistos = [], set()
    for q in TORRE_QUERIES:
        for p in range(paginas):
            try:
                d = _json(
                    f"https://search.torre.co/opportunities/_search/?size={size}"
                    f"&aggregate=false&offset={p * size}",
                    data={"skill/role": {"text": q, "experience": "potential-to-develop"},
                          "remote": {"term": True}})
            except Exception as e:
                print("  [torre]", q, "off", p * size, "ERR", e)
                break
            res = d.get("results", [])
            if not res:
                break
            for r in res:
                if r["id"] in vistos:
                    continue
                vistos.add(r["id"])
                comp = (r.get("compensation") or {}).get("data") or {}
                orgs = r.get("organizations") or []
                per = {"monthly": "mes", "yearly": "ano", "hourly": "hora"}.get(comp.get("periodicity"))
                skills = [s.get("name") for s in (r.get("skills") or [])]
                out.append({
                    "fuente": "torre", "id": r["id"], "titulo": r.get("objective"),
                    "empresa": orgs[0]["name"] if orgs else None,
                    "url": "https://torre.ai/post/" + r["id"],
                    "remoto": bool(r.get("remote")),
                    "ubicacion": (r.get("place") or {}).get("locationType") or "",
                    "sal_min": comp.get("minAmount") or None,
                    "sal_max": comp.get("maxAmount") or None,
                    "moneda": comp.get("currency"), "periodo": per,
                    "texto": " ".join(str(x) for x in
                                      [r.get("objective"), r.get("tagline")] + skills),
                    "publicado": r.get("created"),
                })
            time.sleep(0.35)
    return out


# ------------------------------------------------------------------- elempleo
# El listado trae un bloque JSON-LD ItemList con id + nombre de cada oferta;
# el detalle trae un JobPosting con descripcion y baseSalary.
EE_LISTADOS = [
    "https://www.elempleo.com/co/ofertas-empleo/modalidad-remoto",
    "https://www.elempleo.com/co/ofertas-empleo/trabajo-desarrollador",
    "https://www.elempleo.com/co/ofertas-empleo/trabajo-ingeniero-de-sistemas",
    "https://www.elempleo.com/co/ofertas-empleo/trabajo-soporte-tecnico",
]


def _ld_blocks(html_text):
    for m in re.finditer(r'<script type="application/ld\+json"[^>]*>(.*?)</script>',
                         html_text, re.S):
        raw = m.group(1).strip()
        try:
            yield json.loads(raw)
        except Exception:
            continue


def job_posting(html_text):
    """Encuentra el JobPosting de una pagina, este donde este.

    Computrabajo no publica el JobPosting suelto: lo envuelve en un `@graph`
    junto al Organization y al WebPage. Mirar solo el nivel superior devolvia
    None y el adaptador caia al respaldo de raspar la pagina entera, que trae
    el encabezado y no la oferta. Noventa vacantes por barrido se perdian asi,
    incluida una de 7.500.000 al mes.
    """
    def buscar(nodo):
        if isinstance(nodo, dict):
            if nodo.get("@type") == "JobPosting":
                return nodo
            for clave in ("@graph", "itemListElement", "mainEntity"):
                if clave in nodo:
                    hallado = buscar(nodo[clave])
                    if hallado:
                        return hallado
        elif isinstance(nodo, list):
            for hijo in nodo:
                hallado = buscar(hijo)
                if hallado:
                    return hallado
        return None

    for bloque in _ld_blocks(html_text):
        hallado = buscar(bloque)
        if hallado:
            return hallado
    return None


def elempleo(max_detalle=70):
    fichas, vistos = [], set()
    for url in EE_LISTADOS:
        try:
            s = _get(url, timeout=35)
        except Exception as e:
            print("  [elempleo] listado ERR", e)
            continue
        for blk in _ld_blocks(s):
            if isinstance(blk, dict) and blk.get("@type") == "ItemList":
                for it in blk.get("itemListElement", []):
                    item = it.get("item") or {}
                    oid = item.get("@id")
                    if oid and oid not in vistos:
                        vistos.add(oid)
                        fichas.append({"url": oid, "titulo": item.get("name")})
        time.sleep(0.5)

    out = []
    for f in fichas[:max_detalle]:
        try:
            s = _get(f["url"], timeout=30)
        except Exception:
            continue
        jp = job_posting(s)
        desc = _strip(jp.get("description")) if jp else ""
        texto = (f["titulo"] or "") + " " + desc
        sal_min = sal_max = None
        moneda = None
        if jp:
            bs = ((jp.get("baseSalary") or {}).get("value")) or {}
            sal_min = bs.get("minValue") or bs.get("value")
            sal_max = bs.get("maxValue")
            moneda = (jp.get("baseSalary") or {}).get("currency") or "COP"
        if not sal_min:
            m = re.search(r"\$\s?([\d\.]{7,})", _strip(s))
            if m:
                sal_min = float(m.group(1).replace(".", ""))
                moneda = "COP"
        org = (jp.get("hiringOrganization") or {}).get("name") if jp else None
        out.append({
            "fuente": "elempleo", "id": f["url"].rsplit("-", 1)[-1],
            "titulo": f["titulo"], "empresa": org, "url": f["url"],
            "remoto": bool(re.search(r"remoto|teletrabajo|home office", texto, re.I)),
            "ubicacion": "Colombia",
            "sal_min": float(sal_min) if sal_min else None,
            "sal_max": float(sal_max) if sal_max else None,
            "moneda": moneda, "periodo": "mes",
            "texto": texto, "publicado": jp.get("datePosted") if jp else None,
        })
        time.sleep(0.4)
    return out


# --------------------------------------------------------------- Computrabajo
CT_BUSQUEDAS = ["desarrollador", "ingeniero-de-sistemas", "soporte-tecnico",
                "programador", "devops"]


def computrabajo(paginas=4, max_detalle=80):
    fichas, vistos = [], set()
    for termino in CT_BUSQUEDAS:
        for p in range(1, paginas + 1):
            try:
                s = _get(f"https://co.computrabajo.com/trabajo-de-{termino}?p={p}", timeout=30)
            except Exception as e:
                print("  [computrabajo]", termino, p, "ERR", e)
                break
            arts = re.findall(r"<article[^>]*data-id='([^']+)'[^>]*>(.*?)</article>", s, re.S)
            if not arts:
                break
            for oid, blk in arts:
                if oid in vistos:
                    continue
                vistos.add(oid)
                href = re.search(r'href="(/ofertas-de-trabajo/[^"]+)"', blk)
                tit = re.search(r'<h2[^>]*>\s*<a[^>]*>(.*?)</a>', blk, re.S)
                remoto = bool(re.search(r"remoto|teletrabajo|h[ií]brido|home office", blk, re.I))
                if href and remoto:
                    fichas.append({
                        "id": oid,
                        "url": "https://co.computrabajo.com" + href.group(1),
                        "titulo": _strip(tit.group(1)).strip() if tit else None,
                    })
            time.sleep(0.5)

    out = []
    for f in fichas[:max_detalle]:
        try:
            s = _get(f["url"], timeout=30)
        except Exception:
            continue
        jp = job_posting(s)
        desc = _strip(jp.get("description")) if jp else _strip(s)[:6000]
        titulo = f["titulo"] or (jp.get("title") if jp else None)
        sal_min = sal_max = None
        if jp:
            bs = ((jp.get("baseSalary") or {}).get("value")) or {}
            sal_min = bs.get("minValue") or bs.get("value")
            sal_max = bs.get("maxValue")
        if not sal_min:
            m = re.search(r"\$\s?([\d\.]{7,})", desc)
            if m:
                sal_min = float(m.group(1).replace(".", ""))
        org = (jp.get("hiringOrganization") or {}).get("name") if jp else None
        out.append({
            "fuente": "computrabajo", "id": f["id"], "titulo": titulo,
            "empresa": org, "url": f["url"], "remoto": True, "ubicacion": "Colombia",
            "sal_min": float(sal_min) if sal_min else None,
            "sal_max": float(sal_max) if sal_max else None,
            "moneda": "COP", "periodo": "mes",
            "texto": (titulo or "") + " " + desc,
            "publicado": jp.get("datePosted") if jp else None,
        })
        time.sleep(0.4)
    return out
