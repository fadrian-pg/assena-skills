"""
ASSENA Power BI Studio - borrador automatico de especificacion (spec) a partir
del modelo (y opcionalmente del perfil de datos).

El borrador es un punto de partida solido; Claude lo revisa y lo ajusta al
dominio de negocio antes de aplicarlo (ver SKILL.md, paso 4).
"""
from __future__ import annotations

import re
import time

from pbip_model import NUMERIC_TYPES, looks_like_key, tmdl_quote
from themes import get_palette

MONEY = r"(venta|monto|importe|valor|total|costo|coste|precio|ingreso|margen|utilidad|ganancia|subtotal|neto|bruto|pago|saldo|deuda|presupuesto|gasto|amount|sales|revenue|cost|price|profit|budget|spend|balance)"
QTY = r"(cantidad|unidades|qty|quantity|units|piezas|cajas|kilos|kg|litros|volumen)"
PRIORITY = [r"venta|sales|revenue|ingreso", r"total|monto|importe|valor|amount|neto|subtotal", QTY, r"costo|cost",
            r"margen|utilidad|profit|ganancia", r"descuento|discount", r"precio|price"]
CAT_HINTS = r"(categor|linea|línea|familia|grupo|marca|brand|segment|canal|channel|region|región|zona|provincia|ciudad|city|country|pais|país|sucursal|tienda|store|almacen|bodega|vendedor|asesor|seller|rep|tipo|type|estado|status|area|área|departamento|cargo|proveedor|supplier)"
DESC_HINTS = r"(cliente|customer|producto|product|articulo|artículo|item|sku|proveedor|supplier|nombre|name|descripcion|descripción)"
GEO_HINTS = r"(ciudad|city|provincia|state|pais|país|country|region|región|canton|cantón)"
DATE_HINTS = r"(fecha|date|emision|emisión|pedido|factura|venta|registro|creacion|creación)"


def _q(table: str, col: str) -> str:
    t = table if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", table) else "'%s'" % table.replace("'", "''")
    return "%s[%s]" % (t, col)


def _score(name: str, patterns) -> int:
    n = name.lower()
    for i, p in enumerate(patterns):
        if re.search(p, n):
            return len(patterns) - i
    return 0


def _profile_col(profile: dict, table: str, col: str) -> dict:
    for t in (profile or {}).get("tables", []):
        if t.get("table", "").split(".")[-1].lower() == table.lower() or t.get("modelTable", "").lower() == table.lower():
            for c in t["columns"]:
                if c["column"].lower() == col.lower():
                    return c
    return {}


