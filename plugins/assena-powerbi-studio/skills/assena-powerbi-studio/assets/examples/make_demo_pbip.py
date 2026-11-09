"""
Genera un proyecto PBIP "en blanco" de demostracion: modelo de ventas con 3
tablas (Ventas, Productos, Clientes) cargadas desde CSV locales, relaciones y
una pagina vacia. Tambien crea VentasDB.sqlite con los mismos datos para
probar el perfilado SQL. Sirve para probar el skill sin servidor de BD.

    python make_demo_pbip.py <carpeta_destino>
"""
import json
import random
import sqlite3
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

S = "https://developer.microsoft.com/json-schemas/fabric"


def w(p: Path, txt):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(txt if isinstance(txt, str) else json.dumps(txt, indent=2), encoding="utf-8")


def tag():
    return str(uuid.uuid4())


CSV_DIR = None


def m_source(item):
    """Origen CSV local (funciona sin servidor) - refleja un Power Query real."""
    path = str((CSV_DIR / ("%s.csv" % item)).resolve()).replace('"', '""')
    T = "\t"
    body = [
        "let",
        '    Origen = Csv.Document(File.Contents("%s"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),' % path,
        "    Encabezados = Table.PromoteHeaders(Origen, [PromoteAllScalars=true]),",
        '    Tipos = Table.TransformColumnTypes(Encabezados, %s, "en-US")' % TYPES[item],
        "in",
        "    Tipos",
    ]
    return (T + "partition %s = m\n" % item + T * 2 + "mode: import\n" + T * 2 + "source =\n"
            + "".join(T * 4 + b + "\n" for b in body) + "\n")


TYPES = {
    "Ventas": '{{"IdVenta", Int64.Type}, {"Fecha", type datetime}, {"IdProducto", Int64.Type}, {"IdCliente", Int64.Type}, {"Cantidad", Int64.Type}, {"Monto Venta", type number}, {"Costo", type number}, {"Canal", type text}}',
    "Productos": '{{"IdProducto", Int64.Type}, {"Producto", type text}, {"Categoria", type text}, {"Marca", type text}}',
    "Clientes": '{{"IdCliente", Int64.Type}, {"Cliente", type text}, {"Ciudad", type text}, {"Segmento", type text}}',
}


def col(name, dtype, summarize="none", fmt=None):
    q = name if name.isidentifier() else "'%s'" % name
    s = "\tcolumn %s\n\t\tdataType: %s\n" % (q, dtype)
    if fmt:
        s += "\t\tformatString: %s\n" % fmt
    s += "\t\tlineageTag: %s\n\t\tsummarizeBy: %s\n\t\tsourceColumn: %s\n\n" % (tag(), summarize, name)
    s += "\t\tannotation SummarizationSetBy = Automatic\n\n"
    return s


