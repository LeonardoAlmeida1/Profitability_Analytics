from pathlib import Path
import pandas as pd
import numpy as np


BASE_DIR = Path(__file__).resolve().parent.parent

ARQUIVO_AGENDAS = (
    BASE_DIR
    / "dados"
    / "agendas_tratadas.xlsx"
)

ARQUIVO_SAIDA = (
    BASE_DIR
    / "dados"
    / "analise_agendas.xlsx"
)


MESES = {
    1: "Jan",
    2: "Fev",
    3: "Mar",
    4: "Abr",
    5: "Mai",
    6: "Jun",
    7: "Jul",
    8: "Ago",
    9: "Set",
    10: "Out",
    11: "Nov",
    12: "Dez",
}

DIAS_SEMANA = {
    0: "Segunda",
    1: "Terça",
    2: "Quarta",
    3: "Quinta",
    4: "Sexta",
    5: "Sábado",
    6: "Domingo",
}


def carregar_agendas() -> pd.DataFrame:

    return pd.read_excel(
        ARQUIVO_AGENDAS
    )


def criar_colunas_temporais(
    df: pd.DataFrame
) -> pd.DataFrame:

    df = df.copy()

    df["data_hora"] = pd.to_datetime(
        df["data_hora"]
    )

    df["ano"] = df["data_hora"].dt.year

    df["mes"] = df["data_hora"].dt.month

    df["nome_mes"] = (
        df["mes"]
        .map(MESES)
    )

    df["mes_ano"] = (
        df["nome_mes"]
        + "/"
        + df["ano"].astype(str)
    )

    df["trimestre"] = (
        "T"
        + df["data_hora"]
        .dt.quarter
        .astype(str)
    )

    df["dia_semana"] = (
        df["data_hora"]
        .dt.dayofweek
        .map(DIAS_SEMANA)
    )

    df["numero_semana"] = (
        df["data_hora"]
        .dt.isocalendar()
        .week
        .astype(int)
    )

    df["hora_cheia"] = (
        df["data_hora"]
        .dt.hour
    )

    return df

def criar_resumo_executivo(
    df: pd.DataFrame
) -> pd.DataFrame:
    """
    Calcula os principais KPIs da agenda.
    """

    total_agendamentos = len(df)

    pacientes_unicos = (
        df["prontuario"]
        .dropna()
        .nunique()
    )

    convenios = (
        df["convenio"]
        .nunique()
    )

    procedimentos = (
        df["descricao_procedimento"]
        .nunique()
    )

    medicos = (
        df["medico"]
        .nunique()
    )

    dias_atendimento = (
        df["data"]
        .nunique()
    )

    semanas = (
        df["numero_semana"]
        .astype(str)
        + "-"
        + df["ano"].astype(str)
    ).nunique()

    meses = (
        df["mes_ano"]
        .nunique()
    )

    resumo = pd.DataFrame({

        "Indicador": [

            "Total de Agendamentos",

            "Pacientes Únicos",

            "Convênios Atendidos",

            "Procedimentos Distintos",

            "Médicos",

            "Dias com Atendimento",

            "Média por Dia",

            "Média por Semana",

            "Média por Mês",
        ],

        "Valor": [

            total_agendamentos,

            pacientes_unicos,

            convenios,

            procedimentos,

            medicos,

            dias_atendimento,

            round(
                total_agendamentos
                / dias_atendimento,
                2
            ),

            round(
                total_agendamentos
                / semanas,
                2
            ),

            round(
                total_agendamentos
                / meses,
                2
            ),
        ]
    })

    return resumo

def criar_analise_convenios(
    df: pd.DataFrame
) -> pd.DataFrame:
    """
    Cria indicadores por convênio.
    """

    total_agendamentos = len(df)

    df_convenios = (
        df.groupby("convenio")
        .agg(
            atendimentos=(
                "convenio",
                "size"
            ),

            pacientes_unicos=(
                "prontuario",
                "nunique"
            ),

            procedimentos_distintos=(
                "descricao_procedimento",
                "nunique"
            ),

            medicos_distintos=(
                "medico",
                "nunique"
            )
        )
        .reset_index()
    )

    df_convenios["participacao_pct"] = (
        df_convenios["atendimentos"]
        / total_agendamentos
        * 100
    ).round(2)

    df_convenios = (
        df_convenios
        .sort_values(
            "atendimentos",
            ascending=False
        )
        .reset_index(drop=True)
    )

    df_convenios["ranking"] = (
        df_convenios.index + 1
    )

    return df_convenios

# def criar_evolucao_convenios(
#     df: pd.DataFrame
# ) -> pd.DataFrame:
#     """
#     Compara a evolução dos convênios por ano.
#     """

#     tabela = (
#         pd.pivot_table(
#             df,
#             index="convenio",
#             columns="ano",
#             values="prontuario",
#             aggfunc="count",
#             fill_value=0
#         )
#         .reset_index()
#     )

#     anos = sorted(
#         [col for col in tabela.columns if isinstance(col, int)]
#     )

#     if len(anos) >= 2:

#         ano_anterior = anos[-2]
#         ano_atual = anos[-1]

#         tabela["crescimento_pct"] = (
#             (
#                 tabela[ano_atual]
#                 - tabela[ano_anterior]
#             )
#             / tabela[ano_anterior].replace(0, np.nan)
#             * 100
#         ).round(2)

#     else:

#         tabela["crescimento_pct"] = 0

#     return tabela

