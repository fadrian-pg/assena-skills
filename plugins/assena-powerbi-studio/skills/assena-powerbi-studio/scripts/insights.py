"""
ASSENA Power BI Studio - motor de hallazgos para el Resumen Ejecutivo IA.

Lee los datos reales (CSV local o BD SQL en solo lectura), une la tabla de
hechos con sus dimensiones y calcula hechos cuantitativos: totales, evolucion
anual y mensual, mejores/peores meses, lideres por categoria, concentracion
(Pareto) y margen. Claude usa este JSON para redactar el resumen ejecutivo y las
recomendaciones que se insertan en el informe.
"""
from __future__ import annotations

import csv
import datetime as dt
from collections import defaultdict
from pathlib import Path

from pbip_model import find_table

MAX_ROWS = 2_000_000


def _to_date(v):
    if isinstance(v, dt.datetime):
        return v
    if isinstance(v, dt.date):
        return dt.datetime(v.year, v.month, v.day)
    if isinstance(v, str):
        for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                return dt.datetime.strptime(v[:19], fmt)
            except ValueError:
                pass
    return None


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


class Reader:
    """Lee columnas de una tabla del modelo desde CSV o conexion SQL."""

    def __init__(self, model, conn=None, dialect=None):
        self.model, self.conn, self.dialect = model, conn, dialect

    def rows(self, table: str, cols: list) -> list:
        t = find_table(self.model, table)
        src = t["source"]
        if src.get("kind") == "csv":
            with open(src["server"], newline="", encoding="utf-8-sig") as fh:
                rd = csv.DictReader(fh)
                return [[r.get(c) for c in cols] for i, r in enumerate(rd) if i < MAX_ROWS]
        if self.conn is None:
            raise RuntimeError("La tabla %s viene de %s: indica la conexion (--trusted / --user ...)" % (table, src.get("kind")))
        import db_profile as dp
        if src.get("nativeQuery"):
            frm = "(%s) q" % src["nativeQuery"]
        else:
            obj = src.get("object") or table
            if src.get("schema") and self.dialect != "sqlite":
                obj = "%s.%s" % (src["schema"], obj)
            frm = dp._ident(obj, self.dialect)
        cl = ", ".join(dp._ident(c, self.dialect) for c in cols)
        top = "TOP %d " % MAX_ROWS if self.dialect == "mssql" else ""
        lim = "" if self.dialect == "mssql" else " LIMIT %d" % MAX_ROWS
        cur = self.conn.cursor()
        cur.execute("SELECT %s%s FROM %s%s" % (top, cl, frm, lim))
        return [list(r) for r in cur.fetchall()]


