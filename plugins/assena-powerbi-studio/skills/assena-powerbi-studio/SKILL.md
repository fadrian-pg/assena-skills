---
name: assena-powerbi-studio
description: >
  Crea dashboards profesionales e interactivos de Power BI de forma automatica a
  partir de un archivo "en blanco" ya conectado a una base de datos. Analiza el
  modelo (tablas, columnas, relaciones, origen SQL/CSV), perfila los datos, genera
  medidas DAX, tabla calendario, tema de colores corporativo y paginas de informe
  (KPIs, tendencias, rankings, matrices, segmentadores) en formato PBIP/PBIR listo
  para abrir en Power BI Desktop. Usar cuando el usuario diga "dashboard de Power
  BI", "informe Power BI", "pbix", "pbip", "crear reporte en Power BI", "tablero",
  "analiza mi modelo de Power BI", "medidas DAX", "tema de Power BI", o invoque
  /assena-powerbi-studio.
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash(python *)
  - Bash(python3 *)
---

# ASSENA Power BI Studio

Convierte un proyecto de Power BI en blanco (solo con datos cargados) en un
dashboard ejecutivo completo: modelo enriquecido + tema + paginas + validacion.

`SCRIPTS = <carpeta de este skill>/scripts` — todos los comandos usan
`python "$SCRIPTS/assena_bi.py" <comando>` (Python 3.8+, solo libreria estandar).

## Principios

1. **Nunca edites un .pbix**: es binario. Trabaja siempre sobre **PBIP** (carpeta
   `.Report` + `.SemanticModel` en texto). Si el usuario entrega un .pbix, guialo
   con `references/pbip-setup.md` (Archivo > Guardar como > .pbip, formato PBIR).
2. **Power BI Desktop cerrado** mientras se escriben archivos; despues se abre el
   `.pbip` y se pulsa *Actualizar*. El script crea un respaldo zip en
   `.assena_backups/` antes de cada cambio.
3. **Medidas explicitas siempre** (nunca agregaciones implicitas en visuales).
4. **Credenciales**: nunca en el chat ni en la linea de comandos. SQL Server con
   `--trusted` (Windows) o contraseña en variable de entorno (`--password-env`).
   El perfilado es de solo lectura y con muestra limitada.
5. **Pregunta solo lo indispensable**: objetivo del dashboard / audiencia y la
   paleta si el usuario tiene marca propia. Lo demas, decide con buen criterio.

## Flujo de trabajo

### Paso 1 — Recibir y verificar el proyecto
- Localiza el `.pbip` (o la carpeta). Si es `.pbix`/`.pbit` → detente y explica la
  conversion (references/pbip-setup.md).
- `python "$SCRIPTS/assena_bi.py" inspect <ruta.pbip> --out <tmp>/model.json`
- Comprueba `report.format == "PBIR"`. Si es `PBIR-Legacy`, pide activar PBIR y
  volver a guardar.

### Paso 2 — Entender los datos
- Lee `model.json`: tablas con `roleGuess` (fact/dimension), tipos, relaciones,
  origen (`source.kind`, servidor, BD, objeto o consulta nativa).
- Perfila si hay acceso (recomendado, mejora mucho el resultado):
  - CSV local: `assena_bi.py profile <pbip> --out <tmp>/profile.json`
  - SQL Server: `... profile <pbip> --trusted --out ...` (servidor/BD se detectan del M)
  - PostgreSQL/MySQL: `... profile <pbip> --user U --password-env PGPASS --out ...`
  - Faltan drivers → `pip install pyodbc | psycopg2-binary | pymysql`.
  - Sin acceso → continua solo con el modelo; dilo en el resumen.
- Del perfil extrae: rango de fechas (¿hay hora en la fecha? → avisa, la relacion
  con Calendario requiere fecha sin hora), cardinalidades (categorias 2–30 son
  ideales para graficos), columnas con nulos, negativos (devoluciones), outliers.
- Identifica el **dominio** (ventas, compras, inventario, finanzas, RRHH, salud,
  operaciones…) y consulta `references/dashboard-blueprints.md`.

### Paso 3 — Borrador automatico + hallazgos IA
```
assena_bi.py draft    <pbip> --profile <tmp>/profile.json --out <tmp>/spec0.json
assena_bi.py insights <pbip> --spec <tmp>/spec0.json --out <tmp>/insights.json      # datos reales
assena_bi.py draft    <pbip> --profile <tmp>/profile.json --insights <tmp>/insights.json \
                      --palette <paleta> --title "<Titulo>" --out <tmp>/spec.json
```
(`insights` usa los mismos parametros de conexion que `profile` si el origen es SQL.)

El borrador genera una experiencia completa:
- **Portada** de alto impacto: marca, titulo bicolor, indice de contenido navegable,
  panel de KPIs con tendencia y selector **Claro/Oscuro**.
- **Modo claro/oscuro**: cada pagina se genera en ambas versiones; boton ☀/☾ en el encabezado.
- **Informe Ejecutivo IA**: narrativa con valores **dinamicos** (`{[Medida]}` se
  recalcula con los filtros) + hallazgos y recomendaciones redactados desde
  `insights.json`, mas tendencia y ranking de apoyo.
- **Panorama General** y **Analisis Detallado** (KPIs, tendencia, composicion,
  rankings, combo vs año anterior, matriz).
