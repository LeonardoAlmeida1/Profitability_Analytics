from pathlib import Path
import pandas as pd


from config import DADOS_DIR


ARQUIVO_CUSTOS = DADOS_DIR / "custos_procedimentos.xlsx"
ARQUIVO_CONSOLIDADO = DADOS_DIR / "consolidado.xlsx"


def carregar_custos() -> pd.DataFrame:
    df = pd.read_excel(ARQUIVO_CUSTOS)

    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
    )

    return df


def calcular_custos(df: pd.DataFrame) -> pd.DataFrame:

    df["custo_item"] = (
        df["quantidade"]
        * df["valor_unitário"]
    )

    return df


def consolidar_por_procedimento(
    df: pd.DataFrame
) -> pd.DataFrame:

    resumo = (
        df.groupby(
            "procedimento",
            as_index=False
        )["custo_item"]
        .sum()
        .rename(
            columns={
                "custo_item":
                "custo_total_procedimento"
            }
        )
    )

    return resumo


def salvar_no_excel(
    detalhes: pd.DataFrame,
    resumo: pd.DataFrame
):

    with pd.ExcelWriter(
        ARQUIVO_CONSOLIDADO,
        engine="openpyxl",
        mode="a",
        if_sheet_exists="replace"
    ) as writer:

        detalhes.to_excel(
            writer,
            sheet_name="Custos_Detalhados",
            index=False
        )

        resumo.to_excel(
            writer,
            sheet_name="Custos_Procedimentos",
            index=False
        )


def main():

    print("Calculando custos...")

    df = carregar_custos()

    df = calcular_custos(df)

    resumo = consolidar_por_procedimento(df)

    salvar_no_excel(df, resumo)

    print(
        f"{len(resumo)} procedimentos processados."
    )


if __name__ == "__main__":
    main()