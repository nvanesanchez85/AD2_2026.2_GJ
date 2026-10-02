"""
Sistema experto MULC - Motor de inferencia (Experta, encadenamiento hacia adelante)

Asiste en la evaluación PREVIA de conformidad regulatoria antes de cursar una
solicitud de acceso al MULC del BCRA. No es asesoramiento legal vinculante.

Arquitectura:
    Nivel 0  Hechos iniciales (Dato)         <- formulario del usuario
    Nivel 1  Hechos intermedios básicos      <- inhibición, plazo mínimo, DJ, vinculación, faltantes
    Nivel 2  Hechos intermedios compuestos   <- plazo exigible válido, causal bloqueante, estado documental
    Nivel 3  Situación regulatoria           <- impedida / condicionada / sin obstáculos / indeterminada
    Nivel 4  Regla resolutiva                <- ESTADO_OPERACION (dictamen final)
"""

# --------------------------------------------------------------------------
# Compatibilidad: Experta 1.9.x depende de frozendict 1.2, que usa
# collections.Mapping (eliminado en Python 3.10+). Se restituyen los alias
# ANTES de importar experta.
# --------------------------------------------------------------------------
import collections
import collections.abc

for _nombre in ("Mapping", "MutableMapping", "Iterable", "Callable",
                "Sequence", "MutableSequence", "Set", "MutableSet"):
    if not hasattr(collections, _nombre):
        setattr(collections, _nombre, getattr(collections.abc, _nombre))

from experta import KnowledgeEngine, Fact, Rule, MATCH, TEST, NOT, P  # noqa: E402

# --------------------------------------------------------------------------
# PARÁMETROS NORMATIVOS (premisas aisladas y ajustables)
# Al cambiar la norma se modifica SOLO este bloque, sin reentrenar nada.
# Valores simplificados a efectos del trabajo: validar contra el texto
# ordenado vigente de "Exterior y Cambios" del BCRA antes de uso real.
# --------------------------------------------------------------------------
VENTANA_MEP_DIAS = 90            # días corridos de inhibición por operar MEP/CCL
UMBRAL_ACTIVOS_USD = 100_000     # umbral de libre disponibilidad de activos externos
PLAZOS_MINIMOS = {               # días mínimos de diferimiento por categoría
    "bienes_capital": 30,
    "insumos_criticos": 0,       # 0 = habilitado a la vista
    "consumo_general": 60,
}

TIPOS = {
    "importacion_bienes": "Pago diferido de importaciones de bienes",
    "servicios": "Pago de servicios",
    "pasivos_financieros": "Cancelación de pasivos financieros",
}
CATEGORIAS = {
    "bienes_capital": "Bienes de Capital",
    "insumos_criticos": "Insumos Críticos de Salud/Energía",
    "consumo_general": "Bienes de Consumo General",
}
TIPOS_SERVICIO_DEUDA = ("servicios", "pasivos_financieros")

ETIQUETAS_DICTAMEN = {
    "AUTORIZADO": "AUTORIZADO",
    "CONDICIONAL": "CONDICIONAL / REQUIERE GESTIÓN ADICIONAL",
    "RECHAZADO": "RECHAZADO / BLOQUEADO",
    "SIN_CONCLUSION": "SIN CONCLUSIÓN DETERMINABLE / FALTAN PARÁMETROS",
}


def _usd(valor):
    return f"{valor:,}".replace(",", ".")


ETIQUETAS_DATOS = {
    "tipo_solicitud": "Tipo de solicitud",
    "opero_mep": f"Operó MEP/CCL en los últimos {VENTANA_MEP_DIAS} días",
    "dias_plazo": "Días corridos desde registro aduanero / factura",
    "categoria": "Categoría del bien",
    "activos_externos": f"Disponibilidad líquida en el exterior > USD {_usd(UMBRAL_ACTIVOS_USD)} no aplicada",
    "vinculada": "Contraparte vinculada / mismo grupo económico",
}

