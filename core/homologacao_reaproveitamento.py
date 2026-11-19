# -*- coding: utf-8 -*-
"""
Módulo para gerenciar a automação de reaproveitamento de números de homologação.
Implementa a verificação e processamento automatizado conforme orientações gerenciais.
"""

import re
import time
from pathlib import Path
from typing import Optional, List
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

try:
    import pymupdf as fitz
    PYMUPDF_DISPONIVEL = True
except ImportError:
    PYMUPDF_DISPONIVEL = False

from core.log_print import log_info, log_erro
from core.utils import (
    carregar_json_com_fallback,
    extract_pdf_content_from_ocr,
    salvar_json,
)
from core.const import (
    CERTIFICA_TIPO_ANEXO_REAPROVEITAMENTO,
    CERTIFICA_TIMEOUT_CAMPO_FILTRO_MS,
    CERTIFICA_TIMEOUT_PAGINA,
    CERTIFICA_TIMEOUT_RESULTADO_FILTRO_MS,
)

TEMPO_ABERTURA_HOMOLOGACAO_MS = 30000


def _locator_unico_visivel(locator, descricao):
    """Retorna o único controle visível e habilitado ou falha sem escolher um campo arbitrário."""
    candidatos = []
    for indice in range(locator.count()):
        candidato = locator.nth(indice)
        if candidato.is_visible() and candidato.is_enabled():
            candidatos.append(candidato)

    if len(candidatos) > 1:
        raise RuntimeError(f"Mais de um campo visível corresponde a '{descricao}'.")
    return candidatos[0] if candidatos else None


def _localizar_campo_mascarado(page, locators, descricao):
    """Aguarda o campo do formulário aparecer e seleciona somente um controle visível."""
    limite = time.monotonic() + CERTIFICA_TIMEOUT_CAMPO_FILTRO_MS / 1000
    campo = None
    while campo is None:
        for locator in locators:
            campo = _locator_unico_visivel(locator, descricao)
            if campo is not None:
                break

        if campo is not None:
            break
        if time.monotonic() >= limite:
            raise TimeoutError(
                f"Campo visível '{descricao}' não apareceu após "
                f"{CERTIFICA_TIMEOUT_CAMPO_FILTRO_MS / 1000:g} segundos."
            )
        page.wait_for_timeout(250)

    if campo is None:
        raise RuntimeError(f"Campo visível '{descricao}' não encontrado.")
    return campo


def _preencher_campo_mascarado(page, campo, valor, descricao):
    """Digita em um campo mascarado e verifica o conteúdo antes e depois do blur."""
    campo.click()
    campo.press("Control+A")
    campo.press("Backspace")
    # O campo usa uma máscara; fill() insere o texto em bloco e corrompe a máscara.
    page.keyboard.type(valor, delay=50)
    if campo.input_value() != valor:
        raise RuntimeError(f"O campo '{descricao}' não reteve o valor preenchido.")

    campo.blur()
    if campo.input_value() != valor:
        raise RuntimeError(
            f"O valor do campo '{descricao}' foi alterado após perder o foco."
        )


def preencher_numero_requerimento_filtro(page, num_req):
    """Localiza o campo mascarado do requerimento e digita o valor tecla a tecla."""
    padrao_rotulo = re.compile(
        r"^\s*(?:N[uú]mero|N[º°o])\s+(?:do\s+)?Requerimento\s*:?\s*$",
        re.IGNORECASE,
    )
    locators = (
        page.get_by_placeholder("Informe o Número do Requerimento", exact=True),
        page.get_by_label(padrao_rotulo),
        page.get_by_role("textbox", name=padrao_rotulo),
        page.locator(
            'input:not([type="hidden"]):visible'
            '[id*="requerimento" i], '
            'input:not([type="hidden"]):visible'
            '[name*="requerimento" i], '
            'input:not([type="hidden"]):visible'
            '[placeholder*="requerimento" i], '
            'textarea:visible[id*="requerimento" i], '
            'textarea:visible[name*="requerimento" i]'
        ),
    )
    campo = _localizar_campo_mascarado(page, locators, "Número do Requerimento")
    _preencher_campo_mascarado(page, campo, num_req, "Número do Requerimento")