def criar_analise_procedimentos(
    df: pd.DataFrame
) -> pd.DataFrame:
    """
    Cria indicadores por procedimento.
    """

    total_atendimentos = len(df)

    procedimentos = (
        df.groupby(
            "descricao_procedimento",
            dropna=False
        )
        .agg(
            atendimentos=(
                "descricao_procedimento",
                "size"
            ),

            pacientes_unicos=(
                "prontuario",
                "nunique"
            ),

            convenios=(
                "convenio",
                "nunique"
            ),

            medicos=(
                "medico",
                "nunique"
            )
        )
        .reset_index()
    )

    procedimentos["participacao_pct"] = (
        procedimentos["atendimentos"]
        / total_atendimentos
        * 100
    ).round(2)

    procedimentos = (
        procedimentos
        .sort_values(
            "atendimentos",
            ascending=False
        )
        .reset_index(drop=True)
    )

    procedimentos["ranking"] = (
        procedimentos.index + 1
    )

    return procedimentos

def criar_analise_medicos(
    df: pd.DataFrame
) -> pd.DataFrame:
    """
    Cria indicadores por médico.
    """

    total_atendimentos = len(df)

    medicos = (
        df.groupby(
            "medico",
            dropna=False
        )
        .agg(
            atendimentos=(
                "medico",
                "size"
            ),

            pacientes_unicos=(
                "prontuario",
                "nunique"
            ),

            convenios=(
                "convenio",
                "nunique"
            ),

            procedimentos=(
                "descricao_procedimento",
                "nunique"
            )
        )
        .reset_index()
    )

    medicos["participacao_pct"] = (
        medicos["atendimentos"]
        / total_atendimentos
        * 100
    ).round(2)

    medicos = (
        medicos
        .sort_values(
            "atendimentos",
            ascending=False
        )
        .reset_index(drop=True)
    )

    medicos["ranking"] = (
        medicos.index + 1
    )

    return medicos

def criar_analise_temporal(
    df: pd.DataFrame
) -> dict:
    """
    Cria tabelas temporais para análise
    de comportamento da agenda.
    """

    por_ano = (
        df.groupby("ano")
        .size()
        .reset_index(name="atendimentos")
        .sort_values("ano")
    )

    por_mes = (
        df.groupby(
            ["ano", "mes", "nome_mes", "mes_ano"]
        )
        .size()
        .reset_index(name="atendimentos")
        .sort_values(
            ["ano", "mes"]
        )
    )

    ordem_dias = [
        "Segunda",
        "Terça",
        "Quarta",
        "Quinta",
        "Sexta",
        "Sábado",
        "Domingo"
    ]

    por_dia_semana = (
        df.groupby("dia_semana")
        .size()
        .reset_index(name="atendimentos")
    )

    por_dia_semana["ordem"] = (
        por_dia_semana["dia_semana"]
        .map(
            {dia: i for i, dia in enumerate(ordem_dias)}
        )
    )

    por_dia_semana = (
        por_dia_semana
        .sort_values("ordem")
        .drop(columns="ordem")
    )

    por_hora = (
        df.groupby("hora_cheia")
        .size()
        .reset_index(name="atendimentos")
        .sort_values("hora_cheia")
    )

    return {
        "por_ano": por_ano,
        "por_mes": por_mes,
        "por_dia_semana": por_dia_semana,
        "por_hora": por_hora
    }

def salvar_excel(
    df_base: pd.DataFrame,
    df_resumo: pd.DataFrame,
    df_convenios: pd.DataFrame,
    #df_evolucao: pd.DataFrame
    df_procedimentos:pd.DataFrame,
    df_medicos:pd.DataFrame,
    df_temporal:pd.DataFrame
):

    with pd.ExcelWriter(
        ARQUIVO_SAIDA,
        engine="openpyxl"
    ) as writer:

        df_base.to_excel(
            writer,
            sheet_name="Base",
            index=False
        )

        df_resumo.to_excel(
            writer,
            sheet_name="Resumo_Executivo",
            index=False
        )

        df_convenios.to_excel(
            writer,
            sheet_name="Convenios",
            index=False
        )

        # df_evolucao.to_excel(
        #     writer,
        #     sheet_name="Convenios_Evolucao",
        #     index=False
        # )
        
        df_procedimentos.to_excel(
            writer,
            sheet_name="Procedimentos",
            index=False
        )

        df_medicos.to_excel(
            writer,
            sheet_name="Medicos",
            index=False
        )

        df_temporal["por_ano"].to_excel(
            writer,
            sheet_name="Temporal_Ano",
            index=False
        )

        df_temporal["por_mes"].to_excel(
            writer,
            sheet_name="Temporal_Mes",
            index=False
        )

        df_temporal["por_dia_semana"].to_excel(
            writer,
            sheet_name="Temporal_DiaSemana",
            index=False
        )

        df_temporal["por_hora"].to_excel(
            writer,
            sheet_name="Temporal_Hora",
            index=False
        )        


def main():

    print(
        "Criando base analítica..."
    )

    df = carregar_agendas()

    df = criar_colunas_temporais(df)

    df_resumo = criar_resumo_executivo(df)

    df_convenios = criar_analise_convenios(df)

    #df_evolucao = criar_evolucao_convenios(df)
    df_procedimentos = criar_analise_procedimentos(df)

    df_medicos = criar_analise_medicos(df)

    df_temporal = criar_analise_temporal(df)

    salvar_excel(
        df,
        df_resumo,
        df_convenios,
        #df_evolucao
        df_procedimentos,
        df_medicos,
        df_temporal
    )

    print(
        f"Concluído: {len(df):,} registros."
    )


if __name__ == "__main__":
    main()