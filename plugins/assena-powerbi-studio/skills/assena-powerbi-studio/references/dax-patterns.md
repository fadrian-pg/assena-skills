# Biblioteca de patrones DAX (ASSENA)

Convenciones: medidas en la tabla de hechos, nombres de negocio en español,
`DIVIDE` para divisiones, `VAR` para legibilidad, carpetas `KPIs`, `Tiempo`,
`Ratios`, `Ranking`. `Cal` = tabla calendario (`Calendario[Fecha]`).
Formatos: moneda `\$#,0` o `\$#,0.00`; enteros `#,0`; porcentaje `0.0%`;
variacion con signo `+0.0%;-0.0%;0.0%`.

## Base
```dax
Ventas            = SUM ( Ventas[Monto] )
Cantidad          = SUM ( Ventas[Cantidad] )
Transacciones     = COUNTROWS ( Ventas )
Clientes Activos  = DISTINCTCOUNT ( Ventas[IdCliente] )
Ticket Promedio   = DIVIDE ( [Ventas], [Transacciones] )
Precio Promedio   = DIVIDE ( [Ventas], [Cantidad] )
```

## Inteligencia de tiempo (requiere Calendario marcado como tabla de fechas)
```dax
Ventas AA         = CALCULATE ( [Ventas], SAMEPERIODLASTYEAR ( Calendario[Fecha] ) )
Var % AA          = VAR _a = [Ventas] VAR _b = [Ventas AA]
                    RETURN IF ( NOT ISBLANK ( _b ), DIVIDE ( _a - _b, _b ) )
Ventas YTD        = TOTALYTD ( [Ventas], Calendario[Fecha] )
Ventas YTD AA     = CALCULATE ( [Ventas YTD], SAMEPERIODLASTYEAR ( Calendario[Fecha] ) )
Ventas Mes Ant    = CALCULATE ( [Ventas], DATEADD ( Calendario[Fecha], -1, MONTH ) )
Var % MoM         = DIVIDE ( [Ventas] - [Ventas Mes Ant], [Ventas Mes Ant] )
Ventas Movil 3M   = CALCULATE ( [Ventas], DATESINPERIOD ( Calendario[Fecha], MAX ( Calendario[Fecha] ), -3, MONTH ) )
```
Para que "AA" no compare un año parcial con uno completo, limita a fechas con datos:
```dax
Ventas AA (comparable) =
VAR _ultima = CALCULATE ( MAX ( Ventas[Fecha] ), ALL ( Ventas ) )
RETURN CALCULATE ( [Ventas AA], KEEPFILTERS ( Calendario[Fecha] <= _ultima ) )
```

## Rentabilidad
```dax
Costo      = SUM ( Ventas[Costo] )
Margen     = [Ventas] - [Costo]
Margen %   = DIVIDE ( [Margen], [Ventas] )
Markup %   = DIVIDE ( [Margen], [Costo] )
```

## Participacion y ranking
```dax
% Participacion  = DIVIDE ( [Ventas], CALCULATE ( [Ventas], ALLSELECTED ( Productos[Categoria] ) ) )
Ranking Cliente  = IF ( HASONEVALUE ( Clientes[Cliente] ), RANKX ( ALLSELECTED ( Clientes[Cliente] ), [Ventas] ) )
Ventas Top 10    = VAR _top = TOPN ( 10, ALLSELECTED ( Clientes[Cliente] ), [Ventas] )
                   RETURN CALCULATE ( [Ventas], KEEPFILTERS ( _top ) )
% Acumulado (Pareto) =
VAR _v = [Ventas]
VAR _tabla = ADDCOLUMNS ( ALLSELECTED ( Clientes[Cliente] ), "@v", [Ventas] )
RETURN DIVIDE ( SUMX ( FILTER ( _tabla, [@v] >= _v ), [@v] ), SUMX ( _tabla, [@v] ) )
```

## Metas / cumplimiento
```dax
Meta          = SUM ( Metas[Valor] )
Cumplimiento %= DIVIDE ( [Ventas], [Meta] )
Brecha        = [Ventas] - [Meta]
Semaforo      = SWITCH ( TRUE (), [Cumplimiento %] >= 1, "Verde", [Cumplimiento %] >= 0.9, "Amarillo", "Rojo" )
```

## Inventario
```dax
Stock             = SUM ( Inventario[Cantidad] )
Valor Inventario  = SUMX ( Inventario, Inventario[Cantidad] * Inventario[CostoUnitario] )
Rotacion          = DIVIDE ( [Costo], [Valor Inventario] )
Dias Inventario   = DIVIDE ( 365, [Rotacion] )
Lotes por Vencer 90d = CALCULATE ( COUNTROWS ( Lotes ), Lotes[FechaVence] <= TODAY () + 90, Lotes[FechaVence] >= TODAY () )
```

## Cobranza / finanzas
```dax
Cartera           = SUM ( CxC[Saldo] )
Cartera Vencida   = CALCULATE ( [Cartera], CxC[FechaVence] < TODAY () )
% Vencida         = DIVIDE ( [Cartera Vencida], [Cartera] )
DSO               = DIVIDE ( [Cartera], [Ventas] ) * 365
Gasto vs Ppto %   = DIVIDE ( [Gasto Real], [Presupuesto] )
```

## RRHH / operaciones
```dax
Headcount         = DISTINCTCOUNT ( Empleados[IdEmpleado] )
Rotacion Personal = DIVIDE ( [Bajas], AVERAGEX ( VALUES ( Calendario[Año Mes] ), [Headcount] ) )
Ausentismo %      = DIVIDE ( [Horas Ausencia], [Horas Programadas] )
Tiempo Promedio Atencion = AVERAGEX ( Ordenes, DATEDIFF ( Ordenes[Inicio], Ordenes[Fin], MINUTE ) )
OTIF %            = DIVIDE ( CALCULATE ( [Pedidos], Pedidos[ATiempo] = 1, Pedidos[Completo] = 1 ), [Pedidos] )
```

## Buenas practicas
- Evita columnas calculadas si una medida resuelve lo mismo.
- No uses `FILTER ( Tabla, … )` sobre tablas grandes cuando basta un filtro de columna.
- `ALLSELECTED` respeta segmentadores; `ALL` los ignora.
- Toda medida de texto/semaforo debe tener una medida numerica equivalente para graficar.
