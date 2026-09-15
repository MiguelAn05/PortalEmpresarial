"""
Fórmulas personalizadas de indicadores: `80 * A / B`, `(A - B) / A * 100`.

Hay indicadores que no caben en «un valor» ni en «numerador ÷ denominador»:
Calidad los define con constantes, restas o tres variables. Antes la única
salida era hacer la cuenta en Excel y digitar el resultado — con lo que el
portal perdía los números de base y el acumulado del trimestre salía mal.

Aquí la fórmula se guarda como texto en una gramática CERRADA y se evalúa con
un analizador propio, nunca con `eval`: lo que se escribe en un formulario no
puede ejecutar código en el servidor. La gramática admite solo:

- números (`80`, `2.5`, `2,5`)
- variables: una letra mayúscula `A`–`Z`, cada una declarada en el indicador
- `+ - * /` (también `× ÷ −`, como los muestra la pantalla)
- paréntesis y el signo negativo

Precedencia de siempre: primero `* /`, después `+ -`, de izquierda a derecha.

**Dividir por cero no es un error de la fórmula, es un mes sin dato.** Si en
un periodo no hubo casos, `A / B` con `B = 0` no vale cero — no vale nada — y
así lo trata el semáforo: «sin dato», que no baja el cumplimiento.
"""
import re
from dataclasses import dataclass

MAX_LARGO = 300
MAX_VARIABLES = 10
LETRAS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# Cómo se escribe cada operador para una persona. `*` y `/` son para el
# teclado; en pantalla y en el historial se lee `×` y `÷`.
LEGIBLE = {"+": "+", "-": "−", "*": "×", "/": "÷"}
EQUIVALENTES = {"×": "*", "x": "*", "÷": "/", "−": "-", "–": "-"}


class ErrorFormula(ValueError):
    """La fórmula no se puede leer. El mensaje dice qué corregir."""


class DivisionPorCero(ArithmeticError):
    """Con esos valores la fórmula divide por cero: el periodo queda sin dato."""


@dataclass(frozen=True)
class Token:
    tipo: str      # num | var | op | abre | cierra
    texto: str


_PATRON = re.compile(r"\s*(?:(\d+(?:[.,]\d+)?)|([A-Z])|([+\-*/])|(\()|(\)))")


def tokenizar(formula: str) -> list[Token]:
    texto = (formula or "").strip()
    for raro, normal in EQUIVALENTES.items():
        texto = texto.replace(raro, normal)
    if not texto:
        raise ErrorFormula("La fórmula está vacía. Arma al menos una operación con las variables.")
    if len(texto) > MAX_LARGO:
        raise ErrorFormula(f"La fórmula es demasiado larga (máximo {MAX_LARGO} caracteres).")

    tokens, pos = [], 0
    while pos < len(texto):
        if texto[pos].isspace():
            pos += 1
            continue
        m = _PATRON.match(texto, pos)
        if not m or m.end() == pos:
            simbolo = texto[pos]
            if simbolo.isalpha():
                raise ErrorFormula(
                    f"«{simbolo}» no es una variable. Las variables son letras "
                    "mayúsculas (A, B, C…) declaradas en el indicador."
                )
            raise ErrorFormula(f"«{simbolo}» no se entiende. Usa solo números, variables, + − × ÷ y paréntesis.")
        numero, variable, operador, abre, cierra = m.groups()
        if numero:
            tokens.append(Token("num", numero.replace(",", ".")))
        elif variable:
            tokens.append(Token("var", variable))
        elif operador:
            tokens.append(Token("op", operador))
        elif abre:
            tokens.append(Token("abre", "("))
        else:
            tokens.append(Token("cierra", ")"))
        pos = m.end()
    return tokens


# ── Analizador: descenso recursivo ─────────────────────────────────────
# El árbol son tuplas: ("num", 80.0) | ("var", "A") | ("neg", nodo) |
# (op, izquierda, derecha).

