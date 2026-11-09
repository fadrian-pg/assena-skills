#!/usr/bin/env python3
"""
ASSENA Power BI Studio - CLI

  python assena_bi.py inspect  <proyecto.pbip>                 [--out model.json]
  python assena_bi.py profile  <proyecto.pbip> [opciones BD]   [--out profile.json]
  python assena_bi.py draft    <proyecto.pbip> [--profile p.json] [--palette X] [--title T] [--out spec.json]
  python assena_bi.py apply    <proyecto.pbip> --spec spec.json [--replace-all] [--no-backup]
  python assena_bi.py validate <proyecto.pbip>
  python assena_bi.py palettes

Flujo completo automatizado:  inspect -> (profile) -> draft -> [Claude revisa spec] -> apply -> validate
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pbip_model as pm  # noqa: E402
import pbip_report as pr  # noqa: E402
import themes  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def log(msg):
    print(msg, flush=True)


def _out(data, path):
    txt = json.dumps(data, indent=2, ensure_ascii=False, default=str)
    if path:
        Path(path).write_text(txt, encoding="utf-8")
        log("OK -> %s" % path)
    else:
        print(txt)


# --------------------------------------------------------------------------- #
def cmd_inspect(a):
    proj = pm.find_project(a.project)
    model = pm.load_model(proj["model_dir"])
    s = pm.summarize(model)
    s["project"] = {"name": proj["name"], "report": str(proj["report_dir"]), "model": str(proj["model_dir"])}
    defn = proj["report_dir"] / "definition"
    s["report"] = {"format": "PBIR" if defn.exists() else ("PBIR-Legacy" if (proj["report_dir"] / "report.json").exists() else "?"),
                   "pages": []}
    if defn.exists():
        for pj in sorted((defn / "pages").glob("*/page.json")):
            d = json.loads(pj.read_text(encoding="utf-8-sig"))
            n = len(list((pj.parent / "visuals").glob("*/visual.json")))
            s["report"]["pages"].append({"name": d.get("name"), "displayName": d.get("displayName"), "visuals": n})
    _out(s, a.out)


def _profile_files(model, sample):
    """Perfila tablas cuyo origen es un CSV local (sin BD)."""
    import csv
    import db_profile as dp
    out = []
    for t in model["tables"]:
        src = t["source"]
        if src.get("kind") != "csv" or not Path(src.get("server", "")).exists():
            continue
        with open(src["server"], newline="", encoding="utf-8-sig") as fh:
            rd = csv.reader(fh)
            cols = next(rd)
            rows = []
            for i, r in enumerate(rd):
                if i >= sample:
                    break
                rows.append([_coerce(x) for x in r])
        out.append({"table": t["name"], "modelTable": t["name"], "rowCount": None, "sampled": len(rows),
                    "columns": dp.profile_rows(cols, rows)})
        log("  perfilada %s desde CSV (%d filas)" % (t["name"], len(rows)))
    return out


def _coerce(x):
    import datetime as dt
    if x == "":
        return None
    try:
        return int(x)
    except ValueError:
        pass
    try:
        return float(x)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y"):
        try:
            return dt.datetime.strptime(x, fmt)
        except ValueError:
            pass
    return x


def cmd_profile(a):
    import db_profile as dp
    proj = pm.find_project(a.project)
    model = pm.load_model(proj["model_dir"])
    if not a.dialect and any(t["source"].get("kind") == "csv" for t in model["tables"])             and not any(t["source"].get("kind") in ("mssql", "postgresql", "mysql") for t in model["tables"]):
        _out({"dialect": "csv", "tables": _profile_files(model, a.sample)}, a.out)
        return
    srcs = [t for t in model["tables"] if t["source"].get("kind") in ("mssql", "postgresql", "mysql")]
    dialect = a.dialect or (srcs[0]["source"]["kind"] if srcs else None)
    server = a.server or (srcs[0]["source"].get("server") if srcs else None)
    database = a.database or (srcs[0]["source"].get("database") if srcs else None)
    if not dialect:
        raise pm.PbipError("No detecte origen SQL en el modelo. Indica --dialect/--server/--database "
                           "(o usa --dialect sqlite --database archivo.db).")
    port = None
    if server and ":" in server and dialect != "mssql":
        server, port = server.rsplit(":", 1)
        port = int(port)
    log("Conectando a %s %s / %s (solo lectura)..." % (dialect, server, database))
    conn = dp.connect(dialect, server, database, a.user, a.password_env, a.trusted, port)
    result = {"dialect": dialect, "server": server, "database": database, "tables": []}
    targets = []
    for t in model["tables"]:
        src = t["source"]
        if src.get("kind") not in ("mssql", "postgresql", "mysql", "odbc"):
            continue
        if src.get("nativeQuery"):
            targets.append((t["name"], None, src["nativeQuery"]))
        elif src.get("object"):
            use_schema = src.get("schema") and dialect != "sqlite"
            obj = ("%s.%s" % (src["schema"], src["object"])) if use_schema else src["object"]
            targets.append((t["name"], obj, None))
    if a.tables:
        targets = [(x, x, None) for x in a.tables.split(",")]
    if not targets:
        raise pm.PbipError("No pude mapear tablas del modelo a objetos de la BD. Usa --tables esquema.tabla,...")
    for model_table, obj, q in targets:
        try:
            r = dp.profile_table(conn, dialect, obj, q, a.sample)
            r["modelTable"] = model_table
            result["tables"].append(r)
            log("  perfilada %s (%s filas en muestra)" % (model_table, r["sampled"]))
        except Exception as e:  # seguir con las demas
            log("  ! %s: %s" % (model_table, e))
    conn.close()
    _out(result, a.out)


def cmd_draft(a):
    import drafter
    proj = pm.find_project(a.project)
    model = pm.load_model(proj["model_dir"])
    profile = json.loads(Path(a.profile).read_text(encoding="utf-8")) if a.profile else None
    ins = json.loads(Path(a.insights).read_text(encoding="utf-8")) if a.insights else None
    spec = drafter.draft_spec(pm.summarize(model), profile, a.palette, a.title, ins)
    _out(spec, a.out)


def cmd_insights(a):
    """Calcula hallazgos cuantitativos con los datos reales para el Resumen IA."""
    import insights as ins
    proj = pm.find_project(a.project)
    model = pm.load_model(proj["model_dir"])
    notes = {}
    if a.spec:
        notes = json.loads(Path(a.spec).read_text(encoding="utf-8-sig")).get("_notes", {})
    fact = a.fact or notes.get("factTable")
    value = a.value or (notes.get("numericColumns") or [None])[0]
    if not fact or not value:
        raise pm.PbipError("Indica --fact y --value (o --spec con _notes del borrador)")
    date = a.date or notes.get("dateColumn")
    cost = a.cost or notes.get("costColumn")
    cats = a.categories.split(",") if a.categories else notes.get("categories", [])[:5]
    conn = None
    dialect = None
    kinds = {t["source"].get("kind") for t in model["tables"]}
    if kinds & {"mssql", "postgresql", "mysql"} or a.dialect:
        import db_profile as dp
        src = next((t["source"] for t in model["tables"] if t["source"].get("kind") in ("mssql", "postgresql", "mysql")), {})
        dialect = a.dialect or src.get("kind")
        conn = dp.connect(dialect, a.server or src.get("server"), a.database or src.get("database"), a.user,
                          a.password_env, a.trusted, None)
    reader = ins.Reader(model, conn, dialect)
    result = ins.compute(model, fact, date, value, cats, cost, reader)
    if conn:
        conn.close()
    _out(result, a.out)


def cmd_apply(a):
    spec = json.loads(Path(a.spec).read_text(encoding="utf-8-sig"))
    proj = pm.find_project(a.project)
    if not a.no_backup:
        log("Respaldo: %s" % pm.backup_project(proj))
    model = pm.load_model(proj["model_dir"])
    ms = spec.get("model", {})

    log("[1/4] Modelo semantico")
    cal = ms.get("calendar")
    if cal:
        pm.add_calendar(proj, model, cal.get("name", "Calendario"), cal.get("rangeFrom"), log)
        for ref in cal.get("relateTo", []):
            pm.add_relationship(proj, model, ref, "%s[%s]" % (pm.tmdl_quote(cal.get("name", "Calendario")), "Fecha"), log)
    for r in ms.get("relationships", []):
        pm.add_relationship(proj, model, r["from"], r["to"], log, r.get("active", True))
    if ms.get("measures"):
        pm.add_measures(proj, model, ms["measures"], log)

    log("[2/4] Tema")
    pal = themes.get_palette(spec.get("palette", "corporativo"), spec.get("paletteOverrides"))
    tname = themes.theme_file_name(pal)
    pr.register_theme(proj["report_dir"], themes.build_theme(pal, "ASSENA %s" % pal["id"]), tname, log)

    log("[3/4] Paginas y visuales")
    pr.build_pages(proj["report_dir"], spec, model, pal, log, replace_all=a.replace_all)

    log("[4/4] Validacion")
    problems = validate(proj)
    if problems["errors"]:
        log("ERRORES:\n  - " + "\n  - ".join(problems["errors"]))
        sys.exit(2)
    for w in problems["warnings"]:
        log("  aviso: %s" % w)
    log("\nListo. Cierra Power BI Desktop si estaba abierto, abre %s y pulsa 'Actualizar'." % proj["pbip"].name)


# --------------------------------------------------------------------------- #
def validate(proj) -> dict:
    errors, warnings = [], []
    model = pm.load_model(proj["model_dir"])
    res = pr.FieldResolver(model)
    defn = proj["report_dir"] / "definition"
    if not defn.exists():
        return {"errors": ["El informe no esta en formato PBIR"], "warnings": []}
    for f in list(defn.rglob("*.json")) + list((proj["report_dir"] / "StaticResources").rglob("*.json")):
        try:
            json.loads(f.read_text(encoding="utf-8-sig"))
        except ValueError as e:
            errors.append("JSON invalido %s: %s" % (f, e))
    meta = json.loads((defn / "pages" / "pages.json").read_text(encoding="utf-8-sig"))
    for pid in meta.get("pageOrder", []):
        pj = defn / "pages" / pid / "page.json"
        if not pj.exists():
            errors.append("pages.json referencia la pagina inexistente '%s'" % pid)
            continue
        page = json.loads(pj.read_text(encoding="utf-8-sig"))
        W, H = page.get("width", 1280), page.get("height", 720)
        boxes = []
        vfiles = list((defn / "pages" / pid / "visuals").glob("*/visual.json"))
        ndata = sum(1 for f in vfiles if '"query"' in f.read_text(encoding="utf-8-sig"))
        if ndata > 14:
            warnings.append("Pagina '%s' tiene %d visuales con datos (recomendado <= 14 por rendimiento)" % (page.get("displayName"), ndata))
        for vf in vfiles:
            v = json.loads(vf.read_text(encoding="utf-8-sig"))
            p = v["position"]
            if p["x"] < 0 or p["y"] < 0 or p["x"] + p["width"] > W + 1 or p["y"] + p["height"] > H + 1:
                errors.append("Visual fuera del lienzo en '%s': %s" % (page.get("displayName"), v["name"]))
            vtype = (v.get("visual") or {}).get("visualType")
            decorative = vtype in ("textbox", "actionButton", "pageNavigator")
            if (p["width"] < 60 or p["height"] < 40) and not decorative:
                warnings.append("Visual muy pequeño en '%s': %s" % (page.get("displayName"), v["name"]))
            if not decorative:
                boxes.append((p, v["name"]))
            # valores dinamicos de textos (narrativa)
            for val in (((v.get("visual") or {}).get("objects") or {}).get("values", []) if vtype == "textbox" else []):
                fld = val["properties"]["expr"]["expr"]
                kind = next(iter(fld))
                if kind in ("Column", "Measure"):
                    ent, prop = fld[kind]["Expression"]["SourceRef"]["Entity"], fld[kind]["Property"]
                    try:
                        res.resolve("'%s'[%s]" % (ent.replace("'", "''"), prop))
                    except pm.PbipError as e:
                        errors.append("Texto dinamico en '%s': %s" % (page.get("displayName"), e))
            # navegacion: destino debe existir
            for lk in ((v.get("visual") or {}).get("visualContainerObjects") or {}).get("visualLink", []):
                sec = (lk["properties"].get("navigationSection") or {}).get("expr", {}).get("Literal", {}).get("Value")
                if sec and not (defn / "pages" / sec.strip("'")).exists():
                    errors.append("Boton en '%s' apunta a pagina inexistente %s" % (page.get("displayName"), sec))
            for tt in ((v.get("visual") or {}).get("visualContainerObjects") or {}).get("visualTooltip", []):
                sec = (tt["properties"].get("section") or {}).get("expr", {}).get("Literal", {}).get("Value")
                if sec and not (defn / "pages" / sec.strip("'")).exists():
                    errors.append("Tooltip en '%s' apunta a pagina inexistente %s" % (page.get("displayName"), sec))
            qs = ((v.get("visual") or {}).get("query") or {}).get("queryState", {})
            for role, b in qs.items():
                for pj_ in b.get("projections", []):
                    fld = pj_["field"]
                    kind = next(iter(fld))
                    if kind not in ("Column", "Measure"):
                        continue
                    ent = fld[kind]["Expression"]["SourceRef"]["Entity"]
                    prop = fld[kind]["Property"]
                    try:
                        r = res.resolve("'%s'[%s]" % (ent.replace("'", "''"), prop))
                        if r["kind"] != kind:
                            errors.append("%s.%s esta declarado como %s pero en el modelo es %s" % (ent, prop, kind, r["kind"]))
                    except pm.PbipError as e:
                        errors.append("'%s' / %s: %s" % (page.get("displayName"), v["name"], e))
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i][0], boxes[j][0]
                if a["x"] < b["x"] + b["width"] - 1 and b["x"] < a["x"] + a["width"] - 1 and \
                        a["y"] < b["y"] + b["height"] - 1 and b["y"] < a["y"] + a["height"] - 1:
                    warnings.append("Visuales superpuestos en '%s': %s / %s" % (page.get("displayName"), boxes[i][1], boxes[j][1]))
    # medidas: referencias basicas
    names = {m["name"].lower() for t in model["tables"] for m in t["measures"]}
    import re
    for t in model["tables"]:
        for m in t["measures"]:
            for ref in re.findall(r"(?<![\w'\]])\[([^\]]+)\]", m.get("expression") or ""):
                cols = {c["name"].lower() for tt in model["tables"] for c in tt["columns"]}
                if ref.lower() not in names and ref.lower() not in cols and ref not in ("Date",):
                    warnings.append("La medida [%s] referencia [%s], que no encontre" % (m["name"], ref))
    return {"errors": errors, "warnings": warnings}


def cmd_validate(a):
    proj = pm.find_project(a.project)
    r = validate(proj)
    for e in r["errors"]:
        log("ERROR: " + e)
    for w in r["warnings"]:
        log("aviso: " + w)
    log("Validacion: %d errores, %d avisos" % (len(r["errors"]), len(r["warnings"])))
    sys.exit(1 if r["errors"] else 0)


def cmd_palettes(_a):
    for k, v in themes.load_palettes().items():
        log("%-20s %s" % (k, v["label"]))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="assena_bi", description="ASSENA Power BI Studio")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("inspect"); s.add_argument("project"); s.add_argument("--out"); s.set_defaults(fn=cmd_inspect)

    s = sub.add_parser("profile"); s.add_argument("project")
    s.add_argument("--dialect", choices=["mssql", "postgresql", "mysql", "sqlite"])
    s.add_argument("--server"); s.add_argument("--database"); s.add_argument("--user")
    s.add_argument("--password-env", help="Nombre de la variable de entorno con la contraseña")
    s.add_argument("--trusted", action="store_true", help="Autenticacion de Windows (SQL Server)")
    s.add_argument("--tables", help="Lista esquema.tabla separada por comas (si no se detectan)")
    s.add_argument("--sample", type=int, default=50000); s.add_argument("--out"); s.set_defaults(fn=cmd_profile)

    s = sub.add_parser("insights"); s.add_argument("project"); s.add_argument("--spec")
    s.add_argument("--fact"); s.add_argument("--value"); s.add_argument("--date"); s.add_argument("--cost")
    s.add_argument("--categories", help="Tabla[Col],Tabla[Col]...")
    s.add_argument("--dialect", choices=["mssql", "postgresql", "mysql", "sqlite"])
    s.add_argument("--server"); s.add_argument("--database"); s.add_argument("--user")
    s.add_argument("--password-env"); s.add_argument("--trusted", action="store_true")
    s.add_argument("--out"); s.set_defaults(fn=cmd_insights)

    s = sub.add_parser("draft"); s.add_argument("project"); s.add_argument("--profile")
    s.add_argument("--insights", help="insights.json para redactar hallazgos del Resumen IA")
    s.add_argument("--palette", default="corporativo"); s.add_argument("--title"); s.add_argument("--out")
    s.set_defaults(fn=cmd_draft)

    s = sub.add_parser("apply"); s.add_argument("project"); s.add_argument("--spec", required=True)
    s.add_argument("--replace-all", action="store_true", help="Elimina TODAS las paginas existentes")
    s.add_argument("--no-backup", action="store_true"); s.set_defaults(fn=cmd_apply)

    s = sub.add_parser("validate"); s.add_argument("project"); s.set_defaults(fn=cmd_validate)
    s = sub.add_parser("palettes"); s.set_defaults(fn=cmd_palettes)

    a = ap.parse_args(argv)
    try:
        a.fn(a)
    except (pm.PbipError, KeyError, RuntimeError, ValueError) as e:
        log("ERROR: %s" % e)
        sys.exit(2)


if __name__ == "__main__":
    main()
