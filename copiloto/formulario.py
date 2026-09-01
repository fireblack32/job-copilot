# -*- coding: utf-8 -*-
"""
Genera el formulario que llena la persona.

Dos cosas en una pagina, porque a la persona le llegan juntas:

1. **Lo que tiene que ir a autorizar** — cada accion con su motivo y un enlace
   directo al sitio exacto donde se hace. Sin el enlace la lista es un reproche;
   con el enlace es una tarea de dos clics.
2. **Lo que solo ella sabe** — pretension, disponibilidad, nivel real en una
   tecnologia. Sin esto el copiloto tendria que suponer, y suponer aqui significa
   afirmar cosas que quiza no son ciertas.

La pagina se guarda sola en el navegador mientras se llena, y al final entrega un
JSON para pegar en el perfil. Es deliberadamente un archivo suelto: no hay
servidor todavia, y hacer que dependa de uno seria inventar infraestructura antes
de saber si el formulario sirve.
"""

from __future__ import annotations

import html
import json

from copiloto.handoff import Accion, Estado
from copiloto.preguntas import Cuestionario, Pregunta

_ESTILO = """
:root{--ground:#F5F6FA;--surface:#fff;--surface-alt:#EDEFF6;--ink:#16192B;
--ink-soft:#3B4059;--muted:#5A5F78;--line:#D8DCE9;--accent:#3D46C4;
--accent-soft:#E6E8F8;--alerta:#B33A3A;--alerta-bg:#F7E4E4;--ok:#1F7A5C;--ok-bg:#E2F1EB}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
--ground:#101321;--surface:#171B2C;--surface-alt:#1F2438;--ink:#E9EBF4;
--ink-soft:#C3C7DA;--muted:#949AB5;--line:#2C3248;--accent:#939BF0;
--accent-soft:#23284A;--alerta:#E2756F;--alerta-bg:#3B2020;--ok:#5FC49E;--ok-bg:#16352C}}
*{box-sizing:border-box}
body{background:var(--ground);color:var(--ink);margin:0;padding:0 1.25rem 5rem;
font-family:"Source Serif 4",Georgia,serif;font-size:17px;line-height:1.6}
.env{max-width:56rem;margin:0 auto}
header{padding:3.5rem 0 1.75rem;border-bottom:2px solid var(--ink);margin-bottom:2.5rem}
.eyebrow{font-family:ui-monospace,Consolas,monospace;font-size:.72rem;letter-spacing:.14em;
text-transform:uppercase;color:var(--accent);margin:0 0 .9rem}
h1{font-family:"Archivo",Helvetica,Arial,sans-serif;font-weight:700;
font-size:clamp(1.9rem,5vw,2.9rem);line-height:1.06;letter-spacing:-.02em;
text-wrap:balance;margin:0 0 .9rem}
h2{font-family:"Archivo",Helvetica,Arial,sans-serif;font-weight:600;
font-size:1.5rem;letter-spacing:-.012em;margin:0 0 .4rem}
h3{font-family:"Archivo",Helvetica,Arial,sans-serif;font-weight:600;
font-size:1.02rem;margin:0 0 .3rem}
p{max-width:64ch;margin:0 0 1rem}
.sub{color:var(--ink-soft);font-size:1.1rem}
section{margin-bottom:3.25rem}
.intro{color:var(--muted);margin-bottom:1.5rem}
.tarea{background:var(--surface);border:1px solid var(--line);
border-left:3px solid var(--alerta);border-radius:5px;padding:1.15rem 1.3rem;
margin-bottom:.85rem;display:flex;gap:1rem;align-items:flex-start;flex-wrap:wrap}
.tarea.hecha{border-left-color:var(--ok);opacity:.6}
.tarea .cuerpo{flex:1 1 22rem;min-width:0}
.tarea .motivo{font-size:.94rem;color:var(--muted);margin:0 0 .5rem}
.tarea .vacante{font-family:ui-monospace,Consolas,monospace;font-size:.74rem;
letter-spacing:.05em;text-transform:uppercase;color:var(--accent);margin:0 0 .35rem}
.instruccion{font-size:.94rem;color:var(--ink-soft);margin:0}
.btn{display:inline-block;background:var(--accent);color:#fff;text-decoration:none;
font-family:"Archivo",Helvetica,Arial,sans-serif;font-weight:600;font-size:.88rem;
padding:.55rem 1rem;border-radius:4px;border:0;cursor:pointer;white-space:nowrap}
.btn.fantasma{background:transparent;color:var(--accent);border:1px solid var(--accent)}
.btn:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
.marca{display:flex;align-items:center;gap:.45rem;font-size:.9rem;color:var(--muted);
cursor:pointer;user-select:none}
.campo{background:var(--surface);border:1px solid var(--line);border-radius:5px;
padding:1.15rem 1.3rem;margin-bottom:.85rem}
.campo label{display:block;font-family:"Archivo",Helvetica,Arial,sans-serif;
font-weight:600;font-size:1.02rem;margin-bottom:.3rem}
.campo .ayuda{font-size:.92rem;color:var(--muted);margin:0 0 .75rem;max-width:64ch}
.campo input[type=text],.campo input[type=number],.campo select{
width:100%;max-width:32rem;font:inherit;font-size:.98rem;padding:.55rem .7rem;
background:var(--ground);color:var(--ink);border:1px solid var(--line);border-radius:4px}
.campo input:focus,.campo select:focus{outline:2px solid var(--accent);outline-offset:1px}
.req{color:var(--alerta);font-size:.8rem;margin-left:.3rem}
.aviso{background:var(--alerta-bg);color:var(--alerta);border-radius:5px;
padding:1rem 1.2rem;margin-bottom:1.5rem;font-size:.96rem}
.aviso p{max-width:none;margin:0}
.salida{width:100%;min-height:9rem;font-family:ui-monospace,Consolas,monospace;
font-size:.82rem;padding:.8rem;background:var(--surface-alt);color:var(--ink);
border:1px solid var(--line);border-radius:4px;margin-top:1rem}
footer{border-top:1px solid var(--line);padding-top:1.25rem;margin-top:3rem;
font-size:.88rem;color:var(--muted)}
.acciones-pie{display:flex;gap:.7rem;flex-wrap:wrap;margin-top:1.25rem}
"""

