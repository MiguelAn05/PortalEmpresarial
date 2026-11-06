# Del reloj ZKBio al portal: módulo Marcaciones

El portal **no se conecta a ZKBio Time**. Un script que corre en el servidor
de ZKBio (`sincronizar_marcaciones.py`) lee el reloj y **empuja** al portal,
por HTTPS y con una clave propia, lo que necesita el módulo Marcaciones:

1. **Las marcaciones** de los últimos días (3 por defecto). Reenviarlas es
   inofensivo: el portal no duplica.
2. **La malla de turnos** (`schedules.csv`, la misma de las alertas de
   asistencia): quién es cada persona, su área y sus turnos posibles por día.
3. **Los festivos** (`festivos.csv`) y las **excepciones** (`excepciones.csv`:
   vacaciones, incapacidades, permisos), si existen.

La dirección es lo que importa, igual que con el ERP: el portal está expuesto
a internet, así que ahí no hay ninguna credencial ni ruta hacia el reloj. El
tráfico va de la red interna hacia afuera.

**El script solo LEE de ZKBio.** No crea, no modifica y no borra nada allá.
Es independiente del script de alertas por correo (`alertas_zkteco.py`), que
sigue funcionando aunque el portal esté caído.

## Lo que hay que hacer una sola vez

### 1. En el portal (servidor zeus)

1. Generar la clave y ponerla en `backend/.env.prod`:
   ```
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
   CLAVE_MARCACIONES=<la clave>
   ```
   Un cambio de `.env` se aplica con **`docker compose up -d`**, no con `restart`.
2. Desplegar la versión 0.67 (`git pull`, `docker compose up -d --build backend`)
   y aplicar la migración: `docker exec protokimica_backend alembic upgrade head`.
   Crea las tablas `mar_*` y le da a **Gestión Humana y TICS** la capacidad
   «Ver las marcaciones de todas las áreas».
3. Activar el módulo (no queda contratado solo):
   `docker exec protokimica_backend python -m app.scripts.modulos protokimica --activar marcaciones`
4. En el computador de desarrollo: `npm run build` en `frontend/` y commitear
   `dist/` (se compila aquí y no en el servidor).

### 2. En el servidor de ZKBio

1. Copiar esta carpeta (`integraciones/marcaciones`) junto a la de las alertas,
   por ejemplo `C:\alertas\marcaciones`.
2. Copiar `sincronizar_marcaciones.config.ejemplo.json` como
   `sincronizar_marcaciones.config.json` y revisar:
   - `schedules_csv`: dónde está el `schedules.csv` real (`..\\schedules.csv` si
     queda dentro de `C:\alertas`). Los festivos y excepciones se buscan en esa
     misma carpeta.
   - `mapa_areas`: **el área de la malla tiene que llamarse EXACTAMENTE como en
     Administración › Áreas del portal.** Lo que no esté en el mapa pasa tal cual.
   Para ver cómo quedaría cada área: `py -3 sincronizar_marcaciones.py --areas`.
3. Variables de equipo (con `setx /M`, y abrir una ventana nueva). Si ya están
   las de las alertas, solo falta la tercera:
   `ZK_USER`, `ZK_PASS`, `CLAVE_MARCACIONES` (la misma del `.env.prod`).
4. **Opcional, para que cada persona vea SUS marcaciones:** agregar una columna
   `correo` a `schedules.csv` con el correo con el que la persona entra al
   portal. Sin él, esa persona no ve nada (nunca ve lo de otros). Las alertas
   ignoran la columna.

### 3. Probar y programar

```
py -3 sincronizar_marcaciones.py --selftest        # lógica, sin red
py -3 sincronizar_marcaciones.py --dry-run         # arma el envío y lo resume, sin enviarlo
py -3 sincronizar_marcaciones.py --dias 30         # carga inicial: último mes
schtasks /Create /SC MINUTE /MO 5 /TN "SincronizarMarcaciones" /TR "py -3 C:\alertas\marcaciones\sincronizar_marcaciones.py" /RU SYSTEM
```

(Use la ruta completa de Python en la tarea programada si `py` no está en el
PATH del usuario SYSTEM, como se hizo con las alertas.)

`sincronizar_marcaciones.log` registra cada ejecución y los errores. El script
termina con código distinto de cero si falla, para que el Programador de tareas
lo muestre.

### En qué biométrico se marcó

Cada marcación viaja con la **serie** del equipo (`terminal_sn` de ZKBio), y el
primer lote lleva la lista de equipos con su nombre (`terminal_alias`) y su zona
(`area_alias`), tal como aparecen en ZKBio › Dispositivos. No hay que configurar
nada: si un equipo se renombra en ZKBio, el portal toma el nombre nuevo en el
siguiente envío.

`--dry-run` lista los equipos que vio. Las marcaciones que ya estaban en el
portal reciben su equipo cuando se reenvían: después de actualizar el script,
corre una vez `py -3 sincronizar_marcaciones.py --dias 30`.

## Cómo saber que está funcionando

- En el portal, **Marcaciones** muestra «Actualizado a las…». Si el script deja
  de enviar más de 10 minutos, la pantalla lo avisa con el último error.
- `GET /marcaciones/estado` dice cuándo llegó el último envío. Los envíos
  rechazados (clave mala, lote vacío) también quedan registrados.

## Qué rechaza el portal

| Respuesta | Por qué |
|---|---|
| 503 | Falta `CLAVE_MARCACIONES` en el `.env.prod` |
| 403 | La clave no coincide, o la empresa no tiene contratado Marcaciones |
| 400 | Lote vacío: no se aplica, para que un error al leer ZKBio no parezca «nadie marcó» ni deje a todos desactivados |
| 413 | Más de 20.000 marcaciones en un envío |
| 422 | Un dato inválido (turno mal escrito, hora con zona, estado desconocido): dice cuál |

## Reglas

Son **las mismas de las alertas por correo**: llegada tarde y salida
anticipada con 5 min de tolerancia, ausencia a las 3 h (sábado 1,5 h), almuerzo
de 45 min, break de 15 min, turno por ventana de −45/+10 min y por historial.
Están en `backend/app/modules/marcaciones/constants.py`. **Si cambia una en
`config.json` de las alertas, hay que cambiarla también allí**, o la pantalla y
el correo dirán cosas distintas.
