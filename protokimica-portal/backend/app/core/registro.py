"""
Qué módulos tiene el portal, y cómo cada uno le aporta piezas a los que las
reúnen.

Indicadores e Inicio necesitan saber algo de los demás —qué se puede medir
solo, qué pendientes tiene la persona— y antes lo sabían importando las
tablas de PQRS, Master Planner, Mejora y Encuestas. Así ninguno de esos
módulos se podía quitar: Indicadores no arrancaba sin todos.

Ahora es al revés. Cada módulo deja un archivo con nombre fijo dentro de su
paquete, y quien reúne recorre los módulos instalados y toma lo que haya:

| Archivo                 | Lo reúne      | Qué declara                         |
|-------------------------|---------------|-------------------------------------|
| `fuentes_indicador.py`  | Indicadores   | `FUENTES` y, si aplica, `DINAMICAS` |
| `inicio.py`             | Inicio        | `APORTE` (ver `core/inicio.py`)     |
| `origen_encuesta.py`    | Encuestas     | `ORIGENES` (ver `core/origenes_encuesta.py`) |

Un módulo que no está instalado simplemente no aporta. Un error DENTRO de una
pieza sí revienta, a propósito: esconderlo dejaría un indicador sin calcular
sin que nadie supiera por qué.

**Instalado no es contratado.** `MODULOS_INSTALADOS` dice qué código hay en
este servidor; qué abre cada empresa lo dice `tenant_modulos` (ver
`core/modulos.py`). Quien reúne piezas filtra por las dos cosas con
`paquete_de()` y `modulos.paquete_contratado()`: así una empresa sin PQRS no
ve sus fuentes en Indicadores ni su tarjeta en Inicio.
"""
import importlib
import importlib.util
from types import ModuleType

# El orden importa: es el orden en que salen las fuentes en el desplegable y
# los pendientes en el inicio.
MODULOS_INSTALADOS = (
    "pqrs",
    "autorizaciones",
    "catalogo",
    "notas_credito",
    "master_planner",
    "indicadores",
    "mejora",
    "encuestas",
)


def paquete_de(pieza: ModuleType) -> str:
    """'app.modules.pqrs.inicio' -> 'pqrs'"""
    return pieza.__name__.split(".")[2]


def piezas(nombre: str) -> list[ModuleType]:
    """`app.modules.<modulo>.<nombre>` de cada módulo instalado que lo tenga."""
    encontradas = []
    for modulo in MODULOS_INSTALADOS:
        ruta = f"app.modules.{modulo}.{nombre}"
        try:
            existe = importlib.util.find_spec(ruta) is not None
        except ModuleNotFoundError:
            # El paquete del módulo no está: no está instalado.
            existe = False
        if existe:
            encontradas.append(importlib.import_module(ruta))
    return encontradas