_GUION = """
const CLAVE = 'copiloto-formulario';
function estado(){
  const d = {};
  document.querySelectorAll('[data-clave]').forEach(el=>{
    d[el.dataset.clave] = el.type === 'checkbox' ? el.checked : el.value;
  });
  return d;
}
function guardar(){
  try { localStorage.setItem(CLAVE, JSON.stringify(estado())); } catch(e){}
  pintar();
}
function restaurar(){
  let d = {};
  try { d = JSON.parse(localStorage.getItem(CLAVE) || '{}'); } catch(e){ d = {}; }
  document.querySelectorAll('[data-clave]').forEach(el=>{
    const v = d[el.dataset.clave];
    if (v === undefined) return;
    if (el.type === 'checkbox') el.checked = !!v; else el.value = v;
  });
  pintar();
}
function pintar(){
  document.querySelectorAll('.tarea').forEach(t=>{
    const c = t.querySelector('input[type=checkbox]');
    if (c) t.classList.toggle('hecha', c.checked);
  });
  const faltan = [...document.querySelectorAll('[data-requerida="1"]')]
    .filter(el => !String(el.value || '').trim()).length;
  const bloq = [...document.querySelectorAll('.tarea[data-bloquea="1"] input[type=checkbox]')]
    .filter(c => !c.checked).length;
  const av = document.getElementById('aviso');
  if (bloq || faltan){
    av.style.display = 'block';
    const partes = [];
    if (bloq) partes.push(bloq + (bloq===1?' autorización pendiente':' autorizaciones pendientes'));
    if (faltan) partes.push(faltan + (faltan===1?' respuesta sin llenar':' respuestas sin llenar'));
    av.querySelector('p').textContent = 'Falta: ' + partes.join(' y ') + '. Hasta entonces no se envía ninguna postulación.';
  } else {
    av.style.display = 'none';
  }
}
function copiar(){
  const t = document.getElementById('salida');
  t.value = JSON.stringify(estado(), null, 2);
  t.select();
  try { document.execCommand('copy'); } catch(e){}
  const b = document.getElementById('btn-copiar');
  b.textContent = 'Copiado';
  setTimeout(()=>{ b.textContent = 'Copiar respuestas'; }, 1800);
}
document.addEventListener('input', guardar);
document.addEventListener('change', guardar);
document.addEventListener('DOMContentLoaded', restaurar);
"""


def _esc(s) -> str:
    return html.escape(str(s or ""), quote=True)


