"""
Los canales de atención por los que entra una PQRS. Fuente única del backend.

Antes vivían repetidos en cuatro archivos —`pqrs/service.py`, `PQRSList.jsx` y
dos listas dentro de `FormularioPQRS.jsx`— y ya habían empezado a separarse:
el formulario normal ofrecía «Línea telefónica» y el de felicitaciones
«Llamada telefónica», así que la misma llamada caía en dos canales distintos y
el reporte por canal las contaba aparte.

El gemelo de este archivo es `frontend/src/core/canales.js`, y una prueba
verifica que los dos digan exactamente lo mismo.

**La escritura exacta importa**, igual que con las áreas: el canal se compara
como texto para decidir el prefijo del código de seguimiento. Si alguien
cambia una tilde, las PQRS de ese punto de venta dejan de recibir su
consecutivo propio y pasan a `PK-2026-…` sin que nada avise. Un cambio de
escritura va con migración de datos.
"""

# El orden es el que se muestra en los formularios.
CANALES = [
    "Venta institucional",
    "WhatsApp",
    "Punto de venta Centro",
    "Punto de venta Belén",
    "Punto de venta Guayabal",
    "Punto de venta La 65",
    "Punto de venta Cristo Rey",
    "Punto de venta Itagüí",
    "Línea telefónica",
]

# Los canales que llevan consecutivo propio, y con qué prefijo.
#
# Un punto de venta necesita su propia numeración para que el reporte por
# punto tenga sentido: si todos compartieran consecutivo, «llevamos 40 PQRS»
# no diría nada de ninguna sede en particular. Los canales que no están aquí
# caen en `PK-{año}-{consecutivo}`.
#
# **El prefijo es además el código del QR**: `/q/PVG` abre el formulario ya
# marcado como Guayabal. Por eso no se cambia a la ligera — un letrero
# impreso y pegado en una sede no se actualiza solo.
PREFIJOS_POR_CANAL = {
    "Punto de venta Centro": "PVC",
    "Punto de venta Belén": "PVB",
    "Punto de venta Guayabal": "PVG",
    "Punto de venta La 65": "PV65",
    "Punto de venta Cristo Rey": "PVCR",
    "Punto de venta Itagüí": "PVI",
    "Venta institucional": "VI",
}

# Nombres que quedaron en datos ya guardados y a qué canal corresponden hoy.
# «Llamada telefónica» solo existía en el formulario de felicitaciones: era la
# misma llamada que el resto del portal llama «Línea telefónica», contada
# aparte en los reportes por culpa de una palabra.
EQUIVALENCIAS_HISTORICAS = {
    "Llamada telefónica": "Línea telefónica",
}


def normalizar(canal: str | None) -> str | None:
    """Traduce un nombre viejo al actual. Devuelve None si viene vacío."""
    if not canal or not canal.strip():
        return None
    limpio = canal.strip()
    return EQUIVALENCIAS_HISTORICAS.get(limpio, limpio)


def es_valido(canal: str | None) -> bool:
    """None es válido: una PQRS interna puede no tener canal."""
    return canal is None or canal in CANALES


def prefijo_de(canal: str | None) -> str | None:
    """El prefijo del código de seguimiento, o None si el canal no tiene uno."""
    return PREFIJOS_POR_CANAL.get((canal or "").strip())


def canal_por_codigo(codigo: str | None) -> str | None:
    """
    El canal al que apunta un código de QR (`PVG` → «Punto de venta Guayabal»).

    Se compara sin distinguir mayúsculas porque el código va impreso en un
    letrero y alguien lo va a teclear a mano tarde o temprano.
    """
    if not codigo:
        return None
    buscado = codigo.strip().upper()
    for canal, prefijo in PREFIJOS_POR_CANAL.items():
        if prefijo == buscado:
            return canal
    return None