def preencher_numero_homologacao(page, numero_homologacao):
    """Localiza e digita tecla a tecla o número no campo mascarado de homologação."""
    padrao_rotulo = re.compile(
        r"^\s*N[uú]mero\s+de\s+Homologa[cç][aã]o\s*:?\s*$",
        re.IGNORECASE,
    )
    locators = (
        page.get_by_placeholder("Número de Homologação", exact=True),
        page.get_by_label(padrao_rotulo),
        page.get_by_role("textbox", name=padrao_rotulo),
        page.locator(
            'input:not([type="hidden"]):visible'
            '[id*="homologacao" i], '
            'input:not([type="hidden"]):visible'
            '[name*="homologacao" i], '
            'input:not([type="hidden"]):visible'
            '[placeholder*="homologação" i], '
            'textarea:visible[id*="homologacao" i], '
            'textarea:visible[name*="homologacao" i]'
        ),
    )
    campo = _localizar_campo_mascarado(page, locators, "Número de Homologação")
    _preencher_campo_mascarado(
        page,
        campo,
        numero_homologacao,
        "Número de Homologação",
    )


def abrir_alteracao_homologacao(page):
    """Abre o formulário e aguarda o campo antes de prosseguir."""
    formulario = page.get_by_role(
        "group", name="Altera Numero de Homologação", exact=True
    )
    campo = formulario.get_by_placeholder("Número de Homologação", exact=True)
    botao = page.get_by_role(
        "button", name="Alterar Número de Homologação", exact=True
    )

    if campo.is_visible():
        return
    botao.click(timeout=CERTIFICA_TIMEOUT_CAMPO_FILTRO_MS)
    try:
        campo.wait_for(state="visible", timeout=TEMPO_ABERTURA_HOMOLOGACAO_MS)
    except PlaywrightTimeoutError as erro:
        raise TimeoutError(
            "O formulário de alteração do número de homologação não abriu "
            f"após {TEMPO_ABERTURA_HOMOLOGACAO_MS / 1000:g} segundos."
        ) from erro


def confirmar_alteracao_homologacao(page):
    """Confirma no formulário de homologação e aguarda o sucesso no Certifica."""
    formulario = page.get_by_role(
        "group", name="Altera Numero de Homologação", exact=True
    )
    botao = formulario.get_by_role(
        "button", name=re.compile(r"^(Confirma|Confirmar)$")
    )
    botao.wait_for(state="visible", timeout=CERTIFICA_TIMEOUT_CAMPO_FILTRO_MS)
    botao.click(timeout=CERTIFICA_TIMEOUT_CAMPO_FILTRO_MS)
    page.get_by_text(
        "Número de homologação alterado com sucesso.",
        exact=True,
    ).wait_for(state="visible", timeout=CERTIFICA_TIMEOUT_PAGINA)


def atualizar_numero_homologacao_json(caminho_json, novo_numero):
    """Atualiza cod_homologacao no JSON após a alteração ser confirmada no Certifica."""
    dados = carregar_json_com_fallback(caminho_json)
    requerimento = dados.get("requerimento") if isinstance(dados, dict) else None
    if not isinstance(requerimento, dict):
        log_erro(f"JSON sem bloco 'requerimento'; não foi possível atualizar {caminho_json}.")
        return False

    requerimento["cod_homologacao"] = novo_numero
    if not salvar_json(dados, caminho_json, indent=4):
        log_erro(f"Falha ao salvar o novo número de homologação em {caminho_json}.")
        return False

    log_info(f"JSON atualizado com o número de homologação {novo_numero}.")
    return True


