import re
import time
from playwright.sync_api import sync_playwright
from core.log_print import log_info, log_erro
from core.const import (
    CHROME_PATH, CHROME_ARGS, CERTIFICA_URL, CERTIFICA_TEXTO_LOGIN_OK,
    CERTIFICA_INTERVALO_MONITORAMENTO, CERTIFICA_DIV_POR_TIPO,
    CERTIFICA_SELETOR_CONTADOR, CERTIFICA_TIMEOUT_CONTADOR
    )
from core.utils import get_profile_dir


def pagina_contem_texto(page, texto):
    """Verifica se o texto aparece na página ou em algum de seus frames."""
    for frame in page.frames:
        try:
            if texto in frame.inner_text("body", timeout=2000):
                return True
        except Exception:
            # Frame em navegação/recarga: tenta novamente no próximo ciclo
            continue
    return False


def aguardar_login_certifica(page):
    """Monitora a página até que o texto de login concluído seja exibido."""
    log_info(f"Aguardando login do usuário (monitorando '{CERTIFICA_TEXTO_LOGIN_OK}')...")
    while not pagina_contem_texto(page, CERTIFICA_TEXTO_LOGIN_OK):
        time.sleep(CERTIFICA_INTERVALO_MONITORAMENTO)
    log_info("Login identificado.")


def abrir_lista_certifica(page, tipo):
    """Clica na div correspondente ao tipo escolhido e aguarda a página carregar."""
    div_id = CERTIFICA_DIV_POR_TIPO[tipo]
    log_info(f"Abrindo lista do tipo {tipo}...")
    page.click(f"#{div_id}")
    page.wait_for_load_state("load")
    page.wait_for_load_state("networkidle")
    log_info("Página carregada.")


def obter_total_registros(page):
    """Lê o contador de registros ("NNNN registros") da página e retorna NNNN como inteiro."""
    contador = page.wait_for_selector(CERTIFICA_SELETOR_CONTADOR, timeout=CERTIFICA_TIMEOUT_CONTADOR)
    texto = contador.inner_text()
    correspondencia = re.search(r"\d+", texto)
    if not correspondencia:
        raise ValueError(f"Contador de registros em formato inesperado: '{texto}'")
    return int(correspondencia.group())


def baixar_documentos_certifica(obter_tipo):
    """
    Abre o Certifica, aguarda o login do usuário e pergunta o tipo de download.
    obter_tipo: função que interage com o usuário e retorna o tipo escolhido (ou None).
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                get_profile_dir(),
                headless=False,
                executable_path=CHROME_PATH,
                args=CHROME_ARGS,
                accept_downloads=True
            )
            page = browser.new_page()
            page.goto(CERTIFICA_URL)

            aguardar_login_certifica(page)

            tipo = obter_tipo()
            if tipo is None:
                browser.close()
                return

            if tipo == "3":
                log_info("Download de 'Todos' ainda não implementado.")
            else:
                abrir_lista_certifica(page, tipo)
                total = obter_total_registros(page)
                log_info(f"{total} registros encontrados.")
                if total == 0:
                    log_info("Não há requerimentos a analisar.")

            # Mantém o navegador aberto até o usuário confirmar
            log_info("Pressione ENTER para encerrar o navegador...")
            input()
            browser.close()
    except Exception as e:
        log_erro(f"Erro no download do Certifica: {str(e)}")
