"""
ASSENA Power BI Studio - generacion de temas JSON de Power BI a partir de paletas.
"""
from __future__ import annotations

import json
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"
FONT = "Segoe UI"
FONT_SEMI = "Segoe UI Semibold"


def load_palettes() -> dict:
    data = json.loads((ASSETS / "palettes.json").read_text(encoding="utf-8"))
    data.pop("_info", None)
    return data


def get_palette(name: str, overrides: dict | None = None) -> dict:
    pals = load_palettes()
    if name not in pals:
        raise KeyError("Paleta '%s' no existe. Disponibles: %s" % (name, ", ".join(pals)))
    p = dict(pals[name])
    p["id"] = name
    if overrides:
        p.update({k: v for k, v in overrides.items() if v})
    return p


def _solid(c):
    return {"solid": {"color": c}}


def build_theme(p: dict, theme_name: str) -> dict:
    """Tema de informe Power BI (formato JSON documentado por Microsoft)."""
    return {
        "name": theme_name,
        "dataColors": p["dataColors"],
        "background": p["surface"],
        "secondaryBackground": p["background"],
        "foreground": p["text"],
        "foregroundNeutralSecondary": p["textMuted"],
        "tableAccent": p["dataColors"][0],
        "good": p["good"], "neutral": p["neutral"], "bad": p["bad"],
        "maximum": p["max"], "center": p["center"], "minimum": p["min"],
        "textClasses": {
            "callout": {"fontSize": 26, "fontFace": FONT_SEMI, "color": p["text"]},
            "title": {"fontSize": 12, "fontFace": FONT_SEMI, "color": p["text"]},
            "header": {"fontSize": 12, "fontFace": FONT_SEMI, "color": p["text"]},
            "label": {"fontSize": 10, "fontFace": FONT, "color": p["textMuted"]},
        },
        "visualStyles": {
            "*": {"*": {
                "background": [{"show": True, "color": _solid(p["surface"]), "transparency": 0}],
                "border": [{"show": True, "color": _solid(p["border"]), "radius": 6}],
                "dropShadow": [{"show": p["mode"] == "light", "color": _solid("#0F172A"), "transparency": 92,
                                "position": "Outer", "preset": "Custom", "shadowSpread": 0, "shadowBlur": 10,
                                "angle": 90, "shadowDistance": 2}],
                "padding": [{"top": 10, "bottom": 10, "left": 12, "right": 12}],
                "title": [{"show": True, "fontColor": _solid(p["text"]), "fontSize": 11, "fontFamily": FONT_SEMI,
                           "alignment": "left", "titleWrap": True}],
                "subTitle": [{"fontColor": _solid(p["textMuted"]), "fontSize": 9, "fontFamily": FONT}],
                "visualHeader": [{"show": True, "background": _solid(p["surface"]), "foreground": _solid(p["textMuted"]),
                                  "transparency": 0}],
                "visualTooltip": [{"titleFontColor": _solid(p["textMuted"]), "valueFontColor": _solid(p["text"]),
                                   "background": _solid(p["surface"])}],
                "categoryAxis": [{"labelColor": _solid(p["textMuted"]), "fontSize": 9, "fontFamily": FONT,
                                  "showAxisTitle": False, "gridlineShow": False}],
                "valueAxis": [{"labelColor": _solid(p["textMuted"]), "fontSize": 9, "fontFamily": FONT,
                               "showAxisTitle": False, "gridlineColor": _solid(p["border"]), "gridlineStyle": "dotted"}],
                "legend": [{"show": True, "position": "Top", "labelColor": _solid(p["textMuted"]), "fontSize": 9,
                            "fontFamily": FONT}],
                "labels": [{"color": _solid(p["text"]), "fontSize": 9, "fontFamily": FONT}],
            }},
            "page": {"*": {
                "background": [{"color": _solid(p["background"]), "transparency": 0}],
                "outspace": [{"color": _solid(p["background"]), "transparency": 0}],
            }},
            "card": {"*": {
                "labels": [{"color": _solid(p["text"]), "fontSize": 26, "fontFamily": FONT_SEMI}],
                "categoryLabels": [{"show": True, "color": _solid(p["textMuted"]), "fontSize": 10, "fontFamily": FONT}],
                "title": [{"show": False}],
                "border": [{"show": True, "color": _solid(p["border"]), "radius": 6}],
            }},
            "multiRowCard": {"*": {
                "cardTitle": [{"color": _solid(p["text"]), "fontSize": 13}],
                "dataLabels": [{"color": _solid(p["text"]), "fontSize": 14}],
                "categoryLabels": [{"color": _solid(p["textMuted"]), "fontSize": 9}],
            }},
            "slicer": {"*": {
                "header": [{"show": True, "fontColor": _solid(p["textMuted"]), "textSize": 9, "fontFamily": FONT_SEMI,
                            "outline": "None"}],
                "items": [{"fontColor": _solid(p["text"]), "textSize": 10, "fontFamily": FONT,
                           "background": _solid(p["surface"]), "outline": "None"}],
                "title": [{"show": False}],
                "padding": [{"top": 4, "bottom": 4, "left": 8, "right": 8}],
            }},
            "tableEx": {"*": {
                "grid": [{"gridVertical": False, "gridHorizontal": True, "gridHorizontalColor": _solid(p["border"]),
                          "rowPadding": 4, "textSize": 9}],
                "columnHeaders": [{"fontColor": _solid(p["headerText"]), "backColor": _solid(p["header"]),
                                   "fontFamily": FONT_SEMI, "fontSize": 9}],
                "values": [{"fontColorPrimary": _solid(p["text"]), "backColorPrimary": _solid(p["surface"]),
                            "fontColorSecondary": _solid(p["text"]), "backColorSecondary": _solid(p["background"]),
                            "fontSize": 9}],
                "total": [{"fontColor": _solid(p["text"]), "backColor": _solid(p["border"]), "fontFamily": FONT_SEMI}],
            }},
            "pivotTable": {"*": {
                "grid": [{"gridVertical": False, "gridHorizontal": True, "gridHorizontalColor": _solid(p["border"]),
                          "rowPadding": 4, "textSize": 9}],
                "columnHeaders": [{"fontColor": _solid(p["headerText"]), "backColor": _solid(p["header"]),
                                   "fontFamily": FONT_SEMI, "fontSize": 9}],
                "rowHeaders": [{"fontColor": _solid(p["text"]), "fontSize": 9}],
                "values": [{"fontColorPrimary": _solid(p["text"]), "backColorPrimary": _solid(p["surface"]),
                            "fontColorSecondary": _solid(p["text"]), "backColorSecondary": _solid(p["background"]),
                            "fontSize": 9}],
                "subTotals": [{"fontColor": _solid(p["text"]), "backColor": _solid(p["background"])}],
                "total": [{"fontColor": _solid(p["text"]), "backColor": _solid(p["border"]), "fontFamily": FONT_SEMI}],
            }},
            "lineChart": {"*": {
                "lineStyles": [{"strokeWidth": 3, "lineChartType": "smooth", "showMarker": False}],
            }},
            "areaChart": {"*": {
                "lineStyles": [{"strokeWidth": 2, "lineChartType": "smooth"}],
            }},
            "donutChart": {"*": {
                "slices": [{"innerRadiusRatio": 65}],
                "legend": [{"show": True, "position": "Right"}],
                "labels": [{"show": True, "labelStyle": "Percent of total", "color": _solid(p["text"])}],
            }},
            "textbox": {"*": {
                "background": [{"show": False}], "border": [{"show": False}], "dropShadow": [{"show": False}],
                "visualHeader": [{"show": False}],
                "padding": [{"top": 0, "bottom": 0, "left": 0, "right": 0}],
            }},
        },
    }


def theme_file_name(p: dict) -> str:
    return "Tema_%s.json" % "".join(w.capitalize() for w in p["id"].split("-"))
