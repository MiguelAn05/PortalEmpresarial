"""
El flujo real de las PQRS: por dónde han pasado y qué conceptos se pidieron,
reconstruido del historial.

Primer paso para automatizar el recorrido. **Solo lee**: no escribe nada en
la base, así que se puede correr en producción las veces que haga falta.

    docker exec protokimica_backend python -m app.scripts.analizar_flujo_pqrs
    docker exec protokimica_backend python -m app.scripts.analizar_flujo_pqrs --desde 2026-01-01
    docker exec protokimica_backend python -m app.scripts.analizar_flujo_pqrs --json /tmp/flujo.json

El JSON trae además el recorrido y la cadena de conceptos de cada PQRS, para
revisarlo caso por caso. Para sacarlo del contenedor:
`docker cp protokimica_backend:/tmp/flujo.json .`

La lógica está en `app/modules/pqrs/flujo_historico.py`, con sus pruebas.
"""
import argparse
import json
from datetime import date

import app.main  # noqa: F401  — registra todos los modelos
from app.core.database import SessionLocal
from app.core.tenant_publico import SLUG_PUBLICO
from app.models.tenant import Tenant
from app.modules.pqrs.flujo_historico import MINIMO_CASOS, UMBRAL_PATRON, analizar

FLECHA = " → "


def _titulo(texto: str) -> None:
    print(f"\n{texto}\n{'─' * len(texto)}")


def _ruta(ruta: list[str]) -> str:
    return FLECHA.join(ruta)


def _recorridos(recorridos: list[dict], sangria: str = "  ") -> None:
    for r in recorridos:
        print(f"{sangria}{r['n']:>4}  {r['pct']:>5}%  {_ruta(r['ruta'])}")


def _grupos(grupos: list[dict]) -> None:
    """Cada grupo: la plantilla candidata primero, y debajo cómo se ve hoy."""
    if not grupos:
        print("  (ninguna)")
        return
    for g in grupos:
        con = g["n"] - g["sin_conceptos"]
        print(f"\n  {g['grupo']} — {g['n']} PQRS ({con} pidieron conceptos)")
        p = g["plantilla"]
        if p["hay_plantilla"]:
            pasos = FLECHA.join(f"{x['concepto']} ({x['pct']}%)" for x in p["pasos"])
            print(f"    >> Plantilla candidata: {pasos}")
        else:
            print(f"    >> Sin plantilla: {p['motivo']}")
        if g["cadenas"]:
            print("    Cadenas exactas más comunes:")
            for c in g["cadenas"]:
                print(f"      {c['n']:>3}  {_ruta(c['cadena'])}")
        if g["resuelve"]:
            quien = ", ".join(f"{area} ({n})" for area, n in g["resuelve"])
            print(f"    La resuelve: {quien}")


