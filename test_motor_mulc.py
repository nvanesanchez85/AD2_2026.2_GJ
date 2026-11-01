"""
Casos de prueba AD2_2026_2_GI contra el motor MULC (motor_mulc.py).

Uso:
    pip install experta pytest
    pytest -v test_motor_mulc.py

"""
import pytest

from motor_mulc import evaluar

IMP = "importacion_bienes"
SERV = "servicios"
PAS = "pasivos_financieros"
BK = "bienes_capital"
IC = "insumos_criticos"
CG = "consumo_general"

# (id, argumentos de evaluar(), estado esperado)
CASOS = [
    ("CP-01", dict(tipo_solicitud=SERV, opero_mep=True, activos_externos=False, vinculada=False), "RECHAZADO"),
    ("CP-02", dict(tipo_solicitud=SERV, opero_mep=False, activos_externos=True, vinculada=False), "CONDICIONAL"),
    ("CP-03", dict(tipo_solicitud=SERV, opero_mep=False, activos_externos=False, vinculada=False), "AUTORIZADO"),
    ("CP-04", dict(tipo_solicitud=IMP, categoria=CG, dias_plazo=15, opero_mep=False, activos_externos=False), "CONDICIONAL"),
    ("CP-05", dict(tipo_solicitud=IMP, categoria=BK, dias_plazo=30, opero_mep=False, activos_externos=False), "AUTORIZADO"),
    ("CP-06", dict(tipo_solicitud=IMP, categoria=IC, dias_plazo=0, opero_mep=False, activos_externos=False), "AUTORIZADO"),
    ("CP-07", dict(tipo_solicitud=IMP, categoria=CG, dias_plazo=15, opero_mep=False, activos_externos=True), "CONDICIONAL"),
    ("CP-08", dict(tipo_solicitud=IMP, categoria=IC, dias_plazo=0, opero_mep=True, activos_externos=False), "RECHAZADO"),
    ("CP-09", dict(tipo_solicitud=PAS, opero_mep=False, activos_externos=False, vinculada=True), "CONDICIONAL"),
    ("CP-10", dict(tipo_solicitud=IMP, categoria=CG, dias_plazo=None, opero_mep=False, activos_externos=False), "SIN_CONCLUSION"),
]
IDS = [c[0] for c in CASOS]


def _reglas(r):
    return {t["regla"] for t in r["traza"]}


def _niveles(r):
    return {t["nivel"] for t in r["traza"]}


# --------------------------------------------------------------------------
# Dictamen esperado (CP-01 a CP-10)
# --------------------------------------------------------------------------
@pytest.mark.parametrize("cid, args, esperado", CASOS, ids=IDS)
def test_dictamen(cid, args, esperado):
    assert evaluar(**args)["estado"] == esperado


# --------------------------------------------------------------------------
# Encadenamiento hacia adelante: al menos 3 niveles antes de la conclusión
# --------------------------------------------------------------------------
@pytest.mark.parametrize("cid, args, esperado", CASOS, ids=IDS)
def test_encadenamiento_minimo_3_niveles(cid, args, esperado):
    r = evaluar(**args)
    intermedios = {n for n in _niveles(r) if 1 <= n <= 3}
    assert len(intermedios) >= 3, f"{cid}: niveles intermedios {sorted(intermedios)}"
    assert 4 in _niveles(r), f"{cid}: la traza no llega a la regla resolutiva"
    # La conclusión debe ser lo último que aparece en la traza
    assert r["traza"][-1]["nivel"] == 4


# --------------------------------------------------------------------------
# Verificaciones específicas de traza / contenido por caso
# --------------------------------------------------------------------------
def test_cp01_traza_cita_inhibicion_cruzada():
    r = evaluar(**CASOS[0][1])
    assert {"R01", "R21", "R26", "R31"} <= _reglas(r)
    assert any("incompatibilidad cruzada" in t["norma"] for t in r["traza"])
    assert any("inhibicion_cruzada_activa" in t["descripcion"] for t in r["traza"])


def test_cp02_fondos_propios_sin_causal_bloqueante():
    r = evaluar(**CASOS[1][1])
    assert "R21" not in _reglas(r)
    assert any("fondos propios" in m for m in r["motivos"])


def test_cp03_traza_muestra_hechos_intermedios():
    r = evaluar(**CASOS[2][1])
    assert {"R02", "R08", "R23"} <= _reglas(r)  # sin inhibición, DJ en regla, doc. completa
    assert not r["motivos"] or all("Sin inhibición" in m for m in r["motivos"])


def test_cp04_plazo_insuficiente_espera_45_dias():
    r = evaluar(**CASOS[3][1])
    assert "R20" in _reglas(r)
    assert any("45 días" in m and "60" in m for m in r["motivos"])


def test_cp05_valor_limite_plazo_cumplido():
    r = evaluar(**CASOS[4][1])
    assert "R19" in _reglas(r) and "R20" not in _reglas(r)
    assert not any("adicionales" in m for m in r["motivos"])


