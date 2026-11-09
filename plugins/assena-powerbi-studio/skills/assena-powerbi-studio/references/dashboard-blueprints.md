# Blueprints de dashboard por dominio

Cada dominio: paleta sugerida, KPIs de la fila superior y paginas. Usalos como
punto de partida y adapta a las columnas reales del modelo.

## Estructura universal de pagina (1280×720)
```
┌──────────────────────── Encabezado (titulo + subtitulo) ───────────────────────┐
│ [Segmentador] [Segmentador] [Segmentador] [Segmentador]          (alto 60)      │
│ [ KPI 1 ]     [ KPI 2 ]     [ KPI 3 ]     [ KPI 4 ]               (alto 96)      │
│ [ Tendencia temporal (span 8) ]          [ Composicion (span 4) ]               │
│ [ Ranking / barras (span 6) ]            [ Ranking / barras (span 6) ]          │
└─────────────────────────────────────────────────────────────────────────────────┘
```
Lectura en Z: lo mas importante arriba-izquierda. Max 4 KPIs, max 12 visuales.

## Ventas / comercial — `atardecer` o `corporativo`
- KPIs: Ventas, Var % AA, Margen %, Clientes Activos (o Ticket Promedio).
- Pag 1 Resumen: tendencia mensual Ventas vs AA (line), ventas por canal (donut),
  por categoria (bar desc), top 10 clientes (bar desc).
- Pag 2 Clientes y productos: matriz Categoria>Producto con Ventas/Margen/Var %,
  scatter Ventas vs Margen % por producto, Pareto de clientes.
- Pag 3 Vendedores/zonas: ranking vendedores, cumplimiento vs meta (gauge o bar
  con meta), ventas por ciudad (bar).

## Compras / proveedores — `oceano`
- KPIs: Compras, N° ordenes, Proveedores activos, Lead time promedio.
- Paginas: tendencia de compras, top proveedores, compras por categoria,
  matriz proveedor × mes, cumplimiento de entregas.

## Inventario / logistica — `oceano`
- KPIs: Valor inventario, Dias de inventario, Rotacion, Lotes por vencer.
- Paginas: inventario por bodega (bar), por categoria (treemap), vencimientos por
  mes (column), tabla de lotes criticos ordenada por fecha de vencimiento.

## Finanzas — `esmeralda`
- KPIs: Ingresos, Gastos, Utilidad, Margen neto %.
- Paginas: cascada Ingresos→Costos→Gastos→Utilidad (waterfall), real vs
  presupuesto por cuenta (matriz + combo), cartera por antiguedad (stackedBar),
  DSO tendencia (line).

## Salud / laboratorio — `clinico`
- KPIs: Ordenes/pruebas, Pacientes, Tiempo de respuesta (TAT), % a tiempo.
- Paginas: volumen por dia/hora (column), por area/seccion (bar), TAT por prueba
  (bar), matriz medico/institucion × mes, tendencia de ingresos.

## RRHH / asistencia — `grafito` o `corporativo`
- KPIs: Headcount, Rotacion %, Ausentismo %, Horas extra.
- Paginas: headcount por area (bar), altas/bajas por mes (combo), ausentismo por
  dia de semana (column), tabla de empleados con mas atrasos.

## Proyectos / presupuesto — `corporativo`
- KPIs: Presupuesto, Ejecutado, % Ejecucion, Desviacion.
- Paginas: ejecucion por proyecto (bar con meta), curva S acumulada (line), matriz
  proyecto × rubro, estado de proyectos (donut).

## Soporte / TI — `medianoche`
- KPIs: Tickets abiertos, Tiempo medio de resolucion, % SLA, Satisfaccion.
- Paginas: tickets por estado/prioridad (stackedColumn), tendencia diaria,
  ranking tecnicos, categorias (treemap).
