"""Baixa anexos dos requerimentos com timestamp de log posterior ao limite informado."""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from core.const import (
    CERTIFICA_TIMEOUT_PAGINA,
    CERTIFICA_URL,
    CHROME_ARGS,
    CHROME_PATH,
    REQUERIMENTOS_DIR_INBOX,
    DOWNLOAD_LOG_FILENAME,
)
from core.downloader_certifica import aguardar_login_certifica, baixar_anexos_certifica
from core.log_print import log_erro, log_info
from core.utils import get_files_folder, get_profile_dir, req_para_fullpath


DEFAULT_TIMESTAMP = "2026-10-15 23:00:00"


def listar_requerimentos_apos(root: Path, timestamp: datetime):
    """Retorna requerimentos do log com timestamp posterior ao limite e respectivos JSONs."""
    caminho_log = root.parent / DOWNLOAD_LOG_FILENAME
    log = json.loads(caminho_log.read_text(encoding="utf-8"))
    if not isinstance(log, dict):
        raise ValueError(f"Formato inválido no log de downloads: {caminho_log}")

    requerimentos = []
    for numero, status in log.items():
        if not isinstance(status, dict) or not status.get("timestamp"):
            continue
        timestamp_log = datetime.strptime(status["timestamp"], "%Y-%m-%d %H:%M:%S")
        if timestamp_log <= timestamp:
            continue
        partes = numero.split("/")
        if len(partes) != 2:
            raise ValueError(f"Número de requerimento inválido no log: {numero}")
        caminho_pasta = root / f"_{partes[1]}.{partes[0]}"
        caminho_json = caminho_pasta / f"{caminho_pasta.name[1:]}.json"
        if not caminho_json.is_file():
            raise FileNotFoundError(f"JSON do requerimento {numero} não encontrado: {caminho_json}")
        dados = json.loads(caminho_json.read_text(encoding="utf-8"))
        requerimento = dados.get("requerimento", {})
        if requerimento.get("num_req") != numero or not requerimento.get("link"):
            raise ValueError(f"JSON sem num_req correspondente ou link: {caminho_json}")
        requerimentos.append(
            {
                "num_req": numero,
                "link": requerimento["link"],
                "pasta": caminho_pasta,
                "timestamp": timestamp_log,
            }
        )
    return sorted(requerimentos, key=lambda item: item["timestamp"])


def main():
    parser = argparse.ArgumentParser(
        description="Baixa anexos selecionados pelo timestamp em download_status.json."
    )
    parser.add_argument(
        "--since",
        default=DEFAULT_TIMESTAMP,
        help=f"Timestamp mínimo do log (YYYY-MM-DD HH:MM:SS; padrão: {DEFAULT_TIMESTAMP})",
    )
    args = parser.parse_args()
    timestamp = datetime.strptime(args.since, "%Y-%m-%d %H:%M:%S")
    root = Path(get_files_folder()) / REQUERIMENTOS_DIR_INBOX
    requerimentos = listar_requerimentos_apos(root, timestamp)
    if not requerimentos:
        log_info(f"Nenhum JSON posterior a {args.since} encontrado em {root}.")
        return 0

    log_info(f"{len(requerimentos)} requerimento(s) selecionado(s) após {args.since}.")
    falhas = 0
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch_persistent_context(
            get_profile_dir(),
            headless=False,
            executable_path=CHROME_PATH,
            args=CHROME_ARGS,
            accept_downloads=True,
        )
        try:
            page = browser.new_page()
            page.goto(CERTIFICA_URL)
            aguardar_login_certifica(page)

            for indice, requerimento in enumerate(requerimentos, start=1):
                numero = requerimento["num_req"]
                log_info(f"[{indice}/{len(requerimentos)}] Baixando anexos de {numero}...")
                try:
                    pasta_requerimento = Path(req_para_fullpath(numero))
                    if pasta_requerimento != requerimento["pasta"]:
                        raise ValueError(
                            f"Pasta do JSON não corresponde ao requerimento {numero}: "
                            f"{requerimento['pasta']}"
                        )
                    page.goto(requerimento["link"], timeout=CERTIFICA_TIMEOUT_PAGINA)
                    page.get_by_text("N° do Processo SEI:").wait_for(
                        state="visible",
                        timeout=CERTIFICA_TIMEOUT_PAGINA,
                    )
                    baixados, erros = baixar_anexos_certifica(page, str(pasta_requerimento))
                    falhas += erros
                    log_info(f"Requerimento {numero}: {baixados} arquivo(s), {erros} falha(s).")
                except Exception as erro:
                    falhas += 1
                    log_erro(f"Erro ao baixar anexos de {numero}: {erro}")
        finally:
            browser.close()

    if falhas:
        log_erro(f"Processamento encerrado com {falhas} falha(s).")
        return 1
    log_info("Download dos anexos concluído sem falhas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
