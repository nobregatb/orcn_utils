# -*- coding: utf-8 -*-
"""
Validação de citações de normativos seguidas por referência de data de publicação.
Verifica se cada normativo citado está seguido pela referência à sua data de publicação
conforme determinado no Ato nº 4083, itens 6.6.6.2 V e 6.6.8.1 VII.
"""

import re
import unicodedata
from typing import Dict, List, Set, Tuple, Optional
from pathlib import Path
import json
from core.const import JSON_FILES
from core.log_print import log_info, log_erro


# Padrões para identificação de normativo
PADRAO_NORMATIVO = r'(Ato|RESOLUÇÃO|Resolução)\s+(?:nº|N°|n\.|\(nº\))?\s*(\d+)'

# Padrões para data após normativo (com lookahead para validar que há data)
PADRAO_NORMATIVO_COM_DATA = r'(Ato|RESOLUÇÃO|Resolução)\s+(?:nº|N°|n\.|\(nº\))?\s*(\d+)(?=\s*(?:/|de)\s*\d)'


def _normalizar_espacos(texto: str) -> str:
    """Remove múltiplos espaços, mantém estrutura."""
    return re.sub(r'\s+', ' ', texto).strip()


def _extrair_data_do_nome(nome_normativo: str) -> str:
    """
    Extrai a parte de data do nome do normativo em normas.json.
    
    Exemplos de entrada:
    - "Ato nº 14448, de 04 de dezembro de 2017" → ", de 04 de dezembro de 2017"
    - "Ato nº 10002, de 16 de novembro de 2021" → ", de 16 de novembro de 2021"
    - "Resolução nº 123, de 2020" → ", de 2020"
    
    Args:
        nome_normativo: Campo "nome" do normativo no normas.json
        
    Returns:
        A parte da data (ex: ", de 04 de dezembro de 2017" ou "/2017")
    """
    # Remove espaços extras
    nome = _normalizar_espacos(nome_normativo)
    
    # Tenta encontrar o padrão: "número de data"
    # Padrão mais específico: ", de DD de mês de AAAA" ou ", de DD/MM/AAAA" ou ", de AAAA"
    match = re.search(
        r',?\s*(de|/)\s*(?:\d{1,2}\s+de\s+\w+\s+de\s+)?\d{4}',
        nome,
        re.IGNORECASE
    )
    
    if match:
        return nome[match.start():]
    
    return ""


def _normalizar_para_comparacao(texto: str) -> str:
    """
    Normaliza texto removendo acentos, espaços extras e convertendo para minúsculas
    para comparação de datas flexível.
    """
    # Remove acentos
    nfd = unicodedata.normalize('NFD', texto)
    sem_acentos = ''.join(char for char in nfd if unicodedata.category(char) != 'Mn')
    # Remove espaços e converte para minúsculas
    return re.sub(r'\s+', '', sem_acentos.lower())


def _comparar_datas_flexivel(data_citacao: str, data_normativo: str, aceitar_variacoes: bool = True) -> bool:
    """
    Compara duas datas de forma flexível, aceitando variações de formatação.
    
    Args:
        data_citacao: Data extraída da citação (ex: "04 de dezembro de 2017" ou "04/12/2017" ou "2017")
        data_normativo: Data extraída do normas.json (ex: "04 de dezembro de 2017")
        aceitar_variacoes: Se True, aceita variações como "04" vs "4" e "fevereiro 2017" vs "fevereiro de 2017"
        
    Returns:
        True se as datas correspondem, False caso contrário
    """
    # Normalizar para comparação
    citacao_norm = _normalizar_para_comparacao(data_citacao)
    normativo_norm = _normalizar_para_comparacao(data_normativo)
    
    # Comparação exata (após normalização)
    if citacao_norm == normativo_norm:
        return True
    
    # Se aceitamos variações, remover zeros à esquerda dos dias
    if aceitar_variacoes:
        # Substituir "0d" por "d" (remove zero à esquerda de dias)
        citacao_sem_zero = re.sub(r'0(\d)', r'\1', citacao_norm)
        normativo_sem_zero = re.sub(r'0(\d)', r'\1', normativo_norm)
        
        if citacao_sem_zero == normativo_sem_zero:
            return True
        
        # Remover "de" antes de anos para aceitar "fevereiro 2018" e "fevereiro de 2018"
        # Exemplo: "19defevereiro2018" vs "19defevereirode2018"
        citacao_sem_de = re.sub(r'de(\d{4})', r'\1', citacao_sem_zero)
        normativo_sem_de = re.sub(r'de(\d{4})', r'\1', normativo_sem_zero)
        
        if citacao_sem_de == normativo_sem_de:
            return True
        
        # Também comparar apenas o ano se a citação tiver apenas o ano
        # Extrair ano de ambas
        ano_citacao = re.search(r'(\d{4})', citacao_norm)
        ano_normativo = re.search(r'(\d{4})', normativo_norm)
        
        if ano_citacao and ano_normativo:
            if ano_citacao.group(1) == ano_normativo.group(1):
                # Se a citação contém apenas o ano, é válida
                if re.match(r'^\d{4}$', citacao_norm) or re.match(r'^/?\d{4}$', citacao_norm):
                    return True
    
    return False


