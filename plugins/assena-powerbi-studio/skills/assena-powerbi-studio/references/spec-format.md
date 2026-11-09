# Formato de la spec (spec.json)

La spec describe **que** construir; `apply` se encarga de **como** (posiciones,
JSON PBIR, TMDL). Referencias de campo: `Tabla[Columna]`, `'Tabla con espacios'[Col]`
o `[Medida]` (las medidas se buscan en todo el modelo).

```jsonc
{
  "title": "Dashboard Comercial",
  "subtitle": "Fuente: ERP · actualizacion diaria",      // subtitulo por defecto de paginas
  "palette": "corporativo",                          // ver: assena_bi.py palettes
  "paletteOverrides": { "header": "#2F52A0", "accent": "#25D366" },  // opcional (marca cliente)
  "canvas": { "width": 1280, "height": 720, "headerHeight": 68 },
  "schemaVersions": { "visualContainer": "2.0.0", "page": "2.0.0" },  // opcional
  "model": {
    "calendar": {                       // opcional: crea tabla de fechas DAX (Año, Trimestre, Mes, Año Mes, Dia Semana…)
      "name": "Calendario",
      "rangeFrom": "Ventas[Fecha]",     // años completos entre min y max; omitir = CALENDARAUTO
      "relateTo": ["Ventas[Fecha]"]     // crea relacion Ventas[Fecha] -> Calendario[Fecha]
    },
    "relationships": [ { "from": "Ventas[IdVendedor]", "to": "Vendedores[Id]", "active": true } ],
    "measures": [
      { "table": "Ventas", "name": "Ventas Netas", "expression": "SUM ( Ventas[Monto] )",
        "formatString": "\\$#,0", "displayFolder": "KPIs", "description": "Suma de ventas sin IVA" }
    ]
  },
  "pages": [
    {
      "name": "Resumen Ejecutivo",          // nombre de la pestaña
      "title": "Resumen Comercial 2026",    // texto del encabezado (default = name)
      "subtitle": "KPIs y tendencias",
      "header": true,                       // banda superior de color
      "height": 720,                        // >720 = pagina con scroll vertical
      "rows": [
        { "height": 60, "visuals": [ { "type": "slicer", "field": "Calendario[Año]", "title": "Año", "span": 3 } ] },
        { "height": 96, "visuals": [ { "type": "card", "values": "[Ventas Netas]", "span": 3 } ] },
        { "weight": 1,  "visuals": [ { "type": "line", "title": "…", "category": "Calendario[Año Mes]", "values": ["[Ventas Netas]"], "span": 8 } ] }
      ]
    }
  ]
}
```

## Experiencia de presentacion (v0.2)
```jsonc
"cover": {                                   // portada / intro (pagina inicial)
  "title": "Dashboard Comercial", "subtitle": "Tablero interactivo de ventas",
  "description": "Texto corto de bienvenida…",
  "brand": "ASSENA · BUSINESS INTELLIGENCE", "footer": "Fuente: ERP · actualizado diario",
  "kpis": ["[Ventas]", "[Var % AA]", "[Margen %]"],   // hasta 4 tarjetas
  "eyebrow": "Tablero ejecutivo · Ventas",
  "trend": {"category": "Calendario[Mes Inicio]", "values": "[Ventas]"},   // mini tendencia del panel
  "brandColors": {"accent": "#0066FF"},      // opcional, sobrescribe assets/brand.json
  "enabled": true
},
"navigation": true,
"themeToggle": true,                         // genera paginas claras + oscuras con boton ☀/☾                          // navegador de paginas en el encabezado + boton limpiar filtros
"tooltips": { "measures": ["[Ventas]", "[Var % AA]", "[Transacciones]", "[Margen %]"],
              "width": 320, "height": 240 }   // pagina tooltip oculta, se asigna a todos los graficos
```
- Por visual: `"tooltip": false` lo excluye del tooltip; `"navigation": false` en una
  pagina quita el navegador.
- Formato condicional: `"colorMeasure": "[Color Var %]"` en `card` (color del numero)
  o `bar`/`column` (color de barras). La medida devuelve un hex, p. ej.
  `IF ( [Var %] >= 0, "#1F9D55", "#D64545" )`.

### Texto enriquecido y narrativa dinamica (`type: "text"`)
```jsonc
{ "type": "text", "span": 6, "paragraphs": [
  { "text": "Resumen ejecutivo", "size": 14, "bold": true, "color": "#0B2545" },
  "Las ventas suman {[Ventas]} con {[Transacciones]} transacciones.",       // string simple
  { "text": "Variacion vs año anterior: {[Var % AA]}", "bullet": true, "size": 11 },
  { "text": "Lider: {[Lider Categoria]}", "valueColor": "#2BB673" }
]}
```
`{[Medida]}` o `{Tabla[Columna]}` se convierte en un **valor dinamico** que Power BI
recalcula con los filtros (mismo mecanismo que la narrativa personalizada).

### Botones
`{"type": "button", "text": "Ver detalle →", "target": "<id de pagina>"}` —
`action`: `PageNavigation` (default), `clearSlicers`, `back`; `icon`: `rightArrow`,
`leftArrow`, `back`, `reset`, `clearAllSlicers`, `information`, `help`.
Ids de pagina: `assena00portada`, `assena01<slug>`, `assena02<slug>`…
`{"type": "navigator"}` inserta un navegador de paginas.

## Layout
- Grilla de **12 columnas**, margen 16 px, separacion 12 px.
- Cada fila: `height` fija (px) o `weight` (reparte el alto sobrante). Si los
  `span` de una fila suman menos de 12, se escalan para llenar el ancho.
- Alturas tipicas: segmentadores 56–60, KPIs 90–110, graficos el resto.

## Tipos de visual y claves
| type | Visual Power BI | Claves |
|---|---|---|
| `card` | Tarjeta | `values` (1 medida), `label` |
| `multicard` | Tarjeta de varias filas | `values` [] |
| `kpi` | KPI | `values`, `trend` (fecha), `target` |
| `gauge` | Medidor | `values`, `target`, `min`, `max` |
| `column` / `bar` | Columnas / barras agrupadas | `category`, `values` [], `series`, `sort`, `labels` |
| `stackedColumn` / `stackedBar` / `column100` | Apiladas / 100 % | idem |
| `line` / `area` | Lineas / areas | `category` (fecha), `values` [], `series` |
| `combo` | Columnas + linea | `category`, `columns` [], `lines` [] |
| `donut` / `pie` | Anillo / circular (≤ 6 categorias) | `category`, `values` |
| `treemap` | Mapa de arbol | `category`, `values` |
| `funnel` | Embudo | `category`, `values` |
| `waterfall` | Cascada | `category`, `values` |
| `scatter` | Dispersion | `details`, `x`, `y`, `size`, `series` |
| `table` | Tabla | `values` [] (columnas y medidas) |
| `matrix` | Matriz | `rows` [], `columns` [], `values` [] |
| `slicer` | Segmentador | `field`, `mode` (`Dropdown`, `Basic`, `Between` para fechas/numeros) |
| `text` | Cuadro de texto | `text`, `fontSize`, `bold`, `color`, `align` |
| `map` / `filledMap` | Mapas Bing (**obsoletos**, evitar) | `location`, `size` / `values` |

Comunes a todos: `title`, `subtitle`, `span`, `color` (color fijo de datos),
`background` (fondo propio, quita borde/sombra), `altText` (accesibilidad),
`sort` (`desc`/`asc`), `sortBy` (campo para ordenar; por defecto el primer valor).
