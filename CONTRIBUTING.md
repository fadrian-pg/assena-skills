# Contribuir a ASSENA Skills

¡Gracias por querer mejorar estos skills! Toda contribucion es bienvenida:
correcciones, nuevas paletas, visuales, patrones DAX, traducciones o skills nuevos.

## Flujo
1. Haz un fork y crea una rama: `git checkout -b mejora/nombre-corto`.
2. Haz tus cambios dentro de `plugins/<skill>/`.
3. Ejecuta las pruebas: `python tests/smoke_test.py` (Python 3.8+, sin dependencias).
4. Si cambias algo visual, pruebalo en Power BI Desktop y adjunta una captura.
5. Sube la version (semver) en `plugin.json` **y** en `.claude-plugin/marketplace.json`,
   y agrega una entrada en el `CHANGELOG.md` del plugin.
6. Abre un Pull Request usando la plantilla.

## Reglas de diseño (assena-powerbi-studio)
- Las paletas nuevas deben pasar la validacion de color (daltonismo, contraste,
  luminosidad); ver `references/design-system.md`.
- Nunca editar `.pbix`; todo se genera sobre PBIP/PBIR/TMDL.
- Scripts solo con libreria estandar de Python 3.8+ (dependencias de BD opcionales).
- Nunca incluir datos reales, cadenas de conexion ni credenciales en ejemplos o issues.

## Crear un skill nuevo
1. Copia la estructura de `plugins/assena-powerbi-studio`.
2. Nombre con prefijo `assena-`; `SKILL.md` con `name` y `description` claros
   (la descripcion decide cuando Claude lo activa).
3. Registra el plugin en `.claude-plugin/marketplace.json`.
4. Agrega una prueba en `tests/smoke_test.py`.

## Conducta
Se respetuoso y constructivo. Ver [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