def _tarea(a: Accion) -> str:
    t = a.tipo
    boton = ""
    if a.enlace:
        boton = ('<a class="btn" target="_blank" rel="noopener" href="%s">Ir a hacerlo</a>'
                 % _esc(a.enlace))
    vac = '<p class="vacante">%s</p>' % _esc(a.vacante) if a.vacante else ""
    det = '<p class="instruccion">%s</p>' % _esc(a.detalle) if a.detalle else ""
    marcado = "checked" if a.estado is Estado.LISTA else ""
    return f"""
    <div class="tarea" data-bloquea="{1 if t.bloquea_envio else 0}">
      <div class="cuerpo">
        {vac}
        <h3>{_esc(t.titulo)}</h3>
        <p class="motivo">{_esc(t.motivo)}</p>
        <p class="instruccion">{_esc(t.instruccion)}</p>
        {det}
        <label class="marca">
          <input type="checkbox" data-clave="hecho_{_esc(t.clave)}_{abs(hash(a.vacante)) % 9999}" {marcado}>
          Ya lo hice
        </label>
      </div>
      {boton}
    </div>"""


def _campo(p: Pregunta) -> str:
    req = '<span class="req">obligatorio</span>' if p.requerida else ""
    marca = '1' if p.requerida else '0'
    if p.tipo == "opcion":
        ops = "".join('<option value="%s">%s</option>' % (_esc(o), _esc(o))
                      for o in p.opciones)
        control = ('<select data-clave="%s" data-requerida="%s">'
                   '<option value="">Elegir…</option>%s</select>'
                   % (_esc(p.clave), marca, ops))
    elif p.tipo == "numero":
        control = ('<input type="number" data-clave="%s" data-requerida="%s" min="0">'
                   % (_esc(p.clave), marca))
    else:
        control = ('<input type="text" data-clave="%s" data-requerida="%s">'
                   % (_esc(p.clave), marca))
    ayuda = '<p class="ayuda">%s</p>' % _esc(p.ayuda) if p.ayuda else ""
    return f"""
    <div class="campo">
      <label>{_esc(p.texto)}{req}</label>
      {ayuda}
      {control}
    </div>"""


def render(acciones: list[Accion], cuestionario: Cuestionario,
           titulo: str = "Lo que necesitamos de vos") -> str:
    """Devuelve el HTML completo del formulario."""
    humanas = [a for a in acciones if a.es_de_la_persona]
    tareas = "".join(_tarea(a) for a in humanas) or (
        '<p class="intro">Nada pendiente por ahora.</p>')
    campos = "".join(_campo(p) for p in cuestionario.preguntas)

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
  <p class="sub">El copiloto busca, adapta la hoja de vida, redacta y deja todo
  listo. Lo que aparece aquí es lo que no debe hacer por vos: autorizar cuentas,
  aceptar términos, resolver CAPTCHAs y enviar. Y lo que no puede saber sin
  preguntarte.</p>
</header>

<div class="aviso" id="aviso"><p></p></div>

<section>
  <h2>Autorizaciones y pasos que te tocan</h2>
  <p class="intro">Cada uno dice por qué no lo hacemos nosotros. El botón te lleva
  al sitio exacto.</p>
  {tareas}
</section>

<section>
  <h2>Lo que solo vos sabés</h2>
  <p class="intro">Sin estas respuestas habría que suponer, y suponer aquí
  significa afirmar cosas en tu nombre que quizá no son ciertas.</p>
  {campos}

  <div class="acciones-pie">
    <button class="btn" id="btn-copiar" onclick="copiar()">Copiar respuestas</button>
    <button class="btn fantasma" onclick="document.getElementById('salida').value=JSON.stringify(estado(),null,2)">Ver JSON</button>
  </div>
  <textarea class="salida" id="salida" readonly
    placeholder="Al copiar, las respuestas aparecen aquí en JSON para pegarlas en el perfil."></textarea>
</section>

<footer>
  <p>Lo que escribas se guarda solo en este navegador mientras llenás el
  formulario. No se envía a ningún lado hasta que copies el JSON y lo entregues.</p>
</footer>

</div>
<script>{_GUION}</script>
</body>
</html>"""


def escribir(ruta: str, acciones: list[Accion], cuestionario: Cuestionario,
             titulo: str = "Lo que necesitamos de vos") -> str:
    import io
    with io.open(ruta, "w", encoding="utf-8") as f:
        f.write(render(acciones, cuestionario, titulo))
    return ruta
