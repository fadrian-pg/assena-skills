"""
Prueba de humo de todos los skills del repositorio (sin Power BI ni base de datos).

    python tests/smoke_test.py

assena-powerbi-studio: genera el proyecto demo, ejecuta profile -> draft -> insights
-> draft -> apply -> validate y verifica que no haya errores ni avisos. Tambien
valida los manifiestos JSON del marketplace y de cada plugin.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "plugins" / "assena-powerbi-studio" / "skills" / "assena-powerbi-studio"
CLI = SKILL / "scripts" / "assena_bi.py"


def run(*args):
    r = subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        print(r.stdout, r.stderr)
        raise SystemExit("FALLO: %s" % " ".join(map(str, args)))
    return r.stdout


def check_manifests():
    mk = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    for p in mk["plugins"]:
        pj = json.loads((ROOT / p["source"] / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        assert pj["name"] == p["name"], "nombre distinto en %s" % p["name"]
        assert pj["version"] == p["version"], "version distinta en %s" % p["name"]
        skill_md = ROOT / p["source"] / "skills" / p["name"] / "SKILL.md"
        assert skill_md.read_text(encoding="utf-8").startswith("---\nname: %s" % p["name"]), "frontmatter de %s" % skill_md
    print("OK manifiestos (%d plugins)" % len(mk["plugins"]))


def check_powerbi():
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        run(SKILL / "assets" / "examples" / "make_demo_pbip.py", t)
        pbip = t / "DemoVentas.pbip"
        run(CLI, "inspect", pbip, "--out", t / "model.json")
        run(CLI, "profile", pbip, "--out", t / "profile.json")
        run(CLI, "draft", pbip, "--profile", t / "profile.json", "--out", t / "s0.json")
        run(CLI, "insights", pbip, "--spec", t / "s0.json", "--out", t / "ins.json")
        for pal in ("corporativo", "medianoche"):
            run(CLI, "draft", pbip, "--profile", t / "profile.json", "--insights", t / "ins.json",
                "--palette", pal, "--out", t / "spec.json")
            run(CLI, "apply", pbip, "--spec", t / "spec.json", "--no-backup")
            out = run(CLI, "validate", pbip)
            assert "0 errores, 0 avisos" in out, out
            print("OK assena-powerbi-studio (paleta %s)" % pal)


if __name__ == "__main__":
    check_manifests()
    check_powerbi()
    print("Todas las pruebas pasaron.")
