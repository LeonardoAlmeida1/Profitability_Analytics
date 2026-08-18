import pandas as pd
import pytest

from scripts.analise import (
    normalizar_texto, 
    classificar_margem, 
    remover_procedimentos_excluidos, 
    calcular_indicadores,
    validar_mapeamento,
    )

def test_normalizar_texto():
    resultado = normalizar_texto(
        "  Tomografia   Abdômen Total  "
    )

    assert resultado == "TOMOGRAFIA ABDOMEN TOTAL"

@pytest.mark.parametrize(
    "margem, esperado",
    [
        (-0.01, "PREJUIZO"),
        (0, "BAIXA"),
        (19.99, "BAIXA"),
        (20, "MEDIA"),
        (39.99, "MEDIA"),
        (40, "ALTA"),
    ],
)
def test_classificar_margem(margem, esperado):
    assert classificar_margem(margem) == esperado

def test_remover_procedimentos_excluidos():
    df = pd.DataFrame(
        {
            "procedimento_padrao": [
                "Tomografia",
                "EXCLUIR",
                "Mamografia",
                None,
            ]
        }
    )

    resultado = remover_procedimentos_excluidos(df)

    assert len(resultado) == 3
    assert "EXCLUIR" not in resultado["procedimento_padrao"].fillna("").tolist()

def test_calcular_indicadores():
    df = pd.DataFrame(
        {
            "receita_media": [200.0],
            "custo_total_procedimento": [120.0],
        }
    )

    resultado = calcular_indicadores(df)

    assert resultado.iloc[0]["lucro_bruto"] == 80.0
    assert resultado.iloc[0]["margem_percentual"] == 40.0

def test_validar_mapeamento_remove_duplicidade_simples():
    mapa = pd.DataFrame(
        {
            "descricao_procedimento_convenio": [
                "Colonoscopia Virtual",
                "colonoscopia virtual",
            ],
            "procedimento_padrao": [
                "Tomografia",
                "Tomografia",
            ],
        }
    )

    resultado = validar_mapeamento(mapa)

    assert len(resultado) == 1
    assert resultado.iloc[0]["procedimento_padrao"] == "Tomografia"

def test_validar_mapeamento_bloqueia_conflito():
    mapa = pd.DataFrame(
        {
            "descricao_procedimento_convenio": [
                "Colonoscopia Virtual",
                "colonoscopia virtual",
            ],
            "procedimento_padrao": [
                "Tomografia",
                "Tomografia Contraste",
            ],
        }
    )

    with pytest.raises(ValueError):
        validar_mapeamento(mapa)