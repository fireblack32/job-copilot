# Probar con otra hoja de vida

Para una segunda persona **no hay que desplegar nada todavía**. Lo que hacía falta
era que el sistema dejara de tener a una persona escrita en el código, y eso ya
está: los pisos salariales, la ciudad, las habilidades que puntúan y los términos
con que se consulta cada portal salen ahora del perfil.

Probar con otro CV son tres pasos y unos veinte minutos, casi todos de armar el
perfil.

---

## 1. Armar el perfil de la persona

Copiá `perfil-ejemplo.json` y llenalo. Es el único archivo que cambia entre una
persona y otra.

Lo que el buscador lee de verdad:

| Campo | Para qué sirve | Si falta |
|---|---|---|
| `criterios_busqueda.piso_salarial_cop_mes` | Piso para vacantes remotas | 2 salarios mínimos |
| `criterios_busqueda.piso_salarial_presencial_cop_mes` | Piso para presencial e híbrido | 15% más que el remoto |
| `criterios_busqueda.modalidad` | Qué modalidades acepta | solo remoto |
| `criterios_busqueda.ciudad_presencial` | Ciudad para vacantes con presencia | no se buscan locales |
| `criterios_busqueda.idioma_vacante` | Filtra avisos en otros idiomas | español |
| `habilidades` | **De aquí sale la puntuación de encaje** | no puntúa nada |
| `perfiles_objetivo[].cargos_objetivo` | Términos con que se consulta cada portal | ninguno |
| `perfiles_objetivo[].prioridad` | Qué pesa más en el orden | todo igual |

El piso presencial es más alto que el remoto a propósito: una vacante que obliga
a ir a una oficina cuesta transporte y un par de horas al día, así que tiene que
pagar más para valer lo mismo.

**Lo que ningún CV responde** —pretensión, disponibilidad, nivel honesto en cada
tecnología— sale del formulario que genera `copiloto/formulario.py`. Ese es el
paso que hoy sigue siendo una conversación, y el que más falta hace automatizar.

## 2. Correr el barrido

```bash
cd buscador
PERFIL_MAESTRO="/ruta/al/perfil-de-la-persona.json" \
  python buscar.py --fuentes computrabajo-cali,elempleo-cali,getonbrd,torre,remotive,jobicy
```

Al arrancar imprime los criterios que dedujo y cuántas habilidades va a puntuar.
**Si esa línea no se parece a la persona, el perfil está incompleto** — es la
comprobación más barata antes de esperar veinte minutos de barrido.

Escribe `resultados/crudo.json` (todo lo recolectado) y `resultados/ranking.json`
(lo que pasó los filtros, ordenado).

## 3. Generar el CV adaptado

```bash
cd generador
PERFIL_MAESTRO="/ruta/al/perfil.json" \
  node cv-gen.js ../vacantes/variante-x.json ../salidas/CV.docx
```

La variante define qué se resalta para esa vacante: titular, orden de las
experiencias, agrupación de habilidades y qué proyectos mostrar.

---

## Qué sigue faltando

Esto sirve para **probar**, no para vender. Lo que falta antes de que lo use
alguien que no seamos nosotros:

**Ingesta del CV.** El perfil hoy se arma a mano. Extraerlo de un PDF es el
trabajo más grande que queda, y el que decide si el producto existe: nadie va a
llenar un JSON de sesenta líneas.

**El cuestionario.** Pretensión, disponibilidad y nivel real por tecnología
siguen saliendo de preguntar. `copiloto/preguntas.py` ya tiene el catálogo; falta
que alguien lo responda sin que haya una conversación de por medio.

**Vigilancia por fuente.** Los adaptadores se rompen callados. En una sola sesión
aparecieron cuatro fallos que no dieron ningún error: el `JobPosting` dentro de
`@graph`, el texto que era CSS, la puntuación por subcadena y la ciudad que
coincidía dentro de "calidad". Todos daban números plausibles. Hace falta una
alarma cuando una fuente devuelve cero o cuando la mediana de puntaje se desploma.

**Lo legal.** Raspar portales y postular automáticamente choca con los términos de
varios de ellos, y guardar hojas de vida de terceros cae bajo la Ley 1581 de 2012.
Para una prueba con una segunda persona que da su consentimiento no hay problema;
para cobrar, sí.

## Dónde desplegarlo, cuando toque

Hoy son scripts de línea de comandos: se corren donde haya Python y Node. Cuando
haya interfaz y varios usuarios, lo que este sistema necesita no es un servidor
web sino **una cola de trabajos**: un barrido tarda veinte minutos y no puede
colgar de una petición HTTP.

La forma más corta de llegar ahí: un contenedor con el buscador como tarea
programada, la base de perfiles aparte, y una interfaz mínima que solo lea
resultados y muestre el formulario de traspaso. `serverless-api-kit` ya tiene la
capa de almacenamiento intercambiable y los manifiestos de Kubernetes para eso.
