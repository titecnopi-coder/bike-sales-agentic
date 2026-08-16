"""
Tests unitarios — Calculadora de Métricas de Negocio
=========================================================
Prueba la tool 'calcular_metrica_negocio', que es 100% lógica pura
(sin conexión a bases de datos ni servicios externos) -- por eso es
la candidata ideal para correr en CI/CD sin necesitar credenciales
de GCP guardadas como secretos en GitHub.
"""

import pytest
from tools.calculadora_metricas import calcular_metrica, MetricaInvalidaError


def test_margen_bruto_calculo_correcto():
    resultado = calcular_metrica("margen_bruto", {"ingresos": 1_000_000, "costos": 650_000})
    assert resultado["resultado"] == 35.0
    assert resultado["unidad"] == "%"


def test_margen_bruto_ingresos_cero_lanza_error():
    with pytest.raises(MetricaInvalidaError):
        calcular_metrica("margen_bruto", {"ingresos": 0, "costos": 100})


def test_crecimiento_porcentual_positivo():
    resultado = calcular_metrica(
        "crecimiento_porcentual", {"valor_actual": 120, "valor_anterior": 100}
    )
    assert resultado["resultado"] == 20.0


def test_crecimiento_porcentual_negativo():
    resultado = calcular_metrica(
        "crecimiento_porcentual", {"valor_actual": 80, "valor_anterior": 100}
    )
    assert resultado["resultado"] == -20.0


def test_crecimiento_porcentual_valor_anterior_cero_lanza_error():
    with pytest.raises(MetricaInvalidaError):
        calcular_metrica("crecimiento_porcentual", {"valor_actual": 50, "valor_anterior": 0})


def test_ticket_promedio_calculo_correcto():
    resultado = calcular_metrica(
        "ticket_promedio", {"ingresos_totales": 500_000, "numero_transacciones": 10}
    )
    assert resultado["resultado"] == 50_000.0


def test_ticket_promedio_sin_transacciones_lanza_error():
    with pytest.raises(MetricaInvalidaError):
        calcular_metrica("ticket_promedio", {"ingresos_totales": 500_000, "numero_transacciones": 0})


def test_metrica_no_soportada_lanza_error():
    with pytest.raises(MetricaInvalidaError):
        calcular_metrica("metrica_inventada", {"algo": 1})


def test_falta_valor_requerido_lanza_error():
    with pytest.raises(MetricaInvalidaError):
        calcular_metrica("margen_bruto", {"ingresos": 100})  # falta 'costos'