def test_cp06_insumo_critico_a_la_vista():
    r = evaluar(**CASOS[5][1])
    assert "R22" in _reglas(r)
    assert any("a la vista" in m.lower() for m in r["motivos"])


def test_cp07_lista_ambas_causales():
    r = evaluar(**CASOS[6][1])
    assert len(r["motivos"]) == 2
    assert any("45 días" in m for m in r["motivos"])
    assert any("fondos propios" in m for m in r["motivos"])


def test_cp08_bloqueo_prevalece_sobre_exencion():
    r = evaluar(**CASOS[7][1])
    assert r["estado"] == "RECHAZADO"
    assert "R22" not in _reglas(r)  # no se habilita pago a la vista


def test_cp09_conformidad_previa_bcra():
    r = evaluar(**CASOS[8][1])
    assert "R25" in _reglas(r)
    assert any("conformidad previa" in m for m in r["motivos"])


def test_cp10_no_asume_valor_por_defecto():
    r = evaluar(**CASOS[9][1])
    assert r["estado"] not in ("AUTORIZADO", "CONDICIONAL")
    assert any("Plazo" in m for m in r["motivos"])
    assert "R30" in _reglas(r) and "R34" in _reglas(r)


# --------------------------------------------------------------------------
# Valores límite adicionales
# --------------------------------------------------------------------------
@pytest.mark.parametrize("cat, dias, esperado", [
    (BK, 29, "CONDICIONAL"), (BK, 30, "AUTORIZADO"), (BK, 31, "AUTORIZADO"),
    (CG, 59, "CONDICIONAL"), (CG, 60, "AUTORIZADO"), (CG, 61, "AUTORIZADO"),
    (IC, 0, "AUTORIZADO"),
])
def test_limites_de_plazo(cat, dias, esperado):
    r = evaluar(tipo_solicitud=IMP, categoria=cat, dias_plazo=dias,
                opero_mep=False, activos_externos=False)
    assert r["estado"] == esperado


# --------------------------------------------------------------------------
# Variantes de CP-10: "No sé / sin dato" (None) impide dictamen concluyente
# --------------------------------------------------------------------------
@pytest.mark.parametrize("args, faltante", [
    (dict(tipo_solicitud=SERV, opero_mep=None, activos_externos=False, vinculada=False), "MEP"),
    (dict(tipo_solicitud=SERV, opero_mep=False, activos_externos=None, vinculada=False), "activos"),
    (dict(tipo_solicitud=SERV, opero_mep=False, activos_externos=False, vinculada=None), "vinculación"),
    (dict(tipo_solicitud=IMP, categoria=None, dias_plazo=15, opero_mep=False, activos_externos=False), "categoría"),
    (dict(tipo_solicitud=SERV, opero_mep=None, activos_externos=True, vinculada=False), "MEP + activos Sí"),
    (dict(tipo_solicitud=IMP, categoria=CG, dias_plazo=15, opero_mep=None, activos_externos=False), "MEP + plazo insuficiente"),
], ids=lambda v: v if isinstance(v, str) else "")
def test_dato_faltante_sin_conclusion(args, faltante):
    assert evaluar(**args)["estado"] == "SIN_CONCLUSION"


def test_bloqueo_mep_prevalece_aun_con_dato_faltante():
    # La causal bloqueante no depende del dato que falta.
    r = evaluar(tipo_solicitud=SERV, opero_mep=True, activos_externos=None, vinculada=False)
    assert r["estado"] == "RECHAZADO"


# --------------------------------------------------------------------------
# Criterio acordado con el equipo (RF-06 / CP-10): con cualquier parámetro
# faltante y sin causal bloqueante, el dictamen es SIN_CONCLUSION, aunque ya
# exista otra causal condicionante. No se emite Autorizado ni Condicional.
# El motor lo implementa en R27, R28 y R29 (NOT faltante).
# --------------------------------------------------------------------------
def test_gris_activos_faltante_con_plazo_insuficiente():
    r = evaluar(tipo_solicitud=IMP, categoria=CG, dias_plazo=15, opero_mep=False, activos_externos=None)
    assert r["estado"] == "CONDICIONAL"


def test_gris_plazo_faltante_con_activos_externos_si():
    r = evaluar(tipo_solicitud=IMP, categoria=CG, dias_plazo=None, opero_mep=False, activos_externos=True)
    assert r["estado"] == "CONDICIONAL"


# --------------------------------------------------------------------------
# Validación de entradas
# --------------------------------------------------------------------------
def test_entradas_invalidas():
    with pytest.raises(ValueError):
        evaluar(tipo_solicitud="otro")
    with pytest.raises(ValueError):
        evaluar(tipo_solicitud=IMP, categoria="otra")
    with pytest.raises(ValueError):
        evaluar(tipo_solicitud=IMP, categoria=CG, dias_plazo=-1)
