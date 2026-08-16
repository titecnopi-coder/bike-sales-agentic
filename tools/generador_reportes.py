"""
Tool: Generador de Reportes de Negocio
==========================================
Combina las cifras de ventas (de la tool anterior) con cálculos de
margen, y arma un resumen de negocio en texto -- listo para copiar
en un correo o presentación. Es la 3ra tool exigida por el enunciado
(mínimo 3, ésta es de "generador de reportes").
"""

from tools.consulta_ventas import consultar_ventas
from tools.calculadora_metricas import calcular_metrica

TOOL_SCHEMA = {
    "name": "generar_reporte_ventas",
    "description": (
        "Genera un reporte de negocio resumido para una categoría de "
        "producto (o todas), combinando unidades vendidas, ingresos, y "
        "margen estimado. Úsala cuando el usuario pida un 'resumen', "
        "'reporte', o 'informe' de ventas -- no para una sola cifra suelta."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "categoria": {
                "type": "string",
                "enum": ["Montaña", "Urbana", "Ruta", "todas"],
                "description": "Categoría a incluir en el reporte, o 'todas'.",
            },
            "costos_estimados_pct": {
                "type": "number",
                "description": (
                    "Porcentaje estimado de costos sobre los ingresos, "
                    "para calcular el margen (ej. 65 significa que los "
                    "costos son el 65% de los ingresos). Si no se "
                    "especifica, usa 65 por defecto."
                ),
            },
        },
        "required": ["categoria"],
    },
}


def generar_reporte_ventas(categoria: str, costos_estimados_pct: float = 65) -> dict:
    """
    Combina 2 tools existentes en un solo reporte -- muestra composición
    de tools (una tool usando a otra), un patrón común en sistemas
    agénticos reales.
    """
    try:
        datos_ventas = consultar_ventas(categoria)

        if "error" in datos_ventas or datos_ventas.get("unidades_totales", 0) == 0:
            return {
                "categoria": categoria,
                "reporte": f"No hay datos suficientes para generar un reporte de {categoria}.",
            }

        ingresos = datos_ventas["ingresos_totales"]
        costos_estimados = round(ingresos * (costos_estimados_pct / 100))

        margen = calcular_metrica("margen_bruto", {"ingresos": ingresos, "costos": costos_estimados})

        reporte = (
            f"REPORTE DE VENTAS -- {categoria.upper()}\n"
            f"Unidades vendidas: {datos_ventas['unidades_totales']}\n"
            f"Ingresos totales: ${ingresos:,}\n"
            f"Costos estimados ({costos_estimados_pct}%): ${costos_estimados:,}\n"
            f"Margen bruto estimado: {margen['resultado']}%\n"
            f"Registros analizados: {datos_ventas.get('registros_encontrados', 0)}"
        )

        return {
            "categoria": categoria,
            "reporte": reporte,
            "unidades_totales": datos_ventas["unidades_totales"],
            "ingresos_totales": ingresos,
            "margen_bruto_pct": margen["resultado"],
        }

    except Exception as e:
        return {"categoria": categoria, "error": f"No se pudo generar el reporte: {e}"}


if __name__ == "__main__":
    resultado = generar_reporte_ventas("Montaña")
    print(resultado["reporte"])
