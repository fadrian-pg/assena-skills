"""
ASSENA Power BI Studio - perfilado de datos (solo lectura) directo en la base de datos.

Motores: mssql (pyodbc), postgresql (psycopg2), mysql (pymysql), sqlite (stdlib).
Las credenciales NUNCA se pasan por linea de comandos: usa autenticacion de
Windows (--trusted) o una variable de entorno (--password-env NOMBRE_VAR).

Solo ejecuta SELECT con limite de filas. Muestra estadisticas, nunca datos
sensibles completos (los valores top se truncan a 40 caracteres).
"""
from __future__ import annotations

import datetime as dt
import decimal
import os
import re
from collections import Counter

SAMPLE_DEFAULT = 50000


def _ident(name: str, dialect: str) -> str:
    if not re.match(r"^[\w .\-áéíóúñÁÉÍÓÚÑ]+$", name):
        raise ValueError("Nombre de objeto no permitido: %r" % name)
    parts = name.split(".")
    if dialect == "mssql":
        return ".".join("[%s]" % p for p in parts)
    if dialect == "mysql":
        return ".".join("`%s`" % p for p in parts)
    return ".".join('"%s"' % p for p in parts)


def connect(dialect: str, server: str | None, database: str | None, user: str | None,
            password_env: str | None, trusted: bool, port: int | None):
    password = os.environ.get(password_env) if password_env else None
    if password_env and password is None:
        raise RuntimeError("La variable de entorno %s no esta definida" % password_env)
    if dialect == "sqlite":
        import sqlite3
        return sqlite3.connect("file:%s?mode=ro" % database, uri=True)
    if dialect == "mssql":
        try:
            import pyodbc
        except ImportError:
            raise RuntimeError("Falta pyodbc:  pip install pyodbc")
        drivers = [d for d in pyodbc.drivers() if "SQL Server" in d]
        if not drivers:
            raise RuntimeError("No hay driver ODBC de SQL Server instalado (instala 'ODBC Driver 18 for SQL Server').")
        drv = sorted(drivers, key=lambda d: ("ODBC Driver" in d, d))[-1]
        cs = "DRIVER={%s};SERVER=%s;DATABASE=%s;ApplicationIntent=ReadOnly;TrustServerCertificate=yes;" % (drv, server, database)
        cs += "Trusted_Connection=yes;" if trusted or not user else "UID=%s;PWD=%s;" % (user, password or "")
        return pyodbc.connect(cs, timeout=15)
    if dialect == "postgresql":
        try:
            import psycopg2
        except ImportError:
            raise RuntimeError("Falta psycopg2:  pip install psycopg2-binary")
        conn = psycopg2.connect(host=server, dbname=database, user=user, password=password, port=port or 5432,
                                connect_timeout=15, options="-c default_transaction_read_only=on")
        return conn
    if dialect == "mysql":
        try:
            import pymysql
        except ImportError:
            raise RuntimeError("Falta pymysql:  pip install pymysql")
        return pymysql.connect(host=server, database=database, user=user, password=password or "", port=port or 3306,
                               connect_timeout=15)
    raise RuntimeError("Motor no soportado: %s" % dialect)


def _kind(v):
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, (int, float, decimal.Decimal)):
        return "number"
    if isinstance(v, (dt.date, dt.datetime)):
        return "date"
    return "text"


def profile_rows(cols, rows) -> list:
    out = []
    n = len(rows)
    for i, c in enumerate(cols):
        vals = [r[i] for r in rows]
        nn = [v for v in vals if v is not None and v != ""]
        kinds = Counter(_kind(v) for v in nn[:2000])
        kind = kinds.most_common(1)[0][0] if kinds else "empty"
        distinct = len(set(map(str, nn)))
        info = {"column": c, "kind": kind, "nullPct": round(100.0 * (n - len(nn)) / n, 1) if n else 0,
                "distinct": distinct, "distinctPct": round(100.0 * distinct / len(nn), 1) if nn else 0}
        if kind == "number":
            nums = [float(v) for v in nn if _kind(v) == "number"]
            if nums:
                info.update({"min": min(nums), "max": max(nums), "avg": round(sum(nums) / len(nums), 2),
                             "sum": round(sum(nums), 2), "negatives": sum(1 for x in nums if x < 0),
                             "integers": all(float(x).is_integer() for x in nums[:2000])})
        elif kind == "date":
            ds = [v for v in nn if _kind(v) == "date"]
            info.update({"min": str(min(ds)), "max": str(max(ds))})
            if all(isinstance(d, dt.datetime) for d in ds[:500]):
                info["hasTime"] = any(d.time() != dt.time(0) for d in ds[:2000])
        if kind == "text" and distinct <= 60:
            info["top"] = [[str(k)[:40], v] for k, v in Counter(map(str, nn)).most_common(8)]
        # sugerencia de rol
        if kind == "number" and info.get("distinctPct", 0) > 95 and info.get("integers"):
            info["roleHint"] = "key"
        elif kind == "number":
            info["roleHint"] = "measure"
        elif kind == "date":
            info["roleHint"] = "date"
        elif kind == "text" and 2 <= distinct <= 60:
            info["roleHint"] = "category"
        elif kind == "text" and info.get("distinctPct", 0) > 90:
            info["roleHint"] = "identifier/descriptor"
        out.append(info)
    return out


def profile_table(conn, dialect: str, table: str | None, query: str | None, sample: int) -> dict:
    cur = conn.cursor()
    total = None
    if table:
        ident = _ident(table, dialect)
        cur.execute("SELECT COUNT(*) FROM %s" % ident)
        total = cur.fetchone()[0]
        sql = ("SELECT TOP %d * FROM %s" % (sample, ident)) if dialect == "mssql" else ("SELECT * FROM %s LIMIT %d" % (ident, sample))
    else:
        if not re.match(r"^\s*(with|select)\b", query, re.I) or re.search(r";\s*\S", query):
            raise ValueError("Solo se permiten consultas SELECT simples")
        sql = query
    cur.execute(sql)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchmany(sample)
    return {"table": table or "(consulta)", "rowCount": total, "sampled": len(rows), "columns": profile_rows(cols, rows)}


def list_tables(conn, dialect: str) -> list:
    cur = conn.cursor()
    if dialect == "sqlite":
        cur.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%'")
        return [r[0] for r in cur.fetchall()]
    cur.execute("SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_SCHEMA NOT IN ('information_schema','pg_catalog','sys')")
    return ["%s.%s" % (r[0], r[1]) for r in cur.fetchall()]
