"""
Interfaz Streamlit - Sistema experto MULC (RF-05)
Ejecución (desde la terminal de VS Code, en la carpeta del proyecto):
    streamlit run app_streamlit.py
"""
import streamlit as st

from motor_mulc import (
    evaluar, cantidad_de_reglas, catalogo_markdown,
    TIPOS, CATEGORIAS, PLAZOS_MINIMOS, VENTANA_MEP_DIAS, UMBRAL_ACTIVOS_USD,
)

SIN_DATO = "No sé / sin dato"
NIVELES = {
    0: "Hechos iniciales", 1: "Hechos intermedios básicos", 2: "Hechos intermedios compuestos",
    3: "Situación regulatoria", 4: "Dictamen (regla resolutiva)",
}

st.set_page_config(page_title="Sistema experto MULC", page_icon="⚖️", layout="wide")

st.title("⚖️ Evaluación previa de acceso al MULC")
st.caption(
    "Asistente decisional analítico basado en reglas (Experta · encadenamiento hacia adelante). "
    "No constituye asesoramiento legal vinculante ni reemplaza el dictamen de la entidad bancaria."
)

# ----------------------------- Barra lateral -----------------------------
with st.sidebar:
    st.header("Parámetros normativos vigentes")
    st.write(f"**Ventana de inhibición MEP/CCL:** {VENTANA_MEP_DIAS} días corridos")
    st.write(f"**Umbral de activos externos:** USD {UMBRAL_ACTIVOS_USD:,}".replace(",", "."))
    st.write("**Plazos mínimos de diferimiento:**")
    for k, v in PLAZOS_MINIMOS.items():
        st.write(f"- {CATEGORIAS[k]}: {'a la vista' if v == 0 else f'{v} días'}")
    st.caption("Se modifican en la sección de parámetros de `motor_mulc.py`.")
    st.divider()
    st.write(f"**Base de conocimiento:** {cantidad_de_reglas()} reglas")
    with st.expander("Ver catálogo de reglas"):
        st.markdown(catalogo_markdown())


def ternario(etiqueta, clave, ayuda=None):
    opcion = st.radio(etiqueta, ["Sí", "No", SIN_DATO], index=1, horizontal=True, key=clave, help=ayuda)
    return {"Sí": True, "No": False}.get(opcion)


# ------------------------------- Formulario -------------------------------
st.subheader("1. Datos de la operación")
col1, col2 = st.columns(2)

with col1:
    tipo = st.selectbox(
        "Tipo de solicitud", [None, *TIPOS], index=1,
        format_func=lambda k: SIN_DATO if k is None else TIPOS[k])
    opero_mep = ternario(
        f"¿La razón social o sus directores vendieron valores contra moneda extranjera "
        f"(MEP/CCL) en los últimos {VENTANA_MEP_DIAS} días?", "mep")
    activos = ternario(
        f"¿Posee disponibilidad líquida en el exterior > USD {UMBRAL_ACTIVOS_USD:,} "
        f"no aplicada a operaciones permitidas?".replace(",", "."), "activos")

with col2:
    es_importacion = tipo in (None, "importacion_bienes")
    es_servicio_deuda = tipo in (None, "servicios", "pasivos_financieros")

    dias, categoria, vinculada = None, None, None
    if es_importacion:
        sin_dias = st.checkbox("No dispongo del plazo transcurrido", key="sin_dias")
        dias = None if sin_dias else int(st.number_input(
            "Días corridos desde registro aduanero / factura", min_value=0, value=15, step=1))
        categoria = st.selectbox(
            "Categoría del bien", [None, *CATEGORIAS], index=3,
            format_func=lambda k: SIN_DATO if k is None else CATEGORIAS[k])
    if es_servicio_deuda:
        vinculada = ternario("¿La contraparte es empresa del mismo grupo económico / vinculada?", "vinc")
    if not es_importacion and not es_servicio_deuda:
        st.info("No se requieren datos adicionales para este tipo de solicitud.")

evaluar_ahora = st.button("Evaluar conformidad", type="primary")

# ------------------------------- Resultado -------------------------------
if evaluar_ahora:
    r = evaluar(
        tipo_solicitud=tipo, opero_mep=opero_mep, dias_plazo=dias,
        categoria=categoria, activos_externos=activos, vinculada=vinculada)

    st.subheader("2. Dictamen")
    titulo = f"### {r['etiqueta']}"
    detalle = r["mensaje"] + "\n\n" + "\n".join(f"- {m}" for m in r["motivos"])
    {"AUTORIZADO": st.success, "CONDICIONAL": st.warning,
     "RECHAZADO": st.error, "SIN_CONCLUSION": st.info}[r["estado"]](f"{titulo}\n\n{detalle}")

    st.subheader("3. Traza de inferencia (reglas activadas, en orden)")
    niveles_usados = sorted({t["nivel"] for t in r["traza"] if t["nivel"] > 0})
    st.caption(f"Niveles de encadenamiento hacia adelante recorridos: {len(niveles_usados)} "
               f"({', '.join(f'N{n}' for n in niveles_usados)})")

    nivel_actual = None
    for t in r["traza"]:
        if t["nivel"] != nivel_actual:
            nivel_actual = t["nivel"]
            st.markdown(f"**Nivel {nivel_actual} · {NIVELES[nivel_actual]}**")
        etiqueta = "Hecho" if t["regla"] == "HECHO" else f"`{t['regla']}`"
        extra = f" — _{t['detalle']}_" if t["detalle"] else ""
        st.markdown(f"{t['orden']}. {etiqueta} · {t['descripcion']}{extra}")

    with st.expander("Fundamento normativo de cada regla disparada"):
        for t in r["traza"]:
            if t["regla"] != "HECHO":
                st.markdown(f"- `{t['regla']}` ({t['rf']}): {t['norma']}")
