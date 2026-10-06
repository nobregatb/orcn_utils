import re
import time
from playwright.sync_api import sync_playwright
from core.log_print import log_info, log_erro
from core.const import (
    CHROME_PATH, CHROME_ARGS, CERTIFICA_URL, CERTIFICA_TEXTO_LOGIN_OK,
    CERTIFICA_INTERVALO_MONITORAMENTO, CERTIFICA_DIV_POR_TIPO,
    CERTIFICA_SELETOR_CONTADOR, CERTIFICA_TIMEOUT_CONTADOR,
    CERTIFICA_ID_DIV_LISTA, CERTIFICA_CAMPOS_REQUERIMENTO,
    CERTIFICA_INDICE_PRIMEIRA_COLUNA
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
    """Clica no link da div correspondente ao tipo escolhido e aguarda a página carregar."""
    div_id = CERTIFICA_DIV_POR_TIPO[tipo]
    log_info(f"Abrindo lista do tipo {tipo}...")
    # O onclick (OsAjax) está no <a> dentro da div; clicar no centro da div pode errar o link
    page.click(f"#{div_id} a")
    page.wait_for_load_state("load")
    page.wait_for_load_state("networkidle")
    log_info("Página carregada.")


def obter_total_registros(page):
    """Lê o contador de registros ("NNNN registros") da página e retorna NNNN como inteiro."""
    contador = page.wait_for_selector(CERTIFICA_SELETOR_CONTADOR, timeout=CERTIFICA_TIMEOUT_CONTADOR)
    texto = contador.inner_text()
    # Em listas paginadas o texto é "1 a 50 de 780 registros": o total é o último número
    numeros = re.findall(r"\d+", texto)
    if not numeros:
        raise ValueError(f"Contador de registros em formato inesperado: '{texto}'")
    return int(numeros[-1])


def obter_requerimentos_certifica(page):
    """
    Lê a tabela de requerimentos da lista exibida e retorna uma lista de dicts.
    Usa as colunas de índice 2 a 9 (a partir de 0) e o href do link da primeira delas.
    """
    container = page.wait_for_selector(f"#{CERTIFICA_ID_DIV_LISTA}", timeout=CERTIFICA_TIMEOUT_CONTADOR)
    inicio = CERTIFICA_INDICE_PRIMEIRA_COLUNA
    fim = inicio + len(CERTIFICA_CAMPOS_REQUERIMENTO)
    requerimentos = []
    for linha in container.query_selector_all("tr"):
        # Linhas de cabeçalho usam <th> e não possuem <td>
        colunas = linha.query_selector_all("td")
        if len(colunas) < fim:
            continue

        valores = [coluna.inner_text().strip() for coluna in colunas[inicio:fim]]
        requerimento = dict(zip(CERTIFICA_CAMPOS_REQUERIMENTO, valores))

        link = colunas[inicio].query_selector("a")
        # A propriedade href retorna a URL absoluta, utilizável diretamente em page.goto
        requerimento["link"] = link.evaluate("a => a.href") if link else None
        requerimentos.append(requerimento)
    return requerimentos


def ler_requerimentos_do_tipo(page, tipo):
    """Abre a lista do tipo (1 ou 2) e retorna seus requerimentos (lista vazia se não houver)."""
    abrir_lista_certifica(page, tipo)
    total = obter_total_registros(page)
    log_info(f"{total} registros encontrados.")
    if total == 0:
        log_info("Não há requerimentos a analisar.")
        return []
    requerimentos = obter_requerimentos_certifica(page)
    log_info(f"{len(requerimentos)} requerimentos lidos da tabela.")
    return requerimentos


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

            # "Todos" lê primeiro os retornos para estudo (1) e depois os em análise (2)
            tipos_a_ler = ["1", "2"] if tipo == "3" else [tipo]
            requerimentos = []
            for tipo_atual in tipos_a_ler:
                requerimentos.extend(ler_requerimentos_do_tipo(page, tipo_atual))
            log_info(f"Total de requerimentos lidos: {len(requerimentos)}.")

            # Mantém o navegador aberto até o usuário confirmar
            log_info("Pressione ENTER para encerrar o navegador...")
            input()
            browser.close()
    except Exception as e:
        log_erro(f"Erro no download do Certifica: {str(e)}")
