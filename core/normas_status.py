"""Weekly check of revocation markers on Anatel normative pages."""

import json
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from threading import Thread
from urllib.request import Request, urlopen

from core.const import JSON_FILES
from core.log_print import log_erro, log_info


CAMPO_ULTIMA_VERIFICACAO = "ultima_verificacao_vigencia"
MAX_WORKERS = 8
TIMEOUT_SEGUNDOS = 20


class _ExtratorTextoHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.textos = []
        self.elementos_ignorados = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script", "style", "noscript"}:
            self.elementos_ignorados += 1

    def handle_endtag(self, tag):
        if tag.lower() in {"script", "style", "noscript"} and self.elementos_ignorados:
            self.elementos_ignorados -= 1

    def handle_data(self, data):
        if not self.elementos_ignorados:
            self.textos.append(data)


def _normalizar(texto):
    texto = unicodedata.normalize("NFD", texto.casefold())
    texto = "".join(
        caractere for caractere in texto
        if unicodedata.category(caractere) != "Mn"
    )
    return re.sub(r"\s+", "", texto)


def _pagina_indica_revogacao(nome, html):
    parser = _ExtratorTextoHTML()
    parser.feed(html)
    texto_pagina = _normalizar(" ".join(parser.textos))
    nome_normalizado = _normalizar(nome)
    if not nome_normalizado:
        raise ValueError("nome do normativo ausente")

    correspondencias = list(re.finditer(re.escape(nome_normalizado), texto_pagina))
    if not correspondencias:
        raise ValueError("nome do normativo não encontrado no conteúdo da URL")
    for correspondencia in correspondencias:
        trecho_seguinte = texto_pagina[correspondencia.end():]
        if re.match(r"\(revogad[oa]\)", trecho_seguinte):
            return True
    return False


def _eh_ato(normativo):
    return bool(re.match(r"\s*ato\b", normativo.get("nome", ""), re.IGNORECASE))


def _normas_elegiveis(normas):
    return [
        norma for norma in normas
        if isinstance(norma, dict)
        and str(norma.get("status", "")).casefold() not in {"revogado", "revogada"}
        and not str(norma.get("url", "")).strip().casefold().startswith("https://sei.anatel.gov.br")
    ]


def _semana_atual():
    iso = date.today().isocalendar()
    return iso.year, iso.week


def _ja_verificadas_nesta_semana(data_verificacao):
    try:
        verificada_em = date.fromisoformat(data_verificacao)
    except (TypeError, ValueError):
        return False
    semana_verificada = verificada_em.isocalendar()
    return (semana_verificada.year, semana_verificada.week) == _semana_atual()


def extrair_normas_e_data_verificacao(dados):
    if isinstance(dados, list):
        normas = dados
        data_verificacao = None
    elif isinstance(dados, dict) and isinstance(dados.get("normas"), list):
        normas = dados["normas"]
        data_verificacao = dados.get(CAMPO_ULTIMA_VERIFICACAO)
    else:
        return [], None

    for norma in normas:
        if isinstance(norma, dict):
            norma.pop(CAMPO_ULTIMA_VERIFICACAO, None)
    return normas, data_verificacao


def criar_documento_normas(normas, data_verificacao):
    return {
        CAMPO_ULTIMA_VERIFICACAO: data_verificacao,
        "normas": normas,
    }


def _consultar_norma(norma):
    url = str(norma.get("url", "")).strip()
    if not url.lower().startswith(("http://", "https://")):
        raise ValueError("URL ausente ou inválida")

    requisicao = Request(url, headers={"User-Agent": "ORCN-Utils/1.0"})
    with urlopen(requisicao, timeout=TIMEOUT_SEGUNDOS) as resposta:
        html = resposta.read().decode(resposta.headers.get_content_charset() or "utf-8", errors="replace")

    return _pagina_indica_revogacao(str(norma.get("nome", "")), html)


def iniciar_verificacao_semanal():
    caminho = Path(JSON_FILES["normas"])
    try:
        with caminho.open("r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
        normas, data_verificacao = extrair_normas_e_data_verificacao(dados)
        if not normas:
            raise ValueError("normas.json não contém uma lista de normas")
    except Exception as erro:
        log_erro(f"Não foi possível iniciar a verificação semanal das normas: {erro}")
        return None

    elegiveis = _normas_elegiveis(normas)
    if not elegiveis:
        log_info("Verificação semanal de vigência dispensada: não há normas pendentes.")
        return None
    if _ja_verificadas_nesta_semana(data_verificacao):
        log_info("Verificação semanal de vigência já realizada nesta semana; nenhuma consulta necessária.")
        return None

    resultado = {"consultas": {}, "falhas": {}}

    def consultar_todas():
        total = len(elegiveis)
        concluidas = 0
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            tarefas = {
                executor.submit(_consultar_norma, norma): norma
                for norma in elegiveis
            }
            for tarefa in as_completed(tarefas):
                norma = tarefas[tarefa]
                norma_id = norma.get("id")
                nome = norma.get("nome", norma_id)
                concluidas += 1
                try:
                    revogada = tarefa.result()
                    resultado["consultas"][norma_id] = revogada
                    situacao = "marcador de revogação encontrado" if revogada else "nenhum marcador de revogação encontrado"
                    log_info(
                        f"Verificação de vigência [{concluidas}/{total}] "
                        f"{norma_id} - {nome}: {situacao}."
                    )
                except Exception as erro:
                    resultado["falhas"][norma_id] = str(erro)
                    log_erro(
                        f"Verificação de vigência [{concluidas}/{total}] "
                        f"{norma_id} - {nome}: falha inconclusiva: {erro}"
                    )

    log_info(f"Verificação semanal de vigência iniciada: 0/{len(elegiveis)} normas verificadas.")
    thread = Thread(target=consultar_todas, name="verificacao-semanal-normas", daemon=True)
    thread.start()
    return thread, resultado


def finalizar_verificacao_semanal(execucao):
    if execucao is None:
        return

    thread, resultado = execucao
    thread.join()
    falhas = resultado["falhas"]
    if falhas:
        log_erro(f"Consultas inconclusivas: {len(falhas)}; status preservados e nova tentativa pendente.")

    caminho = Path(JSON_FILES["normas"])
    try:
        with caminho.open("r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
        normas, data_verificacao = extrair_normas_e_data_verificacao(dados)

        atualizadas = []
        for norma in normas:
            norma_id = norma.get("id")
            if norma_id in resultado["consultas"] and resultado["consultas"][norma_id]:
                norma["status"] = "revogado" if _eh_ato(norma) else "revogada"
                atualizadas.append(norma_id)

        if not falhas:
            data_verificacao = date.today().isoformat()

        caminho_temporario = caminho.with_suffix(caminho.suffix + ".tmp")
        with caminho_temporario.open("w", encoding="utf-8") as arquivo:
            json.dump(criar_documento_normas(normas, data_verificacao), arquivo, indent=2, ensure_ascii=False)
        caminho_temporario.replace(caminho)

        if falhas:
            log_info("Verificação inconclusiva; status e data global preservados para nova tentativa.")
        else:
            log_info(f"Verificação semanal de vigência concluída em {date.today().isoformat()}.")
        for norma_id in atualizadas:
            log_info(f"Norma identificada como revogada: {norma_id}.")
    except Exception as erro:
        log_erro(f"Não foi possível salvar os resultados da verificação de normas: {erro}")