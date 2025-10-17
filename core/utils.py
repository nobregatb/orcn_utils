# -*- coding: utf-8 -*-
"""
Funções utilitárias centralizadas do projeto ORCN Utils.
Contém todas as funções auxiliares e utilitárias usadas em múltiplos módulos.
"""

import os
import sys
import re
import json
import subprocess
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

from core.const import (
    TBN_FILES_FOLDER, CHROME_PROFILE_DIR, REQUERIMENTOS_DIR_PREFIX,
    GIT_COMMANDS, GIT_TIMEOUT, VERSAO_PADRAO, MENSAGENS_STATUS, TIPOS_DOCUMENTOS
)
from core.log_print import log_info

# ================================
# FUNÇÕES DE FORMATAÇÃO
# ================================

def limpar_texto(texto, palavras=None, simbolos=None, remover_parenteses=True):
    """
    Remove palavras, símbolos e trechos entre parênteses de uma string.
    Ignora diferenças entre maiúsculas e minúsculas.
    """
    resultado = texto

    # 1️⃣ Remove conteúdo entre parênteses (opcional)
    if remover_parenteses:
        resultado = re.sub(r'\s*\([^)]*\)', '', resultado, flags=re.I)

    # 2️⃣ Remove palavras específicas (case-insensitive)
    if palavras:
        padrao_palavras = r'\b(?:' + '|'.join(map(re.escape, palavras)) + r')\b'
        resultado = re.sub(r'\s*' + padrao_palavras, '', resultado, flags=re.I)

    # 3️⃣ Remove símbolos específicos (case-insensitive, mas não afeta símbolos)
    if simbolos:
        padrao_simbolos = '[' + re.escape(''.join(simbolos)) + ']'
        resultado = re.sub(padrao_simbolos, '', resultado, flags=re.I)

    # 4️⃣ Limpa espaços duplicados e tira espaços extras
    resultado = re.sub(r'\s{2,}', ' ', resultado).strip()

    return resultado



def formatar_cnpj(cnpj_numeros: str) -> str:
    """
    Converte CNPJ de números para formato XX.XXX.XXX/XXXX-XX
    Args:
        cnpj_numeros (str): CNPJ apenas com números (ex: "12345678000123")
    Returns:
        str: CNPJ formatado (ex: "12.345.678/0001-23")
    """
    if not cnpj_numeros or len(cnpj_numeros) != 14:
        return cnpj_numeros
    
    return f"{cnpj_numeros[:2]}.{cnpj_numeros[2:5]}.{cnpj_numeros[5:8]}/{cnpj_numeros[8:12]}-{cnpj_numeros[12:]}"


def desformatar_cnpj(cnpj_formatado: str) -> str:
    """
    Remove formatação do CNPJ, deixando apenas números
    Args:
        cnpj_formatado (str): CNPJ formatado (ex: "12.345.678/0001-23")
    Returns:
        str: CNPJ apenas com números (ex: "12345678000123")
    """
    if not cnpj_formatado:
        return cnpj_formatado
    
    return ''.join(filter(str.isdigit, cnpj_formatado))


def latex_escape_path(caminho: str) -> str:
    """Escapa caracteres especiais do LaTeX dentro de um caminho de arquivo."""
    caminho = caminho.replace("\\", "/")  # usa / para evitar confusão
    # escapa caracteres especiais
    return re.sub(r'([_&#%{}$^~\\])', r'\\\1', caminho)


def escapar_latex(texto: str) -> str:
    """Escapa caracteres especiais do LaTeX."""
    if not isinstance(texto, str):
        return str(texto)
    
    # Dicionário de substituições para caracteres especiais do LaTeX
    substituicoes = {
        '\\': '\\textbackslash{}',
        '{': '\\{',
        '}': '\\}',
        '$': '\\$',
        '&': '\\&',
        '%': '\\%',
        '#': '\\#',
        '^': '\\textasciicircum{}',
        '_': '\\_',
        '~': '\\textasciitilde{}',
    }
    
    # Aplicar substituições
    for char, replacement in substituicoes.items():
        texto = texto.replace(char, replacement)
    
    return texto


# ================================
# FUNÇÕES DE TIPOS DE DOCUMENTO
# ================================

def obter_nome_tipo_documento(tipo_chave: str) -> str:
    """Obtém o nome completo de um tipo de documento pela chave."""
    return TIPOS_DOCUMENTOS.get(tipo_chave, {}).get('nome', 'Tipo desconhecido')

