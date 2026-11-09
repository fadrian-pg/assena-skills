"""
ASSENA Power BI Studio - lectura y escritura del modelo semantico de un PBIP.

Soporta:
  * TMDL  (<Nombre>.SemanticModel/definition/*.tmdl)  -> lectura + escritura
  * TMSL  (<Nombre>.SemanticModel/model.bim)          -> lectura + escritura

Solo usa la libreria estandar (Python 3.8+).
"""
from __future__ import annotations

import json
import re
import shutil
import time
import uuid
import zipfile
from pathlib import Path

NUMERIC_TYPES = {"int64", "double", "decimal", "currency"}
CHILD_KEYWORDS = ("measure", "column", "partition", "hierarchy", "calculationGroup", "calculationItem")


class PbipError(Exception):
    pass


# --------------------------------------------------------------------------- #
#  Localizacion del proyecto
# --------------------------------------------------------------------------- #
def find_project(path: str) -> dict:
    """Devuelve rutas del proyecto PBIP: base, name, report_dir, model_dir."""
    p = Path(path).expanduser().resolve()
    if p.suffix.lower() in (".pbix", ".pbit"):
        raise PbipError(
            "Recibi un archivo %s. Este formato es binario y no se puede editar de forma segura.\n"
            "Abrelo en Power BI Desktop y usa Archivo > Guardar como > 'Proyecto de Power BI (*.pbip)'.\n"
            "Luego vuelve a ejecutar con la ruta del .pbip. (Ver references/pbip-setup.md)" % p.suffix
        )
    pbip_file = None
    if p.is_file() and p.suffix.lower() == ".pbip":
        pbip_file = p
    elif p.is_dir():
        found = sorted(p.glob("*.pbip"))
        if found:
            pbip_file = found[0]
        elif p.name.endswith(".Report") or p.name.endswith(".SemanticModel"):
            stem = p.name.rsplit(".", 1)[0]
            pbip_file = p.parent / (stem + ".pbip")
    if pbip_file is None:
        raise PbipError("No encontre un archivo .pbip en: %s" % p)

    base = pbip_file.parent
    name = pbip_file.stem
    report_dir = base / (name + ".Report")
    if pbip_file.exists():
        try:
            data = json.loads(pbip_file.read_text(encoding="utf-8-sig"))
            for art in data.get("artifacts", []):
                rp = (art.get("report") or {}).get("path")
                if rp:
                    report_dir = (base / rp).resolve()
        except (ValueError, OSError):
            pass

    model_dir = base / (name + ".SemanticModel")
    pbir = report_dir / "definition.pbir"
    if pbir.exists():
        try:
            d = json.loads(pbir.read_text(encoding="utf-8-sig"))
            mp = ((d.get("datasetReference") or {}).get("byPath") or {}).get("path")
            if mp:
                model_dir = (report_dir / mp).resolve()
            elif (d.get("datasetReference") or {}).get("byConnection"):
                model_dir = None  # informe conectado en vivo a un modelo publicado
        except (ValueError, OSError):
            pass

    if not report_dir.exists():
        raise PbipError("No existe la carpeta del informe: %s" % report_dir)
    return {"base": base, "name": name, "pbip": pbip_file, "report_dir": report_dir, "model_dir": model_dir}


def backup_project(proj: dict) -> Path:
    """Crea un zip con .Report y .SemanticModel antes de modificar nada."""
    bdir = proj["base"] / ".assena_backups"
    bdir.mkdir(exist_ok=True)
    target = bdir / ("%s_%s.zip" % (proj["name"], time.strftime("%Y%m%d_%H%M%S")))
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for d in (proj["report_dir"], proj["model_dir"]):
            if not d or not d.exists():
                continue
            for f in d.rglob("*"):
                if f.is_file() and ".pbi" not in f.parts:
                    z.write(f, f.relative_to(proj["base"]))
    return target


