# PBIR y TMDL: referencia tecnica (para depurar o extender)

## Estructura PBIR
```
X.Report/
  definition.pbir                       datasetReference.byPath -> ../X.SemanticModel
  definition/
    version.json
    report.json                         themeCollection + resourcePackages
    pages/pages.json                    pageOrder, activePageName
    pages/<id>/page.json                displayName, width, height, objects.background
    pages/<id>/visuals/<id>/visual.json
  StaticResources/RegisteredResources/Tema_*.json   tema personalizado
```
Paginas creadas por el skill: id `assena<NN><slug>` (se reemplazan en cada `apply`).

## visual.json minimo
```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.0.0/schema.json",
  "name": "3d26bba4e881d864232e",
  "position": {"x": 16, "y": 260, "z": 9000, "width": 824, "height": 216, "tabOrder": 9000},
  "visual": {
    "visualType": "lineChart",
    "query": {"queryState": {
      "Category": {"projections": [{"field": {"Column": {"Expression": {"SourceRef": {"Entity": "Calendario"}}, "Property": "Año Mes"}},
                                    "queryRef": "Calendario.Año Mes", "nativeQueryRef": "Año Mes", "active": true}]},
      "Y": {"projections": [{"field": {"Measure": {"Expression": {"SourceRef": {"Entity": "Ventas"}}, "Property": "Ventas"}},
                             "queryRef": "Ventas.Ventas", "nativeQueryRef": "Ventas"}]}
    }},
    "visualContainerObjects": {"title": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}},
                                                         "text": {"expr": {"Literal": {"Value": "'Ventas mensuales'"}}}}}]}
  }
}
```
Literales: texto `'...'` (comillas simples, duplicar `''`), numeros `12D`,
booleanos `true`/`false`, colores `{"solid": {"color": {"expr": {"Literal": {"Value": "'#0B2545'"}}}}}`.

## Roles por visualType
| visualType | roles |
|---|---|
| card | Values |
| multiRowCard | Values |
| clusteredColumnChart, clusteredBarChart, columnChart, barChart, lineChart, areaChart | Category, Y, Series |
| lineClusteredColumnComboChart | Category, Y (columnas), Y2 (lineas), Series |
| donutChart, pieChart, funnel, waterfallChart | Category, Y |
| treemap | Group, Values |
| scatterChart | Category, X, Y, Size, Series |
| gauge | Y, MinValue, MaxValue, TargetValue |
| kpi | Indicator, TrendLine, Goal |
| tableEx | Values |
| pivotTable | Rows, Columns, Values |
| slicer | Values |

## Versiones de esquema
`apply` detecta la version de `page.json`/`visual.json` existentes; si el informe
esta vacio usa 2.0.0. Si una version futura de Desktop rechaza el archivo:
crea un visual cualquiera a mano, guarda, mira su `$schema` y ponlo en la spec:
`"schemaVersions": {"visualContainer": "2.x.y", "page": "2.x.y"}`.

## Agregar un tipo de visual nuevo al skill
1. Crea un visual a mano en Desktop, guarda como PBIP y abre su `visual.json`.
2. Copia el `visualType` y los nombres de rol de `queryState`.
3. Añade una entrada en `VISUALS` de `scripts/pbip_report.py`:
   `"miTipo": ("visualTypeReal", {"claveSpec": "Rol", ...})`.
4. Documentalo en `spec-format.md` y en el CHANGELOG.

## TMDL generado
```tmdl
table Ventas
	/// Ventas sin IVA
	measure 'Ventas Netas' = SUM ( Ventas[Monto] )
		formatString: \$#,0
		displayFolder: KPIs
		lineageTag: <guid>
```
- Expresiones multilinea entre triple backtick (```).
- Tabla Calendario: `partition Calendario = calculated` con `dataCategory: Time`
  y `Fecha` como `isKey` (queda marcada como tabla de fechas).
- Relaciones nuevas al final de `relationships.tmdl`; `model.tmdl` recibe
  `ref table Calendario` cuando el modelo usa referencias ordenadas.
- Modelos antiguos con `model.bim` (TMSL/JSON) tambien se soportan.

## Formatos capturados de Power BI Desktop 2.159 (v0.2)
**Pagina tooltip** (`page.json`, esquema page >= 2.1.0):
`"type": "Tooltip", "displayOption": "ActualSize", "width": 320, "height": 240, "visibility": "HiddenInViewMode"`

**Asignar tooltip a un visual** (`visualContainerObjects`):
`"visualTooltip": [{"properties": {"show": true, "section": "'<id pagina tooltip>'"}}]` (como Literal)

**Boton de navegacion** (`visualType: actionButton`, `visualContainerObjects.visualLink`):
`type: 'PageNavigation'` + `navigationSection: '<id pagina>'`; otros tipos: `'Back'`,
`'ClearAllSlicers'` (+ `tooltipPlaceholderText`). Estados de formato con
`"selector": {"id": "default" | "hover" | "selected"}` en `objects.text/fill/icon`.

**Navegador de paginas**: `visualType: pageNavigator` (no requiere query).

**Texto con valores dinamicos** (textbox):
`objects.values[] = {"properties": {"expr": {"expr": {"Measure": …}}}, "selector": {"id": "v1"}}` y en
el parrafo `{"value": {"propertyIdentifier": {"objectName": "values", "propertyName": "expr"}, "selector": {"id": "v1"}}}`.

**Formato condicional por medida**: `{"solid": {"color": {"expr": {"Measure": …}}}}` en
`objects.labels.color` (tarjeta) o `objects.dataPoint.fill` (barras).
