from pathlib import Path
import pandas as pd
import unicodedata
import re

from config import DADOS_DIR


ARQUIVO_CONSOLIDADO = DADOS_DIR / "consolidado.xlsx"
ARQUIVO_MAPEAMENTO = DADOS_DIR / "mapeamento_procedimentos.xlsx"
ARQUIVO_NAO_MAPEADOS = DADOS_DIR / "procedimentos_nao_mapeados.xlsx"

# =====================================================
# UTILIDADES
# =====================================================

def normalizar_texto(texto):

    if pd.isna(texto):
        return ""

    texto = str(texto)

    texto = unicodedata.normalize(
        "NFKD",
        texto
    ).encode(
        "ASCII",
        "ignore"
    ).decode(
        "utf-8"
    )

    texto = texto.upper()

    texto = re.sub(
        r"\s+",
        " ",
        texto
    )

    return texto.strip()


def preparar_colunas(df):

    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
    )

    return df


# =====================================================
# IMPORTAÇÃO
# =====================================================

def carregar_dados():

    convenios = pd.read_excel(
        ARQUIVO_CONSOLIDADO,
        sheet_name="Convenios"
    )

    custos = pd.read_excel(
        ARQUIVO_CONSOLIDADO,
        sheet_name="Custos_Procedimentos"
    )

    mapa = pd.read_excel(
        ARQUIVO_MAPEAMENTO
    )

    convenios = preparar_colunas(convenios)
    custos = preparar_colunas(custos)
    mapa = preparar_colunas(mapa)

    return convenios, custos, mapa


# =====================================================
# RECEITAS
# =====================================================

def calcular_receitas(convenios):

    receitas = (
        convenios
        .groupby(
            [
                "convenio",
                "descricao_procedimento"
            ],
            as_index=False
        )["total"]
        .mean()
        .rename(
            columns={
                "total": "receita_media"
            }
        )
    )

    return receitas


# =====================================================
# MAPEAMENTO
# =====================================================

def aplicar_mapeamento(
    receitas,
    mapa
):

    receitas = receitas.copy()

    receitas["descricao_norm"] = (
        receitas["descricao_procedimento"]
        .apply(normalizar_texto)
    )

    return receitas.merge(
        mapa,
        on="descricao_norm",
        how="left"
    )

def validar_mapeamento(mapa: pd.DataFrame) -> pd.DataFrame:
    mapa = mapa.copy()

    mapa["descricao_norm"] = (
        mapa["descricao_procedimento_convenio"]
        .apply(normalizar_texto)
    )

    duplicados = mapa[
        mapa.duplicated(
            subset=["descricao_norm"],
            keep=False
        )
    ].copy()

    if duplicados.empty:
        print("Nenhuma duplicidade encontrada no mapeamento.")
        return mapa

    print(
        f"{len(duplicados)} registros duplicados encontrados no mapeamento."
    )

    conflitos = (
        duplicados
        .groupby("descricao_norm")["procedimento_padrao"]
        .nunique()
    )

    conflitos = conflitos[
        conflitos > 1
    ]

    if not conflitos.empty:
        arquivo_conflitos = (
            DADOS_DIR
            / "conflitos_mapeamento.xlsx"
        )

        duplicados[
            duplicados["descricao_norm"].isin(
                conflitos.index
            )
        ][
            [
                "descricao_procedimento_convenio",
                "procedimento_padrao"
            ]
        ].sort_values(
            "descricao_procedimento_convenio"
        ).to_excel(
            arquivo_conflitos,
            index=False
        )

        raise ValueError(
            f"{len(conflitos)} descrições possuem "
            "mapeamentos conflitantes. "
            "Revise conflitos_mapeamento.xlsx."
        )

    mapa = mapa.drop_duplicates(
        subset=["descricao_norm"],
        keep="first"
    )

    print(
        "Duplicidades simples removidas com segurança."
    )

    return mapa

def remover_procedimentos_excluidos(df):
    return df[
        df["procedimento_padrao"]
        .fillna("")
        .str.upper()
        .ne("EXCLUIR")
    ].copy()

# =====================================================
# NÃO MAPEADOS
# =====================================================

