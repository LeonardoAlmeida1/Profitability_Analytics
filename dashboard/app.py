import pandas as pd
import plotly.express as px
import streamlit as st
from config import DADOS_DIR


ARQUIVO = DADOS_DIR / "consolidado.xlsx"

# =====================================
# CONFIG
# =====================================

st.set_page_config(
    page_title="Rentabilidade Médica",
    page_icon="📈",
    layout="wide"
)

st.title(
    "📈 Dashboard de Rentabilidade"
)

st.subheader("by Leonardo Almeida. 💰")

# =====================================
# IMPORTAÇÃO
# =====================================

@st.cache_data
def carregar_dados():

    return pd.read_excel(
        ARQUIVO,
        sheet_name="Rentabilidade_Convenios"
    )


df = carregar_dados()

# =====================================
# SIDEBAR
# =====================================

st.sidebar.header("Filtros")

convenios = sorted(
    df["convenio"].dropna().unique()
)

procedimentos = sorted(
    df["procedimento_padrao"].dropna().unique()
)

filtro_convenio = st.sidebar.multiselect(
    "Convênio",
    convenios,
    default=convenios
)

filtro_procedimento = st.sidebar.multiselect(
    "Procedimento",
    procedimentos,
    default=procedimentos
)

df_filtrado = df[
    df["convenio"].isin(filtro_convenio)
]

df_filtrado = df_filtrado[
    df_filtrado["procedimento_padrao"]
    .isin(filtro_procedimento)
]

# =====================================
# KPIs
# =====================================

receita_total = (
    df_filtrado["receita_media"]
    .sum()
)

custo_total = (
    df_filtrado["custo_total_procedimento"]
    .sum()
)

lucro_total = (
    df_filtrado["lucro_bruto"]
    .sum()
)

margem_media = (
    df_filtrado["margem_percentual"]
    .mean()
)

qtd_proc = (
    df_filtrado["descricao_norm"]
    .nunique()
)

qtd_prejuizo = (
    df_filtrado[
        df_filtrado["status_financeiro"]
        == "PREJUIZO"
    ]["descricao_norm"]
    .nunique()
)

qtd_baixa = (
    df_filtrado[
        df_filtrado["status_financeiro"]
        == "BAIXA"
    ]["descricao_norm"]
    .nunique()
)

melhor_proc = (
    df_filtrado
    .groupby("procedimento_padrao")
    ["lucro_bruto"]
    .mean()
    .idxmax()
)

pior_proc = (
    df_filtrado
    .groupby("procedimento_padrao")
    ["lucro_bruto"]
    .mean()
    .idxmin()
)

st.subheader("💰 Financeiro")
col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Receita Potencial",
    f"R$ {receita_total:,.2f}"
)

col2.metric(
    "Custo Total",
    f"R$ {custo_total:,.2f}"
)

col3.metric(
    "Lucro Potencial",
    f"R$ {lucro_total:,.2f}"
)

col4.metric(
    "Margem Média",
    f"{margem_media:.2f}%"
)

col5, col6, col7 = st.columns(3)

col5.metric(
    "Procedimentos",
    qtd_proc
)

col6.metric(
    "Procedimentos Prejuízo",
    qtd_prejuizo
)

col7.metric(
    "Procedimentos Margem Baixa",
    qtd_baixa
)

col8, col9 = st.columns(2)

col8.metric(
    "Melhor Procedimento",
    melhor_proc
)

col9.metric(
    "Pior Procedimento",
    pior_proc
)

st.divider()

# =====================================
# TOP LUCRATIVOS
# =====================================

top_lucro = (
    df_filtrado
    .groupby(
        "procedimento_padrao",
        as_index=False
    )["lucro_bruto"]
    .mean()
    .sort_values(
        "lucro_bruto",
        ascending=False
    )
    .head(10)
)

top_lucro = top_lucro.sort_values(
    "lucro_bruto",
    ascending=True
)

fig_top = px.bar(
    top_lucro,
    x="lucro_bruto",
    y="procedimento_padrao",
    orientation="h",
    title="Top 10 Mais Lucrativos"
)