def obter_nome_curto_tipo_documento(tipo_chave: str) -> str:
    """Obtém o nome curto de um tipo de documento pela chave."""
    return TIPOS_DOCUMENTOS.get(tipo_chave, {}).get('nome_curto', 'N/A')

def obter_botao_pdf_tipo_documento(tipo_chave: str) -> str:
    """Obtém o nome do botão PDF para um tipo de documento."""
    return TIPOS_DOCUMENTOS.get(tipo_chave, {}).get('botao_pdf', 'Outros')

def obter_padroes_tipo_documento(tipo_chave: str) -> List[str]:
    """Obtém os padrões de identificação para um tipo de documento."""
    return TIPOS_DOCUMENTOS.get(tipo_chave, {}).get('padroes', [])

def listar_tipos_documento() -> List[str]:
    """Lista todas as chaves de tipos de documento disponíveis."""
    return list(TIPOS_DOCUMENTOS.keys())


# ================================
# FUNÇÕES DE NORMALIZAÇÃO
# ================================

def normalizar(s: Union[str, Any]) -> Union[str, Any]:
    """Normaliza string removendo acentos e convertendo para lowercase."""
    if isinstance(s, str):
        s = s.strip().lower()
        s = ''.join(
            c for c in unicodedata.normalize('NFD', s)
            if unicodedata.category(c) != 'Mn'
        )
    return s


