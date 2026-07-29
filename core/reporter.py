import os
import re
import calendar
import unicodedata
from collections import Counter
from datetime import datetime

import pandas as pd

from core.const import EXCEL_PATH, EXCEL_SHEET_NAME, TBN_FILES_FOLDER, REQUERIMENTOS_DIR_REPORT
from core.log_print import log_info, log_erro, log_erro_critico


# Mapeamento de nomes dos dias da semana para exibição em português.
DIAS_SEMANA_PTBR = {
    0: "segunda-feira",
    1: "terça-feira",
    2: "quarta-feira",
    3: "quinta-feira",
    4: "sexta-feira",
    5: "sábado",
    6: "domingo"
}


def _normalizar_texto(texto):
    """Normaliza texto para comparação tolerante a acentos, caixa e espaços."""
    if texto is None:
        return ""
    texto = str(texto).strip().lower()
    texto = ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )
    texto = re.sub(r'\s+', ' ', texto)
    return texto


def _sugerir_mes_referencia():
    """
    Sugere mês/ano de referência:
    - dia > 10: mês corrente
    - dia <= 10: mês anterior
    """
    agora = datetime.now()
    if agora.day > 10:
        return agora.month, agora.year

    if agora.month == 1:
        return 12, agora.year - 1
    return agora.month - 1, agora.year


def _obter_mes_ano_referencia():
    """Obtém mês/ano do usuário com sugestão padrão e validação de formato."""
    mes_sugerido, ano_sugerido = _sugerir_mes_referencia()
    sugestao = f"{mes_sugerido:02d}/{ano_sugerido}"

    while True:
        entrada = input(f"Mês de referência para o relatório (MM/AAAA) [{sugestao}]: ").strip()
        if not entrada:
            return mes_sugerido, ano_sugerido

        match = re.match(r'^(0[1-9]|1[0-2])/(\d{4})$', entrada)
        if match:
            mes = int(match.group(1))
            ano = int(match.group(2))
            return mes, ano

        log_info("Formato inválido. Use MM/AAAA, por exemplo: 12/2025")


def _converter_tempo_para_timedelta(tempo_valor):
    """Converte campo Tempo para timedelta; falhas retornam 0."""
    if pd.isna(tempo_valor):
        return pd.to_timedelta(0)

    tempo_str = str(tempo_valor).strip()
    if not tempo_str:
        return pd.to_timedelta(0)

    try:
        return pd.to_timedelta(tempo_str)
    except Exception:
        return pd.to_timedelta(0)


def _formatar_timedelta_hhmmss(td_valor):
    """Formata timedelta para HH:MM:SS sem frações de segundo."""
    segundos = int(td_valor.total_seconds()) if hasattr(td_valor, 'total_seconds') else 0
    if segundos < 0:
        segundos = 0
    horas = segundos // 3600
    minutos = (segundos % 3600) // 60
    segundos_restantes = segundos % 60
    return f"{horas:02d}:{minutos:02d}:{segundos_restantes:02d}"


def _formatar_lista_requerimentos(requerimentos):
    """Formata lista de requerimentos, compactando repetições no formato (xN)."""
    if not requerimentos:
        return ""

    contagem = Counter(requerimentos)
    vistos = set()
    itens = []
    for req in requerimentos:
        if req in vistos:
            continue
        vistos.add(req)
        qtd = contagem[req]
        if qtd > 1:
            itens.append(f"{req} (x{qtd})")
        else:
            itens.append(req)
    return ", ".join(itens)