# --------------------------------------------------------------------------- #
#  Utilidades TMDL
# --------------------------------------------------------------------------- #
_SAFE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def tmdl_quote(name: str) -> str:
    if _SAFE_NAME.match(name):
        return name
    return "'" + name.replace("'", "''") + "'"


def _indent(line: str) -> int:
    n = 0
    for ch in line:
        if ch == "\t":
            n += 1
        else:
            break
    if n == 0 and line.startswith("    "):  # tolerancia a espacios
        n = (len(line) - len(line.lstrip(" "))) // 4
    return n


def _parse_name(rest: str):
    """Parsea un nombre TMDL al inicio de 'rest'. Devuelve (nombre, resto)."""
    rest = rest.strip()
    if rest.startswith("'"):
        i, out = 1, []
        while i < len(rest):
            if rest[i] == "'":
                if i + 1 < len(rest) and rest[i + 1] == "'":
                    out.append("'")
                    i += 2
                    continue
                return "".join(out), rest[i + 1:]
            out.append(rest[i])
            i += 1
        return "".join(out), ""
    m = re.match(r"([^=\s]+)(.*)$", rest)
    return (m.group(1), m.group(2)) if m else (rest, "")


def parse_column_ref(ref: str):
    """'Dim Cliente'.Id  ->  ('Dim Cliente', 'Id')"""
    ref = ref.strip()
    if ref.startswith("'"):
        tname, rest = _parse_name(ref)
    else:
        tname, _, rest = ref.partition(".")
        rest = "." + rest
    rest = rest[1:] if rest.startswith(".") else rest
    cname = _parse_name(rest)[0] if rest.startswith("'") else rest.strip()
    return tname, cname


def _blocks(lines, start, depth):
    """Itera bloques hijos a 'depth' a partir de 'start'. Devuelve [(i_ini, i_fin)]."""
    out, i, n = [], start, len(lines)
    cur = None
    while i < n:
        ln = lines[i]
        if ln.strip() == "":
            i += 1
            continue
        ind = _indent(ln)
        if ind < depth:
            break
        if ind == depth:
            if cur is not None:
                out.append((cur, i))
            cur = i
        i += 1
    if cur is not None:
        out.append((cur, i))
    return out


def _props(lines, a, b, depth):
    props = {}
    for ln in lines[a:b]:
        if _indent(ln) == depth and ln.strip():
            s = ln.strip()
            if ":" in s and not s.startswith("annotation") and not s.startswith("changedProperty"):
                k, v = s.split(":", 1)
                props[k.strip()] = v.strip()
            elif re.match(r"^[A-Za-z]+$", s):
                props[s] = True
    return props


def _expr_after_eq(header: str, lines, a, b):
    """Extrae la expresion de 'measure X = expr' (simple o multilinea / ```)."""
    if "=" not in header:
        return ""
    first = header.split("=", 1)[1].strip()
    body = []
    if first.startswith("```"):
        for ln in lines[a + 1:b]:
            if ln.strip().startswith("```"):
                break
            body.append(ln.strip())
        return "\n".join(body).strip()
    if first:
        return first
    for ln in lines[a + 1:b]:
        s = ln.strip()
        if re.match(r"^(formatString|displayFolder|lineageTag|description|isHidden|dataType|annotation|changedProperty|summarizeBy|sourceColumn|dataCategory|sortByColumn|mode|queryGroup)\b", s):
            break
        body.append(s)
    return "\n".join(body).strip()


