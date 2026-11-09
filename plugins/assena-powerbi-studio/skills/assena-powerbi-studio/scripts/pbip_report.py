"""
ASSENA Power BI Studio - escritura del informe en formato PBIR
(<Nombre>.Report/definition/pages/<pagina>/visuals/<visual>/visual.json).

El layout se describe con filas sobre una grilla de 12 columnas; este modulo
calcula posiciones exactas, genera los visual.json y registra el tema.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import time
from pathlib import Path

from pbip_model import PbipError, find_table, split_field

SCHEMA_BASE = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"
DEFAULT_VERSIONS = {"page": "2.0.0", "visualContainer": "2.0.0", "pagesMetadata": "1.0.0"}
MANAGED_PREFIX = "assena"

# tipo de la spec -> (visualType de Power BI, {clave spec: rol del visual})
VISUALS = {
    "card":           ("card", {"values": "Values"}),
    "multicard":      ("multiRowCard", {"values": "Values"}),
    "column":         ("clusteredColumnChart", {"category": "Category", "values": "Y", "series": "Series"}),
    "bar":            ("clusteredBarChart", {"category": "Category", "values": "Y", "series": "Series"}),
    "stackedColumn":  ("columnChart", {"category": "Category", "values": "Y", "series": "Series"}),
    "stackedBar":     ("barChart", {"category": "Category", "values": "Y", "series": "Series"}),
    "column100":      ("hundredPercentStackedColumnChart", {"category": "Category", "values": "Y", "series": "Series"}),
    "line":           ("lineChart", {"category": "Category", "values": "Y", "series": "Series"}),
    "area":           ("areaChart", {"category": "Category", "values": "Y", "series": "Series"}),
    "combo":          ("lineClusteredColumnComboChart", {"category": "Category", "columns": "Y", "lines": "Y2", "series": "Series"}),
    "donut":          ("donutChart", {"category": "Category", "values": "Y"}),
    "pie":            ("pieChart", {"category": "Category", "values": "Y"}),
    "treemap":        ("treemap", {"category": "Group", "values": "Values"}),
    "funnel":         ("funnel", {"category": "Category", "values": "Y"}),
    "waterfall":      ("waterfallChart", {"category": "Category", "values": "Y"}),
    "scatter":        ("scatterChart", {"details": "Category", "x": "X", "y": "Y", "size": "Size", "series": "Series"}),
    "gauge":          ("gauge", {"values": "Y", "min": "MinValue", "max": "MaxValue", "target": "TargetValue"}),
    "kpi":            ("kpi", {"values": "Indicator", "trend": "TrendLine", "target": "Goal"}),
    "table":          ("tableEx", {"values": "Values"}),
    "matrix":         ("pivotTable", {"rows": "Rows", "columns": "Columns", "values": "Values"}),
    "slicer":         ("slicer", {"field": "Values"}),
    "map":            ("map", {"location": "Category", "size": "Size", "series": "Series"}),
    "filledMap":      ("filledMap", {"location": "Category", "values": "Size"}),
    "text":           ("textbox", {}),
    "button":         ("actionButton", {}),
    "spark":          ("areaChart", {"category": "Category", "values": "Y"}),
    "navigator":      ("pageNavigator", {}),
}
NO_TOOLTIP = {"spark", "card", "multicard", "kpi", "gauge", "slicer", "text", "button", "navigator", "table", "matrix"}

SORTABLE = {"column", "bar", "stackedColumn", "stackedBar", "funnel", "treemap", "donut", "pie", "table", "waterfall"}


# --------------------------------------------------------------------------- #
#  Helpers de expresiones PBIR
# --------------------------------------------------------------------------- #
def lit(v):
    if isinstance(v, bool):
        s = "true" if v else "false"
    elif isinstance(v, (int, float)):
        s = "%sD" % v
    else:
        s = "'" + str(v).replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": s}}}


def color(hexv):
    return {"solid": {"color": lit(hexv)}}


def _sel(props: dict, state: str | None = None) -> dict:
    d = {"properties": props}
    if state:
        d["selector"] = {"id": state}
    return d


_PLACEHOLDER = re.compile(r"\{((?:'[^']+'|[^{}\[\]]+)?\[[^\]]+\])\}")


def rich_paragraphs(paras, res, pal):
    """Parrafos de texto con valores dinamicos: 'Ventas de {[Total Ventas]}' se
    actualiza con los filtros (mismo mecanismo que la narrativa personalizada)."""
    out, values, seen = [], [], {}
    dark = pal.get("mode") == "dark"
    tokens = {"@title": pal["text"] if dark else pal["header"], "@text": pal["text"], "@muted": pal["textMuted"],
              "@accent": pal["accent"], "@white": "#FFFFFF", "@sub": pal["headerSubtext"]}

    def tok(c):
        return tokens.get(c, c) if c else None
    for p in paras:
        if isinstance(p, str):
            p = {"text": p}
        if p.get("runs"):  # varios estilos en un mismo parrafo (p. ej. titulo bicolor)
            runs = []
            for r in p["runs"]:
                st = {"fontSize": "%spt" % r.get("size", p.get("size", 11)), "color": tok(r.get("color") or p.get("color")) or pal["text"]}
                if r.get("bold", p.get("bold")):
                    st["fontWeight"] = "bold"
                runs.append({"value": r["text"], "textStyle": st})
            para = {"textRuns": runs}
            if p.get("align"):
                para["horizontalTextAlignment"] = p["align"]
            out.append(para)
            continue
        style = {"fontSize": "%spt" % p.get("size", 11), "color": tok(p.get("color")) or pal["text"]}
        if p.get("bold"):
            style["fontWeight"] = "bold"
        if p.get("font"):
            style["fontFamily"] = p["font"]
        text = ("• " if p.get("bullet") else "") + p.get("text", "")
        runs, pos = [], 0
        for m in _PLACEHOLDER.finditer(text):
            if m.start() > pos:
                runs.append({"value": text[pos:m.start()], "textStyle": dict(style)})
            ref = m.group(1)
            vid = seen.get(ref)
            if vid is None:
                f = res.resolve(ref)
                vid = "v%d" % (len(seen) + 1)
                seen[ref] = vid
                values.append({"properties": {"expr": {"expr": res.field_json(f)}}, "selector": {"id": vid}})
            vstyle = dict(style)
            vstyle["fontWeight"] = "bold"
            if p.get("valueColor"):
                vstyle["color"] = tok(p["valueColor"])
            runs.append({"value": {"propertyIdentifier": {"objectName": "values", "propertyName": "expr"},
                                   "selector": {"id": vid}}, "textStyle": vstyle})
            pos = m.end()
        if pos < len(text) or not runs:
            runs.append({"value": text[pos:], "textStyle": dict(style)})
        para = {"textRuns": runs}
        if p.get("align"):
            para["horizontalTextAlignment"] = p["align"]
        out.append(para)
    return out, values


def button_link(v):
    if v.get("action") == "none":
        return {"show": lit(False)}
    if v.get("action") == "clearSlicers":
        return {"show": lit(True), "type": lit("ClearAllSlicers"),
                "tooltipPlaceholderText": lit(v.get("tooltip", "Limpiar todos los filtros de la pagina"))}
    if v.get("action") == "back":
        return {"show": lit(True), "type": lit("Back")}
    return {"show": lit(True), "type": lit("PageNavigation"), "navigationSection": lit(v["target"])}


def button_objects(v, pal):
    fg = v.get("fontColor", pal["header"])
    bg = v.get("fill", pal["surface"])
    hover_bg = v.get("hoverFill", pal["accent"])
    obj = {
        "icon": [_sel({"show": lit(bool(v.get("icon")))})],
        "text": [_sel({"show": lit(bool(v.get("text")))}),
                 _sel({"text": lit(v.get("text", "")), "fontColor": color(fg), "fontSize": lit(v.get("fontSize", 12)),
                       "bold": lit(v.get("bold", True)), "horizontalAlignment": lit(v.get("align", "center"))}, "default"),
                 _sel({"fontColor": color(v.get("hoverFontColor", "#FFFFFF"))}, "hover")],
        "fill": [_sel({"show": lit(v.get("showFill", True))}),
                 _sel({"fillColor": color(bg), "transparency": lit(v.get("transparency", 0))}, "default"),
                 _sel({"fillColor": color(hover_bg), "transparency": lit(0)}, "hover")],
        "outline": ([_sel({"show": lit(True)}),
                     _sel({"lineColor": color(v["outline"]), "weight": lit(v.get("outlineWeight", 1)),
                           "transparency": lit(v.get("outlineTransparency", 0)), "roundEdge": lit(v.get("roundEdge", 2))}, "default"),
                     _sel({"lineColor": color(v.get("hoverOutline", hover_bg)), "transparency": lit(0)}, "hover")]
                    if v.get("outline") else [_sel({"show": lit(False)})]),
    }
    if v.get("icon"):
        obj["icon"] = [_sel({"show": lit(True)}),
                       _sel({"shapeType": lit(v["icon"]), "lineColor": color(fg)}, "default"),
                       _sel({"lineColor": color(v.get("hoverFontColor", "#FFFFFF"))}, "hover")]
    return obj


def navigator_objects(v, pal):
    return {
        "text": [_sel({"show": lit(True)}),
                 _sel({"fontColor": color(v.get("fontColor", pal["headerSubtext"])), "fontSize": lit(10),
                       "fontFamily": lit("Segoe UI Semibold")}, "default"),
                 _sel({"fontColor": color("#FFFFFF"), "bold": lit(True)}, "selected"),
                 _sel({"fontColor": color("#FFFFFF")}, "hover")],
        "fill": [_sel({"show": lit(True)}),
                 _sel({"fillColor": color(pal["header"]), "transparency": lit(100)}, "default"),
                 _sel({"fillColor": color(pal["accent"]), "transparency": lit(0)}, "selected"),
                 _sel({"fillColor": color("#FFFFFF"), "transparency": lit(85)}, "hover")],
        "outline": [_sel({"show": lit(False)})],
    }


def _id(*parts) -> str:
    return hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:20]


def _slug(s: str) -> str:
    s = s.lower()
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ñ", "n")):
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "", s)[:24] or "pagina"


# --------------------------------------------------------------------------- #
#  Resolucion de campos contra el modelo
# --------------------------------------------------------------------------- #
class FieldResolver:
    def __init__(self, model: dict):
        self.model = model

    def resolve(self, ref: str) -> dict:
        table, name = split_field(ref)
        hits = []
        tables = [find_table(self.model, table)] if table else self.model["tables"]
        if table and tables[0] is None:
            raise PbipError("La tabla '%s' no existe (campo %s)" % (table, ref))
        for t in tables:
            for m in t["measures"]:
                if m["name"].lower() == name.lower():
                    hits.append(("Measure", t["name"], m["name"]))
            for c in t["columns"]:
                if c["name"].lower() == name.lower():
                    hits.append(("Column", t["name"], c["name"]))
        if not hits:
            raise PbipError("El campo %s no existe en el modelo" % ref)
        if len(hits) > 1 and not table:
            ms = [h for h in hits if h[0] == "Measure"]
            if len(ms) == 1:
                hits = ms
            else:
                raise PbipError("El campo %s es ambiguo; usa Tabla[Campo]. Coincidencias: %s" % (ref, hits))
        kind, t, n = hits[0]
        return {"kind": kind, "table": t, "name": n}

    @staticmethod
    def field_json(f: dict) -> dict:
        return {f["kind"]: {"Expression": {"SourceRef": {"Entity": f["table"]}}, "Property": f["name"]}}

    def projection(self, ref: str, active=False) -> dict:
        f = self.resolve(ref)
        p = {"field": self.field_json(f), "queryRef": "%s.%s" % (f["table"], f["name"]), "nativeQueryRef": f["name"]}
        if active:
            p["active"] = True
        return p


# --------------------------------------------------------------------------- #
#  Layout
# --------------------------------------------------------------------------- #
def layout_page(page: dict, width: int, height: int, header_h: int) -> list:
    """Devuelve [(visual_spec, x, y, w, h)] calculando posiciones en grilla de 12."""
    margin = page.get("margin", 16)
    gap = page.get("gap", 12)
    rows = page.get("rows", [])
    top = header_h + (margin if header_h else margin)
    avail_h = height - top - margin - gap * max(len(rows) - 1, 0)
    fixed = sum(r["height"] for r in rows if r.get("height"))
    flex = [r for r in rows if not r.get("height")]
    weights = sum(r.get("weight", 1) for r in flex) or 1
    flex_h = max(avail_h - fixed, 0)
    placed, y = [], top
    for r in rows:
        h = r.get("height") or int(flex_h * r.get("weight", 1) / weights)
        vis = r.get("visuals", [])
        spans = [v.get("span", 12 // max(len(vis), 1)) for v in vis]
        total = sum(spans) or 1
        inner_w = width - 2 * margin - gap * max(len(vis) - 1, 0)
        x = margin
        for i, (v, s) in enumerate(zip(vis, spans)):
            w = int(round(inner_w * s / total)) if i < len(vis) - 1 else (width - margin - x)
            placed.append((v, x, y, w, h))
            x += w + gap
        y += h + gap
    return placed


# --------------------------------------------------------------------------- #
#  Construccion de visuales
# --------------------------------------------------------------------------- #
def _as_list(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def build_visual(v: dict, name: str, pos: tuple, z: int, res: FieldResolver, pal: dict, vc_schema: str) -> dict:
    vtype = v["type"]
    if vtype not in VISUALS:
        raise PbipError("Tipo de visual no soportado: %s (validos: %s)" % (vtype, ", ".join(VISUALS)))
    pbi_type, roles = VISUALS[vtype]
    x, y, w, h = pos
    visual = {"visualType": pbi_type}
    objects, container = {}, {}

    if vtype == "text":
        paras = v.get("paragraphs") or [{"text": v.get("text", ""), "size": v.get("fontSize", 11), "bold": v.get("bold"),
                                         "color": v.get("color"), "align": v.get("align", "left")}]
        pj, values = rich_paragraphs(paras, res, pal)
        objects["general"] = [{"properties": {"paragraphs": pj}}]
        if values:
            objects["values"] = values
    elif vtype == "button":
        objects.update(button_objects(v, pal))
        container["visualLink"] = [{"properties": button_link(v)}]
    elif vtype == "navigator":
        objects.update(navigator_objects(v, pal))
    else:
        query_state = {}
        for key, role in roles.items():
            refs = _as_list(v.get(key))
            if not refs:
                continue
            projs = [res.projection(r, active=(role in ("Category", "Rows") and i == 0)) for i, r in enumerate(refs)]
            query_state[role] = {"projections": projs}
        if not query_state:
            raise PbipError("El visual '%s' (%s) no tiene campos asignados" % (v.get("title", name), vtype))
        visual["query"] = {"queryState": query_state}
        sort = v.get("sort")
        if sort and vtype in SORTABLE:
            by = v.get("sortBy") or (_as_list(v.get("values")) or _as_list(v.get("category")))[0]
            visual["query"]["sortDefinition"] = {
                "sort": [{"field": res.field_json(res.resolve(by)),
                          "direction": "Descending" if sort == "desc" else "Ascending"}],
                "isDefaultSort": True}

    # formato especifico
    if vtype == "slicer":
        objects["data"] = [{"properties": {"mode": lit(v.get("mode", "Dropdown"))}}]
        objects["header"] = [{"properties": {"show": lit(True), "text": lit(v.get("title", ""))}}] if v.get("title") else []
        if not objects["header"]:
            del objects["header"]
    if vtype in ("column", "bar", "stackedColumn", "stackedBar", "line", "area", "combo", "waterfall", "funnel"):
        if v.get("labels", vtype in ("column", "bar", "funnel", "waterfall")):
            objects["labels"] = [{"properties": {"show": lit(True)}}]
    if vtype in ("line", "area", "combo", "stackedColumn", "stackedBar") and not v.get("series"):
        if len(_as_list(v.get("values"))) + len(_as_list(v.get("lines"))) + len(_as_list(v.get("columns"))) <= 1:
            objects["legend"] = [{"properties": {"show": lit(False)}}]
    if vtype in ("column", "bar") and not v.get("series") and len(_as_list(v.get("values"))) == 1:
        objects["legend"] = [{"properties": {"show": lit(False)}}]
    if v.get("color") and vtype not in ("text",):
        objects["dataPoint"] = [{"properties": {"fill": color(v["color"])}}]
    if vtype == "card" and v.get("label"):
        objects["categoryLabels"] = [{"properties": {"show": lit(True)}}]
    if vtype == "card" and v.get("colorMeasure"):
        # formato condicional: el color del numero sale de una medida que devuelve un hex
        objects["labels"] = [{"properties": {"color": {"solid": {"color": {"expr": res.field_json(res.resolve(v["colorMeasure"]))}}}}}]
    if v.get("colorMeasure") and vtype in ("bar", "column"):
        objects["dataPoint"] = [{"properties": {"fill": {"solid": {"color": {"expr": res.field_json(res.resolve(v["colorMeasure"]))}}}}}]

    if vtype == "spark":  # mini tendencia sin ejes (portada)
        objects = {"categoryAxis": [{"properties": {"show": lit(False)}}],
                   "valueAxis": [{"properties": {"show": lit(False)}}],
                   "legend": [{"properties": {"show": lit(False)}}],
                   "labels": [{"properties": {"show": lit(False)}}],
                   "dataPoint": [{"properties": {"fill": color(v.get("color", pal["accent"]))}}],
                   "lineStyles": [{"properties": {"strokeWidth": lit(2), "lineChartType": lit("smooth")}}]}
        container.update({"title": [{"properties": {"show": lit(False)}}],
                          "background": [{"properties": {"show": lit(False)}}],
                          "border": [{"properties": {"show": lit(False)}}],
                          "dropShadow": [{"properties": {"show": lit(False)}}],
                          "visualHeader": [{"properties": {"show": lit(False)}}],
                          "visualTooltip": [{"properties": {"show": lit(False)}}]})

    # tooltip de pagina de informe
    if v.get("_tooltipPage") and vtype not in NO_TOOLTIP:
        container["visualTooltip"] = [{"properties": {"show": lit(True), "section": lit(v["_tooltipPage"])}}]

    # contenedor
    title = v.get("title")
    if vtype in ("button", "navigator"):
        container["title"] = [{"properties": {"show": lit(False)}}]
        container["background"] = [{"properties": {"show": lit(False)}}]
        container["border"] = [{"properties": {"show": lit(False)}}]
        container["dropShadow"] = [{"properties": {"show": lit(v.get("shadow", False))}}]
        container["visualHeader"] = [{"properties": {"show": lit(False)}}]
        container["padding"] = [{"properties": {"top": lit(0), "bottom": lit(0), "left": lit(0), "right": lit(0)}}]
    elif vtype in ("card", "text", "slicer", "spark"):
        container["title"] = [{"properties": {"show": lit(False)}}]
    elif title:
        container["title"] = [{"properties": {"show": lit(True), "text": lit(title)}}]
        if v.get("subtitle"):
            container["subTitle"] = [{"properties": {"show": lit(True), "text": lit(v["subtitle"])}}]
    if vtype == "card" and (v.get("labelColor") or v.get("labelSize")):
        props = {}
        if v.get("labelColor"):
            props["color"] = color(v["labelColor"])
        if v.get("labelSize"):
            props["fontSize"] = lit(v["labelSize"])
        objects.setdefault("labels", [{"properties": {}}])[0]["properties"].update(props)
    if vtype == "card" and v.get("categoryColor"):
        objects["categoryLabels"] = [{"properties": {"show": lit(True), "color": color(v["categoryColor"])}}]
    if v.get("background"):
        container["background"] = [{"properties": {"show": lit(True), "color": color(v["background"]),
                                                   "transparency": lit(v.get("bgTransparency", 0))}}]
        if v.get("borderColor"):
            container["border"] = [{"properties": {"show": lit(True), "color": color(v["borderColor"]),
                                                   "radius": lit(v.get("radius", 12))}}]
        else:
            container["border"] = [{"properties": {"show": lit(False)}}]
        container["dropShadow"] = [{"properties": {"show": lit(False)}}]
    if vtype == "text":
        container["visualHeader"] = [{"properties": {"show": lit(False)}}]
    if v.get("altText") or title:
        container.setdefault("general", [{"properties": {}}])
        container["general"][0]["properties"]["altText"] = lit(v.get("altText") or title)

    if objects:
        visual["objects"] = objects
    if container:
        visual["visualContainerObjects"] = container
    visual["drillFilterOtherVisuals"] = True
    return {
        "$schema": "%s/visualContainer/%s/schema.json" % (SCHEMA_BASE, vc_schema),
        "name": name,
        "position": {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": z},
        "visual": visual,
    }


def header_visual(page: dict, spec: dict, pal: dict, width: int, header_h: int, vc_schema: str, pname: str,
                  transparent: bool = False) -> dict:
    title = page.get("title") or page["name"]
    subtitle = page.get("subtitle") or spec.get("subtitle", "")
    paragraphs = [{"textRuns": [{"value": title, "textStyle": {"fontWeight": "bold", "fontSize": "16pt",
                                                                "color": pal["headerText"], "fontFamily": "Segoe UI Semibold"}}]}]
    eyebrow = page.get("eyebrow", spec.get("title"))
    if eyebrow:
        paragraphs.insert(0, {"textRuns": [{"value": eyebrow.upper(), "textStyle": {
            "fontSize": "8pt", "fontWeight": "bold", "color": _lighten(spec.get("_brandAccent", pal["accent"]), 0.4)}}]})
    if subtitle:
        paragraphs.append({"textRuns": [{"value": subtitle, "textStyle": {"fontSize": "9pt", "color": pal["headerSubtext"]}}]})
    return {
        "$schema": "%s/visualContainer/%s/schema.json" % (SCHEMA_BASE, vc_schema),
        "name": _id(pname, "header"),
        "position": {"x": 0, "y": 0, "z": 0, "height": header_h, "width": width, "tabOrder": 0},
        "visual": {
            "visualType": "textbox",
            "objects": {"general": [{"properties": {"paragraphs": paragraphs}}]},
            "visualContainerObjects": {
                "background": [{"properties": {"show": lit(not transparent), "color": color(pal["header"]), "transparency": lit(0)}}],
                "border": [{"properties": {"show": lit(False)}}],
                "dropShadow": [{"properties": {"show": lit(False)}}],
                "title": [{"properties": {"show": lit(False)}}],
                "visualHeader": [{"properties": {"show": lit(False)}}],
                "padding": [{"properties": {"top": lit(12), "left": lit(24), "right": lit(24), "bottom": lit(0)}}],
            },
        },
    }


# --------------------------------------------------------------------------- #
#  Informe completo
# --------------------------------------------------------------------------- #
def _read_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8-sig"))


def _write_json(p: Path, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _schema_version(path: Path, default: str) -> str:
    try:
        m = re.search(r"/(\d+\.\d+\.\d+)/schema\.json", _read_json(path).get("$schema", ""))
        return m.group(1) if m else default
    except (OSError, ValueError):
        return default


def detect_versions(defn: Path, spec: dict) -> dict:
    v = dict(DEFAULT_VERSIONS)
    v.update(spec.get("schemaVersions", {}))
    pages = list((defn / "pages").glob("*/page.json"))
    if pages and "page" not in spec.get("schemaVersions", {}):
        v["page"] = _schema_version(pages[0], v["page"])
    visuals = list((defn / "pages").glob("*/visuals/*/visual.json"))
    if visuals and "visualContainer" not in spec.get("schemaVersions", {}):
        v["visualContainer"] = _schema_version(visuals[0], v["visualContainer"])
    return v


def ensure_pbir(report_dir: Path) -> Path:
    defn = report_dir / "definition"
    if not defn.exists():
        if (report_dir / "report.json").exists():
            raise PbipError(
                "El informe esta en formato PBIR-Legacy (report.json unico).\n"
                "En Power BI Desktop: Archivo > Opciones > Caracteristicas en vista previa > activa\n"
                "'Almacenar informes con formato de metadatos mejorado (PBIR)', guarda de nuevo el .pbip y reintenta.")
        raise PbipError("No encontre %s" % defn)
    return defn


MANAGED_IMAGES = ("Portada_", "Fondo_")


def clean_images(report_dir: Path):
    res_dir = report_dir / "StaticResources" / "RegisteredResources"
    if res_dir.exists():
        for f in res_dir.iterdir():
            if f.name.startswith(MANAGED_IMAGES):
                f.unlink()
    rpath = report_dir / "definition" / "report.json"
    rep = _read_json(rpath)
    for pkg in rep.get("resourcePackages", []):
        if pkg.get("type") == "RegisteredResources":
            pkg["items"] = [i for i in pkg.get("items", []) if not i.get("name", "").startswith(MANAGED_IMAGES)]
    _write_json(rpath, rep)


def register_image(report_dir: Path, file_name: str, data: bytes):
    """Guarda una imagen en RegisteredResources y la registra en report.json."""
    res_dir = report_dir / "StaticResources" / "RegisteredResources"
    res_dir.mkdir(parents=True, exist_ok=True)
    (res_dir / file_name).write_bytes(data)
    rpath = report_dir / "definition" / "report.json"
    rep = _read_json(rpath)
    pkgs = rep.setdefault("resourcePackages", [])
    pkg = next((p for p in pkgs if p.get("type") == "RegisteredResources"), None)
    if pkg is None:
        pkg = {"name": "RegisteredResources", "type": "RegisteredResources", "items": []}
        pkgs.append(pkg)
    pkg["items"] = [i for i in pkg.get("items", []) if i.get("name") != file_name]
    pkg["items"].append({"name": file_name, "path": file_name, "type": "Image"})
    _write_json(rpath, rep)


def register_theme(report_dir: Path, theme: dict, file_name: str, log):
    defn = ensure_pbir(report_dir)
    res_dir = report_dir / "StaticResources" / "RegisteredResources"
    _write_json(res_dir / file_name, theme)
    rpath = defn / "report.json"
    rep = _read_json(rpath)
    tc = rep.setdefault("themeCollection", {})
    ver = (tc.get("baseTheme") or {}).get("reportVersionAtImport", "5.61")
    old = (tc.get("customTheme") or {}).get("name")
    tc["customTheme"] = {"name": file_name, "reportVersionAtImport": ver, "type": "RegisteredResources"}
    pkgs = rep.setdefault("resourcePackages", [])
    pkg = next((p for p in pkgs if p.get("type") == "RegisteredResources"), None)
    if pkg is None:
        pkg = {"name": "RegisteredResources", "type": "RegisteredResources", "items": []}
        pkgs.append(pkg)
    items = [i for i in pkg.get("items", []) if i.get("type") != "CustomTheme"]
    items.append({"name": file_name, "path": file_name, "type": "CustomTheme"})
    pkg["items"] = items
    if old and old != file_name:
        try:
            (res_dir / old).unlink()
        except OSError:
            pass
    _write_json(rpath, rep)
    log("  + tema '%s' registrado" % file_name)


def _ver_at_least(v: str, minimum: str) -> str:
    t = lambda x: tuple(int(n) for n in x.split("."))
    return v if t(v) >= t(minimum) else minimum


def _page_json(pid, name, w, h, bg, versions, ptype=None, hidden=False, display=None, image=None):
    ver = _ver_at_least(versions["page"], "2.1.0") if ptype else versions["page"]
    pj = {
        "$schema": "%s/page/%s/schema.json" % (SCHEMA_BASE, ver),
        "name": pid,
        "displayName": name,
        "displayOption": display or "FitToPage",
        "height": h,
        "width": w,
        "objects": {
            "background": [{"properties": {"color": color(bg), "transparency": lit(0)}}],
            "outspace": [{"properties": {"color": color(bg), "transparency": lit(0)}}],
        },
    }
    if image:
        pj["objects"]["background"] = [{"properties": {
            "color": color(bg),
            "image": {"image": {
                "name": lit(image),
                "url": {"expr": {"ResourcePackageItem": {"PackageName": "RegisteredResources", "PackageType": 1,
                                                         "ItemName": image}}},
                "scaling": lit("Fill")}},
            "transparency": lit(0)}}]
    if ptype:
        pj["type"] = ptype
    if hidden:
        pj["visibility"] = "HiddenInViewMode"
    return pj


def _lighten(hexv, t):
    h = hexv.lstrip("#")
    c = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    return "#%02X%02X%02X" % tuple(int(x + (255 - x) * t) for x in c)


def _brand():
    import json as _json
    return _json.loads((Path(__file__).resolve().parent.parent / "assets" / "brand.json").read_text(encoding="utf-8"))


def cover_colors(cover, pal):
    """Colores de la portada oscura: base = encabezado de la paleta; acentos =
    color de marca (assets/brand.json, sobrescribible con cover.brandColors)."""
    brand = _brand()
    brand.update(cover.get("brandColors") or {})
    acc = brand["accent"]
    return {"bg": pal["header"], "title": "#FFFFFF", "accent": acc, "accentText": _lighten(acc, 0.38),
            "sub": pal["headerSubtext"], "subLight": _lighten(pal["headerSubtext"], 0.4),
            "glassBorder": _lighten(pal["header"], 0.22), "line": _lighten(pal["header"], 0.16),
            "brandName": brand.get("name", "")}


def _cover_visuals(cover, spec, pal, targets, width, height, mode_ids):
    """Portada ejecutiva: barra superior (marca + selector Claro/Oscuro), columna
    izquierda (titulo bicolor, descripcion, indice de contenido navegable) y panel
    de cristal a la derecha (KPIs + tendencia mensual)."""
    C = cover_colors(cover, pal)
    L = cover.get("left", 64)
    out = []
    # --- barra superior
    brand_runs = []
    if C["brandName"]:
        brand_runs = [{"text": "■  ", "color": C["accent"]}, {"text": C["brandName"].upper(), "bold": True, "color": "#FFFFFF"},
                      {"text": "   |   ", "color": C["line"]}]
    brand_runs.append({"text": (cover.get("brand") or "BUSINESS INTELLIGENCE").upper(), "color": C["sub"]})
    out.append(({"type": "text", "paragraphs": [{"runs": brand_runs, "size": 10}]}, L, 30, 560, 26))
    # selector de tema (segmentado)
    cur, other = mode_ids["mode"], mode_ids["otherCover"]
    tw, th = 92, 30
    tx = width - L - 2 * tw - 4
    for i, (label, m) in enumerate((("☀  Claro", "light"), ("☾  Oscuro", "dark"))):
        active = m == cur
        out.append(({"type": "button", "text": label, "fontSize": 10, "bold": active,
                     **({"action": "none"} if active else {"target": other}),
                     "fill": C["accent"] if active else "#FFFFFF", "transparency": 0 if active else 90,
                     "fontColor": "#FFFFFF" if active else C["subLight"], "hoverFill": C["accent"],
                     "outline": C["accent"] if active else "#FFFFFF", "outlineTransparency": 0 if active else 65},
                    tx + i * (tw + 4), 28, tw, th))
    # --- columna izquierda
    words = (cover.get("title") or spec.get("title", "Dashboard")).split()
    head, last = " ".join(words[:-1]), words[-1] if words else ""
    out += [
        ({"type": "text", "paragraphs": [{"text": (cover.get("eyebrow") or "TABLERO EJECUTIVO").upper(), "size": 10,
                                           "bold": True, "color": C["accentText"]}]}, L, 128, 600, 24),
        ({"type": "text", "paragraphs": [{"runs": [{"text": head + (" " if head else ""), "color": "#FFFFFF"},
                                                   {"text": last, "color": C["accentText"]}], "size": 40, "bold": True}]},
         L, 152, 640, 118),
        ({"type": "text", "paragraphs": [{"text": cover.get("subtitle") or spec.get("subtitle", ""), "size": 15,
                                           "color": C["subLight"]}]}, L, 272, 620, 32),
    ]
    if cover.get("description"):
        out.append(({"type": "text", "paragraphs": [{"text": cover["description"], "size": 11, "color": C["sub"]}]},
                    L, 308, 560, 56))
    out.append(({"type": "text", "paragraphs": [{"text": "CONTENIDO DEL INFORME", "size": 9, "bold": True,
                                                 "color": C["sub"]}]}, L, 380, 400, 22))
    n = max(len(targets), 1)
    bh = 44 if n <= 4 else max(30, int(200 / n))
    for i, (pid, label) in enumerate(targets):
        out.append(({"type": "button", "text": "%02d     %s" % (i + 1, label), "target": pid, "fontSize": 12,
                     "align": "left", "fill": "#FFFFFF", "transparency": 93, "fontColor": "#FFFFFF",
                     "hoverFill": C["accent"], "outline": "#FFFFFF", "outlineTransparency": 72, "hoverOutline": C["accent"]},
                    L, 406 + i * (bh + 8), 470, bh))
    # --- panel de cristal derecho
    pw, ph = 400, 476
    px, py = width - L - pw, 128
    out.append(({"type": "text", "text": "", "background": "#FFFFFF", "bgTransparency": 93,
                 "borderColor": C["glassBorder"], "radius": 16}, px, py, pw, ph))
    out.append(({"type": "text", "paragraphs": [{"text": "INDICADORES CLAVE", "size": 9, "bold": True, "color": C["sub"]}]},
                px + 24, py + 18, pw - 48, 22))
    kpis = cover.get("kpis", [])[:3]
    for i, ref in enumerate(kpis):
        out.append(({"type": "card", "values": ref, "label": True, "tooltip": False,
                     "background": "#FFFFFF", "bgTransparency": 100, "labelColor": "#FFFFFF", "labelSize": 28,
                     "categoryColor": C["sub"]}, px + 16, py + 46 + i * 86, pw - 32, 80))
    trend = cover.get("trend")
    if trend:
        ty = py + 46 + len(kpis) * 86 + 6
        out.append(({"type": "text", "paragraphs": [{"text": "TENDENCIA MENSUAL", "size": 9, "bold": True,
                                                     "color": C["sub"]}]}, px + 24, ty, pw - 48, 20))
        out.append(({"type": "spark", "category": trend["category"], "values": trend["values"], "color": C["accentText"],
                     "tooltip": False}, px + 16, ty + 22, pw - 32, py + ph - ty - 34))
    # --- pie
    out.append(({"type": "text", "text": "", "background": C["line"]}, L, height - 58, width - 2 * L, 1))
    out.append(({"type": "text", "paragraphs": [{"text": cover.get("footer") or "Generado con ASSENA Power BI Studio",
                                                 "size": 9, "color": C["sub"]}]}, L, height - 46, 600, 22))
    out.append(({"type": "text", "paragraphs": [{"text": "Actualizado · %s" % time.strftime("%d/%m/%Y"), "size": 9,
                                                 "color": C["sub"], "align": "right"}]}, width - L - 300, height - 46, 300, 22))
    return out


def _tooltip_visuals(tt, w, h):
    refs = tt.get("measures", [])[:4]
    m, gap = 8, 8
    cols = 2 if len(refs) > 1 else 1
    rows = (len(refs) + cols - 1) // cols
    cw = (w - 2 * m - gap * (cols - 1)) // cols
    ch = (h - 2 * m - gap * (rows - 1)) // max(rows, 1)
    return [({"type": "card", "values": r, "label": True}, m + (i % cols) * (cw + gap), m + (i // cols) * (ch + gap), cw, ch)
            for i, r in enumerate(refs)]


def _nav_items(pal, header_h, width, entries, current, toggle_target, toggle_to_dark, has_slicers):
    """Barra de navegacion propia en el encabezado: Inicio + paginas (la actual
    resaltada), boton limpiar filtros y boton de tema claro/oscuro."""
    nh = 30
    ny = (header_h - nh) // 2
    items, x = [], width - 16
    tw = 38
    x -= tw
    items.append(({"type": "button", "text": "☾" if toggle_to_dark else "☀", "target": toggle_target, "fontSize": 13,
                   "fill": "#FFFFFF", "transparency": 88, "fontColor": "#FFFFFF", "hoverFill": pal["accent"],
                   "outline": "#FFFFFF", "outlineTransparency": 60,
                   "tooltipText": "Cambiar a modo oscuro" if toggle_to_dark else "Cambiar a modo claro"}, x, ny, tw, nh))
    x -= 10
    for label, pid in reversed(entries):
        bw = max(78, int(len(label) * 6.6) + 30)
        x -= bw
        sel = pid == current
        items.append(({"type": "button", "text": label, "target": pid, "fontSize": 10, "bold": sel,
                       **({"action": "none"} if sel else {}),
                       "fill": pal["accent"] if sel else "#FFFFFF", "transparency": 0 if sel else 92,
                       "fontColor": "#FFFFFF" if sel else "#E2E8F0", "hoverFill": pal["accent"],
                       "outline": "#FFFFFF" if not sel else pal["accent"], "outlineTransparency": 70 if not sel else 0},
                      x, ny, bw, nh))
        x -= 4
    if has_slicers:
        x -= nh + 6
        items.append(({"type": "button", "action": "clearSlicers", "icon": "clearAllSlicers", "text": "",
                       "fill": "#FFFFFF", "transparency": 100, "fontColor": pal["headerText"],
                       "hoverFill": pal["accent"]}, x, ny, nh, nh))
    return items


def build_pages(report_dir: Path, spec: dict, model: dict, pal: dict, log, replace_all=False) -> list:
    from modes import apply_dark, dark_palette
    defn = ensure_pbir(report_dir)
    versions = detect_versions(defn, spec)
    pages_dir = defn / "pages"
    pages_dir.mkdir(exist_ok=True)
    meta_path = pages_dir / "pages.json"
    meta = _read_json(meta_path) if meta_path.exists() else {"pageOrder": []}

    # limpiar paginas gestionadas por ASSENA y paginas vacias
    kept = []
    for pid in list(meta.get("pageOrder", [])):
        pdir = pages_dir / pid
        has_visuals = (pdir / "visuals").exists() and any((pdir / "visuals").iterdir())
        if replace_all or pid.startswith(MANAGED_PREFIX) or not has_visuals:
            shutil.rmtree(pdir, ignore_errors=True)
            log("  - pagina eliminada: %s" % pid)
        else:
            kept.append(pid)
    for pdir in pages_dir.iterdir():  # huerfanas
        if pdir.is_dir() and pdir.name.startswith(MANAGED_PREFIX) and pdir.name not in kept:
            shutil.rmtree(pdir, ignore_errors=True)

    clean_images(report_dir)
    brand_accent = cover_colors(spec.get("cover") or {}, pal)["accent"]
    spec = dict(spec, _brandAccent=brand_accent)
    res = FieldResolver(model)
    canvas = spec.get("canvas", {})
    width, height = canvas.get("width", 1280), canvas.get("height", 720)
    header_h = canvas.get("headerHeight", 80)
    vc = versions["visualContainer"]

    cover = spec.get("cover") or None
    if cover and cover.get("enabled") is False:
        cover = None
    tooltip = spec.get("tooltips") if spec.get("tooltips") and spec["tooltips"].get("measures") else None
    toggle = spec.get("themeToggle", True) and pal.get("mode") != "dark"
    modes = ["light", "dark"] if toggle else [pal.get("mode", "light")]
    pals = {"light": pal, "dark": dark_palette(pal)} if toggle else {modes[0]: pal}
    off = {"light": 0, "dark": 50}

    def ids(mode):
        o = off[mode]
        return {"cover": "%s%02dportada" % (MANAGED_PREFIX, o),
                "tip": "%s%02dtooltip" % (MANAGED_PREFIX, 90 + (1 if mode == "dark" else 0)),
                "pages": [("%s%02d%s" % (MANAGED_PREFIX, o + i, _slug(p["name"])), p) for i, p in enumerate(spec["pages"], 1)]}

    def write(pdir, items, P, dark):
        for i, (v, x, y, w, h) in enumerate(items, 1):
            vname = _id(pdir.name, i, v.get("type"), v.get("title", ""), v.get("text", ""))
            vj = build_visual(v, vname, (int(x), int(y), int(w), int(h)), i * 1000, res, P, vc)
            if dark:
                single = len(_as_list(v.get("values"))) <= 1 and not v.get("series") and v.get("type") not in ("combo",)
                apply_dark(vj, P, single_series=single)
            _write_json(pdir / "visuals" / vname / "visual.json", vj)
        return len(items)

    order, hidden = [], []
    for mode in modes:
        P = pals[mode]
        dark = mode == "dark" and toggle
        I = ids(mode)
        other = ids("light" if mode == "dark" else "dark") if toggle else I
        content = I["pages"]
        if cover:
            pdir = pages_dir / I["cover"]
            img = None
            if cover.get("background", "aurora") != "none":
                from backgrounds import cover_png
                img = "Portada_%s.png" % pal.get("id", "tema")
                if mode == modes[0]:
                    register_image(report_dir, img, cover_png(pal, style=cover.get("background", "aurora"),
                                                              accent=cover_colors(cover, pal)["accent"]))
            _write_json(pdir / "page.json", _page_json(I["cover"], cover.get("name", "Portada"), width, height,
                                                       pal["header"], versions, image=img, hidden=dark))
            n = write(pdir, _cover_visuals(cover, spec, pal, [(pid, p["name"]) for pid, p in content], width, height,
                                           {"mode": mode, "otherCover": other["cover"]}), pal, False)
            log("  + portada %s (%d visuales)" % (mode, n))
            (hidden if dark else order).append(I["cover"])
        entries = ([("Inicio", I["cover"])] if cover else []) + [(p["name"], pid) for pid, p in content]
        page_img = None
        if spec.get("pageBackground", True):
            from backgrounds import page_png
            page_img = "Fondo_%s_%s.png" % (pal.get("id", "tema"), mode)
            register_image(report_dir, page_img, page_png(P, brand_accent, header_h / height))
        for k, (pid, page) in enumerate(content):
            ph = page.get("height", height)
            pdir = pages_dir / pid
            _write_json(pdir / "page.json", _page_json(pid, page["name"], width, ph, P["background"], versions,
                                                       display="FitToPage" if ph <= height else "FitToWidth", hidden=dark,
                                                       image=page_img if ph == height else None))
            hh = header_h if page.get("header", True) else 0
            n = 0
            if hh:
                hv = header_visual(page, spec, P, width, hh, vc, pid, transparent=bool(page_img) and ph == height)
                _write_json(pdir / "visuals" / hv["name"] / "visual.json", hv)
                n += 1
            items = []
            for (v, x, y, w, h) in layout_page(page, width, ph, hh):
                v = dict(v)
                if tooltip and v.get("tooltip", True) is not False:
                    v["_tooltipPage"] = I["tip"]
                items.append((v, x, y, w, h))
            for (v, x, y, w, h) in list(items):
                if v.get("type") == "card" and not v.get("background"):
                    items.append(({"type": "text", "text": "", "background": brand_accent}, x, y, w, 4))
            if hh and page.get("navigation", spec.get("navigation", True)):
                slicers = any(it[0].get("type") == "slicer" for it in items)
                items += _nav_items(P, hh, width, entries, pid, other["pages"][k][0] if toggle else pid,
                                    mode == "light", slicers) if toggle else \
                    _nav_items(P, hh, width, entries, pid, pid, True, slicers)[1:]
            n += write(pdir, items, P, dark)
            log("  + pagina '%s' [%s] (%d visuales)" % (page["name"], mode, n))
            (hidden if dark else order).append(pid)
        if tooltip:
            tw, th = tooltip.get("width", 320), tooltip.get("height", 240)
            pdir = pages_dir / I["tip"]
            _write_json(pdir / "page.json", _page_json(I["tip"], tooltip.get("name", "Tooltip KPIs") + (" (oscuro)" if dark else ""),
                                                       tw, th, P["background"], versions, ptype="Tooltip", hidden=True,
                                                       display="ActualSize"))
            write(pdir, _tooltip_visuals(tooltip, tw, th), P, dark)
            hidden.append(I["tip"])
    if toggle:
        log("  + selector de tema claro/oscuro (%d paginas oscuras ocultas)" % len([h for h in hidden if "tooltip" not in h]))

    meta["$schema"] = "%s/pagesMetadata/%s/schema.json" % (SCHEMA_BASE, versions["pagesMetadata"])
    meta["pageOrder"] = order + kept + hidden
    meta["activePageName"] = order[0] if order else (kept[0] if kept else None)
    _write_json(meta_path, meta)
    return order
