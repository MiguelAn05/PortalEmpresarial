"""
Por dónde pasa una solicitud de nota crédito y quién la atiende en cada paso.

**Es la única fuente de la cadena.** El router, los correos y la pantalla
preguntan aquí; si cada uno armara su propia secuencia, el día que se agregue
un paso el que se olvide es el que deja una solicitud atascada sin que nadie
sepa en manos de quién está.

**Toda solicitud empieza por COMERCIAL.** Quien decide si la empresa acepta
devolverle la plata al cliente es Comercial, y eso no cambia porque la venta
se haya hecho en un mostrador o a una institución. Antes las del punto de
venta entraban directo a Contabilidad —era el flujo de siempre, de cuando
esto se pedía por correo—, y el resultado era que Contabilidad terminaba
decidiendo un asunto comercial.

Lo que cambia entre ramas es qué pasa DESPUÉS de Comercial:

    Punto de venta ──► COMERCIAL aprueba
                    ──► el punto emite y registra el número

    Ventas Institucionales
        └─(si el motivo implica producto)─► BODEGA confirma que llegó
                                         ──► COMERCIAL aprueba
                                         ──► CONTABILIDAD verifica en la DIAN
                                         ──► quien emite registra el número

Lo único que agrega el producto es la confirmación de la bodega al principio:
sin producto no hay nada que confirmar y pedirlo sería una firma que no mira
nada, de las que la gente aprende a dar sin leer.

**En la rama del mostrador Contabilidad ya no autoriza.** Tenía un turno
—el estado `solicitada`— entre Comercial y la emisión, y era una firma de
más: la decisión comercial ya está tomada, el punto emite contra su propia
factura y no hay nada que verificar ante la DIAN. Dos manos para lo que
decide una solo agregan el tiempo que la solicitud pasa esperando. En la
institucional Contabilidad sigue igual, porque ahí sí verifica algo: que la
factura tenga saldo a favor.

`solicitada` sobrevive como ETAPA DEL HISTORIAL —las que Contabilidad
autorizó en su día lo siguen diciendo— pero ya no es el estado de ninguna
solicitud viva ni un turno de nadie. La migración `nc_sin_autorizacion_pdv`
movió las que estaban ahí: las que Comercial ya había aprobado quedaron
listas para emitir, y las que no habían pasado por él volvieron a Comercial,
que es donde el flujo de hoy las habría puesto.

**El estado dice de quién es el turno**, así que avanzar es pasar al
siguiente estado de la lista. En cada paso caben tres respuestas:

- **aprobar** — sigue al siguiente de la cadena, o queda lista para emitir;
- **rechazar** — se acabó, y eso es final;
- **devolver** — vuelve al solicitante para que corrija y la reenvíe.

Devolver existe porque «corrígelo y vuelve a mandarlo» no es un rechazo: si
lo fuera, habría que radicar otra desde cero, se gastaría un consecutivo, se
perdería por qué murió la primera y el mismo caso se contaría dos veces en el
informe. Al reenviarla vuelve al PRINCIPIO de su cadena — quien ya había
aprobado lo hizo sobre unos datos que acaban de cambiar, y arrastrar esa
firma sería darla por buena sin que nadie la mire otra vez.
"""
from app.core import bodegas, canales
from app.models.nota_credito import (
    ESTADO_APLICADA, ESTADO_APROBADA, ESTADO_CANCELADA, ESTADO_DEVUELTA,
    ESTADO_EN_BODEGA, ESTADO_EN_COMERCIAL, ESTADO_EN_CONTABILIDAD,
    ESTADO_RECHAZADA, ESTADO_SOLICITADA, ESTADOS, ESTADOS_ABIERTOS,
)
from app.models.user import User

CANAL_INSTITUCIONAL = "Venta institucional"

assert CANAL_INSTITUCIONAL in canales.CANALES, (
    "«Venta institucional» ya no está en core/canales.py. La cadena "
    "institucional de las notas crédito no sabría a quién aplicarse y todo "
    "caería en la rama del punto de venta, sin pasar por Comercial."
)

# Qué capacidad hay que tener para atender cada turno. Un estado que no está
# aquí no es turno de nadie: o es final, o está en manos del solicitante.
CAPACIDAD_POR_ESTADO = {
    ESTADO_EN_BODEGA:       "notas_credito.confirmar_producto",
    ESTADO_EN_COMERCIAL:    "notas_credito.aprobar_comercial",
    ESTADO_EN_CONTABILIDAD: "notas_credito.verificar_dian",
    ESTADO_APROBADA:        "notas_credito.registrar",
}

# Cómo se nombra cada turno en pantalla y en el asunto de un correo. Sin
# esto, un estado como «en_contabilidad» llegaría crudo al usuario.
#
# `solicitada` sigue aquí aunque ya no sea turno de nadie: es una etapa del
# historial, y una solicitud que en su día autorizó Contabilidad tiene que
# poder decir en qué paso fue.
ETIQUETA_ESTADO = {
    ESTADO_SOLICITADA:      "Esperando a Contabilidad",
    ESTADO_EN_BODEGA:       "Esperando a la bodega",
    ESTADO_EN_COMERCIAL:    "Esperando a Coordinación Comercial",
    ESTADO_EN_CONTABILIDAD: "Esperando a Contabilidad",
    ESTADO_APROBADA:        "Aprobada · falta emitirla",
}