def parse_tmdl_table(text: str) -> dict:
    lines = text.splitlines()
    head_i = next((i for i, l in enumerate(lines) if l.startswith("table ")), None)
    if head_i is None:
        raise PbipError("Archivo TMDL sin declaracion 'table'")
    tname, _ = _parse_name(lines[head_i][6:])
    table = {"name": tname, "columns": [], "measures": [], "partitions": [], "props": {}}
    children = _blocks(lines, head_i + 1, 1)
    table["props"] = _props(lines, head_i + 1, children[0][0] if children else len(lines), 1)
    for a, b in children:
        s = lines[a].strip()
        kw = s.split(" ", 1)[0]
        rest = s[len(kw):]
        if kw == "column":
            name, after = _parse_name(rest)
            p = _props(lines, a + 1, b, 2)
            table["columns"].append({
                "name": name,
                "dataType": p.get("dataType", "unknown"),
                "isHidden": bool(p.get("isHidden")),
                "summarizeBy": p.get("summarizeBy"),
                "dataCategory": p.get("dataCategory"),
                "formatString": p.get("formatString"),
                "calculated": after.strip().startswith("="),
                "expression": _expr_after_eq(s, lines, a, b) if after.strip().startswith("=") else None,
            })
        elif kw == "measure":
            name, _ = _parse_name(rest)
            p = _props(lines, a + 1, b, 2)
            table["measures"].append({
                "name": name,
                "expression": _expr_after_eq(s, lines, a, b),
                "formatString": p.get("formatString"),
                "displayFolder": p.get("displayFolder"),
            })
        elif kw == "partition":
            name, after = _parse_name(rest)
            kind = after.replace("=", "").strip()
            src = "\n".join(l.strip() for l in lines[a + 1:b])
            table["partitions"].append({"name": name, "kind": kind, "source": src})
    return table


def parse_tmdl_relationships(text: str) -> list:
    rels, cur = [], None
    for ln in text.splitlines():
        s = ln.strip()
        if ln.startswith("relationship "):
            cur = {"name": s.split(" ", 1)[1], "isActive": True, "crossFilteringBehavior": "oneDirection"}
            rels.append(cur)
        elif cur is not None and ":" in s:
            k, v = [x.strip() for x in s.split(":", 1)]
            if k in ("fromColumn", "toColumn"):
                t, c = parse_column_ref(v)
                cur[k] = {"table": t, "column": c}
            elif k == "isActive":
                cur["isActive"] = v.lower() != "false"
            elif k in ("crossFilteringBehavior", "fromCardinality", "toCardinality"):
                cur[k] = v
    return [r for r in rels if "fromColumn" in r and "toColumn" in r]


# --------------------------------------------------------------------------- #
#  Deteccion de origen de datos (Power Query M)
# --------------------------------------------------------------------------- #
_SOURCES = [
    ("mssql", r'Sql\.Databases?\(\s*"([^"]+)"(?:\s*,\s*"([^"]+)")?'),
    ("postgresql", r'PostgreSQL\.Database\(\s*"([^"]+)"\s*,\s*"([^"]+)"'),
    ("mysql", r'MySQL\.Database\(\s*"([^"]+)"\s*,\s*"([^"]+)"'),
    ("oracle", r'Oracle\.Database\(\s*"([^"]+)"'),
    ("odbc", r'Odbc\.(?:DataSource|Query)\(\s*"([^"]+)"'),
    ("snowflake", r'Snowflake\.Databases\(\s*"([^"]+)"\s*,\s*"([^"]+)"'),
    ("excel", r'Excel\.Workbook\(\s*File\.Contents\(\s*"([^"]+)"'),
    ("csv", r'Csv\.Document\(\s*File\.Contents\(\s*"([^"]+)"'),
    ("sharepoint", r'SharePoint\.(?:Files|Contents|Tables)\(\s*"([^"]+)"'),
    ("web", r'Web\.Contents\(\s*"([^"]+)"'),
]


def detect_source(m_text: str) -> dict:
    info = {}
    for kind, rx in _SOURCES:
        m = re.search(rx, m_text)
        if m:
            info["kind"] = kind
            info["server"] = m.group(1)
            if m.lastindex and m.lastindex >= 2 and m.group(2):
                info["database"] = m.group(2)
            break
    nav = re.search(r'\[\s*Schema\s*=\s*"([^"]+)"\s*,\s*Item\s*=\s*"([^"]+)"\s*\]', m_text)
    if nav:
        info["schema"], info["object"] = nav.group(1), nav.group(2)
    else:
        nav2 = re.search(r'\[\s*Name\s*=\s*"([^"]+)"', m_text)
        if nav2:
            info["object"] = nav2.group(1)
    q = re.search(r'Query\s*=\s*"((?:[^"]|"")*)"', m_text)
    if q:
        info["nativeQuery"] = q.group(1).replace('""', '"').replace("#(lf)", "\n")
    return info


