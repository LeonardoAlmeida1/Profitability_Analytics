"""
04_importar_agendas.py

Modulo de importacao e tratamento das agendas medicas.

Objetivo:
    Consolidar todos os arquivos CSV de agenda (dados/agendas/*.csv),
    aplicar as regras de limpeza definidas para o projeto e gerar:
        - dados/agendas_tratadas.xlsx
        - dados/convenios_faltantes.xlsx
        - dados/log_importacao_agendas.xlsx

Regras de negocio implementadas:
    Regra 1: manter apenas codigo_localprodoctor == 1
    Regra 2/3: remover colunas desnecessarias, manter apenas as colunas de interesse
    Regra 4: convenio vazio -> "SEM CONVENIO INFORMADO" (nao excluir)
    Regra 5: Horário válido: 06:45 até 18:30
    Regra 6: convenio REPRESENTANTES é descartado
    Regra 7: paciente iniciando com "9" é observação interna
    Regra 8: SEM CONVENIO INFORMADO + prontuário vazio + código_procedimento vazio = descartar
    Regra 9/10: validar convenio da agenda contra consolidado.xlsx e listar faltantes
    Regra 11: gerar agendas_tratadas.xlsx

Melhorias adicionais (validadas com o usuario):
    - Coluna data_hora (datetime) combinando data + hora, para uso direto
      nas analises da Etapa 2 (dia da semana, evolucao mensal/anual, horarios).
    - Log de qualidade de importacao (log_importacao_agendas.xlsx), com
      estatisticas por arquivo de origem.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

# --------------------------------------------------------------------------
# Configuracao de logging
# --------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Caminhos do projeto
# --------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
DADOS_DIR = BASE_DIR / "dados"
AGENDAS_DIR = DADOS_DIR / "agendas"

CONSOLIDADO_PATH = DADOS_DIR / "consolidado.xlsx"

OUTPUT_AGENDAS_TRATADAS = DADOS_DIR / "agendas_tratadas.xlsx"
OUTPUT_CONVENIOS_FALTANTES = DADOS_DIR / "convenios_faltantes.xlsx"
OUTPUT_LOG_IMPORTACAO = DADOS_DIR / "log_importacao_agendas.xlsx"

# --------------------------------------------------------------------------
# Constantes de negocio
# --------------------------------------------------------------------------

COLUNAS_ESPERADAS_ENTRADA: list[str] = [
    "codigo_localprodoctor",
    "localprodoctor",
    "medico",
    "convenio",
    "data",
    "hora",
    "prontuario",
    "paciente",
    "idade",
    "identidade",
    "telefones",
    "codigo_procedimento",
    "descricao_procedimento",
    "complemento",
]

COLUNAS_FINAIS: list[str] = [
    "medico",
    "convenio",
    "data",
    "hora",
    "data_hora",
    "prontuario",
    "paciente",
    "codigo_procedimento",
    "descricao_procedimento",
]

CODIGO_LOCALPRODOCTOR_VALIDO = 1
CONVENIO_VAZIO_LABEL = "SEM CONVENIO INFORMADO"

FORMATO_DATA = "%d/%m/%Y"
FORMATO_HORA = "%H:%M"

PADROES_OBSERVACAO = [
    "9",
    "888",
    "***999",
    "**99**",
    "*****",
    "*99**",
]

# --------------------------------------------------------------------------
# Leitura dos arquivos
# --------------------------------------------------------------------------

def listar_arquivos_agenda(agendas_dir: Path) -> list[Path]:
    """Lista todos os arquivos CSV presentes na pasta de agendas.

    Args:
        agendas_dir: caminho da pasta dados/agendas.

    Returns:
        Lista de caminhos (Path) para cada arquivo .csv encontrado,
        ordenada por nome.

    Raises:
        FileNotFoundError: se a pasta nao existir.
        ValueError: se nenhum arquivo CSV for encontrado.
    """
    if not agendas_dir.exists():
        raise FileNotFoundError(f"Pasta de agendas nao encontrada: {agendas_dir}")

    arquivos = sorted(agendas_dir.glob("*.csv"))

    if not arquivos:
        raise ValueError(f"Nenhum arquivo .csv encontrado em: {agendas_dir}")

    return arquivos


def ler_csv_agenda(caminho: Path) -> pd.DataFrame:
    """Le um arquivo CSV de agenda com deteccao automatica de separador e encoding.

    Tenta primeiro utf-8-sig e, em caso de falha, latin-1. O separador
    (virgula ou ponto e virgula) e detectado automaticamente pelo pandas.

    Args:
        caminho: caminho do arquivo CSV a ser lido.

    Returns:
        DataFrame com o conteudo bruto do arquivo, todas as colunas como
        string, para evitar conversoes automaticas indesejadas.

    Raises:
        ValueError: se o arquivo nao puder ser lido em nenhum dos encodings
            testados, ou se as colunas obrigatorias nao forem encontradas.
    """
    ultimo_erro: Exception | None = None

    for encoding in ("utf-8-sig", "latin-1"):
        try:
            df = pd.read_csv(
                caminho,
                sep=";",
                dtype=str,
                encoding=encoding,
                low_memory=False
            )
            df.columns = [coluna.strip() for coluna in df.columns]
            validar_colunas_entrada(df, caminho.name)
            return df
        except Exception as erro:  # tentaremos o proximo encoding
            ultimo_erro = erro
            continue

    raise ValueError(
        f"Nao foi possivel ler o arquivo {caminho.name}. Ultimo erro: {ultimo_erro}"
    )


def validar_colunas_entrada(df: pd.DataFrame, nome_arquivo: str) -> None:
    """Valida se um DataFrame de agenda contem todas as colunas esperadas.

    Args:
        df: DataFrame lido a partir do CSV.
        nome_arquivo: nome do arquivo, usado apenas para mensagens de erro.

    Raises:
        ValueError: se alguma coluna obrigatoria estiver ausente.
    """
    colunas_faltantes = set(COLUNAS_ESPERADAS_ENTRADA) - set(df.columns)

    if colunas_faltantes:
        raise ValueError(
            f"Arquivo {nome_arquivo} esta com colunas faltantes: "
            f"{sorted(colunas_faltantes)}"
        )


# --------------------------------------------------------------------------
# Consolidacao
# --------------------------------------------------------------------------

def consolidar_agendas(agendas_dir: Path) -> tuple[pd.DataFrame, list[dict]]:
    """Le e concatena todos os CSVs de agenda, registrando estatisticas por arquivo.

    Args:
        agendas_dir: caminho da pasta dados/agendas.

    Returns:
        Tupla contendo:
            - DataFrame consolidado com uma coluna adicional "arquivo_origem".
            - Lista de dicionarios com estatisticas de leitura por arquivo,
              usada posteriormente para montar o log de qualidade.
    """
    arquivos = listar_arquivos_agenda(agendas_dir)
    dataframes: list[pd.DataFrame] = []
    log_entries: list[dict] = []

    for arquivo in arquivos:
        logger.info("Lendo arquivo: %s", arquivo.name)

        try:
            df = ler_csv_agenda(arquivo)
        except ValueError as erro:
            logger.error("Falha ao ler %s: %s", arquivo.name, erro)
            log_entries.append(
                {
                    "arquivo": arquivo.name,
                    "linhas_lidas": 0,
                    "status": f"ERRO: {erro}",
                }
            )
            continue

        df["arquivo_origem"] = arquivo.name
        dataframes.append(df)

        log_entries.append(
            {
                "arquivo": arquivo.name,
                "linhas_lidas": len(df),
                "status": "OK",
            }
        )

    if not dataframes:
        raise ValueError("Nenhum arquivo de agenda pode ser lido com sucesso.")

    df_consolidado = pd.concat(dataframes, ignore_index=True)
    logger.info("Total consolidado (antes dos filtros): %d linhas", len(df_consolidado))

    return df_consolidado, log_entries


# --------------------------------------------------------------------------
# Regras de limpeza
# --------------------------------------------------------------------------

def aplicar_filtro_localprodoctor(
    df: pd.DataFrame, log_entries: list[dict]
) -> pd.DataFrame:
    """Aplica a Regra 1: mantem apenas codigo_localprodoctor == 1.

    Args:
        df: DataFrame consolidado, antes do filtro.
        log_entries: lista de log (mutada in-place com a contagem de
            descartes por arquivo).

    Returns:
        DataFrame filtrado.
    """
    codigo_numerico = pd.to_numeric(df["codigo_localprodoctor"], errors="coerce")
    mascara_valida = codigo_numerico == CODIGO_LOCALPRODOCTOR_VALIDO

    total_antes = len(df)
    df_filtrado = df.loc[mascara_valida].copy()
    total_depois = len(df_filtrado)

    logger.info(
        "Filtro codigo_localprodoctor == 1: %d de %d linhas mantidas (%d descartadas)",
        total_depois,
        total_antes,
        total_antes - total_depois,
    )

    descartes_por_arquivo = (
        df.loc[~mascara_valida]
        .groupby("arquivo_origem")
        .size()
        .to_dict()
    )
    for entry in log_entries:
        if entry.get("status") == "OK":
            entry["linhas_descartadas_filtro_local"] = descartes_por_arquivo.get(
                entry["arquivo"], 0
            )

    return df_filtrado


def selecionar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica as Regras 2 e 3: remove colunas desnecessarias e mantem as de interesse.

    A coluna data_hora ainda nao existe neste ponto do pipeline; ela e
    adicionada por construir_data_hora antes desta funcao ser chamada.

    Args:
        df: DataFrame apos o filtro de localprodoctor, ja contendo data_hora.

    Returns:
        DataFrame apenas com as colunas finais definidas em COLUNAS_FINAIS.
    """
    return df[COLUNAS_FINAIS].copy()