def _extrair_normativos_do_texto(texto: str) -> List[Tuple[str, str, str, int]]:
    """
    Extrai todas as citações de normativos do texto com suas posições.
    
    Returns:
        Lista de tuplas (tipo, número, texto_completo, posição_inicio)
        Ex: [('Ato', '14448', 'Ato nº 14448', 123), ...]
    """
    normativos = []
    
    # Procurar por todos os normativos no texto
    for match in re.finditer(PADRAO_NORMATIVO, texto, re.IGNORECASE):
        tipo = match.group(1)
        numero = match.group(2)
        texto_completo = match.group(0)
        posicao = match.start()
        
        normativos.append((tipo, numero, texto_completo, posicao))
    
    return normativos


def _verificar_data_apos_normativo(texto: str, posicao_normativo: int, numero_normativo: str, texto_normativo: str = None) -> bool:
    """
    Verifica se há uma referência de data imediatamente após o normativo na posição indicada.
    
    Args:
        texto: Texto completo onde procurar
        posicao_normativo: Posição inicial do normativo no texto
        numero_normativo: Número do normativo (ex: "14448")
        texto_normativo: Texto do normativo (ex: "Ato nº 14448"), usado para encontrar o ponto após ele
        
    Returns:
        True se há referência de data válida após o normativo
    """
    # Se não temos o texto do normativo, não podemos determinar exatamente onde ele termina
    # Neste caso, procuramos a partir da posição_normativo
    
    if texto_normativo:
        # Encontrar o fim do texto do normativo
        posicao_fim_normativo = posicao_normativo + len(texto_normativo)
    else:
        # Estimar o fim do normativo (após o número)
        posicao_fim_normativo = posicao_normativo + 20  # estimativa
    
    # Procura por referência de data nos próximos 300 caracteres após o normativo
    # Padrões válidos de data após normativo:
    # /2017
    # de 2017
    # , de 2017
    # , de 04 de dezembro de 2017
    # , de 04/12/2017
    # , de 04 de dezembro 2017  (sem "de" antes do ano)
    # , de 04/12/2017
    
    texto_apos = texto[posicao_fim_normativo:posicao_fim_normativo + 300]
    
    # Procurar por padrão de data
    # Precisa de um separador (espaço, vírgula, etc) seguido por data ou barra seguida de ano
    # Padrões aceitos:
    # , de 2021
    # de janeiro de 2022
    # , de 04 de dezembro de 2017
    # , de 04 de dezembro 2017  (sem "de" antes do ano)
    # , de 04/12/2017
    # / 2017
    # Tornando o "de" antes do ano OPCIONAL
    padrao_data = r'^[\s,]*(?:de\s+)?(?:\d{1,2}\s+de\s+)?\w+\s+(?:de\s+)?\d{4}|^[\s,]*(?:de|/)?\s*\d{4}'
    
    if re.search(padrao_data, texto_apos, re.IGNORECASE):
        return True
    
    return False


