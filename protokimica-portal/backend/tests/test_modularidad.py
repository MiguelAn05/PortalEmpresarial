"""
Cada módulo depende solo de los que tiene declarados.

El portal se va a ofrecer por módulos, y eso solo es posible si quitar uno no
rompe a los demás. Antes no era así: guardar archivos y avisar a n8n vivían
dentro de PQRS, Indicadores importaba las tablas de cuatro módulos para sus
fuentes, Inicio las de tres y Encuestas leía la tabla de PQRS. Hoy lo común
está en `app/core` y lo que un módulo le aporta a otro lo declara en su
propio paquete (`fuentes_indicador.py`, `inicio.py`, `origen_encuesta.py`;
ver `core/registro.py`).

Esta prueba falla si un módulo vuelve a importar de otro —sus funciones o
sus tablas— sin que la dependencia esté escrita aquí con su motivo. Quitar
una es la meta; agregar una debería doler.
"""
import re
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"
MODULOS = APP / "modules"

# A qué módulo pertenece cada archivo de `app/models`. `user`, `tenant` y
# `capacidad` son de la plataforma: los usa cualquiera.
DUENO_DE_MODELOS = {
    "pqrs": "pqrs",
    "autorizacion": "autorizaciones",
    "catalogo": "catalogo",
    "nota_credito": "notas_credito",
    "master_planner": "master_planner",
    "indicadores": "indicadores",
    "mejora": "mejora",
    "encuestas": "encuestas",
}

DEPENDENCIAS_PERMITIDAS = {
    # Atención al cliente se vende junta: una autorización se pide sobre una
    # PQRS, y el producto de una PQRS se confirma contra el catálogo.
    "pqrs": {"autorizaciones", "catalogo"},
    "autorizaciones": {"pqrs"},
    # Una OMP nace de un indicador y se verifica contra su medición: Gestión
    # y mejora se vende junta.
    "mejora": {"indicadores"},
}

IMPORTA = re.compile(r"^\s*(?:from|import)\s+app\.(modules|models)\.(\w+)", re.M)


def _dependencias_reales() -> dict[str, dict[str, list[str]]]:
    """{modulo: {modulo_del_que_depende: [archivos]}}"""
    encontradas: dict[str, dict[str, list[str]]] = {}
    for archivo in MODULOS.rglob("*.py"):
        modulo = archivo.relative_to(MODULOS).parts[0]
        for tipo, nombre in IMPORTA.findall(archivo.read_text(encoding="utf-8")):
            destino = nombre if tipo == "modules" else DUENO_DE_MODELOS.get(nombre)
            if destino and destino != modulo:
                (encontradas.setdefault(modulo, {})
                 .setdefault(destino, [])
                 .append(str(archivo.relative_to(APP))))
    return encontradas


def test_ningun_modulo_depende_de_otro_sin_declararlo():
    sobrantes = {
        f"{modulo} -> {destino}": archivos
        for modulo, destinos in _dependencias_reales().items()
        for destino, archivos in destinos.items()
        if destino not in DEPENDENCIAS_PERMITIDAS.get(modulo, set())
    }
    assert not sobrantes, (
        f"Dependencias entre módulos no declaradas: {sobrantes}. "
        "Si es algo que usan varios módulos (archivos, avisos, fechas), va en "
        "app/core. Si un módulo le aporta algo a otro, se declara en su propio "
        "paquete y el otro lo reúne con core/registro.py."
    )


def test_las_dependencias_declaradas_siguen_existiendo():
    """Una excepción que ya no hace falta se borra, o se vuelve a usar sin que nadie lo note."""
    reales = _dependencias_reales()
    viejas = [
        f"{modulo} -> {destino}"
        for modulo, destinos in DEPENDENCIAS_PERMITIDAS.items()
        for destino in destinos
        if destino not in reales.get(modulo, {})
    ]
    assert not viejas, f"Ya no se usan; quítalas de DEPENDENCIAS_PERMITIDAS: {viejas}"


def test_los_modulos_del_registro_existen():
    from app.core.registro import MODULOS_INSTALADOS

    faltan = [m for m in MODULOS_INSTALADOS if not (MODULOS / m / "__init__.py").exists()]
    assert not faltan, f"core/registro.py nombra módulos que no existen: {faltan}"


def test_las_utilidades_compartidas_no_volvieron_a_un_modulo():
    """Que nadie las vuelva a definir dentro de un módulo «para tenerlas a mano»."""
    for archivo in MODULOS.rglob("*.py"):
        texto = archivo.read_text(encoding="utf-8")
        for nombre in ("guardar_archivo", "disparar_webhook_n8n", "enviar_avisos", "con_zona"):
            assert not re.search(rf"^(?:async\s+)?def {nombre}\(", texto, re.M), (
                f"{archivo.relative_to(APP)} vuelve a definir {nombre}(); vive en app/core."
            )
