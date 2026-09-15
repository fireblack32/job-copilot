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
  // La experiencia va en orden cronologico inverso: es lo que esperan los
  // filtros automaticos, y un salto de 2023 a 2025 se lee como un error de
  // fechas. La variante decide QUE experiencias entran; el orden por
  // relevancia solo se respeta si lo pide con `"orden": "relevancia"`.
  const elegidas = v.orden_experiencia || perfil.experiencia.map((e) => e.id);
  const clave = (id) => {
    const e = expPorId[id];
    if (!e) return "";
    return `${e.actual ? "9999-99" : e.fin}|${e.inicio}`;
  };
  const orden = v.orden === "relevancia"
    ? elegidas
    : [...elegidas].sort((a, b) => clave(b).localeCompare(clave(a)));

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
    hijos.push(P.seccion("Proyectos públicos"));
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

  // `en_cv` deja que el perfil diga el nivel con su matiz ("B2 certificado —
  // lectura y escritura técnica") en vez del codigo a secas. Un "B2" pelado
  // promete un ingles hablado que la entrevista despues no confirma.
  hijos.push(P.seccion("Idiomas"));
  for (const i of perfil.idiomas) {
    const nivel = i.en_cv
      || (i.nivel === "B1" ? "B1 — intermedio (lectura técnica de documentación)" : i.nivel);
    hijos.push(P.skill(i.idioma, nivel));
  }

  // Las referencias salen del perfil, una por linea y con los datos en texto
  // plano: un filtro automatico lee telefono y correo solo si no estan
  // partidos en columnas o tablas. "Disponibles a solicitud" no se escribe
  // nunca: no aporta informacion. La variante puede apagarlas con
  // `"incluir_referencias": false`.
  const refs = perfil.referencias || [];
  if (refs.length && v.incluir_referencias !== false) {
    hijos.push(P.seccion("Referencias"));
    for (const r of refs) {
      hijos.push(new Paragraph({
        spacing: { after: 40, line: 264 },
        children: [
          new TextRun({ text: r.nombre, bold: true, size: 21, font: FONT }),
          new TextRun({ text: ` — ${r.cargo}. Tel: ${r.telefono}. Correo: ${r.email}`, size: 21, font: FONT }),
        ],
      }));
    }
  }

  // Las propiedades del documento tambien se leen: algunos filtros toman el
  // titulo del archivo antes que el cuerpo. Sin `keywords`: LibreOffice las
  // parte por espacios al exportar a PDF y quedan palabras sueltas sin sentido.
  return new Document({
    creator: p.nombre_completo,
    title: `Hoja de vida - ${p.nombre_completo} - ${v.titular.replace(/\s+·\s+/g, ", ")}`,
    subject: v.titular.replace(/\s+·\s+/g, ", "),
    description: v.vacante ? `Adaptado para: ${v.vacante}` : "Hoja de vida",
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