def imprimir(r: dict, empresa: str, desde: date | None) -> None:
    s = r["resumen"]
    centro = r["centro"] or "quien reparte"
    print(f"Flujo real de las PQRS · {empresa}" + (f" · radicadas desde {desde}" if desde else " · todo el histórico"))

    _titulo("Resumen")
    print(f"  PQRS analizadas:            {s['pqrs']} ({s['abiertas']} abiertas)")
    print(f"  Pasaron por más de un área: {s['se_movieron']}")
    print(f"  Áreas por PQRS:             {s['areas_promedio']} en promedio, {s['areas_maximo']} como máximo")
    print(f"  Pidieron conceptos:         {s['con_conceptos']} ({s['conceptos_promedio']} en promedio cada una)")
    print(f"  Un área recibió el mismo caso más de una vez (sin contar {centro}): {s['con_repetidas']}")
    print(f"  Con causa («Asociado a»):   {s['con_causa']}")
    if s["movimientos_ilegibles"]:
        print(f"  Movimientos que no se pudieron leer: {s['movimientos_ilegibles']} "
              "(comentario escrito a mano en el formato viejo; no se adivinan)")

    _titulo("Conceptos (autorizaciones)")
    print(f"  {'Veces':>5} {'PQRS':>5}  Concepto (área que responde) — cómo se respondió · tiempo · se volvió a pedir")
    for a in r["autorizaciones"]:
        estados = ", ".join(f"{k}: {v}" for k, v in sorted(a["estados"].items()))
        dias = f" · {a['dias_promedio']} días hábiles" if a["dias_promedio"] is not None else ""
        repedido = f" · pedido de nuevo {a['repedido']} vez/veces tras rechazo o devolución" if a["repedido"] else ""
        print(f"  {a['n']:>5} {a['pqrs']:>5}  {a['tipo']} ({a['area']}) — {estados}{dias}{repedido}")

    _titulo("Por canal")
    _grupos(r["por_canal"])

    _titulo("Por tipo y canal")
    _grupos(r["por_tipo_y_canal"])

    _titulo("Por causa («Asociado a»)")
    if not r["por_asociado"]:
        print("  Todavía no hay PQRS clasificadas. Entre más tengan causa, más dice este bloque:")
        print("  es el que de verdad decide la plantilla.")
    else:
        _grupos(r["por_asociado"])

    _titulo("Áreas que intervienen")
    print(f"  {'Área':<30} {'PQRS':>5} {'%':>6} {'Resolvió':>9}")
    for a in r["areas"]:
        print(f"  {a['area']:<30} {a['pqrs']:>5} {a['pct']:>5}% {a['resolvio']:>9}")

    _titulo(f"Áreas que recibieron el mismo caso más de una vez (sin contar {centro})")
    if not r["repetidas"]:
        print("  Ninguna.")
    for c in r["repetidas"]:
        print(f"  {c['codigo']:<14} {', '.join(c['areas'])}")

    _titulo("Recorridos de áreas más comunes")
    _recorridos(r["recorridos"])

    _titulo("Cuánto se demora cada área (desde la 0.48)")
    if not r["tiempos"]:
        print("  Todavía no hay tramos terminados.")
    for t in r["tiempos"]:
        print(f"  {t['area']:<30} {t['tramos']:>4} veces · {t['dias_promedio']} días hábiles · {t['pasadas']} pasadas de 3 días")

    pct = int(UMBRAL_PATRON * 100)
    print(f"\nUna «plantilla candidata» son los conceptos que pide al menos el {pct}% de las PQRS de su grupo")
    print(f"(contando solo las que piden alguno, y con {MINIMO_CASOS} o más), en el orden en que suelen pedirse.")
    print("Es lo que se hace HOY, errores incluidos: la plantilla oficial la deciden las personas.")
    print("«Sin asignar» al comienzo de una ruta es una PQRS que nació sin área (antes de la 0.49,")
    print("cuando el formulario la dejaba vacía). Desde entonces todas nacen con quien reparte.")


def main() -> None:
    parser = argparse.ArgumentParser(description="El flujo real de las PQRS, desde su historial. Solo lee.")
    parser.add_argument("--empresa", default=SLUG_PUBLICO, help="slug de la empresa (por defecto, la pública)")
    parser.add_argument("--desde", type=date.fromisoformat, help="solo las radicadas desde esta fecha (AAAA-MM-DD)")
    parser.add_argument("--top", type=int, default=5, help="cuántas cadenas mostrar por grupo")
    parser.add_argument("--json", help="además, guarda todo (con el detalle de cada PQRS) en este archivo")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.slug == args.empresa).first()
        if not tenant:
            raise SystemExit(f"No existe la empresa «{args.empresa}». Revisa el slug con --empresa.")
        nombre = getattr(tenant, "nombre", None) or args.empresa
        resultado = analizar(db, tenant.id, args.desde, args.top)
    finally:
        db.close()

    imprimir(resultado, nombre, args.desde)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as archivo:
            json.dump(resultado, archivo, ensure_ascii=False, indent=2, default=str)
        print(f"\nGuardado en {args.json}")


if __name__ == "__main__":
    main()