fig_top.update_traces(
    texttemplate='R$ %{x:,.2f}',
    textposition='outside'
)

st.plotly_chart(
    fig_top,
    width="stretch"
)

# =====================================
# TOP PIORES
# =====================================

top_prejuizo = (
    df_filtrado
    .groupby(
        "procedimento_padrao",
        as_index=False
    )["lucro_bruto"]
    .mean()
    .sort_values(
        "lucro_bruto",
        ascending=True
    )
    .head(10)
)

top_prejuizo = top_prejuizo.sort_values(
    "lucro_bruto",
    ascending=False
)

fig_prejuizo = px.bar(
    top_prejuizo,
    x="lucro_bruto",
    y="procedimento_padrao",
    orientation="h",
    title="Top 10 Menos Lucrativos"
)

fig_prejuizo.update_traces(
    texttemplate='R$ %{x:,.2f}',
    textposition='outside'
)

st.plotly_chart(
    fig_prejuizo,
    use_container_width=True
)

# =====================================
# RECEITA POR CONVÊNIO
# =====================================

receita_conv = (
    df_filtrado
    .groupby(
        "convenio",
        as_index=False
    )["receita_media"]
    .sum()
)

fig_conv = px.bar(
    receita_conv,
    x="convenio",
    y="receita_media",
    title="Receita por Convênio"
)

st.plotly_chart(
    fig_conv,
    use_container_width=True
)

# =====================================
# RANKING DE CONVÊNIOS
# =====================================

ranking_convenios = (
    df_filtrado
    .groupby(
        "convenio",
        as_index=False
    )
    .agg(
        receita=(
            "receita_media",
            "mean"
        ),
        margem=(
            "margem_percentual",
            "mean"
        )
    )
    .sort_values(
        "margem",
        ascending=False
    )
)

fig_rank = px.bar(
    ranking_convenios,
    x="convenio",
    y="margem",
    title="Ranking de Convênios por Margem"
)

fig_rank.update_traces(
    texttemplate="%{y:.2f}%",
    textposition="outside"
)

fig_rank.update_yaxes(
    ticksuffix="%",
    title="Margem (%)"
)

st.plotly_chart(
    fig_rank,
    use_container_width=True
)

# =====================================
# RECEITA X CUSTO
# =====================================

comparativo = (
    df_filtrado
    .groupby(
        "procedimento_padrao",
        as_index=False
    )
    .agg(
        receita=(
            "receita_media",
            "mean"
        ),
        custo=(
            "custo_total_procedimento",
            "mean"
        )
    )
)

fig_comp = px.scatter(
    comparativo,
    x="custo",
    y="receita",
    hover_name="procedimento_padrao",
    title="Receita x Custo"
)

st.plotly_chart(
    fig_comp,
    use_container_width=True
)

# =====================================
# HEATMAP CONVÊNIO x PROCEDIMENTO
# =====================================
heatmap = (
    df_filtrado
    .pivot_table(
        values="margem_percentual",
        index="procedimento_padrao",
        columns="convenio",
        aggfunc="mean"
    )
)

st.subheader(
    "Margem (%) por Convênio e Procedimento"
)

st.dataframe(
    heatmap.style.format("{:.2f}%"),
    use_container_width=True
)

# =====================================
# TABELA EXECUTIVA
# =====================================

st.subheader(
    "Análise Detalhada"
)

tabela_detalhada = df_filtrado[
    [
        "convenio",
        "descricao_procedimento",
        "receita_media",
        "custo_total_procedimento",
        "lucro_bruto",
        "margem_percentual",
        "status_financeiro"
    ]
].copy()

st.dataframe(
    tabela_detalhada.style.format(
        {
            "receita_media": "R$ {:.2f}",
            "custo_total_procedimento": "R$ {:.2f}",
            "lucro_bruto": "R$ {:.2f}",
            "margem_percentual": "{:.2f}%"
        }
    ),
    use_container_width=True
)
