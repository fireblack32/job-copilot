/**
 * Generador de CV adaptado por vacante.
 *
 * Uso:  node cv-gen.js <variante.json> <salida.docx>
 *
 * Lee el perfil maestro (perfil-maestro.json) y una "variante" que define
 * como adaptar ese perfil a una vacante concreta: titular, resumen, orden de
 * experiencias, viñetas reescritas y bloques de habilidades priorizados.
 *
 * Nada de esto inventa datos: la variante solo reordena, prioriza y reformula
 * hechos que ya existen en el perfil maestro.
 */
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, AlignmentType,
  BorderStyle, LevelFormat, convertInchesToTwip, ExternalHyperlink,
} = require("docx");

const FONT = "Calibri";
const ACCENT = "1F3864";

// ---------------------------------------------------------------- primitivas
const P = {
  nombre: (t) => new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { after: 40 },
    children: [new TextRun({ text: t, bold: true, size: 40, font: FONT })],
  }),
  titular: (t) => new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { after: 60 },
    children: [new TextRun({ text: t, size: 22, font: FONT, color: ACCENT, bold: true })],
  }),
  centro: (children) => new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { after: 120 }, children,
  }),
  seccion: (t) => new Paragraph({
    spacing: { before: 240, after: 100 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 8, space: 2, color: ACCENT } },
    children: [new TextRun({ text: t.toUpperCase(), bold: true, size: 24, font: FONT, color: ACCENT })],
  }),
  parrafo: (t) => new Paragraph({
    alignment: AlignmentType.JUSTIFIED, spacing: { after: 100, line: 264 },
    children: [new TextRun({ text: t, size: 21, font: FONT })],
  }),
  cargo: (cargo, empresa) => new Paragraph({
    spacing: { before: 160, after: 0 },
    children: [
      new TextRun({ text: cargo, bold: true, size: 22, font: FONT }),
      new TextRun({ text: " | " + empresa, size: 22, font: FONT }),
    ],
  }),
  meta: (t) => new Paragraph({
    spacing: { after: 60 },
    children: [new TextRun({ text: t, size: 19, font: FONT, color: "595959", italics: true })],
  }),
  vineta: (t) => new Paragraph({
    numbering: { reference: "vinetas", level: 0 }, spacing: { after: 40, line: 264 },
    children: [new TextRun({ text: t, size: 21, font: FONT })],
  }),
  skill: (cat, items) => new Paragraph({
    spacing: { after: 60, line: 264 },
    children: [
      new TextRun({ text: cat + ": ", bold: true, size: 21, font: FONT }),
      new TextRun({ text: items, size: 21, font: FONT }),
    ],
  }),
};

const MESES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
               "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];

function periodo(exp) {
  const fmt = (ym) => {
    if (!ym) return "Actualidad";
    const [y, m] = ym.split("-");
    return `${MESES[parseInt(m, 10)]} ${y}`;
  };
  return `${fmt(exp.inicio)} – ${exp.actual ? "Actualidad" : fmt(exp.fin)}`;
}

/** Quita el esquema y la barra final para que el enlace se lea corto. */
const acortar = (url) => url.replace(/^https?:\/\/(www\.)?/, "").replace(/\/$/, "");

const separador = () => new TextRun({ text: "  |  ", size: 20, font: FONT, color: "595959" });

const enlace = (url) => new ExternalHyperlink({
  link: url,
  children: [new TextRun({ text: acortar(url), size: 20, font: FONT, color: "0563C1", underline: {} })],
});

/**
 * Segunda linea del encabezado: LinkedIn, GitHub, portafolio y disponibilidad.
 *
 * Los enlaces que el perfil no define simplemente no aparecen — un CV con un
 * campo vacio o un placeholder se ve peor que uno sin ese campo.
 */
function enlacesDeContacto(p, v) {
  const partes = [];
  for (const url of [p.linkedin, p.github, p.portafolio]) {
    if (!url) continue;
    if (partes.length) partes.push(separador());
    partes.push(enlace(url));
  }
  if (partes.length) partes.push(separador());
  partes.push(new TextRun({
    text: v.disponibilidad || "Disponibilidad: trabajo 100% remoto",
    size: 20, font: FONT,
  }));
  return partes;
}