# --------------------------------------------------------------------------- #
#  Lectura del modelo completo
# --------------------------------------------------------------------------- #
def load_model(model_dir: Path) -> dict:
    if model_dir is None:
        raise PbipError("El informe esta conectado en vivo a un modelo publicado; no hay modelo local para enriquecer.")
    tmdl_dir = model_dir / "definition"
    bim = model_dir / "model.bim"
    if tmdl_dir.exists():
        model = {"format": "tmdl", "tables": [], "relationships": [], "expressions": ""}
        for f in sorted((tmdl_dir / "tables").glob("*.tmdl")):
            t = parse_tmdl_table(f.read_text(encoding="utf-8-sig"))
            t["file"] = str(f)
            model["tables"].append(t)
        rf = tmdl_dir / "relationships.tmdl"
        if rf.exists():
            model["relationships"] = parse_tmdl_relationships(rf.read_text(encoding="utf-8-sig"))
        ef = tmdl_dir / "expressions.tmdl"
        if ef.exists():
            model["expressions"] = ef.read_text(encoding="utf-8-sig")
        cf = tmdl_dir / "model.tmdl"
        model["culture"] = None
        if cf.exists():
            mm = re.search(r"^\s*culture:\s*(\S+)", cf.read_text(encoding="utf-8-sig"), re.M)
            model["culture"] = mm.group(1) if mm else None
    elif bim.exists():
        data = json.loads(bim.read_text(encoding="utf-8-sig"))
        m = data.get("model", {})
        model = {"format": "tmsl", "tables": [], "relationships": [], "expressions": "", "culture": m.get("culture")}
        for t in m.get("tables", []):
            parts = []
            for p in t.get("partitions", []):
                src = p.get("source", {})
                ex = src.get("expression", "")
                parts.append({"name": p.get("name"), "kind": src.get("type"), "source": "\n".join(ex) if isinstance(ex, list) else ex})
            model["tables"].append({
                "name": t["name"],
                "props": {"dataCategory": t.get("dataCategory")} if t.get("dataCategory") else {},
                "columns": [{
                    "name": c["name"], "dataType": c.get("dataType", "unknown"), "isHidden": c.get("isHidden", False),
                    "summarizeBy": c.get("summarizeBy"), "dataCategory": c.get("dataCategory"),
                    "formatString": c.get("formatString"), "calculated": c.get("type") == "calculated",
                    "expression": c.get("expression")} for c in t.get("columns", []) if c.get("type") != "rowNumber"],
                "measures": [{"name": x["name"], "expression": "\n".join(x["expression"]) if isinstance(x.get("expression"), list) else x.get("expression", ""),
                              "formatString": x.get("formatString"), "displayFolder": x.get("displayFolder")} for x in t.get("measures", [])],
                "partitions": parts,
            })
        for r in m.get("relationships", []):
            model["relationships"].append({
                "name": r.get("name"), "isActive": r.get("isActive", True),
                "crossFilteringBehavior": r.get("crossFilteringBehavior", "oneDirection"),
                "fromColumn": {"table": r["fromTable"], "column": r["fromColumn"]},
                "toColumn": {"table": r["toTable"], "column": r["toColumn"]},
            })
    else:
        raise PbipError("No encontre definition/ (TMDL) ni model.bim en %s" % model_dir)

    for t in model["tables"]:
        src = {}
        for p in t["partitions"]:
            if p.get("kind") in ("m", "M"):
                src = detect_source(p["source"])
                if not src.get("kind") and model["expressions"]:
                    # el origen puede estar en una expresion compartida/parametros
                    shared = detect_source(model["expressions"])
                    for k in ("kind", "server", "database"):
                        if k in shared:
                            src.setdefault(k, shared[k])
            elif p.get("kind") == "calculated":
                src = {"kind": "calculated", "expression": p["source"]}
        t["source"] = src
    return model


