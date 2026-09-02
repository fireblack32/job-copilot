# -*- coding: utf-8 -*-
"""
Tablero de vacantes: todas las candidatas viables, con su enlace, en un archivo.

El copiloto postula, pero se le acaban los turnos, o la sesion se corta, o
simplemente la persona quiere avanzar sin esperar. Cuando eso pasa hoy, el
trabajo del barrido se pierde: doscientas vacantes filtradas quedan dentro de un
JSON que nadie va a leer.

Este tablero es la salida de emergencia. Es un HTML suelto, sin servidor y sin
red, con **todas** las candidatas y un enlace directo a cada una. La persona
postula a mano las que quiera, marca lo que hizo, y copia la lista de vuelta.

    barrido ──> ranking.json ──> tablero.html ──> la persona postula sola
                                       │
                                       └──> copia las URLs ──> bitacora.json
                                                                    │
                            el proximo tablero ya no las ofrece <───┘

El circuito se cierra en `bitacora.py`, y cerrarlo es el punto: sin la vuelta,
el copiloto volveria a recomendar lo que la persona ya postulo, que es
exactamente el error que hace que un asistente deje de ser util.

Uso:

    python -m copiloto.tablero                     # lee resultados/ranking.json
    python -m copiloto.tablero --min-pts 20 --salida tablero.html
"""

from __future__ import annotations

import html
import io
import json
import os

from copiloto.bitacora import Bitacora, separar

# Se reutiliza el mismo lenguaje visual del formulario a proposito: la persona ve
# las dos paginas en la misma tarde y deberian sentirse una sola herramienta.
from copiloto.formulario import _ESTILO as _BASE

_ESTILO = _BASE + """
.barra{position:sticky;top:0;z-index:5;background:var(--ground);
padding:.9rem 0;border-bottom:1px solid var(--line);margin-bottom:1.5rem;
display:flex;gap:.6rem;flex-wrap:wrap;align-items:center}
.barra input[type=search]{flex:1 1 14rem;font:inherit;font-size:.95rem;
padding:.5rem .7rem;background:var(--surface);color:var(--ink);
border:1px solid var(--line);border-radius:4px}
.filtro{font-family:"Archivo",Helvetica,Arial,sans-serif;font-size:.85rem;
font-weight:600;padding:.45rem .8rem;border-radius:4px;cursor:pointer;
background:transparent;color:var(--accent);border:1px solid var(--line)}
.filtro[aria-pressed="true"]{background:var(--accent);color:#fff;border-color:var(--accent)}
.cuenta{font-family:ui-monospace,Consolas,monospace;font-size:.8rem;color:var(--muted)}
.fila{background:var(--surface);border:1px solid var(--line);border-radius:5px;
padding:.85rem 1rem;margin-bottom:.5rem;display:flex;gap:.9rem;align-items:flex-start}
.fila[hidden],.grupo[hidden]{display:none}
.fila.marcada{opacity:.5}
.fila.marcada .cargo{text-decoration:line-through}
.fila.cerrada{border-left:3px solid var(--ok);opacity:.55}
.fila input[type=checkbox]{margin-top:.35rem;width:1.05rem;height:1.05rem;flex:none}
.fila .datos{flex:1 1 auto;min-width:0}
.cargo{font-family:"Archivo",Helvetica,Arial,sans-serif;font-weight:600;
font-size:1.02rem;line-height:1.3;margin:0 0 .15rem}
.cargo a{color:var(--ink);text-decoration:none;border-bottom:1px solid var(--accent)}
.cargo a:hover{color:var(--accent)}
.empresa{font-size:.92rem;color:var(--ink-soft);margin:0 0 .4rem}
.chips{display:flex;gap:.35rem;flex-wrap:wrap}
.chip{font-family:ui-monospace,Consolas,monospace;font-size:.7rem;
letter-spacing:.03em;text-transform:uppercase;color:var(--muted);
background:var(--surface-alt);border-radius:3px;padding:.2rem .45rem}
.chip.plata{color:var(--ok);background:var(--ok-bg)}
.chip.sur{color:var(--accent);background:var(--accent-soft)}
.chip.hecho{color:var(--ok);background:var(--ok-bg);text-transform:none}
.pts{font-family:"Archivo",Helvetica,Arial,sans-serif;font-weight:700;
font-size:1.15rem;color:var(--accent);flex:none;width:2.6rem;text-align:right}
.pts small{display:block;font-size:.6rem;font-weight:600;color:var(--muted);
letter-spacing:.08em;text-transform:uppercase}
.grupo{font-family:ui-monospace,Consolas,monospace;font-size:.74rem;
letter-spacing:.12em;text-transform:uppercase;color:var(--accent);
margin:2.25rem 0 .8rem;padding-bottom:.35rem;border-bottom:1px solid var(--line)}
.vacio{color:var(--muted);font-style:italic;padding:2rem 0}
"""

