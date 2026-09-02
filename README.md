# job-copilot

Buscador de vacantes remotas que recolecta ofertas de nueve portales, las normaliza a un esquema común, las filtra contra un perfil profesional y genera una hoja de vida adaptada a cada vacante.

Nació de un problema concreto: buscar trabajo remoto en español desde Colombia significa revisar a mano media docena de portales que no comparten formato, publican salarios en cuatro monedas distintas y mezclan avisos en inglés con avisos en español. Este proyecto automatiza el barrido y el filtrado, pero **deja la postulación en manos de la persona** — por diseño, no por limitación.

## Qué hace

```
9 portales  →  1.381 vacantes  →  deduplicación  →  filtros  →  277 candidatas  →  CV adaptado
```

Números de un barrido real (agosto de 2026):

| Etapa | Resultado |
|---|---|
| Recolectadas | 1.381 |
| Únicas tras deduplicar | 1.366 |
| Descartadas por no ser remotas | 554 |
| Descartadas por exigir inglés avanzado | 251 |
| Descartadas por geografía incompatible | 5 |
| Descartadas por salario bajo el piso | 5 |
| Descartadas por bajo encaje con el perfil | 265 |
| **Candidatas finales** | **277** |

## Arquitectura

```
buscador/
  fuentes.py      un adaptador por portal → esquema unificado
  fuentes_co.py   adaptadores hispanohablantes (requieren segunda pasada al detalle)
  buscar.py       pipeline: recolectar → deduplicar → normalizar → filtrar → puntuar
generador/
  cv-gen.js       genera el .docx a partir del perfil + una "variante" por vacante
```

### Adaptadores

Cada portal expone sus datos de forma distinta. El adaptador traduce todos al mismo diccionario:

```python
{
  "fuente", "id", "titulo", "empresa", "url", "remoto", "ubicacion",
  "sal_min", "sal_max", "moneda", "periodo", "texto", "publicado"
}
```

Portales soportados: **Get on Board**, **Torre**, **Computrabajo**, **elempleo**, **Remotive**, **Jobicy**, **Himalayas**, **RemoteOK** y **Arbeitnow**. Agregar uno nuevo es escribir una función que devuelva ese diccionario y registrarla en `ADAPTADORES`.

Cinco de ellos exponen API JSON. Los otros publican JSON-LD `JobPosting` incrustado en el HTML del listado, que es más fiable de parsear que el marcado visual porque no cambia con cada rediseño.

## Decisiones de diseño que vale la pena mirar

**Normalización de moneda con tasas en vivo.** La primera versión asumía dólares cuando el portal no declaraba moneda. Torre publica ofertas en rupias indias y pesos mexicanos: una vacante de 10.000.000 INR/año apareció como si pagara 2.600 millones de pesos colombianos al mes. Ahora las tasas se traen al arrancar, una moneda desconocida devuelve `None` en lugar de adivinar, y hay cotas de sanidad que descartan cualquier valor fuera de una banda razonable.

```python
def a_cop_mes(sal, moneda, periodo):
    m = (moneda or "").upper().strip()
    if m not in TASAS_COP:
        return None          # moneda desconocida: no adivinar
    cop = float(sal) * TASAS_COP[m]
    ...
    return cop if COP_MES_MIN < cop < COP_MES_MAX else None
```

**Detección de idioma en dos niveles.** Primero busca requisitos explícitos ("inglés B2", "fluent English"). Después compara densidad de marcadores léxicos: un aviso con muchas más palabras funcionales inglesas que españolas implica un proceso en inglés aunque no lo diga. El segundo nivel es necesario porque los portales rara vez declaran el idioma del proceso.

**Deduplicación por dos claves.** Por `(fuente, id)` y por `(título, empresa)` normalizados sin tildes. La segunda atrapa la misma vacante republicada en varios portales.

**El texto corto degrada el filtrado.** Torre expone unos 300 caracteres por oferta frente a los varios miles de Get on Board. Con tan poco texto la detección de idioma pierde precisión y se cuelan avisos en inglés. Está documentado como limitación conocida en lugar de disimulado.

## Generación de la hoja de vida

El generador separa **los hechos** de **su presentación**:

- `perfil-maestro.json` — la verdad: experiencias, fechas, logros, tecnologías.
- `variante-<vacante>.json` — cómo presentarla para una vacante concreta: titular, resumen, orden de experiencias, viñetas reformuladas, bloques de habilidades priorizados.

Una variante **reordena y reformula**, nunca inventa. Si una tecnología no está en el perfil maestro, no puede aparecer en el documento generado. Es una restricción deliberada: un CV que exagera se cae en la entrevista técnica.

El `.docx` resultante está pensado para pasar filtros ATS: una sola columna, sin tablas ni cajas de texto ni gráficos, encabezados estándar, fechas en formato uniforme.

## Uso

```bash
pip install pypdf
cd generador && npm install docx
```

```bash
# barrido completo
python buscador/buscar.py

# solo algunas fuentes
python buscador/buscar.py --fuentes getonbrd,torre --min-pts 20

# generar un CV adaptado
node generador/cv-gen.js vacantes/variante-ejemplo.json salidas/cv.docx

# tablero con todas las candidatas y su enlace
python -m copiloto.tablero --min-pts 14

# anotar lo que se postulo a mano (pegado tal cual del tablero)
python -m copiloto.registrar < pegado.txt
```

### El tablero y la bitácora

`ranking.json` sirve para automatizar; no sirve para que una persona postule. El
tablero lo convierte en un HTML suelto con **todas** las candidatas, su enlace
directo y una casilla por vacante. Se abre sin servidor y sin red.

Cuando la persona postula por su cuenta, marca lo que hizo y copia la lista. Ese
pegado entra por `copiloto.registrar` y queda en `bitacora.json`, que es la
memoria de qué se tocó ya. El siguiente barrido no vuelve a ofrecerlo.

    barrido ──> ranking.json ──> tablero.html ──> la persona postula sola
                                       │
                                       └──> copia las URLs ──> bitacora.json
                                                                    │
                            el proximo tablero ya no las ofrece <───┘

Una vacante se reconoce por `fuente + id` y también por `empresa + cargo`
normalizados. La segunda hace falta porque los portales reciclan ids y republican
el mismo puesto: sin ella se le manda dos veces la misma hoja de vida a la misma
empresa, que es más caro que perder una vacante.

El perfil se toma de `perfil-maestro.json` en la raíz, o de la ruta que indique la variable de entorno `PERFIL_MAESTRO`. Hay un `perfil-ejemplo.json` para arrancar.

## Sobre automatizar la postulación

El proyecto **no envía postulaciones**. Es una decisión, no una funcionalidad pendiente:

- LinkedIn, Indeed y Computrabajo prohíben el acceso automatizado en sus términos de servicio. La sanción típica es la restricción permanente de la cuenta — justo la cuenta que necesitas para conseguir empleo.
- Las postulaciones masivas automáticas tienen tasa de respuesta pésima y queman empresas que solo se pueden tocar una vez.
- Los formularios reales traen CAPTCHAs y preguntas de filtro que requieren criterio humano.

Lo que sí hace es dejar todo listo: vacante analizada, brechas identificadas, CV adaptado y preguntas preparadas. El clic de enviar lo da la persona.

Solo se usan APIs públicas y páginas de listado públicas.

## Stack

Python 3.12 (biblioteca estándar, sin dependencias externas en el buscador) · Node.js con `docx` para la generación de documentos · LibreOffice para la conversión a PDF.

## Licencia

MIT