def summarize(model: dict) -> dict:
    """Resumen compacto para que Claude analice el modelo."""
    rel_from = {}
    rel_to = {}
    for r in model["relationships"]:
        rel_from.setdefault(r["fromColumn"]["table"], 0)
        rel_from[r["fromColumn"]["table"]] += 1
        rel_to.setdefault(r["toColumn"]["table"], 0)
        rel_to[r["toColumn"]["table"]] += 1
    out = {"format": model["format"], "culture": model.get("culture"), "tables": [], "relationships": []}
    for t in model["tables"]:
        cols = t["columns"]
        num = [c["name"] for c in cols if c["dataType"] in NUMERIC_TYPES and not looks_like_key(c["name"])]
        role = "calculated" if t["source"].get("kind") == "calculated" else (
            "fact" if rel_from.get(t["name"], 0) > rel_to.get(t["name"], 0) or (len(num) >= 2 and not rel_to.get(t["name"])) else
            "dimension" if rel_to.get(t["name"]) else "standalone")
        out["tables"].append({
            "name": t["name"],
            "roleGuess": role,
            "isDateTable": t["props"].get("dataCategory") == "Time",
            "source": t["source"],
            "columns": [{k: v for k, v in c.items() if v not in (None, False, "")} for c in cols],
            "measures": [{"name": m["name"], "expression": m["expression"]} for m in t["measures"]],
        })
    for r in model["relationships"]:
        out["relationships"].append("%s[%s] -> %s[%s]%s" % (
            r["fromColumn"]["table"], r["fromColumn"]["column"], r["toColumn"]["table"], r["toColumn"]["column"],
            "" if r.get("isActive", True) else " (inactiva)"))
    return out


def looks_like_key(col: str) -> bool:
    c = col.lower().replace(" ", "").replace("_", "")
    return bool(re.search(r"(^id|id$|key$|^key|^sk|codigo$|^cod|^code|code$|^nro|numero$|^num$|ruc$|cedula$|telefono$|phone$|zip$|postal)", c))


# --------------------------------------------------------------------------- #
#  Escritura: medidas, tabla calendario, relaciones
# --------------------------------------------------------------------------- #
def _new_tag() -> str:
    return str(uuid.uuid4())


def _measure_tmdl(m: dict) -> str:
    expr = m["expression"].strip()
    head = "\tmeasure %s = " % tmdl_quote(m["name"])
    if "\n" in expr:
        body = "\n".join("\t\t\t" + l for l in expr.splitlines())
        txt = head + "```\n" + body + "\n\t\t\t```\n"
    else:
        txt = head + expr + "\n"
    if m.get("formatString"):
        txt += "\t\tformatString: %s\n" % m["formatString"]
    if m.get("displayFolder"):
        txt += "\t\tdisplayFolder: %s\n" % m["displayFolder"]
    if m.get("description"):
        txt = "\t/// %s\n" % m["description"].replace("\n", " ") + txt
    txt += "\t\tlineageTag: %s\n\n" % _new_tag()
    return txt


def _insert_into_table_file(path: Path, block: str):
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines(keepends=True)
    insert_at = len(lines)
    for i, ln in enumerate(lines):
        st = ln.lstrip("\t")
        if _indent(ln) == 1 and (st.startswith("measure ") or st.startswith("column ") or st.startswith("partition ")):
            insert_at = i
            # retroceder sobre comentarios /// de documentacion
            while insert_at > 0 and lines[insert_at - 1].strip().startswith("///"):
                insert_at -= 1
            break
    lines.insert(insert_at, block)
    path.write_text("".join(lines), encoding="utf-8")


