"""Tests unitarios para las herramientas determinísticas del sistema."""

import pytest

from tools.calculadora_metricas import MetricaInvalidaError, calcular_metrica


def test_margen_bruto() -> None:
    resultado = calcular_metrica(
        "margen_bruto", {"ingresos": 1_000_000, "costos": 650_000}
    )

    assert resultado["resultado"] == 35.0
    assert resultado["unidad"] == "%"


def test_crecimiento_porcentual() -> None:
    resultado = calcular_metrica(
        "crecimiento_porcentual", {"valor_actual": 120, "valor_anterior": 100}
    )

    assert resultado["resultado"] == 20.0
    assert resultado["unidad"] == "%"


def test_ticket_promedio() -> None:
    resultado = calcular_metrica(
        "ticket_promedio", {"ingresos_totales": 500_000, "numero_transacciones": 10}
    )

    assert resultado["resultado"] == 50_000.0
    assert resultado["unidad"] == "moneda"


def test_ingresos_negativos_rechazados() -> None:
    with pytest.raises(MetricaInvalidaError):
        calcular_metrica(
            "margen_bruto", {"ingresos": -100_000, "costos": 65_000}
        )