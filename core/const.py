# -*- coding: utf-8 -*-
"""
Constantes globais do projeto ORCN Utils.
Centraliza todos os valores estáticos e configurações do sistema.
"""

# ================================
# CAMINHOS E DIRETÓRIOS
# ================================

# Caminhos de execução
MIN_FILE_SIZE = 1000
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
TESSERACT_PATH = r"C:\Users\tbnobrega\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"

# Diretório debug específico do desenvolvedor
TBN_FILES_FOLDER = r"C:\Users\tbnobrega\OneDrive - ANATEL\Anatel\_ORCN"

# Nomes de diretórios e arquivos
CHROME_PROFILE_DIR = "meu_perfil_chrome"
EXCEL_FILENAME = 'ORCN.xlsx'
REQUERIMENTOS_DIR_INBOX = "req_inbox"
REQUERIMENTOS_DIR_OUTBOX = "req_outbox"
REQUERIMENTOS_DIR_REPORT = "req_report"
UTILS_DIR = "utils"
DOWNLOAD_LOG_FILENAME = "download_status.json"

# Caminhos completos para planilha e requerimentos
EXCEL_PATH = rf"{TBN_FILES_FOLDER}\ORCN.xlsx"
REQUERIMENTOS_PATH = rf"{TBN_FILES_FOLDER}\{REQUERIMENTOS_DIR_INBOX}"

# Arquivos JSON de configuração
JSON_FILES = {
    'regras': f"{UTILS_DIR}/regras.json",
    'equipamentos': f"{UTILS_DIR}/equipamentos.json",
    'requisitos': f"{UTILS_DIR}/requisitos.json",
    'normas': f"{UTILS_DIR}/normas.json",
    'ocds': f"{UTILS_DIR}/ocds.json"
}

# ================================
# CONFIGURAÇÕES WEB E SCRAPING
# ================================

# NAVEGAÇÃO NO REQUERIMENTO
BOTOES = {
    'anexos': "Anexos",
    'caracteristicas': "Características Técnicas",
    'infos_adicionais': "Informações Adicionais"
}

FRASES = {
    'radiacao_Restrita_ct': "Na instalação do produto, devem ser observadas as condições de uso conforme estabelecido no Regulamento sobre Equipamentos de Radiocomunicação de Radiação Restrita.",
    'analise_simplificada': "Este processo foi analisado conforme Portaria n° 2257, de 03 de março de 2022 (Análise Simplificada)."
}

# URLs do sistema
MOSAICO_BASE_URL = "https://sistemasnet.anatel.gov.br/mosaico/sch/worklist/"
CERTIFICA_URL = "https://appsnet/Certifica/"

# Texto que indica login concluído no Certifica e intervalo de monitoramento (segundos)
CERTIFICA_TEXTO_LOGIN_OK = "Caixa de Entrada Analista"
CERTIFICA_INTERVALO_MONITORAMENTO = 1

# Div a clicar por tipo de download escolhido ("3" - Todos - ainda sem especificação)
CERTIFICA_DIV_POR_TIPO = {
    "2": "wt43_OutSystemsUIWeb_wt2_block_wtContent_wtMainContent_wtCntAnalise",
    "1": "wt43_OutSystemsUIWeb_wt2_block_wtContent_wtMainContent_wtCntRetEstudo",
}

# Contador de registros da lista ("NNNN registros") e tempo máximo de espera (ms)
CERTIFICA_SELETOR_CONTADOR = ".Counter_Message:visible"
CERTIFICA_TIMEOUT_CONTADOR = 30000

# Div que contém a tabela de requerimentos e campos das colunas 2 a 9 (em ordem)
CERTIFICA_ID_DIV_LISTA = "wt43_OutSystemsUIWeb_wt2_block_wtContent_wtMainContent_wt96_wtCntLista"
CERTIFICA_INDICE_PRIMEIRA_COLUNA = 2  # índice (a partir de 0) da coluna "Nº do Requerimento"
CERTIFICA_CAMPOS_REQUERIMENTO = [
    "num_req", "cod_homologacao", "num_cct", "tipo_equipamento",
    "modelo_certificacao", "solicitante", "fabricante", "data",
]

# Página de análise do requerimento (AnaliseRequerimentosCCT): sufixo dos ids das abas
CERTIFICA_TIMEOUT_PAGINA = 3000000
CERTIFICA_ABA_FABRICANTE = "Fabricante"
CERTIFICA_ABA_SOLICITANTE = "solicitante"
CERTIFICA_ABA_PRODUTO = "produto"
CERTIFICA_ABA_ESPECIFICACOES = "EspecTecnica"
CERTIFICA_ABA_LABORATORIO = "Laboratorio"
CERTIFICA_ABA_CERTIFICADO = "Certificado"
# Rótulo que separa, na aba Solicitante, os dados do solicitante dos do OCD
CERTIFICA_ROTULO_INICIO_OCD = "INFORMAÇÕES DO OCD"
# Texto do cabeçalho de cada tabela, usado para identificá-la dentro da aba
CERTIFICA_CABECALHO_MODELOS = "Modelo Produto"
CERTIFICA_CABECALHO_FREQUENCIAS = "Faixa de Frequências"
# Colunas de cada registro da lista de laboratórios (a lista não tem cabeçalho no DOM)
CERTIFICA_CAMPOS_LABORATORIO = ["Nome", "Email", "Contato"]

