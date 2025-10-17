# -*- coding: utf-8 -*-
"""
Constantes globais do projeto ORCN Utils.
Centraliza todos os valores estáticos e configurações do sistema.
"""

# ================================
# CAMINHOS E DIRETÓRIOS
# ================================

# Caminhos de execução
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
TESSERACT_PATH = r"C:\Users\tbnobrega\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"

# Diretório debug específico do desenvolvedor
TBN_FILES_FOLDER = r"C:\Users\tbnobrega\OneDrive - ANATEL\Anatel\_ORCN"

# Nomes de diretórios e arquivos
CHROME_PROFILE_DIR = "meu_perfil_chrome"
#EXCEL_FILENAME = 'ORCN.xlsx'
REQUERIMENTOS_DIR_PREFIX = "Requerimentos"
UTILS_DIR = "utils"

# Arquivos JSON de configuração
JSON_FILES = {
    'regras': "utils/regras.json",
    'equipamentos': "utils/equipamentos.json", 
    'requisitos': "utils/requisitos.json",
    'normas': "utils/normas.json",
    'ocds': "utils/ocds.json"
}

# ================================
# CONFIGURAÇÕES WEB E SCRAPING
# ================================

# URLs do sistema
MOSAICO_BASE_URL = "https://sistemasnet.anatel.gov.br/mosaico/sch/worklist/"

# Seletores CSS
CSS_SELECTORS = {
    'menu_todos': "#menuForm\\:todos",
    'tabela_dados': "css=#form\\:tarefasTable_data tr",
    'iframe_detalhe': "#__frameDetalhe",
    'tabela_analise': "table.analiseTable",
    'link_pdf': "a[href*='.pdf'], a[href*='download']",
    'paginator_options': "select.ui-paginator-rpp-options",
    'blockui': ".ui-blockui"
}

# Botões de anexos para download (será definido após TIPOS_DOCUMENTOS)

# Argumentos do Chrome
CHROME_ARGS = [
    "--start-maximized",
    "--disable-blink-features=AutomationControlled"
]

# ================================
# TIMEOUTS E LIMITES
# ================================

# Timeouts em milissegundos
TIMEOUT_PRIMEFACES_AJAX = 5000
TIMEOUT_FORCE_CLICK = 2000
TIMEOUT_LOAD_STATE = 10000
TIMEOUT_BLOCKUI = 15000
TIMEOUT_MENU_CLICK = 3600000

# Timeouts em segundos
TIMEOUT_LIMITE_SESSAO = 28 * 60  # 28 minutos para evitar timeout do Mosaico

# Delays
SLEEP_AFTER_CLICK = 1
SLEEP_AJAX_WAIT = 0.3
SLEEP_SCROLL_WAIT = 0.3
SLEEP_TABELA_RELOAD = 1
SLEEP_ANEXOS_WAIT = 2

# Limites de paginação
ITEMS_PER_PAGE = "100"

# ================================
# PLANILHA EXCEL
# ================================

# Nomes de planilhas e tabelas
EXCEL_SHEET_NAME = 'Requerimentos-Análise'
EXCEL_TABLE_NAME = 'tabRequerimentos'

# Status de requerimentos
STATUS_EM_ANALISE = ['Em Análise', 'Em Análise - RE']
STATUS_AUTOMATICO = 'AUTOMATICO'

# Índices de colunas na planilha
COLUNA_STATUS = 9
COLUNA_NUMERO_REQ = 1

# ================================
# TIPOS DE DOCUMENTOS
# ================================

# Tabela de requerimentos
TAB_REQUERIMENTOS = {# a coluna 0 é desprezada, não tem dados
                     'num_req': 1,
                     'cod_homologacao': 2,
                     'num_cct': 3,
                     'tipo_equipamento': 4,
                     'modelos': 5,
                     'solicitante': 6,
                     'fabricante': 7,
                     'data': 8,
                     'status': 9
                     }
# ================================
# TIPOS DE DOCUMENTOS UNIFICADOS
# ================================

# Estrutura unificada que consolida tipos, padrões e botões de documentos
TIPOS_DOCUMENTOS = {
    'cct': {
        'nome': 'Certificado de Conformidade Técnica',
        'nome_curto': 'CCT',
        'padroes': ['certificado', 'conformidade', 'tecnica', 'cct'],
        'botao_pdf': 'Certificado de Conformidade Técnica - CCT'
    },
    'ract': {
        'nome': 'Relatório de Avaliação da Conformidade',
        'nome_curto': 'RACT', 
        'padroes': ['relatorio', 'avaliacao', 'conformidade', 'ract'],
        'botao_pdf': 'Relatório de Avaliação da Conformidade - RACT'
    },
    'manual': {
        'nome': 'Manual do Produto',
        'nome_curto': 'Manual',
        'padroes': ['manual', 'produto', 'usuario'],
        'botao_pdf': 'Manual do Produto'
    },
    'relatorio_ensaio': {
        'nome': 'Relatório de Ensaio',
        'nome_curto': 'Relatório',
        'padroes': ['relatorio', 'ensaio', 'teste'],
        'botao_pdf': 'Relatório de Ensaio'
    },
    'art': {
        'nome': 'ART',
        'nome_curto': 'ART',
        'padroes': ['art', 'responsabilidade'],
        'botao_pdf': 'ART'
    },
    'fotos': {
        'nome': 'Fotos',
        'nome_curto': 'Fotos',
        'padroes': ['foto', 'imagem', 'jpg', 'png'],
        'botao_pdf': 'Fotos do produto'
    },
    'contrato_social': {
        'nome': 'Contrato Social',
        'nome_curto': 'Contrato',
        'padroes': ['contrato', 'social', 'estatuto'],
        'botao_pdf': 'Contrato Social'
    },
    'outros': {
        'nome': 'Outros',
        'nome_curto': 'Outros',
        'padroes': [],
        'botao_pdf': 'Outros'
    }
}