def gerar_relatorio_nao_mapeados(df):

    nao_mapeados = (
        df[
            df["procedimento_padrao"]
            .isna()
        ]
        .copy()
    )

    if not nao_mapeados.empty:

        (
            nao_mapeados[
                [
                    "descricao_procedimento",
                    "convenio"
                ]
            ]
            .drop_duplicates()
            .sort_values(
                "descricao_procedimento"
            )
            .to_excel(
                ARQUIVO_NAO_MAPEADOS,
                index=False
            )
        )

        print(
            f"{len(nao_mapeados)} registros sem mapeamento."
        )

    else:

        print(
            "Nenhum procedimento sem mapeamento."
        )


# =====================================================
# CUSTOS
# =====================================================

def cruzar_custos(
    receitas,
    custos
):

    return receitas.merge(
        custos,
        left_on="procedimento_padrao",
        right_on="procedimento",
        how="left"
    )

def gerar_relatorio_sem_custo(df):
    sem_custo = df[
        df["custo_total_procedimento"].isna()
    ].copy()

    if not sem_custo.empty:
        arquivo = DADOS_DIR / "procedimentos_sem_custo.xlsx"

        sem_custo[
            [
                "procedimento_padrao",
                "descricao_procedimento",
                "convenio"
            ]
        ].drop_duplicates().to_excel(
            arquivo,
            index=False
        )

        print(
            f"{len(sem_custo)} registros sem custo cadastrado."
        )

# =====================================================
# INDICADORES
# =====================================================

def calcular_indicadores(df):

    df["lucro_bruto"] = (
        df["receita_media"]
        - df["custo_total_procedimento"]
    )

    df["margem_percentual"] = (
        (
            df["lucro_bruto"]
            / df["receita_media"]
        )
        * 100
    ).round(2)

    return df


# =====================================================
# CLASSIFICAÇÃO
# =====================================================

def classificar_margem(margem):

    if margem < 0:
        return "PREJUIZO"

    elif margem < 20:
        return "BAIXA"

    elif margem < 40:
        return "MEDIA"

    return "ALTA"


def aplicar_classificacao(df):

    df["status_financeiro"] = (
        df["margem_percentual"]
        .apply(classificar_margem)
    )

    return df


# =====================================================
# RESUMO
# =====================================================

def criar_resumo_procedimentos(df):

    resumo = (
        df.groupby(
            "procedimento_padrao",
            as_index=False
        )
        .agg(
            receita_media=(
                "receita_media",
                "mean"
            ),
            custo_total=(
                "custo_total_procedimento",
                "mean"
            ),
            lucro_medio=(
                "lucro_bruto",
                "mean"
            ),
            margem_media=(
                "margem_percentual",
                "mean"
            )
        )
    )

    resumo["status_financeiro"] = (
        resumo["margem_media"]
        .apply(classificar_margem)
    )

    resumo = resumo.sort_values(
        "lucro_medio",
        ascending=False
    )

    return resumo


# =====================================================
# SALVAR
# =====================================================

def salvar(
    detalhado,
    resumo
):

    with pd.ExcelWriter(
        ARQUIVO_CONSOLIDADO,
        engine="openpyxl",
        mode="a",
        if_sheet_exists="replace"
    ) as writer:

        detalhado.to_excel(
            writer,
            sheet_name="Rentabilidade_Convenios",
            index=False
        )

        resumo.to_excel(
            writer,
            sheet_name="Rentabilidade_Resumo",
            index=False
        )


# =====================================================
# MAIN
# =====================================================

def main():

    print(
        "\n=== ANÁLISE DE RENTABILIDADE ===\n"
    )

    convenios, custos, mapa = (
        carregar_dados()
    )

    mapa = validar_mapeamento(
        mapa
    )

    receitas = calcular_receitas(
        convenios
    )

    receitas = aplicar_mapeamento(
        receitas,
        mapa
    )

    receitas = remover_procedimentos_excluidos(
        receitas
    )

    gerar_relatorio_nao_mapeados(
        receitas
    )

    receitas = receitas[
        receitas["procedimento_padrao"].notna()
    ].copy()

    analise = cruzar_custos(
        receitas,
        custos
    )

    gerar_relatorio_sem_custo(
        analise
    )

    analise = analise[
        analise["custo_total_procedimento"].notna()
    ].copy()

    analise = calcular_indicadores(
        analise
    )

    analise = aplicar_classificacao(
        analise
    )

    resumo = criar_resumo_procedimentos(
        analise
    )

    salvar(
        analise,
        resumo
    )

    print(
        "\nAnálise concluída com sucesso."
    )


if __name__ == "__main__":
    main()