# --------------------------------------------------------------------------
# CATÁLOGO DE REGLAS (documentación y trazabilidad normativa)
# --------------------------------------------------------------------------
N_INCOMP = "BCRA - Exterior y Cambios: incompatibilidad cruzada por operaciones MEP/CCL"
N_PLAZOS = "BCRA - Exterior y Cambios: plazos de acceso al MULC para pagos de importaciones (Com. 'A' 7770, 'A' 7782, 'A' 7840 y concordantes)"
N_DJ = "BCRA - Exterior y Cambios: declaración jurada de activos externos líquidos"
N_VINC = "BCRA - Exterior y Cambios: pagos a contrapartes vinculadas (conformidad previa)"
N_INT = "Derivación interna del motor (hecho intermedio)"
N_RES = "Regla resolutiva del sistema (ESTADO_OPERACION)"

CATALOGO = {
    # ---------------- Nivel 1 ----------------
    "R01": dict(nivel=1, rf="RF-01", norma=N_INCOMP,
                regla=f"SI operó MEP/CCL en los últimos {VENTANA_MEP_DIAS} días ENTONCES inhibicion_cruzada_activa = Sí"),
    "R02": dict(nivel=1, rf="RF-01", norma=N_INCOMP,
                regla=f"SI NO operó MEP/CCL en los últimos {VENTANA_MEP_DIAS} días ENTONCES inhibicion_cruzada_activa = No"),
    "R03": dict(nivel=1, rf="RF-02", norma=N_PLAZOS,
                regla="SI importación Y categoría = Bienes de Capital ENTONCES plazo_minimo_requerido = plazo BK"),
    "R04": dict(nivel=1, rf="RF-02", norma=N_PLAZOS,
                regla="SI importación Y categoría = Insumos Críticos ENTONCES plazo_minimo_requerido = a la vista"),
    "R05": dict(nivel=1, rf="RF-02", norma=N_PLAZOS,
                regla="SI importación Y categoría = Consumo General ENTONCES plazo_minimo_requerido = plazo consumo"),
    "R06": dict(nivel=1, rf="RF-02", norma=N_INT,
                regla="SI la solicitud es de servicios o pasivos financieros ENTONCES plazo_no_aplica = Sí"),
    "R07": dict(nivel=1, rf="RF-03", norma=N_DJ,
                regla=f"SI posee activos externos líquidos > USD {_usd(UMBRAL_ACTIVOS_USD)} no aplicados ENTONCES dj_activos_en_regla = No"),
    "R08": dict(nivel=1, rf="RF-03", norma=N_DJ,
                regla=f"SI NO posee activos externos líquidos > USD {_usd(UMBRAL_ACTIVOS_USD)} no aplicados ENTONCES dj_activos_en_regla = Sí"),
    "R09": dict(nivel=1, rf="RF-07", norma=N_VINC,
                regla="SI servicios/pasivos Y contraparte vinculada ENTONCES requiere_conformidad_previa = Sí"),
    "R10": dict(nivel=1, rf="RF-07", norma=N_VINC,
                regla="SI servicios/pasivos Y contraparte NO vinculada ENTONCES requiere_conformidad_previa = No"),
    "R11": dict(nivel=1, rf="RF-07", norma=N_INT,
                regla="SI importación de bienes ENTONCES requiere_conformidad_previa = No (no aplica)"),
    "R12": dict(nivel=1, rf="RF-06", norma=N_INT,
                regla="SI falta el tipo de solicitud ENTONCES faltante = tipo de solicitud"),
    "R13": dict(nivel=1, rf="RF-06", norma=N_INT,
                regla="SI falta el historial bursátil MEP/CCL ENTONCES faltante = historial bursátil"),
    "R14": dict(nivel=1, rf="RF-06", norma=N_INT,
                regla="SI importación Y falta el plazo desde registro/factura ENTONCES faltante = plazo"),
    "R15": dict(nivel=1, rf="RF-06", norma=N_INT,
                regla="SI importación Y falta la categoría del bien ENTONCES faltante = categoría"),
    "R16": dict(nivel=1, rf="RF-06", norma=N_INT,
                regla="SI falta la declaración jurada de activos externos ENTONCES faltante = DJ de activos externos"),
    "R17": dict(nivel=1, rf="RF-06", norma=N_INT,
                regla="SI servicios/pasivos Y falta la vinculación de la contraparte ENTONCES faltante = vinculación"),
    # ---------------- Nivel 2 ----------------
    "R18": dict(nivel=2, rf="RF-02", norma=N_INT,
                regla="SI plazo_no_aplica ENTONCES plazo_exigible_valido = Sí"),
    "R19": dict(nivel=2, rf="RF-02", norma=N_PLAZOS,
                regla="SI días transcurridos >= plazo_minimo_requerido ENTONCES plazo_exigible_valido = Sí"),
    "R20": dict(nivel=2, rf="RF-02", norma=N_PLAZOS,
                regla="SI días transcurridos < plazo_minimo_requerido ENTONCES plazo_exigible_valido = No y se agrega condicionante de plazo"),
    "R21": dict(nivel=2, rf="RF-01", norma=N_INCOMP,
                regla="SI inhibicion_cruzada_activa ENTONCES causal_bloqueante_vigente = Sí"),
    "R22": dict(nivel=2, rf="RF-02", norma=N_PLAZOS,
                regla="SI importación de insumos críticos Y DJ en regla Y sin inhibición ENTONCES pago_a_la_vista_habilitado = Sí"),
    "R23": dict(nivel=2, rf="RF-03", norma=N_INT,
                regla="SI dj_activos_en_regla Y NO requiere conformidad previa ENTONCES estado_documental = completo"),
    "R24": dict(nivel=2, rf="RF-03", norma=N_DJ,
                regla="SI dj_activos_en_regla = No ENTONCES estado_documental = pendiente y condicionante de fondos propios"),
    "R25": dict(nivel=2, rf="RF-07", norma=N_VINC,
                regla="SI requiere_conformidad_previa ENTONCES estado_documental = pendiente y condicionante de conformidad BCRA"),
    # ---------------- Nivel 3 ----------------
    "R26": dict(nivel=3, rf="RF-04", norma=N_INCOMP,
                regla="SI causal_bloqueante_vigente ENTONCES situacion_regulatoria = impedida"),
    "R27": dict(nivel=3, rf="RF-04", norma=N_PLAZOS,
                regla="SI sin inhibición Y plazo_exigible_valido = No ENTONCES situacion_regulatoria = condicionada"),
    "R28": dict(nivel=3, rf="RF-04", norma=N_INT,
                regla="SI sin inhibición Y estado_documental = pendiente Y plazo no incumplido ENTONCES situacion_regulatoria = condicionada"),
    "R29": dict(nivel=3, rf="RF-04", norma=N_INT,
                regla="SI sin inhibición Y plazo válido Y estado_documental = completo ENTONCES situacion_regulatoria = sin obstáculos"),
    "R30": dict(nivel=3, rf="RF-06", norma=N_INT,
                regla="SI hay parámetros faltantes Y no se derivó otra situación ENTONCES situacion_regulatoria = indeterminada"),
    # ---------------- Nivel 4 ----------------
    "R31": dict(nivel=4, rf="RF-01", norma=N_RES,
                regla="SI situacion_regulatoria = impedida ENTONCES ESTADO_OPERACION = RECHAZADO / BLOQUEADO"),
    "R32": dict(nivel=4, rf="RF-04", norma=N_RES,
                regla="SI situacion_regulatoria = condicionada ENTONCES ESTADO_OPERACION = CONDICIONAL / REQUIERE GESTIÓN ADICIONAL"),
    "R33": dict(nivel=4, rf="RF-04", norma=N_RES,
                regla="SI situacion_regulatoria = sin obstáculos ENTONCES ESTADO_OPERACION = AUTORIZADO"),
    "R34": dict(nivel=4, rf="RF-06", norma=N_RES,
                regla="SI situacion_regulatoria = indeterminada ENTONCES ESTADO_OPERACION = SIN CONCLUSIÓN DETERMINABLE"),
}