def find_table(model: dict, name: str):
    for t in model["tables"]:
        if t["name"].lower() == name.lower():
            return t
    return None


def add_measures(proj: dict, model: dict, measures: list, log) -> int:
    added = 0
    existing = {m["name"].lower() for t in model["tables"] for m in t["measures"]}
    existing_cols = {(t["name"].lower(), c["name"].lower()) for t in model["tables"] for c in t["columns"]}
    by_table = {}
    for m in measures:
        if m["name"].lower() in existing:
            log("  = medida ya existe, se omite: [%s]" % m["name"])
            continue
        t = find_table(model, m["table"])
        if t is None:
            raise PbipError("La medida [%s] apunta a la tabla '%s' que no existe." % (m["name"], m["table"]))
        if (t["name"].lower(), m["name"].lower()) in existing_cols:
            raise PbipError("La medida [%s] tiene el mismo nombre que una columna de '%s'. Cambia el nombre." % (m["name"], t["name"]))
        by_table.setdefault(t["name"], []).append(m)
        existing.add(m["name"].lower())

    if model["format"] == "tmdl":
        for tname, ms in by_table.items():
            t = find_table(model, tname)
            block = "".join(_measure_tmdl(m) for m in ms)
            _insert_into_table_file(Path(t["file"]), block)
            for m in ms:
                t["measures"].append(dict(m))
                added += 1
                log("  + medida [%s] en %s" % (m["name"], tname))
    else:
        bim = proj["model_dir"] / "model.bim"
        data = json.loads(bim.read_text(encoding="utf-8-sig"))
        for tname, ms in by_table.items():
            jt = next(x for x in data["model"]["tables"] if x["name"] == tname)
            jt.setdefault("measures", [])
            for m in ms:
                obj = {"name": m["name"], "expression": m["expression"], "lineageTag": _new_tag()}
                for k in ("formatString", "displayFolder", "description"):
                    if m.get(k):
                        obj[k] = m[k]
                jt["measures"].append(obj)
                find_table(model, tname)["measures"].append(dict(m))
                added += 1
                log("  + medida [%s] en %s" % (m["name"], tname))
        bim.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return added


MONTHS_ES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
DAYS_ES = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]


def calendar_dax(range_from: str | None) -> str:
    if range_from:
        t, c = range_from.split("[", 1)
        ref = "%s[%s" % (tmdl_quote(t.strip().strip("'")) if not t.strip().startswith("'") else t.strip(), c)
        start = "DATE ( YEAR ( MIN ( %s ) ), 1, 1 )" % ref
        end = "DATE ( YEAR ( MAX ( %s ) ), 12, 31 )" % ref
        base = "CALENDAR ( %s, %s )" % (start, end)
    else:
        base = "CALENDARAUTO ()"
    months = ", ".join('%d, "%s"' % (i + 1, m) for i, m in enumerate(MONTHS_ES))
    days = ", ".join('%d, "%s"' % (i + 1, d) for i, d in enumerate(DAYS_ES))
    return (
        "VAR _base = %s\n"
        "RETURN\n"
        "SELECTCOLUMNS (\n"
        "    _base,\n"
        '    "Fecha", [Date],\n'
        '    "Año", YEAR ( [Date] ),\n'
        '    "Trimestre", "T" & QUARTER ( [Date] ),\n'
        '    "Mes Num", MONTH ( [Date] ),\n'
        '    "Mes", SWITCH ( MONTH ( [Date] ), %s ),\n'
        '    "Año Mes", FORMAT ( [Date], "YYYY-MM" ),\n'
        '    "Año Mes Num", YEAR ( [Date] ) * 100 + MONTH ( [Date] ),\n'
        '    "Mes Inicio", DATE ( YEAR ( [Date] ), MONTH ( [Date] ), 1 ),\n'
        '    "Día Semana Num", WEEKDAY ( [Date], 2 ),\n'
        '    "Día Semana", SWITCH ( WEEKDAY ( [Date], 2 ), %s )\n'
        ")" % (base, months, days)
    )


