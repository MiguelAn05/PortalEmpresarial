"""
Filtrar por un estado terminal tiene que devolver algo.

Cerrar un proyecto lo ARCHIVA, y la lista escondía los archivados por
defecto. Los dos filtros se anulaban: pedir «cerrado» devolvía siempre una
lista vacía, y había que adivinar que además tocaba marcar «archivados» —
justo lo que uno no marca cuando busca algo que acaba de cerrar.

La regla que lo arregla: **pedir un estado manda sobre el escondite.** Si
alguien filtra por cerrado, es que quiere verlos.
"""


def _proyecto(entorno, nombre, area="Calidad"):
    entorno.como("admin")
    r = entorno.post("/master-planner/proyectos", json={"nombre": nombre, "area": area})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _cerrar(entorno, pid, tipo="finalizado"):
    # Va como formulario, no como JSON: el endpoint acepta adjuntar el acta.
    return entorno.post(f"/master-planner/proyectos/{pid}/cerrar",
                        data={"tipo": tipo, "entregables": "Se entregó lo acordado."})


def _listar(entorno, **params):
    consulta = "&".join(f"{k}={v}" for k, v in params.items())
    ruta = "/master-planner/proyectos" + (f"?{consulta}" if consulta else "")
    return {p["nombre"] for p in entorno.get(ruta).json()}


# ── Master Planner ───────────────────────────────────────────────────

def test_un_proyecto_cerrado_aparece_al_filtrar_por_cerrado(entorno, v):
    """El defecto: la lista salía vacía porque cerrar también archiva."""
    pid = _proyecto(entorno, "Bodega nueva")
    r = _cerrar(entorno, pid)
    v.check("cierra", r.status_code in (200, 201), r.text[:200])

    v.check("aparece filtrando por cerrado",
            "Bodega nueva" in _listar(entorno, estado="cerrado"),
            _listar(entorno, estado="cerrado"))


def test_un_cancelado_aparece_al_filtrar_por_cancelado(entorno, v):
    pid = _proyecto(entorno, "Piloto de empaque")
    # Cancelar exige el motivo: un proyecto abandonado sin explicación no
    # le sirve a nadie al revisarlo después.
    r = entorno.post(f"/master-planner/proyectos/{pid}/cerrar",
                     data={"tipo": "cancelado", "motivo": "Se acabó el presupuesto."})
    v.check("cancela", r.status_code in (200, 201), r.text[:200])

    v.check("aparece", "Piloto de empaque" in _listar(entorno, estado="cancelado"),
            _listar(entorno, estado="cancelado"))


def test_sin_filtro_los_cerrados_siguen_fuera_del_dia_a_dia(entorno, v):
    """
    Que el arreglo no traiga de vuelta lo archivado a la vista de trabajo:
    es justo lo que archivar viene a evitar.
    """
    pid = _proyecto(entorno, "Bodega nueva")
    _proyecto(entorno, "Portal interno")
    _cerrar(entorno, pid)

    vistos = _listar(entorno)
    v.check("el cerrado no está", "Bodega nueva" not in vistos, vistos)
    v.check("el activo sí", "Portal interno" in vistos, vistos)


def test_filtrar_por_un_estado_activo_no_saca_lo_archivado(entorno, v):
    """
    La excepción es solo para los estados terminales. Un proyecto archivado a
    mano en otro estado sigue escondido, que es lo que se pidió al archivarlo.
    """
    pid = _proyecto(entorno, "Proyecto guardado")
    entorno.patch(f"/master-planner/proyectos/{pid}",
                  json={"estado": "pausado", "archivado": True})

    vistos = _listar(entorno, estado="pausado")
    v.check("no aparece", "Proyecto guardado" not in vistos, vistos)
    v.check("pero sí pidiendo el archivo",
            "Proyecto guardado" in _listar(entorno, estado="pausado", archivados="true"))


def test_el_archivo_completo_sigue_funcionando(entorno, v):
    pid = _proyecto(entorno, "Bodega nueva")
    _cerrar(entorno, pid)

    v.check("está en el archivo",
            "Bodega nueva" in _listar(entorno, archivados="true"),
            _listar(entorno, archivados="true"))


# ── Mejora ───────────────────────────────────────────────────────────

def test_una_omp_descartada_se_puede_pedir_por_su_estado(entorno, v):
    """
    El gemelo del mismo defecto: la lista trae solo las abiertas, así que
    filtrar por «descartada» devolvía vacío. El servidor sí sabe darlas
    cuando se piden — lo que fallaba era que la pantalla nunca las pedía.
    """
    entorno.como("calidad")
    creada = entorno.post("/mejora", json={
        "titulo": "Entregas por debajo de la meta", "origen": "otro",
        "area": "Calidad",
    }).json()
    entorno.patch(f"/mejora/{creada['id']}/estado",
                  json={"estado": "descartada", "motivo": "El proceso se rediseñó."})

    descartadas = entorno.get("/mejora?estado=descartada").json()
    v.check("la devuelve", any(o["id"] == creada["id"] for o in descartadas), descartadas)

    # Y `abiertas=true` sigue escondiéndolas: es lo que usa el tablero.
    abiertas = entorno.get("/mejora?abiertas=true").json()
    v.check("pero no entre las abiertas",
            all(o["id"] != creada["id"] for o in abiertas), abiertas)