# Constantes derivadas para compatibilidade (DEPRECATED - usar TIPOS_DOCUMENTOS)
TIPOS_DOCUMENTO = {k: v['nome'] for k, v in TIPOS_DOCUMENTOS.items()}
PADROES_ARQUIVO = {k: v['padroes'] for k, v in TIPOS_DOCUMENTOS.items()}

# Gerar lista de botões PDF dinamicamente
def _gerar_botoes_pdf():
    """Gera lista de botões PDF baseada em TIPOS_DOCUMENTOS"""
    botoes = []
    for tipo_info in TIPOS_DOCUMENTOS.values():
        if tipo_info['botao_pdf'] not in botoes:
            botoes.append(tipo_info['botao_pdf'])
    
    # Adicionar botões específicos que não estão em tipos de documento
    botoes_especiais = ["Selo ANATEL", "Fotos internas"]
    for botao in botoes_especiais:
        if botao not in botoes:
            botoes.append(botao)
    
    return botoes

BOTOES_PDF = _gerar_botoes_pdf()

# Constantes para tipos de documento (chaves da estrutura TIPOS_DOCUMENTOS)
TIPO_CCT = 'cct'
TIPO_RACT = 'ract'
TIPO_MANUAL = 'manual'
TIPO_RELATORIO_ENSAIO = 'relatorio_ensaio'
TIPO_ART = 'art'
TIPO_FOTOS = 'fotos'
TIPO_CONTRATO_SOCIAL = 'contrato_social'
TIPO_OUTROS = 'outros'

# ================================
# MENSAGENS DO SISTEMA
# ================================

# Títulos e cabeçalhos
TITULO_APLICACAO = "*** # ORCN - Download e análise de processos ***"
TITULO_AUTOMACAO = "BOT AUTOMAÇÃO ORCN - DOWNLOAD DE ANEXOS"

# Opções do menu
OPCOES_MENU = {
    'download': 'D',
    'analise': 'A',
    'sair': 'S'
}

DESCRICOES_MENU = {
    'D': "Baixar documentos (SCH ANATEL)",
    'A': "Analisar requerimento(s) (Análise automatizada)",
    'S': "Sair"
}

# Mensagens de status
MENSAGENS_STATUS = {
    'modo_debug': "DEBUG - MODO DEBUG ATIVADO - Usando caminho de desenvolvimento",
    'modo_executavel': "EXECUTAVEL - Usando diretório: {}",
    'modo_script': "SCRIPT - Usando diretório: {}",
    'producao_lista': "PRODUCAO - Modo produção: processando todos os requerimentos da lista",
    'debug_excel': "DEBUG - Modo debug: verificando planilha Excel...",
    'pasta_criada': "   PASTA Pasta criada: {}",
    'req_encontrado': "   FOUND - Requerimento encontrado: {}",
    'total_reqs': "TOTAL - Total de requerimentos a processar: {}",
    'planilha_nao_encontrada': "AVISO - Planilha não encontrada: {}",
    'onclick_executado': "   OK Onclick executado diretamente",
    'aguardando_mosaico': "   OK Aguardando resposta do Mosaico...",
    'force_click': "   REFRESH Tentando force click...",
    'force_click_ok': "   OK Force click funcionou",
    'buscando_anexos': "   REFRESH Buscando anexos...",
    'anexos_carregados': "   OK Página de Anexos carregada",
    'voltando_lista': "   VOLTAR Voltando para a lista...",
    'processamento_concluido': "OK PROCESSAMENTO CONCLUÍDO!",
    'iniciando_automacao': "BOT Iniciando automação ORCN - Download de anexos"
}

# Mensagens de erro
MENSAGENS_ERRO = {
    'planilha_nao_encontrada': "AVISO - Planilha não encontrada: {}",
    'erro_linha': "   ERRO ao ler linha {}: {}",
    'onclick_falhou': "   AVISO Onclick falhou: {}",
    'submit_falhou': "   AVISO Submit falhou",
    'force_click_falhou': "   ERRO Force click falhou: {}",
    'nenhum_pdf': "   AVISO Nenhum PDF foi baixado",
    'botao_nao_encontrado': "   AVISO Botão não encontrado: {}",
    'erro_botao': "   ERRO Erro ao processar botão {}: {}",
    'erro_pdf': "   ERRO Erro ao baixar PDF {} de {}: {}",
    'iframe_nao_encontrado': "AVISO iframe_element não encontrado, pulando...",
    'expect_navigation_falhou': "   AVISO expect_navigation falhou: {}",
    'timeout_preventivo': "TEMPO TIMEOUT PREVENTIVO ATIVADO!",
    'tempo_decorrido': "AVISO Tempo decorrido: {} minutos",
    'encerrando_timeout': "AVISO Encerrando aplicação para evitar timeout do Mosaico (30 min)",
    'executar_novamente': "AVISO Execute novamente o script para continuar processando"
}