def compute(model, fact: str, date_col: str | None, value_col: str, categories: list, cost_col: str | None = None,
            reader: Reader | None = None) -> dict:
    reader = reader or Reader(model)
    # dimension lookups: categoria en otra tabla -> via relacion
    rel_map = {}
    for r in model["relationships"]:
        if r["fromColumn"]["table"].lower() == fact.lower():
            rel_map[r["toColumn"]["table"].lower()] = (r["fromColumn"]["column"], r["toColumn"]["column"])
    fact_cols = [c for c in [date_col, value_col, cost_col] if c]
    lookups = []  # (label, fact_key_col, mapping dict) o (label, fact_col, None)
    for ref in categories:
        t, c = ref.split("[", 1)
        t, c = t.strip().strip("'"), c.rstrip("]")
        if t.lower() == fact.lower():
            lookups.append((c, c, None))
            fact_cols.append(c)
        elif t.lower() in rel_map:
            fk, pk = rel_map[t.lower()]
            mapping = {str(k): v for k, v in reader.rows(t, [pk, c])}
            lookups.append((c, fk, mapping))
            fact_cols.append(fk)
    fact_cols = list(dict.fromkeys(fact_cols))
    idx = {c: i for i, c in enumerate(fact_cols)}
    data = reader.rows(fact, fact_cols)

    total = cost = 0.0
    by_year, by_month = defaultdict(float), defaultdict(float)
    by_cat = {lbl: defaultdict(float) for lbl, _, _ in lookups}
    cost_cat = {lbl: defaultdict(float) for lbl, _, _ in lookups}
    dmin = dmax = None
    n = 0
    for r in data:
        v = _num(r[idx[value_col]])
        if v is None:
            continue
        n += 1
        total += v
        cv = _num(r[idx[cost_col]]) if cost_col else None
        if cv is not None:
            cost += cv
        if date_col:
            d = _to_date(r[idx[date_col]])
            if d:
                dmin = d if dmin is None or d < dmin else dmin
                dmax = d if dmax is None or d > dmax else dmax
                by_year[d.year] += v
                by_month["%04d-%02d" % (d.year, d.month)] += v
        for lbl, col, mapping in lookups:
            key = r[idx[col]]
            name = mapping.get(str(key), "(sin dato)") if mapping is not None else (key or "(sin dato)")
            by_cat[lbl][name] += v
            if cv is not None:
                cost_cat[lbl][name] += cv

    out = {"fact": fact, "metric": value_col, "rows": n, "total": round(total, 2),
           "average": round(total / n, 2) if n else None}
    if cost_col:
        out["cost"] = round(cost, 2)
        out["marginPct"] = round(100 * (total - cost) / total, 1) if total else None
    if dmin:
        out["dateRange"] = [dmin.strftime("%Y-%m-%d"), dmax.strftime("%Y-%m-%d")]
        years = sorted(by_year)
        out["byYear"] = [{"year": y, "total": round(by_year[y], 2)} for y in years]
        # comparacion año contra año en el mismo periodo (YTD comparable)
        if len(years) >= 2:
            last, prev = years[-1], years[-2]
            cut = (dmax.month, dmax.day)
            ytd_last = sum(v for k, v in by_month.items() if int(k[:4]) == last)
            ytd_prev = sum(v for k, v in by_month.items() if int(k[:4]) == prev and (int(k[5:]), 1) <= (cut[0], 1))
            out["ytdComparison"] = {"year": last, "throughMonth": dmax.month, "current": round(ytd_last, 2),
                                    "previousSamePeriod": round(ytd_prev, 2),
                                    "growthPct": round(100 * (ytd_last - ytd_prev) / ytd_prev, 1) if ytd_prev else None,
                                    "note": "El ultimo mes puede estar incompleto (datos hasta %s)" % dmax.strftime("%d/%m/%Y")}
        months = sorted(by_month.items())
        full = months[:-1] if len(months) > 2 else months  # excluir ultimo mes (posiblemente parcial)
        if full:
            best = max(full, key=lambda x: x[1])
            worst = min(full, key=lambda x: x[1])
            avg = sum(v for _, v in full) / len(full)
            out["months"] = {"count": len(months), "best": [best[0], round(best[1], 2)], "worst": [worst[0], round(worst[1], 2)],
                             "monthlyAverage": round(avg, 2),
                             "last3": [[k, round(v, 2)] for k, v in full[-3:]],
                             "last3VsAveragePct": round(100 * (sum(v for _, v in full[-3:]) / 3 - avg) / avg, 1) if avg else None}
    cats = {}
    for lbl, d in by_cat.items():
        items = sorted(d.items(), key=lambda x: -x[1])
        k = max(1, int(round(len(items) * 0.2)))
        info = {"distinct": len(items),
                "top": [{"name": str(nm), "total": round(v, 2), "sharePct": round(100 * v / total, 1) if total else None}
                        for nm, v in items[:5]],
                "bottom": [{"name": str(nm), "total": round(v, 2)} for nm, v in items[-3:]] if len(items) > 5 else [],
                "top20PctShare": round(100 * sum(v for _, v in items[:k]) / total, 1) if total else None}
        if cost_col and cost_cat[lbl]:
            mg = []
            for nm, v in items:
                c = cost_cat[lbl].get(nm, 0)
                if v:
                    mg.append((nm, round(100 * (v - c) / v, 1)))
            mg.sort(key=lambda x: -x[1])
            info["marginBest"] = mg[:3]
            info["marginWorst"] = mg[-3:]
        cats[lbl] = info
    out["categories"] = cats
    return out
