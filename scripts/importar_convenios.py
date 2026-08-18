from pathlib import Path
import shutil
import pandas as pd

from config import DADOS_DIR, MODO


PASTA_CONVENIOS = DADOS_DIR / "Convênios"
PASTA_IMPORTADOS = DADOS_DIR / "Importados"
ARQUIVO_SAIDA = DADOS_DIR / "consolidado.xlsx"


def listar_arquivos_csv(pasta: Path) -> list[Path]:

    if not pasta.exists():
        raise FileNotFoundError(
            f"Diretório não encontrado: {pasta}"
        )

    return sorted(
        pasta.glob("*.csv")
    )


def ler_csv(arquivo: Path) -> pd.DataFrame:

    try:

        return pd.read_csv(
            arquivo,
            sep=";",
            encoding="latin1"
        )

    except Exception as erro:

        print(
            f"Erro ao ler {arquivo.name}: {erro}"
        )

        return pd.DataFrame()


def carregar_consolidado_existente() -> pd.DataFrame:

    if MODO == "demo":
        return pd.DataFrame()

    if not ARQUIVO_SAIDA.exists():

        print(
            "Consolidado não encontrado. Será criado um novo."
        )

        return pd.DataFrame()

    try:

        return pd.read_excel(
            ARQUIVO_SAIDA,
            sheet_name="Convenios"
        )

    except Exception as erro:

        print(
            f"Erro ao ler consolidado: {erro}"
        )

        return pd.DataFrame()


def mover_para_importados(arquivo: Path):

    if MODO == "demo":
        return

    PASTA_IMPORTADOS.mkdir(
        parents=True,
        exist_ok=True
    )

    destino = PASTA_IMPORTADOS / arquivo.name

    if destino.exists():

        destino = (
            PASTA_IMPORTADOS /
            f"{arquivo.stem}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )

    shutil.move(
        str(arquivo),
        str(destino)
    )


def atualizar_convenios() -> pd.DataFrame:

    consolidado = carregar_consolidado_existente()

    arquivos = listar_arquivos_csv(
        PASTA_CONVENIOS
    )

    if not arquivos:

        print(
            "Nenhum CSV encontrado para importar."
        )

        return consolidado

    for arquivo in arquivos:

        print("\n" + "=" * 60)
        print(f"Processando: {arquivo.name}")

        df_novo = ler_csv(
            arquivo
        )

        if df_novo.empty:

            print(
                "Arquivo vazio ou inválido."
            )

            continue

        df_novo["arquivo_origem"] = (
            arquivo.stem
        )

        convenio = (
            df_novo["convenio"]
            .iloc[0]
        )

        print(
            f"Convênio identificado: {convenio}"
        )

        existe = False

        if (
            not consolidado.empty
            and "convenio" in consolidado.columns
        ):

            existe = convenio in (
                consolidado["convenio"]
                .astype(str)
                .unique()
            )

        if existe:

            qtd_antiga = len(
                consolidado[
                    consolidado["convenio"]
                    == convenio
                ]
            )

            qtd_nova = len(
                df_novo
            )

            print(
                f"\nConvênio já existe."
            )

            print(
                f"Registros atuais : {qtd_antiga}"
            )

            print(
                f"Registros novos  : {qtd_nova}"
            )

            resposta = input(
                "\nDeseja substituir? (S/N): "
            ).strip().upper()

            if resposta != "S":

                print(
                    "Importação cancelada."
                )

                continue

            consolidado = consolidado[
                consolidado["convenio"]
                != convenio
            ]

            print(
                "Registros antigos removidos."
            )

        else:

            print(
                "Novo convênio encontrado."
            )

        consolidado = pd.concat(
            [
                consolidado,
                df_novo
            ],
            ignore_index=True
        )

        print(
            f"{len(df_novo)} registros adicionados."
        )

        mover_para_importados(
            arquivo
        )

        print(
            "Arquivo movido para Importados."
        )

    return consolidado


def salvar_excel(df: pd.DataFrame):

    ARQUIVO_SAIDA.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with pd.ExcelWriter(
        ARQUIVO_SAIDA,
        engine="openpyxl"
    ) as writer:

        df.to_excel(
            writer,
            sheet_name="Convenios",
            index=False
        )


def main():

    print(
        "\nImportando convênios..."
    )

    df = atualizar_convenios()

    salvar_excel(
        df
    )

    print(
        f"\nConcluído."
    )

    print(
        f"Total de registros: {len(df):,}"
    )


if __name__ == "__main__":
    main()