class _Analizador:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.i = 0

    def _actual(self) -> Token | None:
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def analizar(self):
        nodo = self._expresion()
        sobrante = self._actual()
        if sobrante is not None:
            if sobrante.tipo == "cierra":
                raise ErrorFormula("Sobra un paréntesis de cierre «)».")
            anterior = self.tokens[self.i - 1].texto
            raise ErrorFormula(
                f"Falta un operador entre «{anterior}» y «{sobrante.texto}» "
                "(por ejemplo × o ÷)."
            )
        return nodo

    def _expresion(self):
        nodo = self._termino()
        while (t := self._actual()) and t.tipo == "op" and t.texto in "+-":
            self.i += 1
            nodo = (t.texto, nodo, self._termino())
        return nodo

    def _termino(self):
        nodo = self._factor()
        while (t := self._actual()) and t.tipo == "op" and t.texto in "*/":
            self.i += 1
            nodo = (t.texto, nodo, self._factor())
        return nodo

    def _factor(self):
        t = self._actual()
        if t is None:
            raise ErrorFormula("La fórmula termina en un operador: falta un número o una variable al final.")
        if t.tipo == "op" and t.texto == "-":
            self.i += 1
            return ("neg", self._factor())
        if t.tipo == "num":
            self.i += 1
            return ("num", float(t.texto))
        if t.tipo == "var":
            self.i += 1
            return ("var", t.texto)
        if t.tipo == "abre":
            self.i += 1
            if (siguiente := self._actual()) and siguiente.tipo == "cierra":
                raise ErrorFormula("Hay unos paréntesis vacíos «()».")
            nodo = self._expresion()
            if (cierre := self._actual()) is None or cierre.tipo != "cierra":
                raise ErrorFormula("Falta cerrar un paréntesis «)».")
            self.i += 1
            return nodo
        if t.tipo == "cierra":
            raise ErrorFormula("Hay un paréntesis «)» donde falta un número o una variable.")
        raise ErrorFormula(f"Hay dos operadores seguidos cerca de «{t.texto}».")


def analizar(formula: str):
    return _Analizador(tokenizar(formula)).analizar()


def variables_usadas(formula: str) -> set[str]:
    return {t.texto for t in tokenizar(formula) if t.tipo == "var"}


def validar(formula: str, letras_declaradas: list[str]) -> None:
    """
    La fórmula se puede leer y usa exactamente las variables declaradas.

    Una variable declarada que la fórmula no usa también es un error: es un
    número que alguien tendría que digitar cada mes para nada.
    """
    analizar(formula)
    usadas = variables_usadas(formula)
    if not usadas:
        raise ErrorFormula("La fórmula no usa ninguna variable. Para un número fijo, usa «Un solo valor».")
    sin_declarar = sorted(usadas - set(letras_declaradas))
    if sin_declarar:
        raise ErrorFormula(
            f"La fórmula usa {', '.join(sin_declarar)}, que no está entre las variables. "
            "Agrégala o quítala de la fórmula."
        )
    sin_usar = sorted(set(letras_declaradas) - usadas)
    if sin_usar:
        raise ErrorFormula(
            f"La variable {', '.join(sin_usar)} no se usa en la fórmula. "
            "Inclúyela o quítala: si no, habría que digitarla cada mes para nada."
        )


def _evaluar(nodo, valores: dict[str, float]) -> float:
    tipo = nodo[0]
    if tipo == "num":
        return nodo[1]
    if tipo == "var":
        return valores[nodo[1]]
    if tipo == "neg":
        return -_evaluar(nodo[1], valores)
    izquierda, derecha = _evaluar(nodo[1], valores), _evaluar(nodo[2], valores)
    if tipo == "+":
        return izquierda + derecha
    if tipo == "-":
        return izquierda - derecha
    if tipo == "*":
        return izquierda * derecha
    if derecha == 0:
        raise DivisionPorCero()
    return izquierda / derecha


def evaluar(formula: str, valores: dict[str, float]) -> float:
    """
    El resultado, redondeado a 4 decimales como se guarda en `ind_mediciones`.

    Lanza `DivisionPorCero` si con esos valores se divide por cero, y
    `ErrorFormula` si falta el valor de alguna variable.
    """
    faltan = sorted(variables_usadas(formula) - set(valores))
    if faltan:
        raise ErrorFormula(f"Falta el valor de {', '.join(faltan)}.")
    return round(_evaluar(analizar(formula), valores), 4)


def legible(formula: str, etiquetas: dict[str, str] | None = None) -> str:
    """
    La fórmula como se lee en voz alta: `80 × Quejas atendidas ÷ Total de quejas`.

    Es lo que se muestra en la ficha del indicador y en el historial: una
    letra suelta no le dice nada a quien no armó la fórmula.
    """
    etiquetas = etiquetas or {}
    partes = []
    for t in tokenizar(formula):
        if t.tipo == "var":
            partes.append(etiquetas.get(t.texto) or t.texto)
        elif t.tipo == "op":
            partes.append(LEGIBLE[t.texto])
        elif t.tipo == "num":
            # Coma decimal, como se escribe en Colombia: «2,5», no «2.5».
            numero = t.texto.rstrip("0").rstrip(".") if "." in t.texto else t.texto
            partes.append(numero.replace(".", ","))
        else:
            partes.append(t.texto)
    texto = " ".join(partes)
    return texto.replace("( ", "(").replace(" )", ")")


def normalizar(formula: str) -> str:
    """La forma canónica que se guarda: `80 * A / B`, con espacios uniformes."""
    return " ".join(t.texto for t in tokenizar(formula)).replace("( ", "(").replace(" )", ")")