def localizar_link_requerimento_na_tabela(page, num_req):
    """Localiza o link exato dentro da tabela que tem a coluna N° do Requerimento."""
    cabecalho = page.get_by_role(
        "columnheader",
        name=re.compile(r"^\s*N[°º]\s+do\s+Requerimento", re.IGNORECASE),
    )
    cabecalho.wait_for(
        state="visible",
        timeout=CERTIFICA_TIMEOUT_RESULTADO_FILTRO_MS,
    )

    tabela = cabecalho.locator("xpath=ancestor::table[1]")
    tabela.wait_for(
        state="visible",
        timeout=CERTIFICA_TIMEOUT_RESULTADO_FILTRO_MS,
    )
    link = tabela.get_by_role("link", name=num_req, exact=True)
    link.wait_for(
        state="visible",
        timeout=CERTIFICA_TIMEOUT_RESULTADO_FILTRO_MS,
    )
    link_visivel = _locator_unico_visivel(link, f"requerimento '{num_req}'")
    if link_visivel is None:
        raise RuntimeError(f"Link do requerimento '{num_req}' deixou de estar visível.")
    return link_visivel


class GerenciadorReaproveitamentoHomologacao:
    """Gerencia a automação de reaproveitamento de números de homologação."""

    # Padrão para identificar números de homologação (XXXXX-XX-XXXXX)
    PADRAO_HOMOLOGACAO = r"\b([A-Z0-9]{5}-[A-Z0-9]{2}-[A-Z0-9]{5})\b"

    def __init__(self):
        """Inicializa o gerenciador."""
        pass

    @staticmethod
    def extrair_num_req_do_json(caminho_json: str) -> Optional[str]:
        """
        Extrai o número de requerimento do arquivo JSON.
        
        Args:
            caminho_json: Caminho absoluto do arquivo JSON
            
        Returns:
            str com num_req (ex: ABCDE/FG) ou None em caso de erro
        """
        try:
            dados = carregar_json_com_fallback(caminho_json)
            if dados and "requerimento" in dados:
                num_req = dados["requerimento"].get("num_req", "")
                if num_req:
                    return num_req.strip()
        except Exception as e:
            log_erro(f"Erro ao ler JSON {caminho_json}: {e}")
        return None

    @staticmethod
    def extrair_cod_homologacao_do_json(caminho_json: str) -> Optional[str]:
        """
        Extrai o código de homologação do arquivo JSON.
        
        Args:
            caminho_json: Caminho absoluto do arquivo JSON
            
        Returns:
            str com cod_homologacao (ex: ABCDE-FG-HIJLM) ou None em caso de erro
        """
        try:
            dados = carregar_json_com_fallback(caminho_json)
            if dados and "requerimento" in dados:
                cod_hom = dados["requerimento"].get("cod_homologacao", "")
                if cod_hom:
                    return cod_hom.strip()
        except Exception as e:
            log_erro(f"Erro ao ler JSON {caminho_json}: {e}")
        return None

    @staticmethod
    def num_req_corresponde_cod_homologacao(num_req: str, cod_homologacao: str) -> bool:
        """
        Verifica se num_req contém os dígitos iniciais de cod_homologacao.
        Ex: num_req='ABCDE/FG' corresponde a cod_homologacao='ABCDE-FG-HIJLM'
        
        Args:
            num_req: Número do requerimento (ex: ABCDE/FG)
            cod_homologacao: Código de homologação (ex: ABCDE-FG-HIJLM)
            
        Returns:
            True se correspondem, False caso contrário
        """
        if not num_req or not cod_homologacao:
            return False
        
        # Remove espaços
        num_req = num_req.strip()
        cod_homologacao = cod_homologacao.strip()
        
        # Substitui / por - para comparação
        num_req_normalizado = num_req.replace("/", "-").upper()
        cod_hom_inicio = cod_homologacao.upper()[:len(num_req_normalizado)]
        
        return num_req_normalizado == cod_hom_inicio

    @staticmethod
    def listar_arquivos_reaproveitamento(pasta_requerimento: str) -> List[str]:
        """
        Lista arquivos de reaproveitamento de homologação na pasta.
        
        Args:
            pasta_requerimento: Caminho da pasta do requerimento
            
        Returns:
            Lista com caminhos absolutos dos arquivos encontrados
        """
        arquivos_reaproveitamento = []
        
        try:
            for arquivo in Path(pasta_requerimento).glob("*"):
                if arquivo.is_file():
                    # Verifica se o nome contém o tipo de reaproveitamento
                    if CERTIFICA_TIPO_ANEXO_REAPROVEITAMENTO in arquivo.name:
                        arquivos_reaproveitamento.append(str(arquivo))
        except Exception as e:
            log_erro(f"Erro ao listar arquivos em {pasta_requerimento}: {e}")
        
        return arquivos_reaproveitamento

    @staticmethod
    def extrair_numeros_homologacao_de_arquivo(caminho_pdf: str) -> List[str]:
        """
        Extrai números de homologação de um arquivo PDF.
        Tenta extrair texto diretamente; se falhar, usa OCR.
        
        Args:
            caminho_pdf: Caminho absoluto do arquivo PDF
            
        Returns:
            Lista de números únicos encontrados (formato XXXXX-XX-XXXXX)
        """
        numeros = set()
        texto_completo = ""
        
        # Tenta extrair com PyMuPDF
        if PYMUPDF_DISPONIVEL:
            try:
                pdf = fitz.open(caminho_pdf)
                for pagina in pdf:
                    texto_completo += pagina.get_text()
                pdf.close()
            except Exception as e:
                log_info(f"Falha ao extrair com PyMuPDF: {e}")
        
        # Se PyMuPDF falhar ou não estiver disponível, tenta OCR
        if not texto_completo:
            log_info(f"Tentando OCR para extrair números de {Path(caminho_pdf).name}...")
            texto_completo = extract_pdf_content_from_ocr(Path(caminho_pdf))
            if not texto_completo:
                log_erro(f"Não foi possível extrair texto de {caminho_pdf}")
                return []
        
        # Extrai todos os números no padrão XXXXX-XX-XXXXX
        matches = re.findall(GerenciadorReaproveitamentoHomologacao.PADRAO_HOMOLOGACAO, texto_completo)
        for match in matches:
            numeros.add(match.upper())
        
        return list(numeros)

    @staticmethod
    def buscar_novo_numero_homologacao(
        pasta_requerimento: str,
        cod_homologacao_atual: str
    ) -> Optional[str]:
        """
        Busca um novo número de homologação nos arquivos de reaproveitamento.
        
        Args:
            pasta_requerimento: Caminho da pasta do requerimento
            cod_homologacao_atual: Código de homologação atual (para exclusão)
            
        Returns:
            str com o novo número de homologação se encontrado exatamente um, None caso contrário
        """
        arquivos = GerenciadorReaproveitamentoHomologacao.listar_arquivos_reaproveitamento(
            pasta_requerimento
        )
        
        if not arquivos:
            log_info("ℹ️ Nenhum arquivo de reaproveitamento encontrado.")
            return None
        
        log_info(f"📄 Encontrado(s) {len(arquivos)} arquivo(s) de reaproveitamento.")
        
        # Coleta todos os números de todos os arquivos
        todos_os_numeros = set()
        
        for arquivo in arquivos:
            numeros = GerenciadorReaproveitamentoHomologacao.extrair_numeros_homologacao_de_arquivo(arquivo)
            if numeros:
                log_info(f"  - {Path(arquivo).name}: {', '.join(numeros)}")
                todos_os_numeros.update(numeros)
        
        # Remove o número atual da lista
        todos_os_numeros.discard(cod_homologacao_atual.upper())
        
        if len(todos_os_numeros) == 0:
            log_info("ℹ️ Nenhum novo número de homologação encontrado (além do atual).")
            return None
        elif len(todos_os_numeros) > 1:
            log_erro(
                f"❌ ERRO: Encontrado(s) {len(todos_os_numeros)} número(s) de homologação "
                f"diferente(s): {', '.join(sorted(todos_os_numeros))}. "
                "Nenhum será processado (esperava-se apenas um)."
            )
            return None
        
        novo_numero = list(todos_os_numeros)[0]
        log_info(f"✅ Encontrado 1 novo número de homologação: {novo_numero}")
        return novo_numero

    @staticmethod
    def alterar_numero_homologacao_no_certifica(
        page: Page,
        num_req: str,
        novo_numero_homologacao: str
    ) -> bool:
        """
        Realiza os passos de alteração de número de homologação no Certifica.
        
        Steps:
        5.1. Abrir a "Caixa Geral" na página inicial do certifica.
        5.2. Na página aberta, clicar no botão "Filtrar".
        5.3. Preencher o campo "Número do Requerimento" com o valor de num_req.
        5.4. Após isso, clicar no botão "Pesquisar".
        5.5. Aparecerá uma tabela abaixo desse botão, com um link em cada célula.
        5.6. Clique no valor do elemento da coluna "N° do Requerimento".
        5.7. Na janela que será aberta, aba Fabricante, clique no botão "Alterar Número de Homologação".
        5.8. Abaixo desse botão, aparecerá um campo "Número de Homologação". Preencha com o valor 
             encontrado no item 5 e clique no botão "Confirma".
        
        Args:
            page: Página Playwright do Certifica
            num_req: Número do requerimento (ex: 25/06969)
            novo_numero_homologacao: Novo número de homologação (ex: ABCDE-FG-HIJLM)
            
        Returns:
            True se a alteração foi bem-sucedida, False caso contrário
        """
        try:
            log_info("🔄 Iniciando processo de alteração de homologação no Certifica...")
            
            # 5.1. Abrir a "Caixa Geral" na página inicial
            log_info("5.1 Navegando para Caixa Geral...")
            # Volta para a página inicial do Certifica
            page.goto("https://appsnet/Certifica/", timeout=CERTIFICA_TIMEOUT_PAGINA)
            page.wait_for_load_state("load")
            page.wait_for_load_state("networkidle")
            
            # Localiza e clica no link da Caixa Geral
            caixa_geral_link = page.locator("a:has-text('Caixa Geral')").first
            caixa_geral_link.wait_for(state="visible", timeout=CERTIFICA_TIMEOUT_PAGINA)
            caixa_geral_link.click()
            page.wait_for_load_state("load")
            page.wait_for_load_state("networkidle")
            log_info("✅ Caixa Geral aberta")
            
            # 5.2. Clicar no botão "Filtrar"
            log_info("5.2 Clicando em 'Filtrar'...")
            botao_filtrar = page.locator("button:has-text('Filtrar'), input[value='Filtrar']").first
            botao_filtrar.wait_for(state="visible", timeout=CERTIFICA_TIMEOUT_PAGINA)
            botao_filtrar.click()
            log_info("✅ Painel de filtro aberto")
            
            # 5.3. Preencher o campo "Número do Requerimento"
            log_info(f"5.3 Preenchendo campo 'Número do Requerimento' com '{num_req}'...")
            preencher_numero_requerimento_filtro(page, num_req)
            log_info(f"✅ Campo validado com o valor '{num_req}'")
            
            # 5.4. Clicar no botão "Pesquisar"
            log_info("5.4 Clicando em 'Pesquisar'...")
            botao_pesquisar = page.locator(
                "button:has-text('Pesquisar'), input[value='Pesquisar']"
            ).first
            botao_pesquisar.wait_for(state="visible", timeout=CERTIFICA_TIMEOUT_PAGINA)
            botao_pesquisar.click()
            log_info("✅ Pesquisa executada")
            
            # 5.5-5.6. Localizar e clicar no link do requerimento na tabela
            log_info(f"5.5-5.6 Procurando link do requerimento '{num_req}' na tabela...")
            link_requerimento = localizar_link_requerimento_na_tabela(page, num_req)
            link_requerimento.click()
            page.wait_for_load_state("load")
            page.wait_for_load_state("networkidle")
            log_info(f"✅ Requerimento '{num_req}' aberto")
            
            # 5.7. Na aba Fabricante, clicar em "Alterar Número de Homologação"
            log_info("5.7 Localizando botão 'Alterar Número de Homologação' na aba Fabricante...")
            
            aba_fabricante = page.get_by_role("tab", name="Fabricante", exact=True)
            aba_fabricante.wait_for(state="visible", timeout=CERTIFICA_TIMEOUT_PAGINA)
            if aba_fabricante.get_attribute("aria-selected") != "true":
                aba_fabricante.click()
                page.wait_for_load_state("networkidle", timeout=CERTIFICA_TIMEOUT_CAMPO_FILTRO_MS)
            abrir_alteracao_homologacao(page)
            log_info("✅ Formulário de alteração de homologação aberto.")
            
            # 5.8. Preencher campo de Número de Homologação e clicar em Confirmar
            log_info(f"5.8 Preenchendo campo com novo número: {novo_numero_homologacao}...")
            preencher_numero_homologacao(page, novo_numero_homologacao)
            log_info(f"✅ Campo preenchido com {novo_numero_homologacao}")
            
            log_info("5.8 Clicando em 'Confirma' no formulário de homologação...")
            confirmar_alteracao_homologacao(page)
            log_info("✅ Número de homologação alterado com sucesso!")
            
            return True
            
        except Exception as e:
            log_erro(f"❌ Falha ao alterar número de homologação: {e}")
            return False