def main(dest, culture="es-ES"):
    global CSV_DIR
    base = Path(dest)
    CSV_DIR = base / "datos"
    name = "DemoVentas"
    w(base / (name + ".pbip"), {"$schema": S + "/pbip/pbipProperties/1.0.0/schema.json", "version": "1.0",
                                 "artifacts": [{"report": {"path": name + ".Report"}}],
                                 "settings": {"enableAutoRecovery": True}})
    r = base / (name + ".Report")
    w(r / "definition.pbir", {"$schema": S + "/item/report/definitionProperties/2.0.0/schema.json", "version": "4.0",
                              "datasetReference": {"byPath": {"path": "../%s.SemanticModel" % name}}})
    d = r / "definition"
    w(d / "version.json", {"$schema": S + "/item/report/definition/versionMetadata/1.0.0/schema.json", "version": "2.0.0"})
    w(d / "report.json", {"$schema": S + "/item/report/definition/report/1.2.0/schema.json",
                          "themeCollection": {"baseTheme": {"name": "CY24SU10", "reportVersionAtImport": "5.61", "type": "SharedResources"}},
                          "layoutOptimization": "None",
                          "resourcePackages": [{"name": "SharedResources", "type": "SharedResources",
                                                "items": [{"name": "CY24SU10", "path": "BaseThemes/CY24SU10.json", "type": "BaseTheme"}]}],
                          "settings": {"useStylableVisualContainerHeader": True, "defaultDrillFilterOtherVisuals": True}})
    w(d / "pages" / "pages.json", {"$schema": S + "/item/report/definition/pagesMetadata/1.0.0/schema.json",
                                   "pageOrder": ["a1b2c3d4e5f6a7b8c9d0"], "activePageName": "a1b2c3d4e5f6a7b8c9d0"})
    w(d / "pages" / "a1b2c3d4e5f6a7b8c9d0" / "page.json",
      {"$schema": S + "/item/report/definition/page/2.0.0/schema.json", "name": "a1b2c3d4e5f6a7b8c9d0",
       "displayName": "Página 1", "displayOption": "FitToPage", "height": 720, "width": 1280})

    m = base / (name + ".SemanticModel")
    w(m / "definition.pbism", {"$schema": S + "/item/semanticModel/definitionProperties/1.0.0/schema.json", "version": "4.2", "settings": {}})
    md = m / "definition"
    w(md / "database.tmdl", "database\n\tcompatibilityLevel: 1567\n\n")
    w(md / "model.tmdl", ("model Model\n\tculture: %s\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n" % culture)
      + "\tsourceQueryCulture: es-EC\n\tdataAccessOptions\n\t\tlegacyRedirects\n\t\treturnErrorValuesAsNull\n\n"
      "annotation PBI_QueryOrder = [\"Ventas\",\"Productos\",\"Clientes\"]\n\n"
      "ref table Ventas\nref table Productos\nref table Clientes\n")
    w(md / "tables" / "Ventas.tmdl", "table Ventas\n\tlineageTag: %s\n\n" % tag()
      + col("IdVenta", "int64") + col("Fecha", "dateTime", fmt="General Date") + col("IdProducto", "int64")
      + col("IdCliente", "int64") + col("Cantidad", "int64", "sum", "0") + col("Monto Venta", "double", "sum")
      + col("Costo", "double", "sum") + col("Canal", "string") + m_source("Ventas")
      + "\tannotation PBI_ResultType = Table\n")
    w(md / "tables" / "Productos.tmdl", "table Productos\n\tlineageTag: %s\n\n" % tag()
      + col("IdProducto", "int64") + col("Producto", "string") + col("Categoria", "string") + col("Marca", "string")
      + m_source("Productos"))
    w(md / "tables" / "Clientes.tmdl", "table Clientes\n\tlineageTag: %s\n\n" % tag()
      + col("IdCliente", "int64") + col("Cliente", "string") + col("Ciudad", "string") + col("Segmento", "string")
      + m_source("Clientes"))
    w(md / "relationships.tmdl",
      "relationship %s\n\tfromColumn: Ventas.IdProducto\n\ttoColumn: Productos.IdProducto\n\n"
      "relationship %s\n\tfromColumn: Ventas.IdCliente\n\ttoColumn: Clientes.IdCliente\n" % (tag(), tag()))

    # datos de ejemplo en SQLite (mismo esquema)
    db = base / "VentasDB.sqlite"
    if db.exists():
        db.unlink()
    random.seed(7)
    con = sqlite3.connect(str(db))
    c = con.cursor()
    c.execute("CREATE TABLE Productos (IdProducto INTEGER, Producto TEXT, Categoria TEXT, Marca TEXT)")
    c.execute("CREATE TABLE Clientes (IdCliente INTEGER, Cliente TEXT, Ciudad TEXT, Segmento TEXT)")
    c.execute('CREATE TABLE Ventas (IdVenta INTEGER, Fecha DATE, IdProducto INTEGER, IdCliente INTEGER, Cantidad INTEGER, "Monto Venta" REAL, Costo REAL, Canal TEXT)')
    cats = ["Reactivos", "Equipos", "Consumibles", "Servicio Técnico", "Repuestos"]
    for i in range(1, 41):
        c.execute("INSERT INTO Productos VALUES (?,?,?,?)", (i, "Producto %02d" % i, random.choice(cats), random.choice(["Alfa", "Beta", "Gamma"])))
    for i in range(1, 121):
        c.execute("INSERT INTO Clientes VALUES (?,?,?,?)", (i, "Cliente %03d" % i, random.choice(["Quito", "Guayaquil", "Cuenca", "Manta", "Loja"]),
                                                            random.choice(["Hospital", "Laboratorio", "Clínica"])))
    d0 = date(2024, 1, 1)
    for i in range(1, 5001):
        q = random.randint(1, 20)
        price = random.uniform(15, 400)
        c.execute("INSERT INTO Ventas VALUES (?,?,?,?,?,?,?,?)", (i, str(d0 + timedelta(days=random.randint(0, 680))), random.randint(1, 40),
                                                                  random.randint(1, 120), q, round(q * price, 2), round(q * price * random.uniform(.55, .8), 2),
                                                                  random.choice(["Directo", "Distribuidor", "Licitación"])))
    con.commit()
    import csv
    CSV_DIR.mkdir(parents=True, exist_ok=True)
    for t in ("Ventas", "Productos", "Clientes"):
        cur = con.execute("SELECT * FROM %s" % t)
        with open(str(CSV_DIR / ("%s.csv" % t)), "w", newline="", encoding="utf-8") as fh:
            wr = csv.writer(fh)
            wr.writerow([d[0] for d in cur.description])
            wr.writerows(cur.fetchall())
    con.close()
    print("Demo creado en", base.resolve())


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "demo", sys.argv[2] if len(sys.argv) > 2 else "es-ES")