_GUION = """
const CLAVE = 'copiloto-tablero';
let filtro = 'todas';

function marcadas(){
  let d = {};
  try { d = JSON.parse(localStorage.getItem(CLAVE) || '{}'); } catch(e){ d = {}; }
  return d;
}
function guardar(){
  const d = {};
  document.querySelectorAll('.fila input[type=checkbox]').forEach(c=>{
    if (c.checked) d[c.dataset.url] = new Date().toISOString().slice(0,10);
  });
  try { localStorage.setItem(CLAVE, JSON.stringify(d)); } catch(e){}
  pintar();
}
function restaurar(){
  const d = marcadas();
  document.querySelectorAll('.fila input[type=checkbox]').forEach(c=>{
    if (d[c.dataset.url]) c.checked = true;
  });
  pintar();
}
function pintar(){
  const q = (document.getElementById('buscar').value || '').toLowerCase().trim();
  let visibles = 0, hechas = 0;
  document.querySelectorAll('.fila').forEach(f=>{
    const c = f.querySelector('input[type=checkbox]');
    const marcada = c && c.checked;
    f.classList.toggle('marcada', !!marcada && !f.classList.contains('cerrada'));
    if (marcada) hechas++;
    let ok = true;
    if (filtro === 'pendientes') ok = !marcada && !f.classList.contains('cerrada');
    else if (filtro !== 'todas') ok = f.dataset.via === filtro;
    if (ok && q) ok = (f.dataset.buscar || '').indexOf(q) >= 0;
    f.hidden = !ok;
    if (ok) visibles++;
  });
  document.querySelectorAll('.grupo').forEach(g=>{
    let n = 0, el = g.nextElementSibling;
    while (el && !el.classList.contains('grupo')){
      if (el.classList.contains('fila') && !el.hidden) n++;
      el = el.nextElementSibling;
    }
    g.hidden = n === 0;
    g.textContent = g.dataset.titulo + ' · ' + n;
  });
  document.getElementById('cuenta').textContent =
    visibles + ' a la vista · ' + hechas + ' marcadas';
}
function filtrar(btn, valor){
  filtro = valor;
  document.querySelectorAll('.filtro').forEach(b=>b.setAttribute('aria-pressed', b===btn));
  pintar();
}
function copiar(){
  const urls = [...document.querySelectorAll('.fila:not(.cerrada) input[type=checkbox]')]
    .filter(c=>c.checked).map(c=>c.dataset.url);
  const t = document.getElementById('salida');
  t.value = urls.length
    ? 'Postule a mano a estas ' + urls.length + ':\\n' + urls.join('\\n')
    : 'Todavia no marcaste ninguna.';
  t.select();
  try { document.execCommand('copy'); } catch(e){}
  const b = document.getElementById('btn-copiar');
  b.textContent = urls.length ? 'Copiado (' + urls.length + ')' : 'Nada marcado';
  setTimeout(()=>{ b.textContent = 'Copiar lo que postule'; }, 2000);
}
document.addEventListener('change', e=>{ if (e.target.type === 'checkbox') guardar(); });
document.addEventListener('input', e=>{ if (e.target.id === 'buscar') pintar(); });
document.addEventListener('DOMContentLoaded', restaurar);
"""