def normalizar_dados(dados: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza todos os dados string em um dicionário."""
    for k, v in dados.items():
        if isinstance(v, list):
            dados[k] = [normalizar(item) if isinstance(item, str) else item for item in v]
        elif isinstance(v, str):
            dados[k] = normalizar(v)
    return dados


# ================================
# FUNÇÕES DE BUSCA EM JSON
# ================================

def buscar_valor(json_data: Union[List[Dict], Dict], key_busca: str, valor_busca: Any, key_retorno: str) -> Optional[Any]:
    """
    Busca em uma lista de dicionários (ou JSON similar)
    onde key_busca == valor_busca e retorna o valor de key_retorno.
    """
    if isinstance(json_data, list):
        for item in json_data:
            if isinstance(item, dict):
                if item.get(key_busca) == valor_busca:
                    return item.get(key_retorno)
    elif isinstance(json_data, dict):
        if json_data.get(key_busca) == valor_busca:
            return json_data.get(key_retorno)
    return None


# ================================
# FUNÇÕES DE VERSIONAMENTO
# ================================

def obter_versao_git() -> str:
    """Obtém a versão do script baseada em git tag ou commit hash."""
    try:
        # Tentar obter a tag mais recente (ordenada por versão)
        resultado = subprocess.run(
            GIT_COMMANDS['tags'],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT
        )
        
        if resultado.returncode == 0 and resultado.stdout.strip():
            # Pegar a primeira linha (tag mais recente)
            tags = resultado.stdout.strip().split('\n')
            if tags and tags[0]:
                return tags[0]
        
        # Fallback: tentar describe --tags
        resultado = subprocess.run(
            GIT_COMMANDS['describe'],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT
        )
        
        if resultado.returncode == 0 and resultado.stdout.strip():
            return resultado.stdout.strip()
        
        # Se não há tags, tentar obter o hash do commit
        resultado = subprocess.run(
            GIT_COMMANDS['commit_hash'],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT
        )
        
        if resultado.returncode == 0 and resultado.stdout.strip():
            return f"commit-{resultado.stdout.strip()}"
            
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        pass
    
    # Fallback para versão baseada em data
    return VERSAO_PADRAO.format(datetime.now().strftime('%Y.%m.%d'))


# ================================
# FUNÇÕES DE SISTEMA E PATHS
# ================================

def is_bundled() -> bool:
    """Verifica se o código está rodando como executável PyInstaller."""
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')


def get_files_folder() -> str:
    """Retorna o diretório base para arquivos baseado no modo de execução."""
    if is_bundled():
        folder = os.path.dirname(sys.executable)
        log_info(MENSAGENS_STATUS['modo_executavel'].format(folder))
        return folder
    else:
        log_info(MENSAGENS_STATUS['modo_script'].format(TBN_FILES_FOLDER))
        return TBN_FILES_FOLDER


def get_profile_dir() -> str:
    """Retorna o diretório do perfil Chrome baseado no modo de execução."""
    if is_bundled():
        files_folder = os.path.dirname(sys.executable)
        return os.path.join(files_folder, CHROME_PROFILE_DIR)
    else:
        return os.path.join(Path(__file__).parent.parent, CHROME_PROFILE_DIR)


def req_para_fullpath(req: str) -> str:
    """Converte número do requerimento (num/ano) para caminho completo da pasta"""
    num, ano = req.split("/")
    requerimento = rf"{REQUERIMENTOS_DIR_PREFIX}\{ano}.{num}"
    full_path = os.path.join(get_files_folder(), requerimento)
    return full_path


def fullpath_para_req(nome_diretorio: str) -> str:
    """
    Converte nome do diretório (formato YY.num ou _YY.num) para número do requerimento (num/ano)
    
    Args:
        nome_diretorio (str): Nome do diretório no formato "YY.12345" ou "_YY.12345"
    
    Returns:
        str: Requerimento no formato "12345/YYYY"
    
    Examples:
        >>> fullpath_para_req("25.12345")
        "12345/2025"
        >>> fullpath_para_req("_25.12345")
        "12345/2025"
        >>> fullpath_para_req("24.98765")
        "98765/2024"
    """
    # Remove underscore inicial se existir
    nome_limpo = nome_diretorio.lstrip('_')
    
    # Divide por ponto para separar ano e número
    partes = nome_limpo.split('.')
    
    if len(partes) != 2:
        raise ValueError(f"Formato inválido: {nome_diretorio}. Esperado: 'YY.numero' ou '_YY.numero'")
    
    ano_curto, numero = partes
    
    # Converte ano de 2 dígitos para 4 dígitos
    # Assume que anos 00-99 são 2000-2099
    ano_completo = f"20{ano_curto.zfill(2)}"
    
    return f"{numero}/{ano_completo}"


def criar_pasta_se_nao_existir(req: str) -> str:
    """Cria pasta do requerimento se não existir e retorna o caminho"""
    full_path = req_para_fullpath(req)
    if not os.path.exists(full_path):
        os.makedirs(full_path, exist_ok=True)
        log_info(f"📁 Pasta criada: {full_path}")
    return full_path


# ================================
# FUNÇÕES DE MANIPULAÇÃO DE ARQUIVOS
# ================================

def carregar_json(caminho: Union[str, Path], encoding: str = 'utf-8') -> Optional[Union[Dict, List]]:
    """
    Carrega dados de um arquivo JSON de forma segura.
    
    Args:
        caminho: Caminho para o arquivo JSON
        encoding: Codificação do arquivo (padrão: utf-8)
    
    Returns:
        Dados do JSON ou None em caso de erro
    """
    try:
        with open(caminho, 'r', encoding=encoding) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, Exception):
        return None


def salvar_json(dados: Union[Dict, List], caminho: Union[str, Path], encoding: str = 'utf-8', indent: int = 2) -> bool:
    """
    Salva dados em um arquivo JSON de forma segura.
    
    Args:
        dados: Dados para salvar
        caminho: Caminho para o arquivo JSON
        encoding: Codificação do arquivo (padrão: utf-8)
        indent: Indentação para formatação (padrão: 2)
    
    Returns:
        True se salvou com sucesso, False caso contrário
    """
    try:
        with open(caminho, 'w', encoding=encoding) as f:
            json.dump(dados, f, ensure_ascii=False, indent=indent)
        return True
    except Exception:
        return False


# ================================
# FUNÇÕES DE VALIDAÇÃO
# ================================

def validar_cnpj(cnpj: str) -> bool:
    """
    Valida se um CNPJ possui formato válido (apenas estrutura, não algoritmo).
    
    Args:
        cnpj: CNPJ para validar (formatado ou não)
    
    Returns:
        True se o formato é válido, False caso contrário
    """
    if not cnpj:
        return False
    
    # Remove formatação
    cnpj_numeros = desformatar_cnpj(cnpj)
    
    # Verifica se tem 14 dígitos
    return len(cnpj_numeros) == 14 and cnpj_numeros.isdigit()


def validar_caminho_arquivo(caminho: Union[str, Path]) -> bool:
    """
    Valida se um caminho de arquivo existe e é um arquivo válido.
    
    Args:
        caminho: Caminho para validar
    
    Returns:
        True se é um arquivo válido, False caso contrário
    """
    try:
        path_obj = Path(caminho)
        return path_obj.exists() and path_obj.is_file()
    except Exception:
        return False


def validar_caminho_diretorio(caminho: Union[str, Path]) -> bool:
    """
    Valida se um caminho de diretório existe e é um diretório válido.
    
    Args:
        caminho: Caminho para validar
    
    Returns:
        True se é um diretório válido, False caso contrário
    """
    try:
        path_obj = Path(caminho)
        return path_obj.exists() and path_obj.is_dir()
    except Exception:
        return False