CAL_COLUMNS = [
    ("Fecha", "dateTime", "dd/mm/yyyy", None, True),
    ("Año", "int64", "0", None, False),
    ("Trimestre", "string", None, None, False),
    ("Mes Num", "int64", "0", None, False),
    ("Mes", "string", None, "Mes Num", False),
    ("Año Mes", "string", None, "Año Mes Num", False),
    ("Año Mes Num", "int64", "0", None, False),
    ("Mes Inicio", "dateTime", "mmm yyyy", None, False),
    ("Día Semana Num", "int64", "0", None, False),
    ("Día Semana", "string", None, "Día Semana Num", False),
]


def add_calendar(proj: dict, model: dict, name: str, range_from: str | None, log) -> bool:
    if find_table(model, name):
        log("  = la tabla calendario '%s' ya existe, se omite" % name)
        return False
    dax = calendar_dax(range_from)
    if model["format"] == "tmdl":
        tdir = proj["model_dir"] / "definition" / "tables"
        out = ["table %s\n" % tmdl_quote(name), "\tdataCategory: Time\n", "\tlineageTag: %s\n\n" % _new_tag()]
        for cname, dtype, fmt, sort_by, is_key in CAL_COLUMNS:
            out.append("\tcolumn %s\n" % tmdl_quote(cname))
            out.append("\t\tdataType: %s\n" % dtype)
            if is_key:
                out.append("\t\tisKey\n")
            if fmt:
                out.append("\t\tformatString: %s\n" % fmt)
            out.append("\t\tlineageTag: %s\n" % _new_tag())
            out.append("\t\tsummarizeBy: none\n")
            out.append("\t\tisNameInferred\n")
            out.append("\t\tsourceColumn: [%s]\n" % cname)
            if sort_by:
                out.append("\t\tsortByColumn: %s\n" % tmdl_quote(sort_by))
            out.append("\n")
        out.append("\tpartition %s = calculated\n" % tmdl_quote(name))
        out.append("\t\tmode: import\n")
        out.append("\t\tsource = ```\n")
        out.extend("\t\t\t\t%s\n" % l for l in dax.splitlines())
        out.append("\t\t\t\t```\n\n")
        out.append("\tannotation PBI_Id = assena-calendar\n")
        fpath = tdir / (name + ".tmdl")
        fpath.write_text("".join(out), encoding="utf-8")
        mf = proj["model_dir"] / "definition" / "model.tmdl"
        if mf.exists():
            mt = mf.read_text(encoding="utf-8-sig")
            if re.search(r"^ref table ", mt, re.M) and not re.search(r"^ref table %s\s*$" % re.escape(tmdl_quote(name)), mt, re.M):
                lines = mt.splitlines(keepends=True)
                last = max(i for i, l in enumerate(lines) if l.startswith("ref table "))
                if not lines[last].endswith("\n"):
                    lines[last] += "\n"
                lines.insert(last + 1, "ref table %s\n" % tmdl_quote(name))
                mf.write_text("".join(lines), encoding="utf-8")
        tinfo = {"name": name, "file": str(fpath), "props": {"dataCategory": "Time"}, "measures": [], "partitions": [],
                 "source": {"kind": "calculated"}}
    else:
        bim = proj["model_dir"] / "model.bim"
        data = json.loads(bim.read_text(encoding="utf-8-sig"))
        cols = []
        for cname, dtype, fmt, sort_by, is_key in CAL_COLUMNS:
            c = {"type": "calculatedTableColumn", "name": cname, "dataType": dtype, "isNameInferred": True,
                 "sourceColumn": "[%s]" % cname, "summarizeBy": "none", "lineageTag": _new_tag()}
            if fmt:
                c["formatString"] = fmt
            if sort_by:
                c["sortByColumn"] = sort_by
            if is_key:
                c["isKey"] = True
            cols.append(c)
        data["model"]["tables"].append({
            "name": name, "dataCategory": "Time", "lineageTag": _new_tag(), "columns": cols,
            "partitions": [{"name": name, "mode": "import", "source": {"type": "calculated", "expression": dax.splitlines()}}]})
        bim.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tinfo = {"name": name, "props": {"dataCategory": "Time"}, "measures": [], "partitions": [], "source": {"kind": "calculated"}}
    tinfo["columns"] = [{"name": c[0], "dataType": c[1], "isHidden": False, "summarizeBy": "none", "dataCategory": None,
                         "formatString": c[2], "calculated": False, "expression": None} for c in CAL_COLUMNS]
    model["tables"].append(tinfo)
    log("  + tabla calendario '%s' (%s)" % (name, ("rango de " + range_from) if range_from else "CALENDARAUTO"))
    return True