GRUPOS = [
    ("cali-sur", "Cali · sur — la preferencia declarada"),
    ("cali", "Cali · resto de la ciudad"),
    ("remota", "Remotas"),
]


def _esc(s) -> str:
    return html.escape(str(s or ""), quote=True)


def _grupo_de(v: dict) -> str:
    if v.get("via") == "cali":
        return "cali-sur" if v.get("zona") == "sur" else "cali"
    return "remota"


def _plata(v: dict) -> str | None:
    """Salario en una linea, o None si el aviso no lo dice.

    Se muestra el rango cuando existe: 'desde 4M' y 'de 4M a 9M' llevan a
    decisiones distintas, y el segundo dato se estaba perdiendo.
    """
    lo, hi = v.get("cop_min"), v.get("cop_max")
    if not lo and not hi:
        return None
    def m(n):
        return "%.1fM" % (n / 1_000_000) if n else "?"
    if lo and hi and hi != lo:
        return "$%s a $%s" % (m(lo), m(hi))
    return "$%s" % m(hi or lo)


def _fila(v: dict, cerrada: bool = False) -> str:
    url = str(v.get("url") or "")
    chips = []
    if v.get("modalidad"):
        chips.append('<span class="chip">%s</span>' % _esc(v["modalidad"]))
    if v.get("zona") == "sur":
        chips.append('<span class="chip sur">sur</span>')
    if v.get("ubicacion"):
        chips.append('<span class="chip">%s</span>' % _esc(v["ubicacion"])[:40])
    plata = _plata(v)
    if plata:
        chips.append('<span class="chip plata">%s</span>' % _esc(plata))
    if v.get("fuente"):
        chips.append('<span class="chip">%s</span>' % _esc(v["fuente"]))
    if cerrada:
        chips.append('<span class="chip hecho">%s</span>'
                     % _esc(v.get("cerrada_porque") or "ya postulada"))

    buscar = _esc(" ".join(str(v.get(k) or "") for k in
                           ("titulo", "empresa", "ubicacion", "fuente")).lower())
    return f"""
    <div class="fila{' cerrada' if cerrada else ''}" data-via="{_esc(_grupo_de(v))}"
         data-buscar="{buscar}">
      <input type="checkbox" data-url="{_esc(url)}" {'checked disabled' if cerrada else ''}
             aria-label="Ya postule a esta">
      <div class="datos">
        <p class="cargo"><a href="{_esc(url)}" target="_blank" rel="noopener">{_esc(v.get('titulo') or 'Sin titulo')}</a></p>
        <p class="empresa">{_esc(v.get('empresa') or 'Empresa no declarada')}</p>
        <div class="chips">{''.join(chips)}</div>
      </div>
      <div class="pts">{_esc(v.get('pts', 0))}<small>pts</small></div>
    </div>"""


def render(pendientes: list[dict], cerradas: list[dict] | None = None,
           titulo: str = "Vacantes listas para postular") -> str:
    """Devuelve el HTML completo del tablero."""
    cerradas = cerradas or []
    porgrupo: dict[str, list[str]] = {g: [] for g, _ in GRUPOS}
    for v in pendientes:
        porgrupo[_grupo_de(v)].append(_fila(v))
    for v in cerradas:
        porgrupo[_grupo_de(v)].append(_fila(v, cerrada=True))

    cuerpo = ""
    for gclave, gtitulo in GRUPOS:
        filas = porgrupo.get(gclave) or []
        if not filas:
            continue
        cuerpo += '<p class="grupo" data-titulo="%s">%s · %d</p>%s' % (
            _esc(gtitulo), _esc(gtitulo), len(filas), "".join(filas))
    if not cuerpo:
        cuerpo = '<p class="vacio">No quedan vacantes por postular en este barrido.</p>'

    n_cali = sum(1 for v in pendientes if v.get("via") == "cali")
    en_cali = ", %d en Cali" % n_cali if n_cali else ""
    ya = ("Otras %d aparecen tachadas: ya se enviaron." % len(cerradas)
          if cerradas else "")
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_esc(titulo)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@600;700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap">
<style>{_ESTILO}</style>
</head>
<body>
<div class="env">