# Prioridades (salience): el motor procesa nivel por nivel; la regla de
# "información insuficiente" solo dispara cuando ninguna otra puede hacerlo.
S_N1, S_N2, S_N3, S_N4, S_INDETERMINADA = 40, 30, 20, 10, -10


# --------------------------------------------------------------------------
# HECHOS
# --------------------------------------------------------------------------
class Dato(Fact):
    """Hecho de entrada (nivel 0): nombre, valor."""


class Faltante(Fact):
    """Hecho de entrada (nivel 0): parámetro NO informado por el usuario (RF-06)."""


class Hecho(Fact):
    """Hecho derivado por el motor (niveles 1 a 3): nombre, valor."""


class Dictamen(Fact):
    """Hecho final (nivel 4): estado."""


# --------------------------------------------------------------------------
# MOTOR
# --------------------------------------------------------------------------
class MotorMULC(KnowledgeEngine):

    def __init__(self):
        super().__init__()
        self.traza = []
        self.resultado = None

    # ----- utilidades (no contienen lógica de negocio) -----
    def _disparar(self, rid, detalle=""):
        info = CATALOGO[rid]
        self.traza.append({
            "orden": len(self.traza) + 1, "regla": rid, "nivel": info["nivel"],
            "rf": info["rf"], "descripcion": info["regla"], "detalle": detalle,
            "norma": info["norma"],
        })

    def _valores(self, nombre):
        return [f["valor"] for f in self.facts.values()
                if type(f).__name__ == "Hecho" and f.get("nombre") == nombre]

    def _cerrar(self, estado, mensaje, motivos):
        self.declare(Dictamen(estado=estado))
        self.resultado = {"estado": estado, "etiqueta": ETIQUETAS_DICTAMEN[estado],
                          "mensaje": mensaje, "motivos": motivos}

    # ======================= NIVEL 1 =======================
    @Rule(Dato(nombre="opero_mep", valor=True), salience=S_N1)
    def r01_inhibicion_activa(self):
        self.declare(Hecho(nombre="inhibicion_cruzada_activa", valor=True))
        self._disparar("R01", "Dato ingresado: operó MEP/CCL = Sí")

    @Rule(Dato(nombre="opero_mep", valor=False), salience=S_N1)
    def r02_inhibicion_inactiva(self):
        self.declare(Hecho(nombre="inhibicion_cruzada_activa", valor=False))
        self._disparar("R02", "Dato ingresado: operó MEP/CCL = No")

    @Rule(Dato(nombre="tipo_solicitud", valor="importacion_bienes"),
          Dato(nombre="categoria", valor="bienes_capital"), salience=S_N1)
    def r03_plazo_bienes_capital(self):
        m = PLAZOS_MINIMOS["bienes_capital"]
        self.declare(Hecho(nombre="plazo_minimo_requerido", valor=m))
        self._disparar("R03", f"Plazo mínimo para Bienes de Capital: {m} días")

    @Rule(Dato(nombre="tipo_solicitud", valor="importacion_bienes"),
          Dato(nombre="categoria", valor="insumos_criticos"), salience=S_N1)
    def r04_plazo_insumos_criticos(self):
        m = PLAZOS_MINIMOS["insumos_criticos"]
        self.declare(Hecho(nombre="plazo_minimo_requerido", valor=m))
        self._disparar("R04", f"Plazo mínimo para Insumos Críticos: {m} días (a la vista)")

    @Rule(Dato(nombre="tipo_solicitud", valor="importacion_bienes"),
          Dato(nombre="categoria", valor="consumo_general"), salience=S_N1)
    def r05_plazo_consumo_general(self):
        m = PLAZOS_MINIMOS["consumo_general"]
        self.declare(Hecho(nombre="plazo_minimo_requerido", valor=m))
        self._disparar("R05", f"Plazo mínimo para Bienes de Consumo General: {m} días")

    @Rule(Dato(nombre="tipo_solicitud", valor=P(lambda t: t in TIPOS_SERVICIO_DEUDA)), salience=S_N1)
    def r06_plazo_no_aplica(self):
        self.declare(Hecho(nombre="plazo_no_aplica", valor=True))
        self._disparar("R06", "El plazo de importaciones no aplica a servicios / pasivos financieros")

    @Rule(Dato(nombre="activos_externos", valor=True), salience=S_N1)
    def r07_dj_no_en_regla(self):
        self.declare(Hecho(nombre="dj_activos_en_regla", valor=False))
        self._disparar("R07", "Dato ingresado: posee activos externos líquidos sobre el umbral")

    @Rule(Dato(nombre="activos_externos", valor=False), salience=S_N1)
    def r08_dj_en_regla(self):
        self.declare(Hecho(nombre="dj_activos_en_regla", valor=True))
        self._disparar("R08", "Dato ingresado: no posee activos externos líquidos sobre el umbral")

    @Rule(Dato(nombre="tipo_solicitud", valor=P(lambda t: t in TIPOS_SERVICIO_DEUDA)),
          Dato(nombre="vinculada", valor=True), salience=S_N1)
    def r09_requiere_conformidad(self):
        self.declare(Hecho(nombre="requiere_conformidad_previa", valor=True))
        self._disparar("R09", "Contraparte vinculada en servicios / pasivos financieros")

    @Rule(Dato(nombre="tipo_solicitud", valor=P(lambda t: t in TIPOS_SERVICIO_DEUDA)),
          Dato(nombre="vinculada", valor=False), salience=S_N1)
    def r10_no_requiere_conformidad(self):
        self.declare(Hecho(nombre="requiere_conformidad_previa", valor=False))
        self._disparar("R10", "Contraparte no vinculada")

    @Rule(Dato(nombre="tipo_solicitud", valor="importacion_bienes"), salience=S_N1)
    def r11_conformidad_no_aplica(self):
        self.declare(Hecho(nombre="requiere_conformidad_previa", valor=False))
        self._disparar("R11", "La conformidad por vinculación se evalúa solo en servicios / pasivos")

    # ----- faltantes (RF-06) -----
    @Rule(Faltante(nombre="tipo_solicitud"), salience=S_N1)
    def r12_falta_tipo(self):
        self.declare(Hecho(nombre="faltante", valor="Tipo de solicitud"))
        self._disparar("R12", "No se informó el tipo de solicitud")

    @Rule(Faltante(nombre="opero_mep"), salience=S_N1)
    def r13_falta_historial(self):
        self.declare(Hecho(nombre="faltante", valor="Historial bursátil (MEP/CCL)"))
        self._disparar("R13", "No se informó el historial bursátil")

    @Rule(Dato(nombre="tipo_solicitud", valor="importacion_bienes"),
          Faltante(nombre="dias_plazo"), salience=S_N1)
    def r14_falta_plazo(self):
        self.declare(Hecho(nombre="faltante", valor="Plazo desde registro aduanero / factura"))
        self._disparar("R14", "No se informó el plazo transcurrido")

    @Rule(Dato(nombre="tipo_solicitud", valor="importacion_bienes"),
          Faltante(nombre="categoria"), salience=S_N1)
    def r15_falta_categoria(self):
        self.declare(Hecho(nombre="faltante", valor="Categoría del bien"))
        self._disparar("R15", "No se informó la categoría del bien")

    @Rule(Faltante(nombre="activos_externos"), salience=S_N1)
    def r16_falta_dj(self):
        self.declare(Hecho(nombre="faltante", valor="Declaración jurada de activos externos"))
        self._disparar("R16", "No se informó la declaración jurada de activos externos")

    @Rule(Dato(nombre="tipo_solicitud", valor=P(lambda t: t in TIPOS_SERVICIO_DEUDA)),
          Faltante(nombre="vinculada"), salience=S_N1)
    def r17_falta_vinculacion(self):
        self.declare(Hecho(nombre="faltante", valor="Vinculación de la contraparte"))
        self._disparar("R17", "No se informó si la contraparte es vinculada")

    # ======================= NIVEL 2 =======================
    @Rule(Hecho(nombre="plazo_no_aplica", valor=True), salience=S_N2)
    def r18_plazo_valido_no_aplica(self):
        self.declare(Hecho(nombre="plazo_exigible_valido", valor=True))
        self._disparar("R18", "Sin exigencia de plazo para esta solicitud")

    @Rule(Hecho(nombre="plazo_minimo_requerido", valor=MATCH.minimo),
          Dato(nombre="dias_plazo", valor=MATCH.dias),
          TEST(lambda minimo, dias: dias >= minimo), salience=S_N2)
    def r19_plazo_cumple(self, minimo, dias):
        self.declare(Hecho(nombre="plazo_exigible_valido", valor=True))
        self._disparar("R19", f"{dias} días transcurridos >= {minimo} días exigidos")

    @Rule(Hecho(nombre="plazo_minimo_requerido", valor=MATCH.minimo),
          Dato(nombre="dias_plazo", valor=MATCH.dias),
          TEST(lambda minimo, dias: dias < minimo), salience=S_N2)
    def r20_plazo_no_cumple(self, minimo, dias):
        faltan = minimo - dias
        self.declare(Hecho(nombre="plazo_exigible_valido", valor=False))
        self.declare(Hecho(nombre="condicionante", valor=(
            f"Plazo de giro insuficiente: transcurrieron {dias} días y el mínimo exigido "
            f"es {minimo}; deben esperarse {faltan} días adicionales.")))
        self._disparar("R20", f"{dias} días transcurridos < {minimo} días exigidos (faltan {faltan})")

    @Rule(Hecho(nombre="inhibicion_cruzada_activa", valor=True), salience=S_N2)
    def r21_causal_bloqueante(self):
        self.declare(Hecho(nombre="causal_bloqueante_vigente", valor=True))
        self._disparar("R21", "La inhibición cruzada constituye causal impeditiva taxativa")

    @Rule(Dato(nombre="tipo_solicitud", valor="importacion_bienes"),
          Dato(nombre="categoria", valor="insumos_criticos"),
          Hecho(nombre="dj_activos_en_regla", valor=True),
          Hecho(nombre="inhibicion_cruzada_activa", valor=False), salience=S_N2)
    def r22_pago_a_la_vista(self):
        self.declare(Hecho(nombre="pago_a_la_vista_habilitado", valor=True))
        self._disparar("R22", "Insumo crítico con DJ en regla: exención de plazo de diferimiento")

    @Rule(Hecho(nombre="dj_activos_en_regla", valor=True),
          Hecho(nombre="requiere_conformidad_previa", valor=False), salience=S_N2)
    def r23_documentacion_completa(self):
        self.declare(Hecho(nombre="estado_documental", valor="completo"))
        self._disparar("R23", "DJ en regla y sin conformidad previa pendiente")

    @Rule(Hecho(nombre="dj_activos_en_regla", valor=False), salience=S_N2)
    def r24_documentacion_pendiente_fondos(self):
        self.declare(Hecho(nombre="estado_documental", valor="pendiente"))
        self.declare(Hecho(nombre="condicionante", valor=(
            f"Debe aplicar sus fondos propios líquidos del exterior (disponibilidad > USD "
            f"{_usd(UMBRAL_ACTIVOS_USD)}) o justificar su destino antes de acceder al MULC.")))
        self._disparar("R24", "Activos externos no declarados/justificados: uso de fondos propios previo")

    @Rule(Hecho(nombre="requiere_conformidad_previa", valor=True), salience=S_N2)
    def r25_documentacion_pendiente_conformidad(self):
        self.declare(Hecho(nombre="estado_documental", valor="pendiente"))
        self.declare(Hecho(nombre="condicionante", valor=(
            "Requiere conformidad previa del BCRA por tratarse de una contraparte vinculada.")))
        self._disparar("R25", "Pago a contraparte vinculada: conformidad previa del BCRA")

    # ======================= NIVEL 3 =======================
    @Rule(Hecho(nombre="causal_bloqueante_vigente", valor=True), salience=S_N3)
    def r26_situacion_impedida(self):
        self.declare(Hecho(nombre="situacion_regulatoria", valor="impedida"))
        self._disparar("R26", "Causal bloqueante vigente")

    @Rule(Hecho(nombre="inhibicion_cruzada_activa", valor=False),
          Hecho(nombre="plazo_exigible_valido", valor=False), salience=S_N3)
    def r27_condicionada_por_plazo(self):
        self.declare(Hecho(nombre="situacion_regulatoria", valor="condicionada"))
        self._disparar("R27", "Sin inhibición, pero el plazo exigible no se cumple")

    @Rule(Hecho(nombre="inhibicion_cruzada_activa", valor=False),
          Hecho(nombre="estado_documental", valor="pendiente"),
          NOT(Hecho(nombre="plazo_exigible_valido", valor=False)), salience=S_N3)
    def r28_condicionada_documental(self):
        self.declare(Hecho(nombre="situacion_regulatoria", valor="condicionada"))
        self._disparar("R28", "Sin inhibición, pero hay documentación / autorización pendiente")

    @Rule(Hecho(nombre="inhibicion_cruzada_activa", valor=False),
          Hecho(nombre="plazo_exigible_valido", valor=True),
          Hecho(nombre="estado_documental", valor="completo"), salience=S_N3)
    def r29_sin_obstaculos(self):
        self.declare(Hecho(nombre="situacion_regulatoria", valor="sin_obstaculos"))
        self._disparar("R29", "Sin inhibición, plazo válido y documentación completa")

    @Rule(Hecho(nombre="faltante", valor=MATCH.parametro),
          NOT(Hecho(nombre="situacion_regulatoria")), salience=S_INDETERMINADA)
    def r30_situacion_indeterminada(self, parametro):
        self.declare(Hecho(nombre="situacion_regulatoria", valor="indeterminada"))
        self._disparar("R30", "Con los datos disponibles no se puede determinar una situación")

    # ======================= NIVEL 4 (resolutivas) =======================
    @Rule(Hecho(nombre="situacion_regulatoria", valor="impedida"), salience=S_N4)
    def r31_dictamen_rechazado(self):
        self._cerrar(
            "RECHAZADO",
            f"Acceso al MULC bloqueado: la razón social o sus directores operaron MEP/CCL "
            f"dentro de los últimos {VENTANA_MEP_DIAS} días corridos (incompatibilidad cruzada). "
            f"La causal es impeditiva y no depende del bien o servicio.",
            ["Incompatibilidad cruzada por operaciones MEP/CCL vigente."])
        self._disparar("R31", "Dictamen final: RECHAZADO / BLOQUEADO")

    @Rule(Hecho(nombre="situacion_regulatoria", valor="condicionada"), salience=S_N4)
    def r32_dictamen_condicional(self):
        motivos = self._valores("condicionante")
        self._cerrar(
            "CONDICIONAL",
            "La operación no está bloqueada, pero requiere gestión adicional antes de cursarse.",
            motivos)
        self._disparar("R32", f"Dictamen final: CONDICIONAL ({len(motivos)} condicionante/s)")

    @Rule(Hecho(nombre="situacion_regulatoria", valor="sin_obstaculos"), salience=S_N4)
    def r33_dictamen_autorizado(self):
        a_la_vista = self._valores("pago_a_la_vista_habilitado")
        motivos = ["Sin inhibición MEP/CCL, plazo exigible cumplido y documentación completa."]
        motivos += ["Pago a la vista habilitado (insumo crítico con DJ en regla)."] * len(a_la_vista)
        self._cerrar(
            "AUTORIZADO",
            "La operación cumple la totalidad de los requisitos evaluados para cursar el pago por la entidad bancaria.",
            motivos)
        self._disparar("R33", "Dictamen final: AUTORIZADO")

    @Rule(Hecho(nombre="situacion_regulatoria", valor="indeterminada"), salience=S_N4)
    def r34_dictamen_sin_conclusion(self):
        faltantes = self._valores("faltante")
        self._cerrar(
            "SIN_CONCLUSION",
            "Información insuficiente para emitir dictamen. Complete los parámetros indicados y vuelva a evaluar.",
            [f"Falta informar: {p}" for p in faltantes])
        self._disparar("R34", f"Dictamen final: SIN CONCLUSIÓN (faltan {len(faltantes)} parámetro/s)")


