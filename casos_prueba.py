"""
Casos de prueba de homologación - Sistema experto MULC.

Ejecución:  python casos_prueba.py
Cada caso verifica: (1) el dictamen esperado, (2) que se disparen las reglas
clave y (3) que la traza exhiba al menos 3 niveles de encadenamiento hacia
adelante antes de la conclusión (RF-04) cuando el caso tiene datos completos.
"""
from motor_mulc import (evaluar, formatear_traza, cantidad_de_reglas,
                        ETIQUETAS_DICTAMEN)

# (id, descripción, argumentos de evaluar(), dictamen esperado, reglas que deben dispararse)
CASOS = [
    (1, "Incompatibilidad temporal: MEP en la ventana, bien de consumo general",
     dict(tipo_solicitud="importacion_bienes", opero_mep=True, dias_plazo=90,
          categoria="consumo_general", activos_externos=False),
     "RECHAZADO", ["R01", "R21", "R26", "R31"]),

    (2, "Incompatibilidad temporal independiente del bien: MEP + insumo crítico con DJ en regla",
     dict(tipo_solicitud="importacion_bienes", opero_mep=True, dias_plazo=0,
          categoria="insumos_criticos", activos_externos=False),
     "RECHAZADO", ["R01", "R21", "R26", "R31"]),

    (3, "Plazos escalonados: consumo general a 15 días de nacionalización",
     dict(tipo_solicitud="importacion_bienes", opero_mep=False, dias_plazo=15,
          categoria="consumo_general", activos_externos=False),
     "CONDICIONAL", ["R05", "R20", "R27", "R32"]),

    (4, "Exención crítica: insumo médico/sanitario con DJ en regla (pago a la vista)",
     dict(tipo_solicitud="importacion_bienes", opero_mep=False, dias_plazo=0,
          categoria="insumos_criticos", activos_externos=False),
     "AUTORIZADO", ["R04", "R19", "R22", "R23", "R29", "R33"]),

    (5, "Bien de capital con plazo cumplido (45 >= 30 días)",
     dict(tipo_solicitud="importacion_bienes", opero_mep=False, dias_plazo=45,
          categoria="bienes_capital", activos_externos=False),
     "AUTORIZADO", ["R03", "R19", "R29", "R33"]),

    (6, "Bien de capital con plazo incumplido (10 < 30 días)",
     dict(tipo_solicitud="importacion_bienes", opero_mep=False, dias_plazo=10,
          categoria="bienes_capital", activos_externos=False),
     "CONDICIONAL", ["R03", "R20", "R27", "R32"]),

    (7, "Plazo cumplido pero con activos externos líquidos sobre el umbral (fondos propios)",
     dict(tipo_solicitud="importacion_bienes", opero_mep=False, dias_plazo=90,
          categoria="consumo_general", activos_externos=True),
     "CONDICIONAL", ["R07", "R19", "R24", "R28", "R32"]),

    (8, "Pago de servicios a contraparte vinculada: conformidad previa del BCRA",
     dict(tipo_solicitud="servicios", opero_mep=False, activos_externos=False, vinculada=True),
     "CONDICIONAL", ["R09", "R25", "R28", "R32"]),

    (9, "Cancelación de pasivos financieros con contraparte no vinculada",
     dict(tipo_solicitud="pasivos_financieros", opero_mep=False, activos_externos=False, vinculada=False),
     "AUTORIZADO", ["R10", "R18", "R23", "R29", "R33"]),

    (10, "Datos incompletos: importación sin categoría del bien",
     dict(tipo_solicitud="importacion_bienes", opero_mep=False, dias_plazo=90, activos_externos=False),
     "SIN_CONCLUSION", ["R15", "R30", "R34"]),
]


def ejecutar(verbose=True):
    resultados = []
    for cid, desc, args, esperado, reglas_clave in CASOS:
        r = evaluar(**args)
        disparadas = [t["regla"] for t in r["traza"] if t["nivel"] > 0]
        niveles = sorted({t["nivel"] for t in r["traza"] if t["nivel"] > 0})
        ok_estado = r["estado"] == esperado
        faltan = [x for x in reglas_clave if x not in disparadas]
        ok_reglas = not faltan
        ok_niveles = len(niveles) >= 3
        ok = ok_estado and ok_reglas and ok_niveles
        resultados.append((cid, desc, esperado, r["estado"], niveles, faltan, ok))
        if verbose:
            marca = "OK  " if ok else "FALLA"
            print(f"[{marca}] Caso {cid:>2}: {desc}")
            print(f"         esperado={esperado}  obtenido={r['estado']}  niveles={niveles}"
                  + (f"  reglas_no_disparadas={faltan}" if faltan else ""))
    total_ok = sum(1 for x in resultados if x[-1])
    if verbose:
        print(f"\nBase de conocimiento: {cantidad_de_reglas()} reglas (mínimo exigido: 20)")
        print(f"Resultado: {total_ok}/{len(resultados)} casos aprobados")
    return total_ok == len(resultados)


if __name__ == "__main__":
    raise SystemExit(0 if ejecutar() else 1)