# ================================
# FORMATAÇÃO E SEPARADORES
# ================================

# Caracteres de separação
SEPARADOR_LINHA = "="*60
SEPARADOR_MENOR = "="*50

# Formatação de arquivos
FORMATO_DATA_ARQUIVO = "%Y.%m.%d"
FORMATO_NOME_ARQUIVO = "[{tipo}][{data} - ID {id}] {nome} [req {num} de {ano}]{ext}"
FORMATO_NOME_SIMPLES = "[{categoria}] {nome}{ext}"

# Caracteres inválidos para nomes de arquivo
CARACTERES_INVALIDOS = r'[<>:"/\\|?*]'
SUBSTITUTO_CARACTERE = '_'

# ================================
# CONFIGURAÇÕES DE OCR/PDF
# ================================

# Extensões de arquivo suportadas
EXTENSOES_PDF = ['.pdf']
EXTENSOES_IMAGEM = ['.jpg', '.jpeg', '.png', '.tiff', '.bmp']

# Configurações de processamento
LIMITE_CARACTERES_ERRO = 50
LIMITE_CARACTERES_LOG = 80

# ================================
# VERSIONING
# ================================

# Padrão de versionamento
VERSAO_PADRAO = "v{}"  # será preenchido com data atual

# Comandos Git para versionamento
GIT_COMMANDS = {
    'tags': ["git", "tag", "--sort=-version:refname"],
    'describe': ["git", "describe", "--tags", "--abbrev=0"],
    'commit_hash': ["git", "rev-parse", "--short", "HEAD"]
}

# Timeout para comandos Git
GIT_TIMEOUT = 5

# ================================
# EXTENSÕES DE ARQUIVO
# ================================

# Extensões comuns
EXT_PDF = '.pdf'
EXT_JSON = '.json'
EXT_TEX = '.tex'
EXT_XLSX = '.xlsx'

# Padrões de glob
GLOB_PDF = '*.pdf'
GLOB_JSON = '*.json'

# ================================
# STATUS DE ANÁLISE
# ================================

# Status de conformidade
STATUS_CONFORME = "CONFORME"
STATUS_NAO_CONFORME = "NAO_CONFORME"
STATUS_INCONCLUSIVO = "INCONCLUSIVO"
STATUS_ERRO = "ERRO"
STATUS_PROCESSADO = "PROCESSADO"

# ================================
# ANÁLISE DE DOCUMENTOS
# ================================

# Palavras-chave essenciais para análise de manuais
# Estrutura: {"palavra_chave": {"normas": ["norma1", "norma2"]}}
PALAVRAS_CHAVE_MANUAL = {
    "declaração em conformidade com os Requisitos de Segurança Cibernética": {"normas": []},
    "produto não acabado": {"normas": []},
    "uso profissional": {"normas": []},
    "ipv6": {"normas": ["ato77", "ato7971"]},
    "wan": {"normas": ["ato77", "ato7971"]},
    "bluetooth": {"normas": []},
    "e1": {"normas": []},
    "e3": {"normas": []},
    "smart": {"normas": []},
    "tv": {"normas": []},
    "STM-1": {"normas": []},
    "STM-4": {"normas": []},
    "STM-16": {"normas": []},
    "STM-64": {"normas": []},
    "nfc": {"normas": []},
    "wi-fi": {"normas": []},
    "voz": {"normas": []},
    "esim": {"normas": []},
    "simcard": {"normas": []},
    "bateria": {"normas": []},
    "carregador": {"normas": []},
    "handheld": {"normas": []},
    "hand-held": {"normas": []},
    "hand held": {"normas": []},
    "smartphone": {"normas": []},
    "celular": {"normas": []},
    "aeronáutico": {"normas": []},
    "marítimo": {"normas": []},
    "dsl": {"normas": []},
    "adsl": {"normas": []},
    "vdsl": {"normas": []},
    "xdsl": {"normas": []},
    "gpon": {"normas": []},
    "epon": {"normas": []},
    "xpon": {"normas": []},
    "satélite": {"normas": []},
    "satellite": {"normas": []},
    "produto não acabado": {"normas": []},
}

# ================================
# VALORES PADRÃO E PLACEHOLDERS
# ================================

# Valores padrão
VALOR_NAO_DISPONIVEL = "N/A"
ENCODING_UTF8 = "utf-8"
ENCODING_LATIN1 = "latin-1"

# ================================
# NOTA: Funções utilitárias movidas para core/utils.py
# ================================