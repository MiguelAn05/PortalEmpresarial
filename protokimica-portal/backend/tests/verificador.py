"""
Un acumulador de comprobaciones.

`assert` corta en la primera falla, y cuando algo se rompe conviene ver TODO
lo que se rompió de una sola pasada en vez de arreglar-correr-arreglar. Esto
recoge todas las fallas de un bloque y las reporta juntas al final.
"""


class Verificador:
    def __init__(self):
        self.fallos = []

    def check(self, nombre: str, condicion, contexto=None) -> bool:
        """Registra una comprobación. `contexto` se imprime solo si falla."""
        if not condicion:
            detalle = f"  · {nombre}"
            if contexto is not None:
                detalle += f"\n      obtenido: {contexto!r}"
            self.fallos.append(detalle)
        return bool(condicion)

    def listo(self) -> None:
        """Falla la prueba si hubo comprobaciones rotas, listándolas todas."""
        if self.fallos:
            raise AssertionError(
                f"\n{len(self.fallos)} comprobación(es) fallaron:\n" + "\n".join(self.fallos)
            )
