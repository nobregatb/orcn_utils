# -*- coding: utf-8 -*-
"""Atualiza somente os JSONs existentes dos requerimentos em análise no Certifica."""

import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent))

from core.const import (
    CERTIFICA_TIMEOUT_PAGINA,
    CERTIFICA_URL,
    CHROME_ARGS,
    CHROME_PATH,
)
from core.downloader_certifica import (
    aguardar_login_certifica,
    extrair_dados_requerimento_certifica,
    gravar_json_requerimento_certifica,
    ler_requerimentos_do_tipo,
)
from core.log_print import log_erro, log_info
from core.utils import carregar_json, get_profile_dir, req_para_fullpath


def pasta_json_existente(num_req):
    """Retorna a pasta do requerimento (mesmo caminho do download) se o JSON já existir; senão None."""
    if num_req.count("/") != 1:
        raise ValueError(f"Número de requerimento inválido (esperado 'num/ano'): '{num_req}'")
    pasta = req_para_fullpath(num_req)
    caminho_json = os.path.join(pasta, f"{os.path.basename(pasta)[1:]}.json")
    # JSON ilegível seria tratado como vazio e sobrescrito pela gravação da aplicação
    if not os.path.isfile(caminho_json) or not isinstance(carregar_json(caminho_json), dict):
        return None
    return pasta


def atualizar_jsons_em_analise():
    """Lê a lista Em Análise e atualiza somente os JSONs já existentes no inbox."""
    atualizados = 0
    ignorados = 0
    falhas = 0

    with sync_playwright() as playwright:
        contexto = playwright.chromium.launch_persistent_context(
            get_profile_dir(),
            headless=False,
            executable_path=CHROME_PATH,
            args=CHROME_ARGS,
            accept_downloads=False,
        )
        try:
            page = contexto.new_page()
            page.goto(CERTIFICA_URL)
            aguardar_login_certifica(page)

            # Tipo 2 corresponde à caixa "Em Análise" do analista.
            requerimentos = ler_requerimentos_do_tipo(page, "2")
            log_info(f"{len(requerimentos)} requerimento(s) encontrados em Em Análise.")

            for indice, requerimento in enumerate(requerimentos, start=1):
                num_req = requerimento["num_req"]
                try:
                    pasta = pasta_json_existente(num_req)
                    if pasta is None:
                        ignorados += 1
                        log_info(
                            f"⏭️ Requerimento {num_req}: JSON inexistente ou ilegível; "
                            "nenhum arquivo será criado."
                        )
                        continue
                    if not requerimento.get("link"):
                        raise ValueError("Requerimento sem link para a página de análise.")

                    log_info(
                        f"▶️ [{indice}/{len(requerimentos)}] Atualizando JSON de {num_req}..."
                    )
                    page.goto(
                        requerimento["link"],
                        timeout=CERTIFICA_TIMEOUT_PAGINA,
                    )
                    page.get_by_text("N° do Processo SEI:").wait_for(
                        state="visible",
                        timeout=CERTIFICA_TIMEOUT_PAGINA,
                    )
                    dados = extrair_dados_requerimento_certifica(page)
                    gravar_json_requerimento_certifica(requerimento, dados, pasta)

                    subprodutos = dados["caracteristicas_tecnicas"]["subprodutos"]
                    log_info(
                        f"✅ JSON atualizado: {pasta} "
                        f"({len(subprodutos)} subproduto(s))."
                    )
                    atualizados += 1
                except Exception as erro:
                    falhas += 1
                    log_erro(f"Falha ao atualizar {num_req}: {erro}")
        finally:
            contexto.close()

    log_info(
        "Atualização concluída — "
        f"{atualizados} atualizado(s), {ignorados} sem JSON existente, {falhas} falha(s)."
    )


if __name__ == "__main__":
    atualizar_jsons_em_analise()