def draft_spec(summary: dict, profile: dict | None = None, palette: str = "corporativo", title: str | None = None,
               insights: dict | None = None) -> dict:
    tables = [t for t in summary["tables"] if t["roleGuess"] != "calculated" and not t["isDateTable"]]
    if not tables:
        raise ValueError("El modelo no tiene tablas de datos")
    rels = summary["relationships"]

    def numeric_cols(t):
        out = []
        for c in t["columns"]:
            if c.get("dataType") in NUMERIC_TYPES and not looks_like_key(c["name"]) and not c.get("isHidden") \
                    and c.get("summarizeBy") != "none":
                if _profile_col(profile, t["name"], c["name"]).get("roleHint") == "key":
                    continue
                out.append(c["name"])
        return out

    def date_cols(t):
        return [c["name"] for c in t["columns"] if c.get("dataType") == "dateTime"]

    def score_fact(t):
        from_side = sum(1 for r in rels if r.startswith(t["name"] + "[") or r.startswith("'%s'[" % t["name"]))
        return len(numeric_cols(t)) * 2 + from_side * 3 + (2 if date_cols(t) else 0) + (3 if t["roleGuess"] == "fact" else 0)

    fact = max(tables, key=score_fact)
    F = fact["name"]
    nums = sorted(numeric_cols(fact), key=lambda c: -_score(c, PRIORITY))[:4]
    dcols = sorted(date_cols(fact), key=lambda c: -_score(c, [DATE_HINTS]))
    fact_date = dcols[0] if dcols else None

    # tabla calendario
    model_spec = {"measures": [], "relationships": []}
    date_table = next((t for t in summary["tables"] if t["isDateTable"]), None)
    if date_table:
        cal_name = date_table["name"]
        cal_date = next((c["name"] for c in date_table["columns"] if c.get("dataType") == "dateTime"), "Fecha")
        cal_cols = {c["name"] for c in date_table["columns"]}
        year_col = next((c for c in ("Año", "Anio", "Year", "Ano") if c in cal_cols), None)
        ym_col = next((c for c in ("Año Mes", "AñoMes", "YearMonth", "Mes Año") if c in cal_cols), None)
    elif fact_date:
        cal_name, cal_date, year_col, ym_col = "Calendario", "Fecha", "Año", "Año Mes"
        mstart_col = "Mes Inicio"  # eje continuo mensual (sin barra de desplazamiento)
        model_spec["calendar"] = {"name": cal_name, "rangeFrom": _q(F, fact_date), "relateTo": [_q(F, fact_date)]}
    else:
        cal_name = cal_date = year_col = ym_col = None
    if date_table or not fact_date:
        mstart_col = None

    # medidas
    measures = []

    def add(name, expr, fmt, folder="KPIs", desc=None):
        measures.append({"table": F, "name": name, "expression": expr, "formatString": fmt, "displayFolder": folder,
                         "description": desc})
        return "[%s]" % name

    main = None
    measure_refs = []
    for c in nums:
        money = re.search(MONEY, c.lower()) and not re.search(QTY, c.lower())
        # nunca usar el mismo nombre que una columna (Power BI no lo permite)
        label = ("Suma %s" % c) if re.match(r"(?i)^total", c) else ("Total %s" % c)
        ref = add(label, "SUM ( %s )" % _q(F, c), r"\$#,0" if money else "#,0",
                  desc="Suma de %s" % c)
        measure_refs.append((ref, bool(money), c))
        if main is None:
            main = ref
    tx = add("Transacciones", "COUNTROWS ( %s )" % tmdl_quote(F), "#,0", desc="Numero de registros de %s" % F)
    if main is None:
        main = tx
    money_main = measure_refs[0][1] if measure_refs else False
    ticket = None
    if measure_refs and money_main:
        ticket = add("Ticket Promedio", "DIVIDE ( %s, %s )" % (main, tx), r"\$#,0.00", desc="Valor promedio por transaccion")
    ly = var = None
    if cal_name and main != tx:
        mname = main.strip("[]")
        ly = add("%s AA" % mname, "CALCULATE ( %s, SAMEPERIODLASTYEAR ( %s ) )" % (main, _q(cal_name, cal_date)),
                 r"\$#,0" if money_main else "#,0", "Tiempo", "Mismo periodo del año anterior")
        var = add("Var %% %s vs AA" % mname, "VAR _a = %s\nVAR _b = %s\nRETURN\n    IF ( NOT ISBLANK ( _b ), DIVIDE ( _a - _b, _b ) )" % (main, ly),
                  "0.0%;-0.0%;0.0%", "Tiempo", "Variacion porcentual contra el año anterior")
    sales = next((r for r, _, c in measure_refs if re.search(r"venta|sales|revenue|ingreso|total|monto|importe", c.lower())), None)
    cost = next((r for r, _, c in measure_refs if re.search(r"costo|cost", c.lower())), None)
    margin_pct = None
    if sales and cost and sales != cost:
        mg = add("Margen", "%s - %s" % (sales, cost), r"\$#,0", desc="Ventas menos costo")
        margin_pct = add("Margen %", "DIVIDE ( %s, %s )" % (mg, sales), "0.0%", desc="Margen sobre ventas")
    model_spec["measures"] = [{k: v for k, v in m.items() if v} for m in measures]

    # categorias: columnas texto de dimensiones relacionadas + de la propia fact
    related = set()
    for r in rels:
        m = re.match(r"^'?(.+?)'?\[.*\] -> '?(.+?)'?\[", r)
        if m and m.group(1) == F:
            related.add(m.group(2))
    cands = []
    for t in summary["tables"]:
        if t["name"] != F and t["name"] not in related:
            continue
        if t["isDateTable"]:
            continue
        for c in t["columns"]:
            if c.get("dataType") != "string" or c.get("isHidden") or looks_like_key(c["name"]):
                continue
            prof = _profile_col(profile, t["name"], c["name"])
            distinct = prof.get("distinct")
            s = 0
            if re.search(CAT_HINTS, c["name"].lower()):
                s += 5
            if re.search(DESC_HINTS, c["name"].lower()):
                s += 3
            if distinct is not None:
                s += 4 if 2 <= distinct <= 30 else (1 if distinct <= 200 else -3)
            cands.append({"ref": _q(t["name"], c["name"]), "name": c["name"], "score": s, "distinct": distinct,
                          "geo": bool(re.search(GEO_HINTS, c["name"].lower())),
                          "desc": bool(re.search(DESC_HINTS, c["name"].lower()))})
    cands.sort(key=lambda c: -c["score"])
    cats = [c for c in cands if not c["desc"]] or cands
    descs = [c for c in cands if c["desc"]]
    low = next((c for c in cats if c["distinct"] is not None and c["distinct"] <= 8), cats[0] if cats else None)
    cat1 = next((c for c in cats if c is not low), low)
    cat2 = next((c for c in cats if c is not cat1 and c is not low), None)
    top_desc = descs[0] if descs else None
    geo = next((c for c in cands if c["geo"]), None)

    # ---------------- paginas ----------------
    slicers = []
    if year_col:
        slicers.append({"type": "slicer", "field": _q(cal_name, year_col), "title": "Año", "mode": "Dropdown"})
    for c in [x for x in (cat1, cat2) if x][:2]:
        slicers.append({"type": "slicer", "field": c["ref"], "title": c["name"], "mode": "Dropdown"})
    if len(slicers) < 4 and cal_name and not date_table:
        slicers.append({"type": "slicer", "field": _q(cal_name, "Mes"), "title": "Mes", "mode": "Dropdown"})
    slicers = slicers[:4]
    for s in slicers:
        s["span"] = 3

    kpis = [{"type": "card", "values": main, "label": True}]
    if var:
        kpis.append({"type": "card", "values": var, "label": True})
    kpis.append({"type": "card", "values": tx, "label": True})
    if margin_pct:
        kpis.append({"type": "card", "values": margin_pct, "label": True})
    elif ticket:
        kpis.append({"type": "card", "values": ticket, "label": True})
    elif len(measure_refs) > 1:
        kpis.append({"type": "card", "values": measure_refs[1][0], "label": True})
    for k in kpis:
        k["span"] = 12 // len(kpis)

    mname = main.strip("[]")
    rows1 = []
    if slicers:
        rows1.append({"height": 60, "visuals": slicers})
    rows1.append({"height": 96, "visuals": kpis})
    r3 = []
    if ym_col:
        trend = {"type": "line", "title": "Tendencia mensual de %s" % mname, "category": _q(cal_name, mstart_col or ym_col),
                 "values": [main] + ([ly] if ly else []), "span": 8 if low else 12}
        r3.append(trend)
    if low:
        r3.append({"type": "donut", "title": "%s por %s" % (mname, low["name"]), "category": low["ref"],
                   "values": main, "span": 4 if r3 else 12})
    if r3:
        rows1.append({"visuals": r3})
    r4 = []
    if cat1:
        r4.append({"type": "bar", "title": "%s por %s" % (mname, cat1["name"]), "category": cat1["ref"],
                   "values": main, "sort": "desc", "span": 6})
    if top_desc:
        r4.append({"type": "bar", "title": "Top %s por %s" % (top_desc["name"], mname), "category": top_desc["ref"],
                   "values": main, "sort": "desc", "span": 6})
    elif cat2:
        r4.append({"type": "column", "title": "%s por %s" % (mname, cat2["name"]), "category": cat2["ref"],
                   "values": main, "sort": "desc", "span": 6})
    if r4:
        rows1.append({"visuals": r4})

    pages = [{"name": "Panorama General", "title": "Panorama General",
              "subtitle": "Indicadores clave y tendencias", "rows": rows1}]

    rows2 = []
    if slicers:
        rows2.append({"height": 60, "visuals": [dict(s) for s in slicers]})
    if ym_col:
        rows2.append({"visuals": [{"type": "combo", "title": "%s mensual vs año anterior" % mname,
                                   "category": _q(cal_name, ym_col), "columns": main,
                                   "lines": ly or tx, "span": 12}]})
    detail = []
    mrows = [c["ref"] for c in (cat1, cat2) if c]
    if mrows:
        vals = [main] + ([ly, var] if ly else []) + [tx]
        detail.append({"type": "matrix", "title": "Detalle por %s" % " / ".join(c["name"] for c in (cat1, cat2) if c),
                       "rows": mrows, "values": vals, "span": 7})
    if geo:
        # Los mapas Bing estan obsoletos en Power BI; se usa barra ordenada por zona geografica
        detail.append({"type": "bar", "title": "%s por %s" % (mname, geo["name"]), "category": geo["ref"],
                       "values": main, "sort": "desc", "span": 5})
    elif cat2 or low:
        c = cat2 or low
        detail.append({"type": "treemap", "title": "Participacion por %s" % c["name"], "category": c["ref"],
                       "values": main, "span": 5})
    if detail:
        rows2.append({"visuals": detail})
    if len(rows2) > (1 if slicers else 0):
        pages.append({"name": "Analisis Detallado", "title": "Análisis Detallado",
                      "subtitle": "Comparativos y desglose", "rows": rows2})

    # ---------------- formato condicional ----------------
    pal = get_palette(palette)
    if var:
        cvar = add("Color %s" % var.strip("[]"), 'IF ( %s >= 0, "%s", "%s" )' % (var, pal["good"], pal["bad"]),
                   None, "Formato", "Color semaforo para la variacion (verde/rojo)")
        for pg in pages:
            for r in pg["rows"]:
                for v in r["visuals"]:
                    if v.get("type") == "card" and v.get("values") == var:
                        v["colorMeasure"] = cvar

    # ---------------- narrativa dinamica (Resumen IA) ----------------
    lead = cat1 or low
    top_m = share_m = best_m = None
    if lead:
        col = lead["ref"]
        top_m = add("Lider %s" % lead["name"],
                    "VAR _t = TOPN ( 1, ALLSELECTED ( %s ), %s )\nRETURN CONCATENATEX ( _t, %s, \", \" )" % (col, main, col),
                    None, "Narrativa", "Elemento con mayor %s segun filtros" % mname)
        share_m = add("%% Lider %s" % lead["name"],
                      "DIVIDE (\n    CALCULATE ( %s, TOPN ( 1, ALLSELECTED ( %s ), %s ) ),\n    CALCULATE ( %s, ALLSELECTED ( %s ) )\n)"
                      % (main, col, main, main, col), "0.0%", "Narrativa", "Participacion del lider")
    if ym_col:
        ymref = _q(cal_name, ym_col)
        best_m = add("Mejor Mes", "VAR _t = TOPN ( 1, ALLSELECTED ( %s ), %s )\nRETURN CONCATENATEX ( _t, %s, \", \" )"
                     % (ymref, main, ymref), None, "Narrativa", "Mes con mayor %s" % mname)
    model_spec["measures"] = [{k: v for k, v in m.items() if v} for m in measures]

    H, M = "@title", "@muted"
    narr = [{"text": "Resumen ejecutivo", "size": 14, "bold": True, "color": H},
            {"text": "En el periodo seleccionado, %s suma {%s} en {%s} transacciones%s." % (
                mname, main, tx, (", con un ticket promedio de {%s}" % ticket) if ticket else "")}]
    if var:
        narr.append({"text": "Frente al mismo periodo del año anterior, la variacion es de {%s}." % var})
    if margin_pct:
        narr.append({"text": "El margen se ubica en {%s}." % margin_pct})
    if top_m:
        narr.append({"text": "Por %s, lidera {%s}, que concentra {%s} del total." % (lead["name"].lower(), top_m, share_m)})
    if best_m:
        narr.append({"text": "El mes con mejor desempeño fue {%s}." % best_m})
    narr.append({"text": "Las cifras de este resumen se recalculan con los filtros del informe.", "size": 9, "color": M})

    hl = [{"text": "Hallazgos y recomendaciones (IA)", "size": 14, "bold": True, "color": H}]
    bullets = insight_bullets(insights) if insights else [
        "Ejecuta 'assena_bi.py insights' para que la IA redacte los hallazgos con los datos reales."]
    hl += [{"text": t, "bullet": True, "size": 11} for t in bullets]
    stamp = "Analisis generado con IA · ASSENA Power BI Studio · %s" % time.strftime("%d/%m/%Y")
    if insights and insights.get("dateRange"):
        stamp += " · datos hasta %s" % insights["dateRange"][1]
    hl.append({"text": stamp, "size": 8, "color": M})
    ai_rows = []
    if slicers:
        ai_rows.append({"height": 60, "visuals": [dict(s) for s in slicers]})
    ai_rows.append({"height": 96, "visuals": [dict(k) for k in kpis]})
    ai_rows.append({"height": 210, "visuals": [
        {"type": "text", "paragraphs": narr, "span": 6, "altText": "Resumen ejecutivo dinamico"},
        {"type": "text", "paragraphs": hl, "span": 6, "altText": "Hallazgos y recomendaciones"}]})
    support = []
    if ym_col:
        support.append({"type": "area", "title": "Evolucion mensual de %s" % mname, "category": _q(cal_name, mstart_col or ym_col),
                        "values": main, "span": 7})
    if lead:
        support.append({"type": "bar", "title": "%s por %s" % (mname, lead["name"]), "category": lead["ref"],
                        "values": main, "sort": "desc", "span": 5 if support else 12})
    if support:
        ai_rows.append({"visuals": support})
    pages.insert(0, {"name": "Informe Ejecutivo IA", "title": "Informe Ejecutivo", "subtitle": "Resumen generado con IA",
                     "rows": ai_rows})

    cover_kpis = [main] + ([var] if var else []) + [margin_pct or ticket or tx]
    return {
        "title": title or "Dashboard %s" % F,
        "subtitle": "Tablero interactivo de %s" % F.lower(),
        "palette": palette,
        "canvas": {"width": 1280, "height": 720, "headerHeight": 80},
        "cover": {"title": title or "Dashboard %s" % F, "subtitle": "Tablero interactivo de %s" % F.lower(),
                  "description": "Explora los indicadores clave, tendencias y el detalle por categoria. "
                                 "Usa los botones para navegar y los filtros de cada pagina para profundizar.",
                  "kpis": cover_kpis,
                  "eyebrow": "Tablero ejecutivo · %s" % F,
                  "trend": ({"category": _q(cal_name, mstart_col or ym_col), "values": main} if ym_col else None)},
        "themeToggle": True,
        "navigation": True,
        "tooltips": {"measures": [m for m in [main, var, tx, margin_pct or ticket] if m][:4]},
        "model": model_spec,
        "pages": pages,
        "_notes": {
            "factTable": F, "dateColumn": fact_date, "numericColumns": nums,
            "costColumn": next((c for c in nums if re.search(r"costo|cost", c.lower())), None),
            "categories": [c["ref"] for c in cands[:8]],
            "review": "Revisa nombres de medidas, formatos y titulos. Ejecuta 'insights' y reescribe los hallazgos "
                      "de la pagina 'Informe Ejecutivo IA' con lenguaje de negocio.",
        },
    }