<header>
  <p class="eyebrow">Copiloto de postulaciones · AInovaX</p>
  <h1>{_esc(titulo)}</h1>
  <p class="sub">{len(pendientes)} vacantes pasaron los filtros y siguen sin
  postular{en_cali}. Están ordenadas por encaje: postulá de arriba hacia abajo.
  {ya}</p>
</header>

<div class="barra">
  <input type="search" id="buscar" placeholder="Filtrar por cargo, empresa o portal…">
  <button class="filtro" aria-pressed="true" onclick="filtrar(this,'todas')">Todas</button>
  <button class="filtro" aria-pressed="false" onclick="filtrar(this,'pendientes')">Sin marcar</button>
  <button class="filtro" aria-pressed="false" onclick="filtrar(this,'cali-sur')">Cali sur</button>
  <button class="filtro" aria-pressed="false" onclick="filtrar(this,'cali')">Cali</button>
  <button class="filtro" aria-pressed="false" onclick="filtrar(this,'remota')">Remotas</button>
  <span class="cuenta" id="cuenta"></span>
</div>

{cuerpo}

<section>
  <h2>Cuando termines</h2>
  <p class="intro">Copiá la lista y pegámela. Con eso el próximo barrido ya no te
  vuelve a ofrecer lo que postulaste, y el copiloto sigue por las que faltan.</p>
  <div class="acciones-pie">
    <button class="btn" id="btn-copiar" onclick="copiar()">Copiar lo que postulé</button>
  </div>
  <textarea class="salida" id="salida" readonly
    placeholder="Al copiar aparecen aquí las URLs de lo que marcaste."></textarea>
</section>

<footer>
  <p>Lo que marques se guarda solo en este navegador. Nada se envía a ningún
  lado: el tablero abre los enlaces, la postulación la hacés vos.</p>
</footer>

</div>
<script>{_GUION}</script>
</body>
</html>"""


def escribir(ruta: str, pendientes: list[dict], cerradas: list[dict] | None = None,
             titulo: str = "Vacantes listas para postular") -> str:
    with io.open(ruta, "w", encoding="utf-8") as f:
        f.write(render(pendientes, cerradas, titulo))
    return ruta


# ----------------------------------------------------------------------- cli
AQUI = os.path.dirname(os.path.abspath(__file__))
RANKING = os.path.join(AQUI, "..", "resultados", "ranking.json")
BITACORA = os.path.join(AQUI, "..", "resultados", "bitacora.json")


def main(argv=None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="Genera el tablero de vacantes.")
    p.add_argument("--ranking", default=RANKING)
    p.add_argument("--bitacora", default=BITACORA)
    p.add_argument("--salida", default=os.path.join(AQUI, "..", "tablero.html"))
    p.add_argument("--min-pts", type=int, default=0,
                   help="Oculta las que no llegan a este encaje.")
    a = p.parse_args(argv)

    with io.open(a.ranking, encoding="utf-8") as f:
        candidatas = [v for v in json.load(f) if v.get("pts", 0) >= a.min_pts]

    bit = Bitacora(a.bitacora)
    pendientes, cerradas = separar(candidatas, bit)
    ruta = escribir(a.salida, pendientes, cerradas)

    print("tablero  :", os.path.abspath(ruta))
    print("candidatas:", len(candidatas), "| pendientes:", len(pendientes),
          "| ya postuladas:", len(cerradas))
    if len(bit):
        print("bitacora :", bit.resumen())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
