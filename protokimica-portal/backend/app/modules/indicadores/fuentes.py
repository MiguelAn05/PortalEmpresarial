"""
Indicadores que el portal calcula solo, sin que nadie digite nada.

Cada fuente devuelve numerador y denominador cuando el indicador es una
proporción. Eso es lo que permite que el acumulado trimestral y anual sea
correcto: se suman los numeradores y los denominadores, no se promedian los
porcentajes de cada mes.

**Este archivo no conoce a ningún módulo.** Las fuentes las declara cada uno
en su `fuentes_indicador.py` —PQRS las suyas, Master Planner las suyas— y
aquí solo se reúnen (ver `core/registro.py`). Antes vivían todas en este
archivo, que importaba las tablas de PQRS, Master Planner, Mejora y
Encuestas: Indicadores no podía instalarse sin los cuatro.

Para agregar una fuente nueva: declararla en el `fuentes_indicador.py` de su
módulo. Ni este archivo ni el resto de Indicadores necesitan cambios.
"""
from sqlalchemy.orm import Session

from app.core import registro
from app.core.fuentes import FuentesDinamicas, Resultado  # noqa: F401  (Resultado: lo usan las pruebas)
from app.core.modulos import paquete_contratado
from app.models.tenant import Tenant


def _reunir() -> tuple[dict, list[FuentesDinamicas], dict[str, str]]:
    catalogo: dict[str, dict] = {}
    dinamicas: list[FuentesDinamicas] = []
    # De qué paquete viene cada fuente y cada prefijo dinámico: con eso se
    # filtra por lo que la empresa tiene contratado.
    paquete: dict[str, str] = {}
    for pieza in registro.piezas("fuentes_indicador"):
        for clave, cfg in getattr(pieza, "FUENTES", {}).items():
            # Dos módulos con la misma clave harían que uno pisara al otro en
            # silencio, y un indicador empezaría a medir otra cosa.
            assert clave not in catalogo, (
                f"La fuente '{clave}' está declarada dos veces (la segunda en {pieza.__name__})."
            )
            catalogo[clave] = cfg
            paquete[clave] = registro.paquete_de(pieza)
        dinamica = getattr(pieza, "DINAMICAS", None)
        if dinamica is not None:
            dinamicas.append(dinamica)
            paquete[dinamica.prefijo] = registro.paquete_de(pieza)
    return catalogo, dinamicas, paquete


# Las fijas, ya reunidas: `{clave: {... "fn": función}}`. Son TODAS las que
# hay en el servidor; qué ve cada empresa lo filtra `_contratada()`.
CATALOGO, DINAMICAS, _PAQUETE = _reunir()

# Lo que solo sirve por dentro y no se publica en la API.
_PRIVADAS = {"fn", "una_por_area"}


def _dinamica_de(clave: str) -> FuentesDinamicas | None:
    return next((d for d in DINAMICAS if d.es_suya(clave)), None)


def _contratada(db: Session, tenant_id: int, clave_o_prefijo: str) -> bool:
    """¿La empresa tiene el módulo que aporta esta fuente?"""
    paquete = _PAQUETE.get(clave_o_prefijo)
    return paquete is None or paquete_contratado(db.get(Tenant, tenant_id), paquete)


def es_por_area(clave: str | None) -> bool:
    """¿La fuente se calcula con los datos del área del indicador?"""
    return bool(CATALOGO.get(clave or "", {}).get("por_area"))


def una_por_area(db: Session, tenant_id: int) -> tuple[str, dict] | None:
    """
    La fuente que se crea en todas las áreas con un botón («Gestión de OMP»),
    o None si el módulo que la aporta no está instalado o no está contratado.
    """
    return next(
        ((clave, cfg) for clave, cfg in CATALOGO.items()
         if cfg.get("una_por_area") and _contratada(db, tenant_id, clave)),
        None,
    )


def calcular(clave: str, db: Session, tenant_id: int, anio: int, mes: int,
             area: str | None = None) -> Resultado:
    dinamica = _dinamica_de(clave)
    fuente = CATALOGO.get(clave)
    if not dinamica and not fuente:
        raise ValueError(f"No existe la fuente automática '{clave}'.")

    # Un indicador creado cuando la empresa tenía el módulo sigue existiendo
    # si lo deja de tener. Se queda «sin dato»: un error haría fallar el
    # cálculo del mes entero, y un cero diría que se midió y dio cero.
    if not _contratada(db, tenant_id, dinamica.prefijo if dinamica else clave):
        return Resultado(
            valor=None, numerador=0, denominador=0,
            detalle="El módulo que alimenta este indicador no está contratado.",
        )
    if dinamica:
        return dinamica.calcular(clave, db, tenant_id, anio, mes)
    if fuente.get("por_area"):
        if not area:
            raise ValueError(
                f"«{fuente['nombre']}» se calcula por área: asígnale un área al indicador."
            )
        return fuente["fn"](db, tenant_id, anio, mes, area)
    # `acepta_area` es más suave que `por_area`: el área ACOTA el cálculo si
    # la hay, y sin ella se mide toda la empresa. Un indicador de gerencia
    # quiere el total; uno de un área, lo suyo.
    if fuente.get("acepta_area"):
        return fuente["fn"](db, tenant_id, anio, mes, area)
    return fuente["fn"](db, tenant_id, anio, mes)


def catalogo_publico(db: Session | None = None, tenant_id: int | None = None) -> list[dict]:
    """
    El catálogo sin las funciones, para exponerlo por la API.

    Con `db` agrega las fuentes dinámicas (las encuestas existentes). Sin él
    devuelve solo las fijas, que es lo que necesitan las pruebas y cualquier
    consulta que no dependa de qué encuestas haya creadas.
    """
    if db is None or tenant_id is None:
        return [
            {"clave": clave, **{k: v for k, v in cfg.items() if k not in _PRIVADAS}}
            for clave, cfg in CATALOGO.items()
        ]
    fijas = [
        {"clave": clave, **{k: v for k, v in cfg.items() if k not in _PRIVADAS}}
        for clave, cfg in CATALOGO.items() if _contratada(db, tenant_id, clave)
    ]
    return fijas + [
        f for d in DINAMICAS if _contratada(db, tenant_id, d.prefijo)
        for f in d.listar(db, tenant_id)
    ]


def existe_fuente(clave: str, db: Session, tenant_id: int) -> bool:
    """
    ¿Se puede calcular esta clave? Para validar al crear el indicador, en vez
    de dejar que falle meses después cuando alguien pida el cálculo.
    """
    if clave in CATALOGO:
        return _contratada(db, tenant_id, clave)
    dinamica = _dinamica_de(clave)
    return bool(
        dinamica and _contratada(db, tenant_id, dinamica.prefijo)
        and dinamica.existe(clave, db, tenant_id)
    )
