# Changelog — ASSENA Power BI Studio

## 0.5.1 — 2026-11-09
- Corregido: `colorMeasure` en graficos `bar`/`column` no coloreaba cada barra. El `dataPoint` ahora incluye el selector `dataViewWildcard` (matchingOption 1) que Power BI exige para el formato condicional por punto. Verificado en Power BI Desktop.

## 0.5.0 — 2026-11-09
- **Encabezado de alto impacto**: banda de 80 px con degradado (color de encabezado ->
  azul de marca), resplandor y ondas, linea de acento inferior; renderizada como fondo
  de pagina PNG (`backgrounds.page_png`) en version clara y oscura. Texto con eyebrow
  (nombre del tablero), titulo y subtitulo.
- **Botones rectangulares con borde definido** (1 px, esquinas de 2 px) en navegacion,
  indice de portada y selector de tema; el borde se ilumina en azul al pasar el mouse.
- **KPIs**: franja de acento superior, numeros 26 pt; radios de tarjetas 6 px (look mas recto).
- Imagenes gestionadas (`Portada_*`, `Fondo_*`) se limpian y regeneran en cada apply.

## 0.4.0 — 2026-11-09
- **Selector de tema claro/oscuro**: cada pagina se genera en ambas versiones (oscuras
  ocultas) y un boton ☀/☾ salta a la pagina equivalente. Variante oscura derivada de la
  paleta + serie validada para fondo oscuro; overrides de color por visual (`modes.py`).
- **Portada rediseñada** (vuelve al estilo oscuro, mejorado): barra de marca, selector
  Claro/Oscuro, titulo bicolor, indice de contenido navegable, panel de cristal con KPIs y
  tendencia mensual, ondas en azul de marca, haz de luz y textura de puntos.
- **Barra de navegacion propia** en el encabezado (Inicio + paginas, actual resaltada).
- Calendario: columna `Mes Inicio` (fecha) para ejes temporales continuos sin scroll.
- Textos: tokens de color (`@title`, `@muted`, `@accent`) y parrafos con varios estilos (`runs`).
- Se retira la portada clara de 0.3.0.

## 0.3.0 — 2026-11-09
- **Nuevas paletas profesionales** (reemplazan las de marca ASSENA): corporativo, grafito,
  esmeralda, atardecer, oceano, clinico y medianoche. Validadas numericamente: separacion
  bajo daltonismo, vision normal, banda de luminosidad, croma y contraste >= 3:1; orden
  optimizado entre 40.320 permutaciones.
- **Portada rediseñada**: fondo generativo (degradado + resplandores + anillos), dos
  columnas, boton primario + botones cristal, KPIs tipo cristal, fecha de actualizacion.
- Imagenes registradas como recurso del informe (`register_image`); fondo de pagina con imagen.
- Tarjetas: opciones `labelColor`, `labelSize`, `categoryColor`, `bgTransparency`, `borderColor`, `radius`.
- Tema renombrado a `Tema_<paleta>.json`.

## 0.2.0 — 2026-11-09
- **Portada / intro** con marca, titulo, descripcion, botones de navegacion a cada pagina y KPIs.
- **Navegacion**: navegador de paginas en el encabezado de cada pagina + boton "limpiar filtros".
- **Tooltips personalizados**: pagina tooltip oculta (4 KPIs) asignada automaticamente a los graficos.
- **Resumen Ejecutivo IA**: nueva pagina con narrativa de valores dinamicos (`{[Medida]}`) y
  hallazgos/recomendaciones calculados con datos reales (`assena_bi.py insights`).
- Medidas de narrativa: lider por categoria, % del lider, mejor mes.
- **Formato condicional**: `colorMeasure` en tarjetas y barras (variacion % verde/rojo).
- Nuevos tipos de visual: `button`, `navigator`; `text` con `paragraphs` enriquecidos.
- Validador: verifica destinos de botones, paginas tooltip y textos dinamicos.
- Correcciones: sin barras de desplazamiento en textos (padding 0), encabezado mas compacto.
- Formatos JSON capturados de Power BI Desktop 2.159 y verificados abriendo el demo.

## 0.1.0 — 2026-11-09
- Primera version.
- CLI `assena_bi.py`: `inspect`, `profile`, `draft`, `apply`, `validate`, `palettes`.
- Lectura/escritura de modelos TMDL y TMSL (model.bim); deteccion de origen M
  (SQL Server, PostgreSQL, MySQL, Oracle, ODBC, Snowflake, Excel, CSV, SharePoint, Web).
- Perfilado solo-lectura: SQL Server (pyodbc), PostgreSQL, MySQL, SQLite y CSV.
- Borrador automatico de spec: tabla de hechos, medidas (totales, AA, Var %, margen, ticket), calendario, 2 paginas.
- Generador PBIR con grilla de 12 columnas, encabezado de marca, 22 tipos de visual.
- 7 paletas profesionales y tema JSON completo.
- Respaldo automatico, idempotencia y validador (campos, posiciones, superposiciones, JSON).
- Probado en Power BI Desktop 2.159 (noviembre 2026) con el proyecto demo.