def processar_reaproveitamento_homologacao_apos_download(
    pasta_requerimento: str,
    caminho_json_requerimento: str,
    page: Page
) -> bool:
    """
    Processa a automação de reaproveitamento de homologação após download dos anexos.
    
    Fluxo:
    1. Verifica se num_req corresponde ao início de cod_homologacao
    2. Se SIM, busca arquivos de reaproveitamento
    3. Extrai números de homologação alternativos
    4. Se encontrar exatamente um, altera automaticamente no Certifica
    
    Args:
        pasta_requerimento: Caminho da pasta do requerimento
        caminho_json_requerimento: Caminho do arquivo JSON do requerimento
        page: Página Playwright (para interagir com o Certifica)
        
    Returns:
        True se processado com sucesso, False caso contrário
    """
    try:
        gerenciador = GerenciadorReaproveitamentoHomologacao()
        
        log_info("\n" + "="*70)
        log_info("🔍 Verificando necessidade de reaproveitamento de homologação...")
        log_info("="*70)
        
        # Passo 1: Verificar correspondência num_req <-> cod_homologacao
        num_req = gerenciador.extrair_num_req_do_json(caminho_json_requerimento)
        cod_homologacao = gerenciador.extrair_cod_homologacao_do_json(caminho_json_requerimento)
        
        if not num_req or not cod_homologacao:
            log_info("ℹ️ Dados incompletos no JSON. Pulando verificação de reaproveitamento.")
            return False
        
        log_info(f"📋 Nº Requerimento: {num_req}")
        log_info(f"📋 Código Homologação: {cod_homologacao}")
        
        if not gerenciador.num_req_corresponde_cod_homologacao(num_req, cod_homologacao):
            log_info("ℹ️ Nº Requerimento NÃO corresponde ao código de homologação. Nenhuma ação necessária.")
            return False
        
        log_info("✅ Nº Requerimento corresponde ao código de homologação. Continuando...")
        
        # Passo 2: Buscar novo número de homologação
        novo_numero = gerenciador.buscar_novo_numero_homologacao(pasta_requerimento, cod_homologacao)
        
        if not novo_numero:
            log_info("ℹ️ Nenhum novo número de homologação encontrado ou múltiplos encontrados.")
            return False
        
        # Passo 3: Alterar no Certifica
        log_info(f"\n🚀 Alterando número de homologação no Certifica...")
        log_info(f"   De: {cod_homologacao}")
        log_info(f"   Para: {novo_numero}")
        
        sucesso = gerenciador.alterar_numero_homologacao_no_certifica(page, num_req, novo_numero)
        
        if not sucesso:
            log_info("❌ Falha ao processar reaproveitamento de homologação.")
            return False

        if not atualizar_numero_homologacao_json(caminho_json_requerimento, novo_numero):
            log_erro(
                "O número foi alterado no Certifica, mas não foi possível atualizar o JSON."
            )
            return False

        log_info("✅ Reaproveitamento de homologação processado com SUCESSO!")
        return True
            
    except Exception as e:
        log_erro(f"Erro geral ao processar reaproveitamento: {e}")
        return False