def gerar_relatorio_pgd():
    """
    Função para gerar o relatório de desempenho para PGD.
    """
    try:
        log_info("Gerando relatório de desempenho para PGD...")

        # Pergunta o mês/ano de referência ao usuário com sugestão automática.
        mes_referencia, ano_referencia = _obter_mes_ano_referencia()

        # Define caminho de saída no diretório de relatórios do OneDrive ORCN.
        pasta_saida = os.path.join(TBN_FILES_FOLDER, REQUERIMENTOS_DIR_REPORT)
        os.makedirs(pasta_saida, exist_ok=True)
        nome_arquivo = f"{ano_referencia:04d}.{mes_referencia:02d}.txt"
        caminho_saida = os.path.join(pasta_saida, nome_arquivo)

        if not os.path.exists(EXCEL_PATH):
            log_erro(f"Planilha não encontrada: {EXCEL_PATH}")
            return

        # Carrega a aba principal de análise e valida colunas obrigatórias.
        df = pd.read_excel(EXCEL_PATH, sheet_name=EXCEL_SHEET_NAME)
        colunas_obrigatorias = [
            "Data da Conclusão",
            "Tempo",
            "Análise",
            "Nº do Requerimento",
            "Situação"
        ]

        colunas_faltantes = [col for col in colunas_obrigatorias if col not in df.columns]
        if colunas_faltantes:
            log_erro(f"Colunas obrigatórias ausentes na planilha: {', '.join(colunas_faltantes)}")
            return

        # Normaliza datas e filtra apenas o mês/ano solicitado.
        df["Data da Conclusão"] = pd.to_datetime(df["Data da Conclusão"], dayfirst=True, errors='coerce')
        df_mes = df[
            (df["Data da Conclusão"].dt.month == mes_referencia) &
            (df["Data da Conclusão"].dt.year == ano_referencia)
        ].copy()

        # Converte o campo Tempo para timedelta para somatórios diário e mensal.
        df_mes["Tempo_td"] = df_mes["Tempo"].apply(_converter_tempo_para_timedelta)
        carga_total_mes = df_mes["Tempo_td"].sum() if not df_mes.empty else pd.to_timedelta(0)

        linhas_relatorio = []
        linhas_relatorio.append(
            f"Carga horária cumprida com análise de requerimentos no SCH: {_formatar_timedelta_hhmmss(carga_total_mes)}, conforme detalhado abaixo:\n"
        )

        # Gera saída para todos os dias do mês, inclusive os sem registros.
        total_dias = calendar.monthrange(ano_referencia, mes_referencia)[1]
        for dia in range(1, total_dias + 1):
            data_dia = datetime(ano_referencia, mes_referencia, dia)
            df_dia = df_mes[df_mes["Data da Conclusão"].dt.day == dia].copy()
            tempo_dia = df_dia["Tempo_td"].sum() if not df_dia.empty else pd.to_timedelta(0)

            linhas_relatorio.append(
                f"{dia:02d}/{mes_referencia:02d}/{ano_referencia} ({DIAS_SEMANA_PTBR[data_dia.weekday()]}) - {_formatar_timedelta_hhmmss(tempo_dia)}:"
            )

            categorias = {
                "AP - Requerimento(s) encaminhado(s) para aprovação": [],
                "AP - Requerimento(s) em exigência": [],
                "AP - Requerimento(s) cancelado(s)": [],
                "AS - Requerimento(s) encaminhado(s) para aprovação": [],
                "AS - Requerimento(s) em exigência": [],
                "AS - Requerimento(s) cancelado(s)": [],
                "ERRO": []
            }

            # Classifica cada linha em uma das 6 categorias principais ou em ERRO.
            for _, row in df_dia.iterrows():
                req = str(row.get("Nº do Requerimento", "")).strip()
                if not req or req.lower() == "nan":
                    req = "N/A"

                analise = _normalizar_texto(row.get("Análise", ""))
                situacao = _normalizar_texto(row.get("Situação", ""))

                categorizado = False
                if analise == "padrao":
                    if situacao.startswith("em aprovacao"):
                        categorias["AP - Requerimento(s) encaminhado(s) para aprovação"].append(req)
                        categorizado = True
                    elif situacao.startswith("exigencia"):
                        categorias["AP - Requerimento(s) em exigência"].append(req)
                        categorizado = True
                    elif situacao.startswith("cancelamento"):
                        categorias["AP - Requerimento(s) cancelado(s)"].append(req)
                        categorizado = True
                elif analise == "simplificada":
                    if situacao.startswith("em aprovacao"):
                        categorias["AS - Requerimento(s) encaminhado(s) para aprovação"].append(req)
                        categorizado = True
                    elif situacao.startswith("exigencia"):
                        categorias["AS - Requerimento(s) em exigência"].append(req)
                        categorizado = True
                    elif situacao.startswith("cancelamento"):
                        categorias["AS - Requerimento(s) cancelado(s)"].append(req)
                        categorizado = True

                if not categorizado:
                    categorias["ERRO"].append(req)

            ordem_categorias = [
                "AP - Requerimento(s) encaminhado(s) para aprovação",
                "AP - Requerimento(s) em exigência",
                "AP - Requerimento(s) cancelado(s)",
                "AS - Requerimento(s) encaminhado(s) para aprovação",
                "AS - Requerimento(s) em exigência",
                "AS - Requerimento(s) cancelado(s)",
                "ERRO"
            ]

            total_itens_dia = sum(len(categorias[chave]) for chave in ordem_categorias)
            if total_itens_dia == 0:
                linhas_relatorio.append("\tNão disponível")
            else:
                for chave in ordem_categorias:
                    if categorias[chave]:
                        lista_formatada = _formatar_lista_requerimentos(categorias[chave])
                        linhas_relatorio.append(f"\t{chave}: {lista_formatada}.")

            linhas_relatorio.append("")

        # Escreve arquivo final em UTF-8 no diretório req_report.
        with open(caminho_saida, 'w', encoding='utf-8') as f:
            f.write("\n".join(linhas_relatorio).rstrip() + "\n")

        log_info(f"Relatório de desempenho para PGD gerado com sucesso: {caminho_saida}")
    except Exception as e:
        log_erro(f"Erro ao gerar relatório de desempenho para PGD: {str(e)}")