def _carregar_normas() -> Dict[str, Dict]:
    """
    Carrega o arquivo normas.json e retorna um dicionário indexado por número do ato.
    
    Returns:
        Dict[numero -> informações do ato]
        Ex: {'14448': {'nome': 'Ato nº 14448, de 04 de dezembro de 2017', ...}, ...}
    """
    normas_por_numero = {}
    
    try:
        caminho = Path(JSON_FILES["normas"])
        with open(caminho, 'r', encoding='utf-8') as f:
            dados = json.load(f)
        
        normas_lista = dados if isinstance(dados, list) else dados.get('normas', [])
        
        for norma in normas_lista:
            if isinstance(norma, dict):
                # Extrair número do ID (ex: "ato14448" -> "14448")
                norma_id = norma.get('id', '')
                match_num = re.search(r'(\d+)$', norma_id)
                if match_num:
                    numero = match_num.group(1)
                    normas_por_numero[numero] = norma
    
    except Exception as e:
        log_erro(f"Erro ao carregar normas.json: {e}")
    
    return normas_por_numero


def validar_citacoes_normativos(texto: str, aceitar_variacoes: bool = True) -> Tuple[List[str], List[Tuple[str, str]]]:
    """
    Valida se todas as citações de normativos no texto estão seguidas por referência de data.
    
    Regra: Cada normativo deve ser seguido pela referência à sua data de publicação.
    Se há múltiplas citações do mesmo normativo, basta que uma tenha a data adequada.
    
    IMPORTANTE: Apenas normativos que estão EFETIVAMENTE CITADOS no texto são validados.
    Normativos não mencionados não geram exigências.
    
    Args:
        texto: Texto do documento a validar (RACT ou CCT)
        aceitar_variacoes: Se True, aceita variações de formatação de data (04 vs 4)
        
    Returns:
        Tupla (lista_exigências, lista_normativo_sem_data)
        - lista_exigências: Lista de textos de exigência a serem criadas
        - lista_normativo_sem_data: Lista de tuplas (numero, nome_normativo) dos que falharam
    """
    if not texto or not isinstance(texto, str):
        return [], []
    
    # Carregar normas
    normas_por_numero = _carregar_normas()
    if not normas_por_numero:
        return [], []
    
    # Extrair todos os normativos do texto
    normativos_encontrados = _extrair_normativos_do_texto(texto)
    
    # Se não encontrou nenhum normativo no texto, retornar vazio
    if not normativos_encontrados:
        return [], []
    
    # Rastrear quais normativos já passaram na validação (podem ter múltiplas citações)
    normativos_validados = set()
    normativos_com_falha = set()
    
    for tipo, numero, texto_completo, posicao in normativos_encontrados:
        # Se já validamos esse normativo (passou ou falhou), pular
        if numero in normativos_validados or numero in normativos_com_falha:
            continue
        
        # Verificar se há data após este normativo
        if _verificar_data_apos_normativo(texto, posicao, numero, texto_completo):
            # Ter um referência de data é suficiente para aprovar este normativo
            normativos_validados.add(numero)
            continue
        
        # Se não passou na validação, registrar como falha
        # MAS APENAS SE O NORMATIVO ESTÁ NO ARQUIVO normas.json
        # Isso evita criar exigências para normativos que não deveriam ser validados
        if numero in normas_por_numero:
            normativos_com_falha.add(numero)
    
    # Construir lista de exigências e detalhes apenas para normativos que FALHARAM
    exigencias = []
    detalhes = []
    
    for numero in sorted(normativos_com_falha):
        norma = normas_por_numero[numero]
        nome_normativo = norma.get('nome', f'Ato nº {numero}')
        norma_id = norma.get('id', f'normativo{numero}')  # Usar ID do arquivo normas.json
        # Armazenar (id, numero, nome_normativo) para uso posterior
        detalhes.append((norma_id, numero, nome_normativo))
        
        # Criar exigência para este normativo
        exigencia = (
            f"Adequar a citação ao {nome_normativo} neste documento. "
            "Conforme determinado por meio do Ato nº 4083, de 31 de julho de 2020, "
            "nos itens 6.6.6.2 V e 6.6.8.1 VII, as referências aos atos normativos "
            "devem conter título, número e ano de emissão de cada normativo."
        )
        exigencias.append(exigencia)
    
    return exigencias, detalhes


