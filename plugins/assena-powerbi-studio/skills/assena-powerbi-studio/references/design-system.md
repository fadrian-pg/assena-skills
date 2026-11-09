# Sistema de diseño ASSENA para Power BI

## Lienzo y grilla
- Pagina 1280×720 (16:9), *Ajustar a pagina*. Paginas largas: alto 1100–1400 con scroll.
- Grilla 12 columnas · margen 16 px · separacion 12 px (la aplica `apply`).
- Encabezado de dos niveles: banda de 72 px en degradado (encabezado de la paleta ->
  azul de marca) con ondas y linea de acento (eyebrow 8 pt, titulo 16 pt, subtitulo 9 pt,
  controles a la derecha) + barra de pestañas de 38 px a todo el ancho, una pestaña por
  pagina con anchos iguales; la actual con subrayado de acento. Escala a 8+ paginas.
- Fondo de pagina `background` (gris muy claro) y tarjetas `surface` blancas con
  borde suave, radio 6 px y sombra sutil; KPIs con franja de acento superior de 4 px.
- Botones: rectangulares, borde de 1 px, esquinas de 2 px; activo relleno de acento.

## Jerarquia
1. KPIs (fila superior, max 4): un numero grande + etiqueta. Nada de graficos aqui.
2. Tendencia temporal (izquierda, ancho 8/12).
3. Composicion (derecha, 4/12): donut ≤ 6 categorias o barras.
4. Rankings y detalle (abajo).

## Reglas de graficos
- Barras horizontales para categorias con nombres largos; columnas para tiempo.
- Ordena rankings de mayor a menor (`"sort": "desc"`).
- Lineas para tendencia (meses/dias); nunca pie para series de tiempo.
- Una sola serie → un solo color (sin leyenda). Varias series → leyenda arriba.
- Etiquetas de datos en barras/columnas; ejes sin titulo (el titulo del visual basta).
- Sin 3D, sin degradados, sin mas de 7 colores en un visual.
- Titulos descriptivos: "Ventas mensuales vs año anterior", no "Grafico 1".
- Matrices: maximo 2 niveles de filas y 4–5 medidas.
- Texto alternativo (`altText`) en cada visual para accesibilidad.

## Paletas (assets/palettes.json)
Paletas neutrales y profesionales (sin colores de marca propios), **validadas
numericamente**, no elegidas a ojo:

| Prueba | Criterio |
|---|---|
| Daltonismo (protanopia/deuteranopia, Machado 2009) | dE OKLab x100 entre colores vecinos >= 8 (objetivo) |
| Vision normal | dE entre vecinos >= 15 |
| Luminosidad / croma | OKLCH L 0.43-0.77 (claro), C >= 0.10 (no se ven grises) |
| Contraste | cada color >= 3:1 sobre la tarjeta; textos y estados >= 4.5:1 |
| Orden | se probaron las 40.320 permutaciones; se eligio la de mayor separacion |

| id | Uso | Encabezado | Color 1 | dE daltonismo | dE normal |
|---|---|---|---|---|---|
| `corporativo` (default) | Ejecutivo / general | #0B1F3A | #1F5FBF | 13.7 | 21.2 |
| `grafito` | Consultoria, tecnologia | #111827 | #4F46E5 | 9.4 | 16.6 |
| `esmeralda` | Finanzas, presupuesto | #0B2B26 | #047857 | 10.2 | 16.7 |
| `atardecer` | Ventas, marketing, retail | #1C1917 | #C2410C | 13.7 | 18.8 |
| `oceano` | Logistica, inventario, TI | #082F49 | #0369A1 | 13.5 | 19.8 |
| `clinico` | Salud, laboratorio | #0B3B3F | #0D9488 | 14.1 | 20.3 |
| `medianoche` | Modo oscuro, pantallas | #020617 | #3B82F6 | 14.1 | 16.2 |

Reglas de uso del color:
- **Una sola serie = un solo color** (slot 1). No colorear barras por categoria.
- Series multiples: colores en el **orden fijo** de la paleta, nunca al azar.
- Mas de 8 series -> agrupar en "Otros" o usar matriz/tabla.
- Verde/ambar/rojo (`good/neutral/bad`) reservados para estados y semaforos.
- Escala secuencial (`min -> max`) de un solo tono para mapas de calor.

## Portada
Fondo generativo oscuro (`scripts/backgrounds.py`): degradado del encabezado de la
paleta, resplandor y ondas concentricas en el **azul de marca** (`assets/brand.json`,
ASSENA `#0066FF`), haz de luz diagonal y textura de puntos.
Composicion:
- Barra superior: marca (■ ASSENA | BUSINESS INTELLIGENCE) + selector **Claro / Oscuro**.
- Izquierda: eyebrow, titulo 40pt **bicolor** (ultima palabra en azul de marca),
  subtitulo, descripcion e **indice de contenido** (botones 01, 02, 03… a cada pagina).
- Derecha: panel de cristal con 3 KPIs y **tendencia mensual** (mini area sin ejes).
- Pie: linea fina, credito y fecha de actualizacion.
Opciones: `cover.brandColors`, `cover.eyebrow`, `cover.trend`, `cover.background: "none"`.

## Modo claro / oscuro
Power BI no cambia de tema en tiempo de ejecucion; el skill genera cada pagina dos
veces (clara visible + oscura oculta) y un boton ☀/☾ en el encabezado salta a la
pagina equivalente. La variante oscura se deriva de la paleta (`modes.dark_palette`)
y usa la serie validada para superficie oscura (`medianoche`). La navegacion es una
barra de botones propia (Inicio + paginas, la actual resaltada) que respeta el tema.
`"themeToggle": false` en la spec lo desactiva.

## Marca del cliente
En la spec: `"paletteOverrides": {"header": "#2F52A0", "accent": "#F5A623",
"dataColors": ["#2F52A0", "#F5A623", ...]}`. Verifica contraste del texto blanco
sobre `header` (≥ 4.5:1).

## Para agregar una paleta nueva
Añade una entrada en `assets/palettes.json` con las mismas claves (mode, header,
headerText, headerSubtext, background, surface, border, text, textMuted, accent,
accent2, dataColors[8], good, neutral, bad, min, center, max).