# Anexos: tipos baixados (os do SCH + Registro de Ocorrências), como exibidos na aba Anexos
CERTIFICA_TIPO_ANEXO_REAPROVEITAMENTO = "Reaproveitamento de Número de Homologação SCH"
CERTIFICA_TIPOS_ANEXO_BAIXAR = [
    "Manual do Usuário",
    "Fotos Externas do Produto",
    "Fotos Internas do Produto",
    "RACT - Relatório de Avaliação da Conformidade Técnica",
    "CCT - Certificado de Conformidade Técnica",
    "Selo ANATEL",
    "Relatório de Ensaio",
    "Registro de Ocorrências",
    CERTIFICA_TIPO_ANEXO_REAPROVEITAMENTO,
]
CERTIFICA_ABA_ANEXOS = "Anexos"
CERTIFICA_TEXTO_ANEXO_DESATIVADO = "(DESATIVADO)"
CERTIFICA_TIMEOUT_DOWNLOAD = 60000

# Lista os anexos da aba: tipo (texto em negrito do bloco), dados da linha e id do link de download.
CERTIFICA_JS_LER_ANEXOS = """([sufixo, textoDesativado]) => {
    const aba = [...document.querySelectorAll('[id]')]
        .find(e => e.id.endsWith('wttab_' + sufixo + '_block_wtContent'));
    if (!aba) return null;
    const txt = (e) => e.innerText.replace(/\\s+/g, ' ').trim();
    // O aviso existe sempre no HTML e fica oculto por style inline; innerText não serve se a aba estiver oculta
    const avisoVisivel = (celula, texto) => [...celula.querySelectorAll('div')]
        .some(d => d.textContent.includes(texto) && d.style.display !== 'none');
    const anexos = [];
    aba.querySelectorAll('table[id$="wtTableDocumentos"]').forEach(tabela => {
        const bloco = tabela.closest('.ThemeGrid_Width9').previousElementSibling;
        const tipo = txt(bloco.querySelector('span'));
        tabela.querySelectorAll('tbody tr').forEach(tr => {
            const link = tr.querySelector('a[title="Download"]');
            if (!link) return;
            const c = tr.children;
            const arquivo = txt(c[0].firstElementChild);
            anexos.push({
                tipo, arquivo, desativado: avisoVisivel(c[0], textoDesativado),
                data_hora: txt(c[1]), descricao: txt(c[2]), link_id: link.id
            });
        });
    });
    return anexos;
}"""

# Lê uma aba: pares rótulo->valor (<label> + texto solto) e tabelas (lista de linhas de células)
CERTIFICA_JS_LER_ABA = """(sufixo) => {
    const aba = [...document.querySelectorAll('[id]')]
        .find(e => e.id.endsWith('wttab_' + sufixo + '_block_wtContent'));
    if (!aba) return null;
    const limpo = (el) => {
        const c = el.cloneNode(true);
        c.querySelectorAll('script, style').forEach(s => s.remove());
        return c.textContent.replace(/\\s+/g, ' ').trim();
    };
    const pares = [];
    aba.querySelectorAll('label').forEach(l => {
        const rotulo = limpo(l);
        const valor = limpo(l.parentElement).replace(rotulo, '').trim();
        pares.push([rotulo, valor]);
    });
    const tabelas = [...aba.querySelectorAll('table')].map(t =>
        [...t.querySelectorAll('tr')].map(r => [...r.children].map(limpo)));
    const registros = [...aba.querySelectorAll('.ListRecords > div')]
        .map(r => [...r.children].map(limpo));
    return {pares, tabelas, registros};
}"""

# Seletores CSS
CSS_SELECTORS = {
    'menu_todos': "#menuForm\\:todos",
    'menu_emAnalise': "#menuForm\\:emAnalise",
    'menu_retornoParaEstudo': "#menuForm\\:j_idt41",
    'tabela_dados': "css=#form\\:tarefasTable_data tr",
    'tabela_dados_em_analise': "css=#form\\:datatableForm\\:tarefasTable_data tr",
    'iframe_detalhe': "#__frameDetalhe",
    'tabela_analise': "table.analiseTable",
    'link_pdf': "a[href*='.pdf'], a[href*='download']",
    'paginator_options': "select.ui-paginator-rpp-options",
    'blockui': ".ui-blockui",
    'salvarFraseRR': "#formAnalise\\:j_idt666"
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
TIMEOUT_PRIMEFACES_AJAX = 15000
TIMEOUT_FORCE_CLICK = 2000
TIMEOUT_LOAD_STATE = 10000
TIMEOUT_BLOCKUI = 15000
TIMEOUT_MENU_CLICK = 3600000

# Timeouts em segundos para controle de sessão/MFA
TIMEOUT_SESSAO_MFA = 30 * 60  # 30 minutos para solicitar re-autenticação MFA

# Configurações de retry
MAX_TENTATIVAS_BOTAO = 5  # Máximo de tentativas por botão ao buscar PDFs
MAX_TENTATIVAS_DOWNLOAD = 5  # Máximo de tentativas por arquivo individual

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
STATUS_EM_ANALISE = ['Em Análise']#, 'Em Análise - RE']
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
    botoes = ['Certificado de Conformidade Técnica', 'Relatório de Avaliação da Conformidade - RACT', 'Manual do Produto', 'Relatório de Ensaio', 'Fotos do produto', 'Selo ANATEL', 'Fotos internas']
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
    'pgd': 'P',
    'sair': 'S'
}