def _money(v):
    return "$%s" % format(round(v), ",") if v is not None else "-"


def insight_bullets(ins: dict) -> list:
    """Hallazgos y recomendaciones redactados por reglas a partir de insights.json.
    Claude los reescribe/afina en el Paso 4 del skill."""
    b, recs = [], []
    if ins.get("dateRange"):
        b.append("Acumulado de %s entre %s y %s (%s registros)." % (_money(ins["total"]), ins["dateRange"][0],
                                                                   ins["dateRange"][1], format(ins["rows"], ",")))
    y = ins.get("ytdComparison")
    if y and y.get("growthPct") is not None:
        g = y["growthPct"]
        b.append("En %s (hasta el mes %d) el resultado %s %.1f%% frente al mismo periodo del año anterior." % (
            y["year"], y["throughMonth"], "crece" if g >= 0 else "cae", abs(g)))
        if g < 0:
            recs.append("Revisar las causas de la caida interanual por categoria y cliente.")
    m = ins.get("months")
    if m:
        b.append("Mejor mes: %s (%s); mes mas bajo: %s (%s)." % (m["best"][0], _money(m["best"][1]),
                                                               m["worst"][0], _money(m["worst"][1])))
        if m.get("last3VsAveragePct") is not None:
            p = m["last3VsAveragePct"]
            b.append("Los ultimos 3 meses completos estan %.1f%% %s del promedio mensual."
                     % (abs(p), "por encima" if p >= 0 else "por debajo"))
            if p < -5:
                recs.append("La tendencia reciente esta bajo el promedio: activar acciones comerciales de corto plazo.")
    for name, c in list(ins.get("categories", {}).items())[:3]:
        if not c["top"]:
            continue
        t = c["top"][0]
        txt = "%s: lidera '%s' con %.1f%% del total" % (name, t["name"], t["sharePct"] or 0)
        if c["distinct"] >= 10:
            txt += "; el 20%% superior concentra %.1f%%" % (c["top20PctShare"] or 0)
        b.append(txt + ".")
        if (c["top20PctShare"] or 0) >= 70 and c["distinct"] >= 10:
            recs.append("Alta concentracion en %s: diversificar para reducir dependencia." % name.lower())
        if c.get("marginWorst") and ins.get("marginPct") is not None and c["marginWorst"][-1][1] < ins["marginPct"] - 5:
            w = c["marginWorst"][-1]
            recs.append("Revisar precios/costos en %s '%s' (margen %.1f%%)." % (name.lower(), w[0], w[1]))
    if ins.get("marginPct") is not None:
        b.append("Margen global: %.1f%%." % ins["marginPct"])
    return b[:6] + ["Recomendacion: " + r for r in recs[:3]]