def consolidar_exigencias_normativos(lista_exigencias: List[str], detalhes: Optional[List[Tuple]] = None) -> Optional[str]:
    """
    Consolida múltiplas exigências de normativos em uma única exigência.
    Remove duplicatas de IDs de atos/resoluções.
    
    Args:
        lista_exigencias: Lista de exigências individuais de normativos
        detalhes: Lista de tuplas dos normativos falhados.
                 Formato esperado: [(id, numero, nome), ...] ou [(numero, nome), ...]
        
    Returns:
        Exigência consolidada ou None se a lista estiver vazia
    """
    if not lista_exigencias:
        return None
    
    # Se temos detalhes, usá-los diretamente (mais confiável)
    if detalhes and isinstance(detalhes, list) and len(detalhes) > 0:
        # Suportar ambos os formatos: (id, numero, nome) ou (numero, nome)
        ids_unicos = []
        for detalhe in detalhes:
            if isinstance(detalhe, tuple):
                if len(detalhe) == 3:
                    # Novo formato: (id, numero, nome)
                    norma_id = detalhe[0]
                elif len(detalhe) == 2:
                    # Formato antigo: (numero, nome)
                    norma_id = detalhe[0]
                else:
                    continue
                
                if norma_id and norma_id not in ids_unicos:
                    ids_unicos.append(norma_id)
        
        if ids_unicos:
            ids_str = ', '.join(ids_unicos)
        else:
            ids_str = None
    else:
        ids_str = None
    
    # Fallback: extrair IDs/números das exigências (menos confiável, mas mantém compatibilidade)
    if not ids_str:
        ids_atos = []
        
        for exigencia in lista_exigencias:
            # Procurar por padrão "(XXX)" no final da exigência
            match_parenteses = re.search(r'\(([^)]+)\)$', exigencia)
            if match_parenteses:
                # Encontrou parênteses no final, extrair IDs/números de lá
                conteudo_parenteses = match_parenteses.group(1)
                # Pode ser "resolucao772, resolucao773" ou "14448, 772, 773"
                partes = [p.strip() for p in conteudo_parenteses.split(',')]
                for parte in partes:
                    if parte and parte != '4083':  # Excluir o número da regra
                        ids_atos.append(parte)
            
            # Também procurar por padrão "resolucaoXXX" ou "atoXXX" no texto
            matches = re.findall(r'(?:resolucao|ato)(\d+)', exigencia, re.IGNORECASE)
            for match in matches:
                if match != '4083':  # Excluir o número da regra
                    if f"resolucao{match}" not in ids_atos and f"ato{match}" not in ids_atos:
                        # Preferir usar o padrão encontrado completo
                        pass
        
        if ids_atos:
            ids_str = ', '.join(sorted(set(ids_atos)))
        else:
            return None
    
    exigencia_consolidada = (
        f"Adequar as citações aos documentos normativos nesse documento. "
        f"Conforme determinado por meio do Ato nº 4083, de 31 de julho de 2020, "
        f"nos itens 6.6.6.2 V e 6.6.8.1 VII, as referências aos atos normativos "
        f"devem conter título, número e ano de emissão de cada normativo. "
        f"({ids_str})"
    )
    
    return exigencia_consolidada


def validar_modulos_rf_atrelados(texto: str) -> Optional[str]:
    """
    Verifica se o texto contém as palavras 'atrelado', 'atrelada', 'vinculado' ou 'vinculada',
    indicando referência ou vínculo de módulos de RF já homologados.
    
    Se encontradas, retorna a exigência específica conforme Ofício 218/2022.
    
    Args:
        texto: Conteúdo do documento (CCT)
        
    Returns:
        String da exigência se houver ocorrência, None caso contrário
    """
    if not texto:
        return None
    
    # Normalizar texto para busca case-insensitive
    texto_normalizado = unicodedata.normalize('NFKD', texto.lower()).encode('ASCII', 'ignore').decode('ASCII')
    
    # Verificar presença de "atrelado", "atrelada", "vinculado" ou "vinculada"
    palavras_procuradas = ['atrelado', 'atrelada', 'vinculado', 'vinculada']
    encontrado = any(palavra in texto_normalizado for palavra in palavras_procuradas)
    
    if encontrado:
        exigencia = (
            "Ao referenciar, ou vincular, módulos de RF já homologados, observar as orientações "
            "(sobre frases específicas) passadas por meio do Ofício 218/2022/ORCN/SOR-ANATEL "
            "(SEI nº 8661772). No caso específico, o item 3.6.1. III."
        )
        return exigencia
    
    return None
