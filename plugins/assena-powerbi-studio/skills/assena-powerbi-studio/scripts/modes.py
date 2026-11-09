"""
ASSENA Power BI Studio - modo oscuro.

Power BI no cambia de tema en tiempo de ejecucion, asi que el skill genera cada
pagina en version clara y oscura; un boton alterna entre paginas equivalentes.
Este modulo deriva la variante oscura de una paleta y aplica overrides de color
a cada visual ya construido (fondos, ejes, leyendas, etiquetas, tablas...).
"""
from __future__ import annotations

from themes import get_palette

DARK_SERIES = get_palette("medianoche")  # serie validada para superficie oscura


def _rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def _hex(c):
    return "#%02X%02X%02X" % tuple(max(0, min(255, int(round(x)))) for x in c)


def mix(a, b, t):
    ca, cb = _rgb(a), _rgb(b)
    return _hex([ca[i] + (cb[i] - ca[i]) * t for i in range(3)])


def dark_palette(pal: dict) -> dict:
    """Variante oscura coherente con la paleta clara (mismo matiz de marca)."""
    if pal.get("mode") == "dark":
        return dict(pal)
    bg = mix("#0B1120", pal["header"], 0.35)
    d = dict(pal)
    d.update({
        "id": pal.get("id", "tema") + "-oscuro",
        "mode": "dark",
        "header": mix(pal["header"], "#000000", 0.45),
        "headerText": "#F8FAFC",
        "headerSubtext": pal["headerSubtext"],
        "background": bg,
        "surface": mix(bg, "#FFFFFF", 0.07),
        "border": mix(bg, "#FFFFFF", 0.16),
        "text": "#E5E9F0",
        "textMuted": "#9AA6B8",
        "accent": mix(pal["accent"], "#FFFFFF", 0.18),
        "dataColors": DARK_SERIES["dataColors"],
        "good": DARK_SERIES["good"], "neutral": DARK_SERIES["neutral"], "bad": DARK_SERIES["bad"],
        "min": DARK_SERIES["min"], "center": DARK_SERIES["center"], "max": DARK_SERIES["max"],
    })
    return d


def _lit(v):
    if isinstance(v, bool):
        s = "true" if v else "false"
    elif isinstance(v, (int, float)):
        s = "%sD" % v
    else:
        s = "'" + str(v).replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": s}}}


def _col(h):
    return {"solid": {"color": _lit(h)}}


def _merge(objs: dict, key: str, props: dict, overwrite=False):
    lst = objs.setdefault(key, [{"properties": {}}])
    target = next((x for x in lst if "selector" not in x), None)
    if target is None:
        target = {"properties": {}}
        lst.insert(0, target)
    for k, v in props.items():
        if overwrite or k not in target["properties"]:
            target["properties"][k] = v


CHARTS = {"clusteredColumnChart", "clusteredBarChart", "columnChart", "barChart", "hundredPercentStackedColumnChart",
          "lineChart", "areaChart", "lineClusteredColumnComboChart", "waterfallChart", "funnel", "scatterChart",
          "donutChart", "pieChart", "treemap"}


def apply_dark(vj: dict, d: dict, single_series: bool = False) -> dict:
    """Aplica colores oscuros a un visual.json construido para modo claro."""
    v = vj["visual"]
    t = v["visualType"]
    obj = v.setdefault("objects", {})
    cont = v.setdefault("visualContainerObjects", {})
    if t in ("textbox", "actionButton", "pageNavigator"):
        if not obj:
            v.pop("objects")
        return vj
    bg_set = "background" in cont and cont["background"][0]["properties"].get("transparency")
    if not bg_set:
        cont["background"] = [{"properties": {"show": _lit(True), "color": _col(d["surface"]), "transparency": _lit(0)}}]
        cont["border"] = [{"properties": {"show": _lit(True), "color": _col(d["border"]), "radius": _lit(10)}}]
        cont["dropShadow"] = [{"properties": {"show": _lit(False)}}]
    _merge(cont, "title", {"fontColor": _col(d["text"])})
    cont["visualHeader"] = [{"properties": {"background": _col(d["surface"]), "foreground": _col(d["textMuted"]),
                                            "border": _col(d["border"])}}]
    cont["visualTooltip"] = cont.get("visualTooltip") or [{"properties": {}}]
    _merge(cont, "visualTooltip", {"titleFontColor": _col(d["textMuted"]), "valueFontColor": _col(d["text"]),
                                   "background": _col(d["surface"])})
    if t in CHARTS:
        for ax in ("categoryAxis", "valueAxis"):
            _merge(obj, ax, {"labelColor": _col(d["textMuted"])})
        _merge(obj, "valueAxis", {"gridlineColor": _col(d["border"])})
        _merge(obj, "legend", {"labelColor": _col(d["textMuted"])})
        _merge(obj, "labels", {"color": _col(d["text"])})
        if single_series and "dataPoint" not in obj and t not in ("donutChart", "pieChart", "treemap"):
            obj["dataPoint"] = [{"properties": {"fill": _col(d["dataColors"][0])}}]
    elif t in ("card", "multiRowCard"):
        _merge(obj, "labels", {"color": _col(d["text"])})
        _merge(obj, "categoryLabels", {"color": _col(d["textMuted"])})
    elif t == "slicer":
        _merge(obj, "header", {"fontColor": _col(d["textMuted"])})
        _merge(obj, "items", {"fontColor": _col(d["text"]), "background": _col(d["surface"])})
    elif t in ("tableEx", "pivotTable"):
        _merge(obj, "values", {"fontColorPrimary": _col(d["text"]), "backColorPrimary": _col(d["surface"]),
                               "fontColorSecondary": _col(d["text"]), "backColorSecondary": _col(mix(d["surface"], "#FFFFFF", 0.04))})
        _merge(obj, "columnHeaders", {"fontColor": _col("#FFFFFF"), "backColor": _col(d["header"])})
        _merge(obj, "grid", {"gridHorizontalColor": _col(d["border"])})
        _merge(obj, "total", {"fontColor": _col(d["text"]), "backColor": _col(d["border"])})
        if t == "pivotTable":
            _merge(obj, "rowHeaders", {"fontColor": _col(d["text"])})
            _merge(obj, "subTotals", {"fontColor": _col(d["text"]), "backColor": _col(mix(d["surface"], "#FFFFFF", 0.04))})
    if not obj:
        v.pop("objects")
    return vj