def tratar_convenio_vazio(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica a Regra 4: substitui convenios vazios pelo rotulo de auditoria.

    Trata tanto valores nulos (NaN) quanto strings vazias ou compostas
    apenas por espacos.

    Args:
        df: DataFrame de agendas.

    Returns:
        DataFrame com a coluna "convenio" tratada.
    """
    df = df.copy()
    df["convenio"] = df["convenio"].fillna("").str.strip()
    df.loc[df["convenio"] == "", "convenio"] = CONVENIO_VAZIO_LABEL
    return df

def remover_horarios_invalidos(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove registros fora do horário operacional da clínica.

    Horário considerado válido:
    - Início: 06:45
    - Fim: 18:30

    Args:
        df: DataFrame das agendas.

    Returns:
        DataFrame contendo apenas horários válidos.
    """

    df = df.copy()

    hora_convertida = pd.to_datetime(
        df["hora"],
        format="%H:%M",
        errors="coerce"
    ).dt.time

    hora_inicio = pd.Timestamp("06:45").time()
    hora_fim = pd.Timestamp("18:30").time()

    mascara_valida = (
        (hora_convertida >= hora_inicio)
        & (hora_convertida <= hora_fim)
    )

    qtd_excluidos = (~mascara_valida).sum()

    if qtd_excluidos:
        logger.info(
            "%d registros removidos por estarem fora do horário operacional.",
            qtd_excluidos
        )

    return df.loc[mascara_valida].copy()


def construir_data_hora(df: pd.DataFrame) -> pd.DataFrame:
    """Cria a coluna data_hora combinando as colunas data e hora.

    Formato esperado: data "dd/mm/aaaa", hora "HH:MM". Registros que nao
    puderem ser convertidos recebem data_hora = NaT (nao descartados),
    para nao perder dados por causa de um erro de digitacao no sistema
    de origem.

    Args:
        df: DataFrame de agendas contendo as colunas "data" e "hora".

    Returns:
        DataFrame com a coluna adicional "data_hora" (datetime64).
    """
    df = df.copy()
    data_hora_texto = df["data"].str.strip() + " " + df["hora"].str.strip()
    df["data_hora"] = pd.to_datetime(
        data_hora_texto,
        #format=f"{FORMATO_DATA} {FORMATO_HORA}",
        errors="coerce",
    )

    qtd_invalidas = df["data_hora"].isna().sum()
    if qtd_invalidas:
        logger.warning(
            "%d registros com data/hora invalida (data_hora = NaT).", qtd_invalidas
        )

    return df

def limpar_textos_dataframe(df: pd.DataFrame) -> pd.DataFrame:

    df = df.copy()
    colunas_texto = df.select_dtypes(
        include=["object", "string"]
    ).columns

    for coluna in colunas_texto:

        df[coluna] = (
            df[coluna]
            .astype(str)
            .str.replace(
                r'[\x00-\x08\x0B-\x0C\x0E-\x1F]',
                '',
                regex=True
            )
        )

    return df

def remover_registros_sem_atendimento(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove registros que não representam atendimentos válidos.

    Regra:
    - convenio = "SEM CONVENIO INFORMADO"
    - prontuario vazio
    - codigo_procedimento vazio

    Quando as três condições ocorrem simultaneamente, o registro é removido.

    Args:
        df: DataFrame das agendas.

    Returns:
        DataFrame sem os registros descartados.
    """

    df = df.copy()

    mascara_excluir = (
        df["convenio"].fillna("").eq("SEM CONVENIO INFORMADO")
        & df["prontuario"].fillna("").astype(str).str.strip().eq("")
        & df["codigo_procedimento"].fillna("").astype(str).str.strip().eq("")
    )

    qtd_excluidos = mascara_excluir.sum()

    if qtd_excluidos:
        logger.info(
            "%d registros removidos por não representarem atendimentos válidos.",
            qtd_excluidos
        )

    return df.loc[~mascara_excluir].copy()

def remover_representantes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove visitas de representantes comerciais.
    """

    df = df.copy()

    mascara = (
        df["convenio"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
        .eq("REPRESENTANTES")
    )

    qtd = mascara.sum()

    if qtd:
        logger.info(
            "%d registros removidos (Representantes).",
            qtd
        )

    return df.loc[~mascara].copy()

def remover_observacoes_agenda(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove registros que representam observações internas
    e não atendimentos reais.
    """

    df = df.copy()

    paciente = (
        df["paciente"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    mascara = False

    for padrao in PADROES_OBSERVACAO:
        mascara = mascara | paciente.str.startswith(
            padrao.upper()
        )

    qtd = mascara.sum()

    if qtd:
        logger.info(
            "%d observações internas removidas.",
            qtd
        )

    return df.loc[~mascara].copy()

# --------------------------------------------------------------------------
# Validacao de convenios
# --------------------------------------------------------------------------

def carregar_convenios_consolidado(path: Path) -> set[str]:
    """Carrega o conjunto de convenios cadastrados em consolidado.xlsx.

    Args:
        path: caminho do arquivo consolidado.xlsx.

    Returns:
        Conjunto de nomes de convenio (strings, sem espacos nas bordas),
        sem valores nulos.

    Raises:
        FileNotFoundError: se o arquivo nao existir.
        ValueError: se a coluna "convenio" nao existir no arquivo.
    """
    if not path.exists():
        raise FileNotFoundError(f"Arquivo consolidado nao encontrado: {path}")

    df_consolidado = pd.read_excel(path, dtype=str)
    df_consolidado.columns = [coluna.strip() for coluna in df_consolidado.columns]

    if "convenio" not in df_consolidado.columns:
        raise ValueError(
            f"Coluna 'convenio' nao encontrada em {path.name}. "
            f"Colunas disponiveis: {list(df_consolidado.columns)}"
        )

    convenios = (
        df_consolidado["convenio"]
        .dropna()
        .str.strip()
        .loc[lambda serie: serie != ""]
        .unique()
    )

    return set(convenios)


def identificar_convenios_faltantes(
    df: pd.DataFrame, convenios_validos: set[str]
) -> pd.DataFrame:
    """Aplica as Regras 5 e 6: identifica convenios da agenda ausentes no consolidado.

    Registros com o rotulo "SEM CONVENIO INFORMADO" sao excluidos desta
    comparacao, pois representam ausencia de dado e nao uma divergencia
    de cadastro entre agenda e consolidado.

    Args:
        df: DataFrame de agendas ja tratado (com convenio vazio preenchido).
        convenios_validos: conjunto de convenios existentes em consolidado.xlsx.

    Returns:
        DataFrame com uma unica coluna "convenio", contendo os convenios
        encontrados na agenda mas ausentes no consolidado, sem duplicidade
        e ordenados alfabeticamente.
    """
    convenios_agenda = set(df["convenio"].unique()) - {CONVENIO_VAZIO_LABEL}
    faltantes = sorted(convenios_agenda - convenios_validos)

    logger.info("Convenios encontrados na agenda e ausentes no consolidado: %d", len(faltantes))

    return pd.DataFrame({"convenio": faltantes})


# --------------------------------------------------------------------------
# Log de qualidade
# --------------------------------------------------------------------------

def gerar_log_qualidade(
    log_entries: list[dict], df_tratado: pd.DataFrame
) -> pd.DataFrame:
    """Monta o DataFrame de log de qualidade da importacao.

    Args:
        log_entries: estatisticas coletadas durante a leitura e o filtro
            de localprodoctor, por arquivo de origem.
        df_tratado: DataFrame final, ja tratado, usado para contar
            registros com data_hora invalida por arquivo.

    Returns:
        DataFrame consolidado com o resumo de qualidade por arquivo.
    """
    df_log = pd.DataFrame(log_entries)

    if "linhas_descartadas_filtro_local" not in df_log.columns:
        df_log["linhas_descartadas_filtro_local"] = 0
    df_log["linhas_descartadas_filtro_local"] = df_log[
        "linhas_descartadas_filtro_local"
    ].fillna(0).astype(int)

    df_log["linhas_finais"] = df_log["linhas_lidas"] - df_log[
        "linhas_descartadas_filtro_local"
    ]

    return df_log


# --------------------------------------------------------------------------
# Persistencia dos resultados
# --------------------------------------------------------------------------

def salvar_resultados(
    df_tratado: pd.DataFrame,
    df_convenios_faltantes: pd.DataFrame,
    df_log: pd.DataFrame,
) -> None:
    """Salva os tres arquivos de saida da Etapa 1 em dados/.

    Args:
        df_tratado: DataFrame final de agendas tratadas.
        df_convenios_faltantes: DataFrame de convenios ausentes no consolidado.
        df_log: DataFrame de log de qualidade da importacao.
    """
    DADOS_DIR.mkdir(parents=True, exist_ok=True)

    df_tratado.to_excel(OUTPUT_AGENDAS_TRATADAS, index=False)
    logger.info("Arquivo gerado: %s (%d linhas)", OUTPUT_AGENDAS_TRATADAS, len(df_tratado))

    df_convenios_faltantes.to_excel(OUTPUT_CONVENIOS_FALTANTES, index=False)
    logger.info(
        "Arquivo gerado: %s (%d convenios)",
        OUTPUT_CONVENIOS_FALTANTES,
        len(df_convenios_faltantes),
    )

    df_log.to_excel(OUTPUT_LOG_IMPORTACAO, index=False)
    logger.info("Arquivo gerado: %s", OUTPUT_LOG_IMPORTACAO)


# --------------------------------------------------------------------------
# Orquestracao
# --------------------------------------------------------------------------

def main() -> None:
    """Executa o pipeline completo de importacao e tratamento das agendas."""
    try:
        df_bruto, log_entries = consolidar_agendas(AGENDAS_DIR)

        df_filtrado = aplicar_filtro_localprodoctor(df_bruto, log_entries)
        df_filtrado = tratar_convenio_vazio(df_filtrado)
        df_filtrado = remover_horarios_invalidos(df_filtrado)
        df_filtrado = remover_representantes(df_filtrado)
        df_filtrado = remover_observacoes_agenda(df_filtrado)
        df_filtrado = remover_registros_sem_atendimento(df_filtrado)
        df_filtrado = construir_data_hora(df_filtrado)
        df_tratado = selecionar_colunas(df_filtrado)

        convenios_validos = carregar_convenios_consolidado(CONSOLIDADO_PATH)
        df_convenios_faltantes = identificar_convenios_faltantes(
            df_tratado, convenios_validos
        )

        df_log = gerar_log_qualidade(log_entries, df_tratado)

        df_tratado = limpar_textos_dataframe(df_tratado)
        df_convenios_faltantes = limpar_textos_dataframe(df_convenios_faltantes)
        df_log = limpar_textos_dataframe(df_log)

        salvar_resultados(df_tratado, df_convenios_faltantes, df_log)

        logger.info("Importacao das agendas concluida com sucesso.")

    except (FileNotFoundError, ValueError) as erro:
        logger.error("Falha na importacao das agendas: %s", erro)
        raise


if __name__ == "__main__":
    main()