def add_relationship(proj: dict, model: dict, from_ref: str, to_ref: str, log, active=True) -> bool:
    ft, fc = split_field(from_ref)
    tt, tc = split_field(to_ref)
    for x, y in ((ft, fc), (tt, tc)):
        t = find_table(model, x)
        if not t or not any(c["name"].lower() == y.lower() for c in t["columns"]):
            raise PbipError("Relacion invalida: no existe la columna %s[%s]" % (x, y))
    for r in model["relationships"]:
        if r["fromColumn"]["table"].lower() == ft.lower() and r["fromColumn"]["column"].lower() == fc.lower() \
                and r["toColumn"]["table"].lower() == tt.lower():
            log("  = relacion %s -> %s ya existe" % (from_ref, to_ref))
            return False
    if active:
        for r in model["relationships"]:
            if r.get("isActive", True) and {r["fromColumn"]["table"].lower(), r["toColumn"]["table"].lower()} == {ft.lower(), tt.lower()}:
                active = False
                log("  ! ya hay una relacion activa entre %s y %s; la nueva se crea INACTIVA" % (ft, tt))
    rid = _new_tag()
    if model["format"] == "tmdl":
        rf = proj["model_dir"] / "definition" / "relationships.tmdl"
        txt = rf.read_text(encoding="utf-8-sig") if rf.exists() else ""
        if txt and not txt.endswith("\n"):
            txt += "\n"
        if txt:
            txt += "\n"
        txt += "relationship %s\n" % rid
        if not active:
            txt += "\tisActive: false\n"
        txt += "\tfromColumn: %s.%s\n\ttoColumn: %s.%s\n" % (tmdl_quote(ft), tmdl_quote(fc), tmdl_quote(tt), tmdl_quote(tc))
        rf.write_text(txt, encoding="utf-8")
    else:
        bim = proj["model_dir"] / "model.bim"
        data = json.loads(bim.read_text(encoding="utf-8-sig"))
        rel = {"name": rid, "fromTable": ft, "fromColumn": fc, "toTable": tt, "toColumn": tc}
        if not active:
            rel["isActive"] = False
        data["model"].setdefault("relationships", []).append(rel)
        bim.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    model["relationships"].append({"name": rid, "isActive": active, "fromColumn": {"table": ft, "column": fc},
                                   "toColumn": {"table": tt, "column": tc}})
    log("  + relacion %s -> %s%s" % (from_ref, to_ref, "" if active else " (inactiva)"))
    return True


def split_field(ref: str):
    """'Tabla[Campo]' / ''Mi Tabla'[Campo]' / '[Medida]' -> (tabla|None, campo)"""
    ref = ref.strip()
    m = re.match(r"^(?:'((?:[^']|'')+)'|([^\[\]]+))?\s*\[([^\]]+)\]$", ref)
    if not m:
        raise PbipError("Referencia de campo invalida: %r (usa Tabla[Campo] o [Medida])" % ref)
    table = m.group(1).replace("''", "'") if m.group(1) else (m.group(2).strip() if m.group(2) else None)
    return table, m.group(3).strip()


def unused_dir(path: Path):
    if path.exists():
        shutil.rmtree(path)