# --------------------------------------------------------------------------
# API PÚBLICA
# --------------------------------------------------------------------------
def _legible(nombre, valor):
    if isinstance(valor, bool):
        return "Sí" if valor else "No"
    if nombre == "tipo_solicitud":
        return TIPOS[valor]
    if nombre == "categoria":
        return CATEGORIAS[valor]
    return str(valor)


def evaluar(tipo_solicitud=None, opero_mep=None, dias_plazo=None,
            categoria=None, activos_externos=None, vinculada=None):
    """Evalúa una solicitud. Un parámetro en None se considera NO informado (RF-06).

    Devuelve dict con: estado, etiqueta, mensaje, motivos, traza.
    """
    if tipo_solicitud is not None and tipo_solicitud not in TIPOS:
        raise ValueError(f"tipo_solicitud inválido: {tipo_solicitud!r}")
    if categoria is not None and categoria not in CATEGORIAS:
        raise ValueError(f"categoria inválida: {categoria!r}")
    if dias_plazo is not None and dias_plazo < 0:
        raise ValueError("dias_plazo no puede ser negativo")

    motor = MotorMULC()
    motor.reset()
    datos = {"tipo_solicitud": tipo_solicitud, "opero_mep": opero_mep, "dias_plazo": dias_plazo,
             "categoria": categoria, "activos_externos": activos_externos, "vinculada": vinculada}
    for nombre, valor in datos.items():
        if valor is None:
            motor.declare(Faltante(nombre=nombre))
            texto = f"{ETIQUETAS_DATOS[nombre]} = NO INFORMADO"
        else:
            motor.declare(Dato(nombre=nombre, valor=valor))
            texto = f"{ETIQUETAS_DATOS[nombre]} = {_legible(nombre, valor)}"
        motor.traza.append({
            "orden": len(motor.traza) + 1, "regla": "HECHO", "nivel": 0, "rf": "-",
            "descripcion": texto, "detalle": "", "norma": "Dato ingresado por el usuario"})
    motor.run()

    resultado = dict(motor.resultado)
    resultado["traza"] = motor.traza
    return resultado


def cantidad_de_reglas():
    return len(MotorMULC().get_rules())


def formatear_traza(traza):
    lineas = []
    for t in traza:
        sangria = "  " * t["nivel"]
        extra = f"  [{t['detalle']}]" if t["detalle"] else ""
        lineas.append(f"{t['orden']:>2}. N{t['nivel']} {sangria}{t['regla']:<5} {t['descripcion']}{extra}")
    return "\n".join(lineas)


def catalogo_markdown():
    filas = ["| ID | Nivel | RF | Regla (condición → conclusión) |", "|---|---|---|---|"]
    for rid, info in CATALOGO.items():
        filas.append(f"| {rid} | {info['nivel']} | {info['rf']} | {info['regla']} |")
    return "\n".join(filas)


if __name__ == "__main__":
    r = evaluar("importacion_bienes", False, 15, "consumo_general", False)
    print(r["etiqueta"], "-", r["mensaje"])
    print(formatear_traza(r["traza"]))
