# Preparar el archivo: de .pbix a proyecto PBIP (PBIR)

El skill trabaja sobre **Power BI Project (.pbip)** porque guarda informe y modelo
como archivos de texto (JSON/TMDL) que se pueden generar y versionar con git.

## 1. Crear el archivo "en blanco" conectado a la BD
1. Power BI Desktop > **Obtener datos** > SQL Server / PostgreSQL / MySQL / Excel / CSV.
2. Selecciona las tablas o vistas (hechos + dimensiones). Transforma en Power Query
   lo minimo: tipos de dato correctos, fecha sin hora, nombres legibles.
3. En **Vista de modelo** revisa relaciones (Desktop las autodetecta por nombre).
4. No hace falta crear visuales.

## 2. Activar el formato de proyecto (una sola vez)
Archivo > Opciones y configuracion > Opciones > **Caracteristicas en vista previa**:
- ☑ *Guardar como proyecto de Power BI (.pbip)* (si aparece; en versiones recientes ya es GA)
- ☑ *Almacenar informes con formato de metadatos mejorado (PBIR)*
- ☑ *Almacenar el modelo semantico con formato TMDL* (recomendado)
Reinicia Power BI Desktop.

## 3. Guardar como .pbip
Archivo > **Guardar como** > tipo **Proyecto de Power BI (*.pbip)** en una carpeta
propia. Resultado:

```
MiProyecto.pbip
MiProyecto.Report/
  definition.pbir
  definition/  (report.json, pages/…)        <- PBIR
MiProyecto.SemanticModel/
  definition/  (model.tmdl, tables/*.tmdl, relationships.tmdl)  <- TMDL
  .pbi/cache.abf  (datos en cache, no se edita)
```

Si ves `MiProyecto.Report/report.json` y **no** existe `definition/`, el informe
esta en PBIR-Legacy: activa la opcion PBIR del paso 2 y guarda de nuevo.

## 4. Despues de que el skill aplique cambios
1. Cierra Power BI Desktop **antes** de ejecutar `apply` (si estaba abierto,
   Desktop podria sobrescribir los archivos al guardar).
2. Abre `MiProyecto.pbip`.
3. Inicio > **Actualizar** (si se creo la tabla Calendario y aparece el aviso de
   "objetos calculados", usa *Actualizar ahora*).
4. Guarda. Para publicar: Inicio > Publicar (o via Fabric/Git).

## 5. Restaurar
Cada `apply` deja un zip en `.assena_backups/`. Para volver atras, cierra Desktop,
borra las carpetas `.Report` y `.SemanticModel` y descomprime el zip en su lugar.