// ------------------------------------------------------------------ ensamble
function construir(perfil, v) {
  const p = perfil.personal;
  const expPorId = Object.fromEntries(perfil.experiencia.map((e) => [e.id, e]));
  const orden = v.orden_experiencia || perfil.experiencia.map((e) => e.id);

  const hijos = [
    P.nombre(p.nombre_completo),
    P.titular(v.titular),
    P.centro([
      new TextRun({ text: `${p.ciudad}, ${p.departamento}, ${p.pais}`, size: 20, font: FONT }),
      new TextRun({ text: "  |  ", size: 20, font: FONT, color: "595959" }),
      new TextRun({ text: p.telefono, size: 20, font: FONT }),
      new TextRun({ text: "  |  ", size: 20, font: FONT, color: "595959" }),
      new TextRun({ text: p.email, size: 20, font: FONT }),
    ]),
    P.centro(enlacesDeContacto(p, v)),
    P.seccion("Perfil profesional"),
    ...v.perfil.map(P.parrafo),
  ];

  // Los proyectos publicos van antes que la experiencia: son lo unico que el
  // reclutador puede verificar por su cuenta antes de llamarte.
  if (v.proyectos?.length) {
    hijos.push(P.seccion("Proyectos publicos"));
    for (const pr of v.proyectos) {
      hijos.push(new Paragraph({
        spacing: { before: 140, after: 0 },
        children: [
          new TextRun({ text: pr.nombre, bold: true, size: 22, font: FONT }),
          new TextRun({ text: "  ", size: 22, font: FONT }),
          enlace(pr.url),
        ],
      }));
      hijos.push(P.meta(pr.stack));
      for (const b of pr.puntos) hijos.push(P.vineta(b));
    }
  }

  hijos.push(P.seccion("Experiencia profesional"));

  for (const id of orden) {
    const e = expPorId[id];
    if (!e) throw new Error("Experiencia desconocida en la variante: " + id);
    const ov = (v.experiencia_override || {})[id] || {};
    hijos.push(P.cargo(ov.cargo || e.cargo, e.empresa));
    hijos.push(P.meta(`${periodo(e)}  ·  ${e.modalidad}`));
    for (const b of (ov.logros || e.logros)) hijos.push(P.vineta(b));
  }

  hijos.push(P.seccion("Habilidades técnicas"));
  for (const [cat, items] of v.habilidades) hijos.push(P.skill(cat, items));

  hijos.push(P.seccion("Educación"));
  for (const ed of perfil.educacion) {
    hijos.push(P.cargo(ed.titulo, ed.institucion));
    hijos.push(P.meta(`Graduado en ${ed.anio_grado}  ·  ${ed.ciudad}, ${perfil.personal.pais}`));
  }

  hijos.push(P.seccion("Certificaciones"));
  for (const c of perfil.certificaciones) hijos.push(P.vineta(`${c.nombre} — ${c.entidad}, ${c.anio}.`));

  hijos.push(P.seccion("Idiomas"));
  for (const i of perfil.idiomas) hijos.push(P.skill(i.idioma, i.nivel === "B1" ? "B1 — intermedio (lectura técnica de documentación)" : i.nivel));

  // "Referencias disponibles a solicitud" no aporta informacion: se asume, y
  // ocupa una linea que puede ser la que empuja el CV a una pagina de mas.
  // Solo se incluye si la variante lo pide expresamente.
  if (v.incluir_referencias) {
    hijos.push(P.seccion("Referencias"));
    hijos.push(P.parrafo("Referencias laborales y personales disponibles a solicitud."));
  }

  return new Document({
    creator: p.nombre_completo,
    title: `CV - ${p.nombre_completo} - ${v.titular}`,
    description: v.vacante ? `Adaptado para: ${v.vacante}` : "Hoja de vida optimizada para ATS",
    numbering: {
      config: [{
        reference: "vinetas",
        levels: [{
          level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: convertInchesToTwip(0.25), hanging: convertInchesToTwip(0.17) } } },
        }],
      }],
    },
    styles: { default: { document: { run: { font: FONT, size: 21 } } } },
    sections: [{
      properties: { page: { margin: { top: 720, right: 1000, bottom: 720, left: 1000 } } },
      children: hijos,
    }],
  });
}

// ---------------------------------------------------------------------- main
const [, , variantePath, salida] = process.argv;
if (!variantePath || !salida) {
  console.error("uso: node cv-gen.js <variante.json> <salida.docx>");
  process.exit(1);
}
const PERFIL = process.env.PERFIL_MAESTRO || path.join(__dirname, "..", "perfil-maestro.json");
const perfil = JSON.parse(fs.readFileSync(PERFIL, "utf8"));
const variante = JSON.parse(fs.readFileSync(variantePath, "utf8"));

Packer.toBuffer(construir(perfil, variante)).then((buf) => {
  fs.mkdirSync(path.dirname(salida), { recursive: true });
  fs.writeFileSync(salida, buf);
  console.log("OK ->", salida, buf.length, "bytes");
});