- **Navegacion**: barra de botones en el encabezado (Inicio + paginas) + "limpiar filtros".
- **Tooltips**: pagina tooltip oculta con 4 KPIs asignada a todos los graficos.
- **Formato condicional**: variacion % en verde/rojo via medida de color.
- Medidas: totales, transacciones, ticket, AA, Var %, margen, color, narrativa
  (lider por categoria, % lider, mejor mes) y tabla Calendario.
`_notes` explica lo que detecto.

### Paso 4 — Revisar y mejorar la spec (aqui aportas el criterio)
Edita `spec.json` siguiendo `references/spec-format.md`:
- Nombres de medidas en lenguaje de negocio ("Ventas Netas", no "Total Monto Venta").
- Formatos correctos (`\$#,0`, `#,0`, `0.0%`) y carpetas (`KPIs`, `Tiempo`, `Ratios`).
- Añade medidas del dominio con `references/dax-patterns.md` (YTD, MoM, ranking,
  % participacion, rotacion, cumplimiento vs meta…). DAX con `DIVIDE`, `VAR`.
- Paginas segun el blueprint: 1) Resumen ejecutivo, 2) Analisis/desglose,
  3) Detalle operativo (opcional). Max ~12 visuales por pagina.
- Diseño: `references/design-system.md` (grilla 12 col, 4 KPIs arriba, tendencia a
  la izquierda, composicion a la derecha, rankings ordenados desc, sin 3D, sin
  pies con >6 porciones, titulos que dicen *que* muestra el grafico).
- Paleta: `assena_bi.py palettes` lista las disponibles; `paletteOverrides` para
  colores de marca del cliente.
- **Resumen Ejecutivo IA (tu aporte mas visible)**: lee `insights.json` y reescribe
  los parrafos de "Hallazgos y recomendaciones (IA)" como un analista senior:
  3–5 hallazgos con cifras concretas (crecimiento comparable, estacionalidad,
  concentracion, margenes, anomalias) y 2–3 recomendaciones accionables. Usa
  `{[Medida]}` donde convenga que el dato se actualice solo. No inventes cifras:
  todo numero estatico debe salir de `insights.json`. Mantén la linea final con
  la fecha y "datos hasta…". Ajusta tambien titulo/descripcion de la portada.

### Paso 5 — Aplicar
`assena_bi.py apply <pbip> --spec <tmp>/spec.json`
Hace: respaldo → calendario + relaciones + medidas (TMDL/TMSL) → tema → paginas
→ validacion. Es idempotente: re-ejecutar reemplaza las paginas `assena*` y omite
medidas existentes. Paginas del usuario con visuales se conservan
(`--replace-all` las elimina).
Si hay errores de validacion, corrige la spec y repite.

### Paso 6 — Entregar
- Indica al usuario: abrir el `.pbip` → **Actualizar** (Inicio > Actualizar >
  Esquema y datos si se creo el Calendario) → revisar.
- Si hay herramienta de control de escritorio y Power BI Desktop instalado, puedes
  abrir el `.pbip`, actualizar y tomar captura para verificar.
- Recuerda: la portada es la pagina inicial; en Desktop los botones usan Ctrl+clic.
- Escribe `ASSENA_BI_RESUMEN.md` junto al `.pbip`: hallazgos de los datos, medidas
  creadas (nombre, formula, para que sirve), paginas y como usarlas, supuestos y
  siguientes pasos (RLS, publicacion, actualizacion programada, metas reales).

## Problemas frecuentes
| Sintoma | Causa / solucion |
|---|---|
| "No se puede abrir el informe / esquema" | Version de esquema: añade `"schemaVersions": {"visualContainer": "x.y.z"}` copiando la de un visual creado a mano (references/pbir-visuals.md). |
| Visual con error de campo | Nombre de tabla/columna distinto; `validate` lo detecta. |
| Calendario vacio o relacion sin coincidencias | La fecha de la tabla de hechos tiene hora → crea columna de solo fecha en Power Query. |
| Tarjetas "(En blanco)" | Falta actualizar datos en Desktop. |
| Mapa Bing obsoleto | No usar `map`/`filledMap`; preferir barras por zona o Azure Maps manual. |
| Montos como `$3637,452` en Desktop | Configuracion regional de Windows (agrupacion de digitos). El formato `\$#,0` es el mismo que genera Power BI; en el Servicio se ve bien. Revisa Archivo > Opciones > Configuracion regional. |
| Botones no navegan en Desktop | En modo edicion se usa **Ctrl + clic**; publicado funciona con clic normal. |
| "Culture … may be changed only before…" | Nunca cambies `culture` de un modelo existente; el skill no la toca. |

## Archivos de referencia
- `references/pbip-setup.md` — convertir .pbix → .pbip (PBIR) paso a paso.
- `references/spec-format.md` — formato completo de la spec y tipos de visual.
- `references/dax-patterns.md` — biblioteca de medidas DAX por dominio.
- `references/dashboard-blueprints.md` — paginas recomendadas por dominio.
- `references/design-system.md` — reglas de diseño, grilla, paletas.
- `references/pbir-visuals.md` — estructura PBIR/TMDL para depurar o extender.
- `assets/examples/make_demo_pbip.py` — genera un proyecto demo para pruebas.
