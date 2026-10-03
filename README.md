# Sistema experto MULC · Evaluación previa de conformidad cambiaria

Sistema experto **basado en reglas** (biblioteca [Experta](https://github.com/nilp0inter/experta), encadenamiento hacia adelante) que asiste a responsables de comercio exterior y tesorería pyme en la evaluación previa de una solicitud de acceso al **Mercado Único y Libre de Cambios (MULC)** del Banco Central de la República Argentina.

A partir de un cuestionario guiado, el sistema determina si la operación es:

| Dictamen | Significado |
|---|---|
| 🟢 **AUTORIZADO** | Cumple los requisitos evaluados para cursar el pago por la entidad bancaria. |
| 🟡 **CONDICIONAL / REQUIERE GESTIÓN ADICIONAL** | Requiere esperar días adicionales, aplicar fondos propios o contar con conformidad previa del BCRA. |
| 🔴 **RECHAZADO / BLOQUEADO** | Existe una causal impeditiva (incompatibilidad cruzada por operaciones MEP/CCL). |
| 🔵 **SIN CONCLUSIÓN DETERMINABLE** | Faltan parámetros para emitir un dictamen; se indica cuáles. |

Cada dictamen se acompaña de la **traza de reglas** activadas, desde los hechos iniciales hasta la conclusión, con su fundamento normativo.

> ⚠️ **Aviso.** Es un asistente decisional analítico y de control previo. **No constituye asesoramiento legal vinculante** ni reemplaza el dictamen de la entidad bancaria. Los plazos mínimos por categoría son **parámetros de trabajo simplificados**: deben contrastarse con el texto ordenado vigente de *Exterior y Cambios* del BCRA antes de cualquier uso real.

## ¿Por qué un sistema experto y no Machine Learning?

- **Determinismo normativo:** el régimen cambiario es legal y procedimental; una operación cumple o no cumple, no hay probabilidades.
- **Explicabilidad y trazabilidad:** compliance necesita saber qué regla impide o condiciona la operación, algo que un modelo de caja negra no ofrece.
- **Volatilidad de parámetros:** ante una reforma (por ejemplo, cambiar la ventana de inhibición de 90 a 180 días) se modifica una premisa aislada, sin reentrenar ni recopilar datos históricos.

## Cómo razona el sistema

La base de conocimiento tiene **34 reglas** con encadenamiento hacia adelante en **4 niveles**:

```
Nivel 0  Hechos iniciales (formulario)
   │
Nivel 1  Hechos intermedios básicos        inhibicion_cruzada_activa · plazo_minimo_requerido
   │                                       dj_activos_en_regla · requiere_conformidad_previa · faltante      (R01–R17)
Nivel 2  Hechos intermedios compuestos     plazo_exigible_valido · causal_bloqueante_vigente
   │                                       estado_documental · pago_a_la_vista_habilitado                    (R18–R25)
Nivel 3  Situación regulatoria             impedida · condicionada · sin_obstaculos · indeterminada          (R26–R30)
   │
Nivel 4  Regla resolutiva ESTADO_OPERACION RECHAZADO · CONDICIONAL · AUTORIZADO · SIN_CONCLUSION             (R31–R34)
```

**Precedencia:** una causal bloqueante (operación MEP/CCL dentro de la ventana) prevalece sobre cualquier otra y no depende del bien. Si no hay bloqueo, cualquier condicionante cierto da dictamen condicional. Solo cuando faltan datos y no hay un veredicto cierto se informa "Información insuficiente para emitir dictamen".

### Entradas

| Entrada | Valores |
|---|---|
| Tipo de solicitud | Pago diferido de importaciones, pago de servicios, cancelación de pasivos financieros |
| Historial bursátil | ¿Vendió valores contra moneda extranjera (MEP/CCL) en los últimos 90 días? |
| Plazo desde registro aduanero / factura | Días corridos |
| Categoría del bien | Bienes de Capital, Insumos Críticos de Salud/Energía, Bienes de Consumo General |
| Declaración jurada de activos externos | ¿Disponibilidad líquida en el exterior > USD 100.000 no aplicada? |
| Vinculación de la contraparte | ¿Es empresa del mismo grupo económico? |

Cualquier dato puede quedar como "No sé / sin dato".

## Estructura del repositorio

```
├── Sistema_Experto_MULC.ipynb   Notebook con el diseño, el motor, las pruebas y la interfaz
├── motor_mulc.py                Base de conocimiento, reglas y función evaluar()
├── casos_prueba.py              10 casos de prueba de homologación
├── app_streamlit.py             Interfaz web (Streamlit)
├── requirements.txt             Dependencias
└── README.md
```

## Instalación

Requiere **Python 3.9 o superior** (probado en 3.12).

```bash
git clone https://github.com/TU_USUARIO/TU_REPOSITORIO.git
cd TU_REPOSITORIO

python -m venv .venv
# Windows:      .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate

pip install -r requirements.txt
```

> **Compatibilidad.** Experta 1.9.x depende de `frozendict 1.2`, que usa `collections.Mapping` (eliminado en Python 3.10+). `motor_mulc.py` restituye esos alias antes de importar Experta, por lo que no hay que hacer ningún ajuste manual.

## Uso

### Interfaz web

```bash
streamlit run app_streamlit.py
```

Se abre en `http://localhost:8501`. Muestra el dictamen destacado en color, el listado ordenado de reglas activadas agrupado por nivel y el fundamento normativo de cada una.

### Desde Python

```python
from motor_mulc import evaluar, formatear_traza

r = evaluar(
    tipo_solicitud="importacion_bienes",
    opero_mep=False,
    dias_plazo=15,
    categoria="consumo_general",
    activos_externos=False,
)

print(r["etiqueta"])            # CONDICIONAL / REQUIERE GESTIÓN ADICIONAL
print(r["motivos"])             # plazo insuficiente: 15 días, mínimo 60
print(formatear_traza(r["traza"]))
```

Un parámetro en `None` se considera no informado.

### Notebook

Abrir `Sistema_Experto_MULC.ipynb` en VS Code (extensiones Python y Jupyter) y ejecutar todas las celdas. Las celdas `%%writefile` regeneran `motor_mulc.py`, `casos_prueba.py` y `app_streamlit.py`.

## Pruebas

```bash
python casos_prueba.py
```

Ejecuta 10 casos que cubren:

- Incompatibilidad temporal (MEP/CCL en la ventana, con y sin insumo crítico).
- Plazos escalonados (consumo general a 15 días, bienes de capital con plazo cumplido e incumplido).
- Exención crítica (insumo sanitario con DJ en regla, pago a la vista).
- Activos externos sobre el umbral (fondos propios).
- Contraparte vinculada (conformidad previa del BCRA).
- Pasivos financieros sin vinculación.
- Datos incompletos.

Cada caso verifica el dictamen esperado, las reglas clave disparadas y que la traza recorra al menos 3 niveles de encadenamiento.

## Parámetros ajustables

Las premisas normativas están aisladas al comienzo de `motor_mulc.py`:

```python
VENTANA_MEP_DIAS = 90            # días corridos de inhibición por operar MEP/CCL
UMBRAL_ACTIVOS_USD = 100_000     # umbral de libre disponibilidad de activos externos
PLAZOS_MINIMOS = {
    "bienes_capital": 30,
    "insumos_criticos": 0,       # 0 = a la vista
    "consumo_general": 60,
}
```

Ante una reforma normativa se cambia una premisa y las reglas la toman sin tocar su lógica.

## Alcance

**Incluye:** evaluación de pago de importaciones, servicios y cancelación de pasivos financieros según los requisitos descritos en el brief, con explicación de reglas y manejo de datos faltantes.

**No incluye:**
- Conexión a APIs externas (BCRA, AFIP) ni consulta de cotizaciones en tiempo real. Todas las premisas se ingresan en el formulario.
- Validación de autenticidad documental: el sistema confía en los datos declarados por el usuario.
- Asesoramiento legal vinculante.

## Supuestos a validar

- Los **plazos mínimos** por categoría (bienes de capital 30 días, consumo general 60 días, insumos críticos a la vista) son parámetros de trabajo. El brief fija la ventana de 90 días y el umbral de USD 100.000.
- Las referencias normativas de la traza apuntan a las fuentes en general (texto ordenado de *Exterior y Cambios* y Com. "A" 7770, 7782, 7840 y concordantes), no a artículos o puntos específicos.
- La vinculación de la contraparte se evalúa solo en servicios y pasivos financieros, no en importaciones de bienes.

## Fuentes de conocimiento

1. Banco Central de la República Argentina: texto ordenado de *Exterior y Cambios* y Comunicaciones "A" 7770, "A" 7782, "A" 7840 y concordantes.
2. Secretaría de Comercio / AFIP: Nomenclatura Común del MERCOSUR y lineamientos de regularización de pagos aduaneros.
3. Guías públicas de comercio exterior de entidades financieras.

## Glosario

- **MULC:** mercado oficial donde se negocian las divisas al tipo de cambio formal.
- **Dólar MEP / CCL:** operaciones bursátiles para obtener divisas mediante compraventa de bonos o acciones con liquidación en moneda extranjera.
- **Incompatibilidad cruzada:** prohibición de comprar dólares oficiales si dentro de la ventana de inhibición se operó MEP o CCL.
- **Bienes de Capital (BK):** maquinaria y equipamiento productivo duradero, con plazos de pago escalonados.
- **Forward chaining:** estrategia en la que el motor parte de los hechos provistos y evalúa las reglas para derivar nuevos hechos hasta la conclusión final.

## Autoría

Trabajo práctico desarrollado en el marco de la cursada de la asignatura: Análisis de datos II: Sistemas expertos y redes de conocimiento. Docente: Dr. Asuaje, Agustín. Estudiantes: Alcaraz, Amalia García, Pedro Facundo Guerra, Lautaro Llampa, Jose Cristian Lionel Sánchez, Nancy Vanesa