DESCRICOES_MENU = {
    'D': "Baixar documentos (SCH ANATEL)",
    'A': "Analisar requerimento(s) (Análise automatizada)",
    'P': "Relatório para PGD (Desempenho)",
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
# Estrutura: {"palavra_chave": {"normas": ["norma1", "norma2"], "efeito": "aplica|desobriga", "ignorar_espacos": opcional}}
# ignorar_espacos=True: a busca desconsidera espacos (ex.: "20 mW" casa com "20mW")
PALAVRAS_CHAVE_MANUAL = {
    #"declaração em conformidade com os Requisitos de Segurança Cibernética": {"normas": []},
    "e.i.r.p.": {"normas": [], "efeito": "aplica"},
    "vinculada": {"normas": [], "efeito": "aplica"},
    "vinculado": {"normas": [], "efeito": "aplica"},
    "módulo de RF": {"normas": [], "efeito": "aplica"},
    "produto não acabado": {"normas": [], "efeito": "aplica"},
    "uso profissional": {"normas": [], "efeito": "aplica"},
    "ipv6": {"normas": ["ato7971"], "efeito": "aplica"},
    "wan": {"normas": ["ato77"], "efeito": "aplica"},
    "cpe": {"normas": ["ato2436"], "efeito": "aplica"},
    "customer-premises equipment": {"normas": ["ato2436"], "efeito": "aplica"},
    "customer-provided equipment": {"normas": ["ato2436"], "efeito": "aplica"},
    "reaproveitar": {"normas": [], "efeito": "aplica"},
    "reaproveitando": {"normas": [], "efeito": "aplica"},
    "reutilizar": {"normas": [], "efeito": "aplica"},
    "reutilizando": {"normas": [], "efeito": "aplica"},
    #"bluetooth": {"normas": []},
    #"e1": {"normas": []},
    #"e3": {"normas": []},
    #"smart": {"normas": []},
    #"tv": {"normas": []},
    #"STM-1": {"normas": []},
    #"STM-4": {"normas": []},
    #"STM-16": {"normas": []},
    #"STM-64": {"normas": []},
    #"nfc": {"normas": []},
    "wi-fi": {"normas": ["ato77"], "efeito": "aplica"},
    #"voz": {"normas": []},
    #"esim": {"normas": []},
    #"simcard": {"normas": []},
    #"bateria": {"normas": []},
    #"carregador": {"normas": []},
    "handheld": {"normas": [], "efeito": "aplica"},
    "hand-held": {"normas": [], "efeito": "aplica"},
    "hand held": {"normas": [], "efeito": "aplica"},
    "smartphone": {"normas": [], "efeito": "aplica"},
    "celular": {"normas": [], "efeito": "aplica"},
    #"aeronáutico": {"normas": []},
    #"marítimo": {"normas": []},
    #"dsl": {"normas": []},
    #"adsl": {"normas": []},
    #"vdsl": {"normas": []},
    #"xdsl": {"normas": []},
    #"gpon": {"normas": []},
    #"epon": {"normas": []},
    #"xpon": {"normas": []},
    #"satélite": {"normas": []},
    #"satellite": {"normas": []} 
    "Ensaio de SAR não aplicável: o equipamento não é terminal portátil": {"normas": ["ato17865"], "efeito": "desobriga", "ignorar_espacos": True},
    "Ensaio de SAR não aplicável: o equipamento possui potência média emitida em um tempo médio de 6 (seis) minutos igual ou inferior a 20 mW e o pico de potência emitida é menor que 20 W": {"normas": ["ato17865"], "efeito": "desobriga", "ignorar_espacos": True},
    "Ensaio de SAR não aplicável: equipamento utilizado a mais de 20 cm do corpo do usuário": {"normas": ["ato17865"], "efeito": "desobriga", "ignorar_espacos": True},
    "Ensaio de SAR não aplicável: O equipamento opera com frequência inferior a 300 MHz ou superior a 6 GHz": {"normas": ["ato17865"], "efeito": "desobriga", "ignorar_espacos": True},
    "Ensaio de SAR não aplicável: Produto não acabado, de uso interno, cuja integração em outros equipamentos pode requerer nova avaliação": {"normas": ["ato17865"], "efeito": "desobriga", "ignorar_espacos": True}
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