# Qué se le pide a quien atiende cada turno. Va al correo y al encabezado de
# la pantalla: un aviso que dice «tienes algo pendiente» sin decir qué hay
# que hacer se archiva sin abrir.
QUE_HACER = {
    ESTADO_EN_BODEGA:       "Confirma si el producto llegó a la bodega y en qué estado.",
    ESTADO_EN_COMERCIAL:    "Aprueba o rechaza la nota crédito.",
    ESTADO_EN_CONTABILIDAD: "Verifica ante la DIAN si la factura tiene saldo a favor.",
    ESTADO_APROBADA:        "Emite la nota crédito y registra su número.",
}

ACCION_APROBAR = "aprobar"
ACCION_RECHAZAR = "rechazar"
ACCION_DEVOLVER = "devolver"
ACCIONES = (ACCION_APROBAR, ACCION_RECHAZAR, ACCION_DEVOLVER)


# ── Por qué se filtra la lista ──────────────────────────────────────
#
# **En el orden del flujo, y eso importa.** Cuando la lista de filtros se
# armaba recorriendo los estados tal como están declarados, salía
# «Contabilidad, bodega, Comercial» — y quien la lee concluye, con razón, que
# el flujo va en ese orden. El orden de una lista es una afirmación sobre el
# proceso aunque nadie la escriba.
#
# Un grupo puede cubrir VARIOS estados: «Contabilidad» son los dos momentos
# en que la pelota está en su cancha, que para quien filtra son uno solo.
GRUPO_MI_TURNO = "mi_turno"       # se resuelve contra el usuario, no contra una lista

GRUPOS_FILTRO: dict[str, tuple[str, ...]] = {
    "abiertas":     (),   # se llena abajo con ESTADOS_ABIERTOS
    "bodega":       (ESTADO_EN_BODEGA,),
    "comercial":    (ESTADO_EN_COMERCIAL,),
    # Solo la rama institucional: en la del mostrador Contabilidad ya no
    # tiene turno. El grupo se queda porque el turno de la DIAN sigue ahí.
    "contabilidad": (ESTADO_EN_CONTABILIDAD,),
    "por_emitir":   (ESTADO_APROBADA,),
    "devueltas":    (ESTADO_DEVUELTA,),
    "emitidas":     (ESTADO_APLICADA,),
    "rechazadas":   (ESTADO_RECHAZADA,),
    "retiradas":    (ESTADO_CANCELADA,),
}
GRUPOS_FILTRO["abiertas"] = tuple(ESTADOS_ABIERTOS)

assert set(ESTADOS) == {
    estado for clave, estados in GRUPOS_FILTRO.items() if clave != "abiertas"
    for estado in estados
}, (
    "Hay un estado de nota crédito que ningún filtro alcanza, o un filtro que "
    "apunta a un estado que ya no existe. Un estado sin filtro es una "
    "solicitud que no aparece por ningún lado."
)


def estados_del_filtro(clave: str) -> tuple[str, ...]:
    """Los estados que cubre un filtro; vacío si la clave no es un grupo."""
    return GRUPOS_FILTRO.get(clave, ())


def es_institucional(punto_venta: str | None) -> bool:
    """La rama se decide por el canal, que ya se elige de una lista cerrada."""
    return canales.normalizar(punto_venta) == CANAL_INSTITUCIONAL


def cadena(punto_venta: str | None, requiere_bodega: bool = False) -> tuple[str, ...]:
    """
    Los turnos por los que pasa esta solicitud, en orden, hasta quedar lista
    para emitir. `ESTADO_APROBADA` cierra la lista en las dos ramas: es el
    turno de quien la emite.
    """
    # El mostrador: Comercial decide y el punto emite. Contabilidad no tiene
    # turno aquí — no hay nada que verificar ante la DIAN y la decisión
    # comercial ya está tomada.
    if not es_institucional(punto_venta):
        return (ESTADO_EN_COMERCIAL, ESTADO_APROBADA)
    if requiere_bodega:
        return (ESTADO_EN_BODEGA, ESTADO_EN_COMERCIAL, ESTADO_EN_CONTABILIDAD, ESTADO_APROBADA)
    return (ESTADO_EN_COMERCIAL, ESTADO_EN_CONTABILIDAD, ESTADO_APROBADA)


def estado_inicial(punto_venta: str | None, requiere_bodega: bool = False) -> str:
    """Dónde nace la solicitud: el primer turno de su cadena."""
    return cadena(punto_venta, requiere_bodega)[0]


def siguiente(estado: str, punto_venta: str | None, requiere_bodega: bool = False) -> str | None:
    """
    El turno que sigue al aprobar, o `None` si ya no hay más.

    Devuelve `None` también cuando el estado no pertenece a esta cadena: eso
    es un caso imposible por diseño (el router comprueba el turno antes), y
    adivinar un «siguiente» sería inventar un paso.
    """
    pasos = cadena(punto_venta, requiere_bodega)
    if estado not in pasos:
        return None
    posicion = pasos.index(estado)
    return pasos[posicion + 1] if posicion + 1 < len(pasos) else None


def capacidad_de(estado: str) -> str | None:
    """Qué capacidad atiende este turno. `None` si no es turno de nadie."""
    return CAPACIDAD_POR_ESTADO.get(estado)


def atiende_la_bodega(usuario: User, bodega: str | None) -> bool:
    """
    ¿A esta persona le toca esta bodega?

    Misma regla que el punto de venta en PQRS: quien tiene bodega marcada
    atiende la suya, y quien no la tiene atiende todas — es el coordinador
    que responde por las dos, y dejarlo por fuera lo obligaría a inventarse
    una bodega falsa para poder trabajar.
    """
    suya = bodegas.normalizar(usuario.bodega)
    return suya is None or suya == bodegas.normalizar(bodega)


def etiqueta(estado: str) -> str:
    """Cómo se le dice a este estado en pantalla."""
    return ETIQUETA_ESTADO.get(estado, estado.replace("_", " ").capitalize())
