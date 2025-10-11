"""
Analisador de Certificados de Conformidade Técnica (CCT)
Sistema de extração e validação de dados de arquivos PDF
"""
from pdf2image import convert_from_path
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Users\tbnobrega\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"

from datetime import datetime
import unicodedata
import re
import fitz
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pymupdf4llm
#from json_logic import jsonLogic

def buscar_valor(json_data, key_busca, valor_busca, key_retorno):
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


def normalizar(s):
    if isinstance(s, str):
        s = s.strip().lower()
        s = ''.join(
            c for c in unicodedata.normalize('NFD', s)
            if unicodedata.category(c) != 'Mn'
        )
    return s

def normalizar_dados(dados):
    for k, v in dados.items():
        if isinstance(v, list):
            dados[k] = [normalizar(x) for x in v]
        elif isinstance(v, str):
            dados[k] = normalizar(v)
    return dados

# Versão do aplicativo - obtida automaticamente via git tag
def get_version() -> str:
    """Obtém a versão do aplicativo via git tag"""
    try:
        version = subprocess.check_output(
            ['git', 'describe', '--tags', '--always'],
            stderr=subprocess.DEVNULL,
            cwd=Path(__file__).parent
        ).decode('utf-8').strip()
        return version
    except:
        return "v0.0.0-dev"

VERSION = get_version()

def log(message: str):
    """
    Função centralizada de logging que exibe no console e salva em arquivo
    
    Args:
        message: Mensagem para log
    """
    
    
    # Define o caminho do arquivo de log
    log_file_path = r"C:\Users\tbnobrega\Desktop\log.txt"
    
    # Salva em arquivo
    try:
       
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
                
        with open(log_file_path, 'a', encoding='utf-8') as f:
            f.write(log_entry)
    except Exception as e:
        print(f"[ERRO] Falha ao escrever no arquivo de log: {e}")

    # Sempre exibe no console
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    print(log_entry)


class CCTAnalyzer:
    """Classe principal para análise de certificados CCT"""
    
    def __init__(self, home_dir: Optional[str] = None):
        # self.base_dir = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
        # Alternativa: permite especificar diretório customizado
        # home_dir = Path(base_dir)
        path_executavel = Path(__file__).parent

        if home_dir:
            self.base_dir = Path(home_dir)  / "Requerimentos"
            # self.utils_dir = Path(home_dir) / "utils"
        else:
            self.base_dir = path_executavel
        
        self.utils_dir = path_executavel / "utils"        
        
        self.rules: Dict = {}
        self._setup_directories()
        self._load_configurations()
    
    def log(self, message: str):
        """Método de log da classe que usa a função global de log"""
        log(message)
    
    def _get_norma_info(self, norma: str) -> Optional[Dict]:
        """
        Busca informações de uma norma no arquivo normas.json
        
        Args:
            norma: Nome/código da norma
            
        Returns:
            Dicionário com dados da norma ou None se não encontrada
        """
        normas_file = self.utils_dir / "normas.json"
        
        try:
            if not normas_file.exists():
                return None
                
            with open(normas_file, 'r', encoding='utf-8') as f:
                normas_data = json.load(f)
            
            # Buscar norma pelo nome/código normalizado
            norma_normalizada = normalizar(norma)
            
            if isinstance(normas_data, list):
                for item in normas_data:
                    if isinstance(item, dict):
                        # Verificar se algum campo da norma corresponde
                        for key in ['nome', 'codigo', 'id']:
                            if key in item:
                                if normalizar(str(item[key])) == norma_normalizada:
                                    return item
            elif isinstance(normas_data, dict):
                # Se for dicionário, buscar diretamente pela chave
                return normas_data.get(norma)
            
            return None
            
        except Exception as e:
            self.log(f"[ERRO] Falha ao consultar normas.json: {e}")
            return None
    
    def _setup_directories(self):
        """Cria diretório utils se não existir"""
        self.utils_dir.mkdir(exist_ok=True)
        self.log(f"[INFO] Diretório utils: {self.utils_dir}")
    
    def _load_configurations(self):
        """Carrega configurações de regras"""
        # Verificar se arquivo ocds.json existe
        ocds_file = self.utils_dir / "ocds.json"
        if not ocds_file.exists():
            self.log(f"[AVISO] Arquivo {ocds_file} não encontrado.")
        else:
            # Contar OCDs disponíveis
            try:
                with open(ocds_file, 'r', encoding='utf-8') as f:
                    ocds_data = json.load(f)
                self.log(f"[INFO] {len(ocds_data)} OCDs disponíveis em ocds.json")
            except:
                self.log(f"[AVISO] Erro ao ler {ocds_file}")
        
        # Verificar se arquivo equipamentos.json existe
        equipamentos_file = self.utils_dir / "equipamentos.json"
        if not equipamentos_file.exists():
            self.log(f"[AVISO] Arquivo {equipamentos_file} não encontrado.")
        else:
            # Contar equipamentos disponíveis
            try:
                with open(equipamentos_file, 'r', encoding='utf-8') as f:
                    equipamentos_data = json.load(f)
                self.log(f"[INFO] {len(equipamentos_data)} equipamentos disponíveis em equipamentos.json")
            except:
                self.log(f"[AVISO] Erro ao ler {equipamentos_file}")
        
        # Verificar se arquivo requisitos.json existe
        requisitos_file = self.utils_dir / "requisitos.json"
        if not requisitos_file.exists():
            self.log(f"[AVISO] Arquivo {requisitos_file} não encontrado.")
        else:
            # Contar requisitos disponíveis
            try:
                with open(requisitos_file, 'r', encoding='utf-8') as f:
                    requisitos_data = json.load(f)
                self.log(f"[INFO] {len(requisitos_data)} requisitos disponíveis em requisitos.json")
            except:
                self.log(f"[AVISO] Erro ao ler {requisitos_file}")
        
        # Verificar se arquivo normas.json existe
        normas_file = self.utils_dir / "normas.json"
        if not normas_file.exists():
            self.log(f"[AVISO] Arquivo {normas_file} não encontrado.")
        else:
            # Contar normas disponíveis
            try:
                with open(normas_file, 'r', encoding='utf-8') as f:
                    normas_data = json.load(f)
                    normas_count = len(normas_data) if isinstance(normas_data, (list, dict)) else 0
                self.log(f"[INFO] {normas_count} normas disponíveis em normas.json")
            except:
                self.log(f"[AVISO] Erro ao ler {normas_file}")
        
    
    def find_cct_files(self, search_dir: str) -> List[Path]:
        """
        Encontra arquivos PDF de CCT no diretório especificado
        
        Args:
            search_dir: Nome do diretório ou '*' para busca recursiva
        
        Returns:
            Lista de caminhos para arquivos CCT encontrados
        """
        pattern = "[Certificado de Conformidade Técnica - CCT]"
        files = []
        
        if search_dir == "*":
            self.log(f"[INFO] Buscando CCTs em todos os subdiretórios de {self.base_dir}...")
            for pdf_file in self.base_dir.rglob("*.pdf"):
                if pattern in pdf_file.name:
                    files.append(pdf_file)
        else:
            target_dir = self.base_dir / search_dir
            if not target_dir.exists():
                self.log(f"[ERRO] Diretório não encontrado: {target_dir}")
                return []
            
            self.log(f"[INFO] Buscando CCTs em {target_dir}...")
            for pdf_file in target_dir.glob("*Certificado de Conformidade Técnica - CCT*.pdf"):
                files.append(pdf_file)
        
        return files
    
    def extract_pdf_content(self, pdf_path: Path) -> Optional[str]:
        """
        Extrai conteúdo de PDF usando pymupdf4llm
        
        Args:
            pdf_path: Caminho para arquivo PDF
        
        Returns:
            Conteúdo extraído como string ou None em caso de erro
        """
        try:
            self.log(f"[INFO] Extraindo conteúdo de: {pdf_path.name}")
            #content = pymupdf4llm.to_markdown(pdf_path)
            pdf = fitz.open(pdf_path)
            content = ""
            for pagina in pdf:
                content += pagina.get_text() + "\n"
            pdf.close()

            if content.strip() == "":
                self.log(f"[AVISO] PDF aparentemente vazio, tentando OCR: {pdf_path.name}")
                content = self.extract_pdf_content_from_ocr(pdf_path)
            return content
        except Exception as e:
            self.log(f"[ERRO] Falha ao extrair {pdf_path.name}: {e}")
            return None
    
    def extract_pdf_content_from_ocr(self, pdf_path: Path) -> Optional[str]:
        try:
            # Converte cada página do PDF em imagem
            paginas = convert_from_path(pdf_path)

            # Inicializa variável para armazenar o texto completo
            texto_completo = ""

            # Extrai texto de cada página via OCR
            for i, pagina in enumerate(paginas, start=1):
                texto_pagina = pytesseract.image_to_string(pagina, lang='por')  # use 'eng' para inglês
                texto_completo += f"\n--- Página {i} ---\n"
                texto_completo += texto_pagina
            return texto_completo
        
        except Exception as e:
            self.log(f"[ERRO] Falha ao extrair {pdf_path.name}: {e}")
            return None
    
    def extract_ocd_from_content(self, content: str) -> Optional[str]:
        """
        Identifica o OCD baseado no conteúdo do certificado
        Retorna nomes padronizados em lowercase para corresponder às chaves dos padrões
        """
        ocd_signatures = {
            "ncc": "Associação NCC Certificações do Brasil",
            "brics": "BRICS Certificações de Sistemas de Gestões e Produtos",
            "abcp": "ABCP Certificadora de Produtos LTDA",
            "acert": "ACERT ORGANISMO DE CERTIFICACAO DE PRODUTOS EM SISTEMAS",
            "sgs": "SGS do Brasil Ltda.",
            "bracert": "BraCert – BRASIL CERTIFICAÇÕES LTDA",
            "ccpe": "CCPE – CENTRO DE CERTIFICAÇÃO",
            "eldorado": "OCD-Eldorado",
            "icc": "organismo ICC no uso das atribuições que lhe confere o Ato de Designação N° 696",
            "moderna": "Moderna Tecnologia LTDA",
            "master": "Master Associação de Avaliação de Conformidade",
            "ocp-teli": "OCP-TELI",
            "tuv": "Certificado: TÜV",
            "ul": "UL do Brasil Ltda, Organismo de Certificação Designado",
            "qc": "QC Certificações",
            "versys": "Associação Versys de Tecnologia",
            "cpqd": "CPQD",
            "associação lmp certificações": "Associação LMP Certificações"
        }
        
        for ocd_key, signature in ocd_signatures.items():
            if re.search(re.escape(signature), content, re.IGNORECASE):
                return ocd_key
        
        return None
         
    
    def get_ocd_name(self, cnpj: Optional[str]) -> str:
        """Obtém nome do OCD a partir do CNPJ consultando ./utils/ocds.json"""
        if not cnpj:
            return "[ERRO] CNPJ não informado"
        
        # Consulta o arquivo ocds.json
        ocds_file = self.utils_dir / "ocds.json"
        
        try:
            if ocds_file.exists():
                with open(ocds_file, 'r', encoding='utf-8') as f:
                    ocds_data = json.load(f)
                
                # Busca pelo CNPJ
                ocd_info = buscar_valor(ocds_data, 'cnpj', cnpj, 'nome')
                if ocd_info:
                    return ocd_info

            return f"[ERRO] OCD não cadastrado (CNPJ: {cnpj})"
            
        except Exception as e:
            self.log(f"[ERRO] Falha ao consultar ocds.json: {e}")
            return f"[ERRO]OCD não cadastrado (CNPJ: {cnpj})"
    
    def extract_tipo_equipamento(self, content: str) -> List[Dict]:
        """
        Extrai tipos de equipamento consultando equipamentos.json e buscando matches no conteúdo
        
        Args:
            content: Conteúdo do certificado
            ocd_name: Nome do OCD (não usado na nova implementação)
            
        Returns:
            Lista de dicionários com equipamentos encontrados
        """
        equipamentos_encontrados = []
        
        # Consulta o arquivo equipamentos.json
        equipamentos_file = self.utils_dir / "equipamentos.json"
        
        try:
            if not equipamentos_file.exists():
                self.log(f"[AVISO] Arquivo {equipamentos_file} não encontrado")
                return []
                
            with open(equipamentos_file, 'r', encoding='utf-8') as f:
                equipamentos_data = json.load(f)
            
            # Normaliza o conteúdo do certificado para comparação
            content_normalizado = normalizar(content)
            
            # Percorre todos os equipamentos do JSON
            for equipamento in equipamentos_data:
                if isinstance(equipamento, dict) and 'nome' in equipamento:
                    nome_equipamento = normalizar(equipamento['nome']) #TEOGENES INCLUI NORMALIZACAO
                    nome_normalizado = normalizar(nome_equipamento)
                    
                    # Verifica se o nome do equipamento está presente no conteúdo
                    if nome_normalizado in content_normalizado:
                        # Verifica se já foi adicionado (evita duplicatas)
                        ja_existe = any(
                            eq.get('nome') == nome_equipamento 
                            for eq in equipamentos_encontrados
                        )
                        
                        if not ja_existe:
                            equipamentos_encontrados.append(equipamento)
            
            return equipamentos_encontrados
            
        except Exception as e:
            self.log(f"[ERRO] Falha ao consultar equipamentos.json: {e}")
            return []
            
    def _get_ocd_patterns(self) -> Dict[str, Dict]:
        """
        Define os padrões de extração para cada OCD
        
        Para adicionar um novo OCD:
        1. Adicione a assinatura em extract_ocd_from_content()
        2. Adicione a configuração aqui com:
           - start_pattern: regex para início da seção de normas
           - end_pattern: regex para fim da seção de normas  
           - processing_type: "custom" para lógica especial ou "regex_patterns" para padrão
           - custom_patterns: (opcional) lista de padrões especiais para processing_type="custom"
        
        Returns:
            Dicionário com configurações por OCD
        """
        return {
            "moderna": {
                "start_pattern": r'acima\s+discriminado\(s\)\s+está\(ão\)\s+em\s+conformidade\s+com\s+os\s+documentos\s+normativos\s+indicados\.',
                "end_pattern": r'Diretor\s+de\s+Tecnologia',
                "processing_type": "custom",  # ou "regex_patterns"
                "custom_patterns": ['ATO', 'RESOLUÇÃO']
            },
            "ncc": {
                "start_pattern": r'Regulation\s+Applicable',
                "end_pattern": r'Conforme\s+os\s+termos\s+do\s+Ato\s+de\s+Designação\s+nº\s+16\.955',
                "processing_type": "custom",  # ou "regex_patterns"
                "custom_patterns": ['ATO', 'RESOLUÇÃO']
            },
            "brics": {
                "start_pattern": r'Standards?\s+Applied',
                "end_pattern": r'BRICS\s+Certificações',
                "processing_type": "regex_patterns"
            },
            "abcp": {
                "start_pattern": r'Normas?\s+Verificadas?',
                "end_pattern": r'ABCP\s+Certificadora',
                "processing_type": "regex_patterns"
            },
            "acert": {
                "start_pattern": r'Standards?\s+(?:Applied|Verified)',
                "end_pattern": r'ACERT\s+ORGANISMO',
                "processing_type": "regex_patterns"
            },
            "sgs": {
                "start_pattern": r'Technical\s+Standards?',
                "end_pattern": r'SGS\s+do\s+Brasil',
                "processing_type": "regex_patterns"
            },
            "bracert": {
                "start_pattern": r'Normas?\s+Aplicadas?',
                "end_pattern": r'BraCert.*BRASIL\s+CERTIFICAÇÕES',
                "processing_type": "regex_patterns"
            },
            "ccpe": {
                "start_pattern": r'Technical\s+Standards?',
                "end_pattern": r'CCPE.*CENTRO\s+DE\s+CERTIFICAÇÃO',
                "processing_type": "regex_patterns"
            },
            "eldorado": {
                "start_pattern": r'NORMAS\s+APLICÁVEIS/\s+APPLICABLE\s+STANDARDS',
                "end_pattern": r'O\s+OCD-Eldorado\s+atribui\s+a\s+certificação\s-aos\s+produtos\s+mencionados\s+acima',
                "processing_type": "custom",  # ou "regex_patterns"
                "custom_patterns": ['ATO', 'RESOLUÇÃO']
            },
            "icc": {
                "start_pattern": r'Regulation\s+Applicable',
                "end_pattern": r'O\s+organismo\s+ICC\s+no\s+uso\s+das\s+atribuições\s+que\s+lhe\s+confere\s+o\s+Ato\s+de\s+Designação',
                "processing_type": "custom",  # ou "regex_patterns"
                "custom_patterns": ['ATO', 'RESOLUÇÃO']
            },
            "master": {
                "start_pattern": r'Reference\s+Standards',
                "end_pattern": r'LABORATÓRIOS\s+DE\s+ENSAIOS',
                "processing_type": "custom",  # ou "regex_patterns"
                "custom_patterns": ['ATO', 'RESOLUÇÃO']
            },
            "ocp-teli": {
                "start_pattern": r'Regulamentos\s+Aplicáveis:',
                "end_pattern": r'OCD\s+designado\s+pelo\s+Ato\s+nº\s+19\.434',
                "processing_type": "custom",  # ou "regex_patterns"
                "custom_patterns": ['ATO', 'RESOLUÇÃO']
            },
            "tuv": {
                "start_pattern": r'Standards?\s+Applied',
                "end_pattern": r'TÜV',
                "processing_type": "regex_patterns"
            },
            "ul": {
                "start_pattern": r'normative\s+documents',
                "end_pattern": r'e\s+atesta\s+que\s+o\s+produto\s+para\s+telecomunicações\s+está\s+em\s+conformidade',
                "processing_type": "custom",  # ou "regex_patterns"
                "custom_patterns": ['ATO', 'RESOLUÇÃO']
            },
            "qc": {
                "start_pattern": r'Certification\s+programor\s+regulation',
                "end_pattern": r'Emissão',
                "processing_type": "custom",  # ou "regex_patterns"
                "custom_patterns": ['ATO', 'RESOLUÇÃO']
            },
            "versys": {
                "start_pattern": r'Applicable\s+Standards:',
                "end_pattern": r'Data\s+Certificação',
                "processing_type": "custom",  # ou "regex_patterns"
                "custom_patterns": ['ATO', 'RESOLUÇÃO']
            },
            "cpqd": {
                "start_pattern": r'Documentos\s+normativos/\s+Technical\s+Standards:',
                "end_pattern": r'Relatório\s+de\s+Conformidade\s+/\s+Report\s+Number:',
                "processing_type": "custom",  # ou "regex_patterns"
                "custom_patterns": ['ATO', 'RESOLUÇÃO']
            },
            "associação lmp certificações": {
                "start_pattern": r'Certificamos\s+que\s+o\s+produto\s+está\s+em\s+conformidade\s+com\s+as\s+seguintes\s+referências:',
                "end_pattern": r'Organismo\s+de\s+Certificação\s+Designado\s+pela\s+ANATEL\s+—\s+Agência\s+Nacional\s+de\s+Telecomunicações',
                "processing_type": "custom",  # ou "regex_patterns"
                "custom_patterns": ['ATO', 'RESOLUÇÃO'] 
            }
        }
    
    def _extract_normas_by_pattern(self, content: str, start_pattern: str, end_pattern: str, processing_type: str, custom_patterns: List[str] = None) -> List[str]:
        """
        Extrai normas usando padrões específicos de início e fim
        
        Args:
            content: Conteúdo do certificado
            start_pattern: Padrão regex para início da seção
            end_pattern: Padrão regex para fim da seção
            processing_type: Tipo de processamento ("custom" ou "regex_patterns")
            custom_patterns: Padrões customizados para processamento especial
            
        Returns:
            Lista de normas encontradas
        """
        normas = []
        
        # Encontra as posições de início e fim
        start_match = re.search(start_pattern, content, re.IGNORECASE)
        end_match = re.search(end_pattern, content, re.IGNORECASE)
        
        if start_match and end_match:
            # Extrai o texto entre as duas strings
            start_pos = start_match.end()
            end_pos = end_match.start()
            normas_section = content[start_pos:end_pos]
            
            if processing_type == "custom" and custom_patterns:
                # Processamento customizado (usado pela Moderna)
                lines = normas_section.split('\n')
                for line in lines:
                    line = line.strip()
                    if line:  # Se a linha não está vazia
                        # Remove pontos entre números (ex: 802.11 -> 80211, mas mantém : em anos)
                        temp_line = re.sub(r'(\d{4})', r'YEAR\1YEAR', line)
                        temp_line = re.sub(r'(\d)\.(\d)', r'\1\2', temp_line)
                        cleaned_line = re.sub(r'YEAR(\d{4})YEAR', r'\1', temp_line)
                        
                        # Adiciona a norma limpa se contém padrões reconhecíveis
                        if any(pattern in cleaned_line.upper() for pattern in custom_patterns):
                            # Processa atos e resoluções
                            match_ato = re.search(r'(ato)\s+[^\d]*(\d+)', cleaned_line, re.IGNORECASE)
                            match_resolucao = re.search(r'(resolução)\s+[^\d]*(\d+)', cleaned_line, re.IGNORECASE)
                            
                            if match_ato:
                                tipo = match_ato.group(1).lower()
                                numero = match_ato.group(2)
                                norma_formatada = f"{tipo}{numero}"
                                normas.append(norma_formatada)
                            elif match_resolucao:
                                tipo = match_resolucao.group(1).lower().replace('ção', 'cao')
                                numero = match_resolucao.group(2)
                                norma_formatada = f"{tipo}{numero}"
                                normas.append(norma_formatada)
                            else:
                                normas.append(cleaned_line)
                                
            elif processing_type == "regex_patterns":
                # Processamento usando padrões regex padrão
                default_patterns = [
                    r'ABNT\s+NBR\s+\d+(?::\d{4})?',
                    r'ANSI/IEEE\s+Std\s+[\d\.\-]+',
                    r'IEEE\s+Std\s+[\d\.\-]+',
                    r'IEC\s+\d+(?:-\d+)?(?::\d{4})?',
                    r'CISPR\s+\d+(?::\d{4})?',
                    r'FCC\s+CFR\s+Title\s+\d+\s+Part\s+\d+',
                    r'Ato\s+[^\d]*(\d+)',
                    r'Resolução\s+[^\d]*(\d+)'
                ]
                
                for pattern in default_patterns:
                    matches = re.findall(pattern, normas_section, re.IGNORECASE)
                    normas.extend(matches)
        
        return normas
    
    def extract_normas_verificadas(self, content: str, nome_ocd: str) -> List[str]:
        """
        Extrai normas verificadas baseado no OCD específico
        
        Args:
            content: Conteúdo do certificado
            nome_ocd: Nome do OCD identificado
            
        Returns:
            Lista de normas verificadas
        """
        normas = []
        ocd_patterns = self._get_ocd_patterns()
        
        # Busca configuração para o OCD específico
        ocd_key = nome_ocd.lower()
        ocd_config = ocd_patterns.get(ocd_key)
        
        if ocd_config:
            # Usa padrões específicos do OCD
            normas = self._extract_normas_by_pattern(
                content,
                ocd_config['start_pattern'],
                ocd_config['end_pattern'],
                ocd_config['processing_type'],
                ocd_config.get('custom_patterns', [])
            )
        else:
            # Método padrão para OCDs não configurados
            self.log(f"[AVISO] OCD '{nome_ocd}' não tem padrões específicos configurados, usando método padrão")
            default_patterns = [
                r'ABNT\s+NBR\s+\d+(?::\d{4})?',
                r'ANSI/IEEE\s+Std\s+[\d\.\-]+',
                r'IEEE\s+Std\s+[\d\.\-]+',
                r'IEC\s+\d+(?:-\d+)?(?::\d{4})?',
                r'CISPR\s+\d+(?::\d{4})?',
                r'FCC\s+CFR\s+Title\s+\d+\s+Part\s+\d+'
            ]
            
            for pattern in default_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                normas.extend(matches)
        
        return list(set(normas))  # Remove duplicatas
    
    def extract_data_from_cct(self, content: str) -> Dict:
        """
        Extrai todas as variáveis necessárias do CCT
        
        Returns:
            Dicionário com dados extraídos
        """
        #cnpj = self.extract_ocd_from_content(content)
        #nome_ocd = self.get_ocd_name(cnpj)
        nome_ocd = self.extract_ocd_from_content(content)
        tipo_equipamento = self.extract_tipo_equipamento(content)
        if nome_ocd:
            normas_verificadas = self.extract_normas_verificadas(content, nome_ocd)
        else:
            nome_ocd = "[ERRO] OCD não identificado"
            normas_verificadas = []

        ''' TEOGENES - desabilitado para testes
        if not nome_ocd or len(tipo_equipamento)==0 or len(normas_verificadas)==0:
            self.log(f"[ERRO] Falha na extração de dados essenciais do CCT.")
            self.log(f"       Nome OCD: {nome_ocd}")
            self.log(f"       Tipo Equipamento: {len(tipo_equipamento)} encontrado(s)")
            self.log(f"       Normas: {len(normas_verificadas)} encontrada(s)")'''
            
        # Extração de outras variáveis (exemplo)
        data = {
            'nome_ocd': nome_ocd,
            'tipo_equipamento': tipo_equipamento,
            'normas_verificadas': normas_verificadas,
            #'data_emissao': None,  # Implementar extração
            #'data_validade': None,  # Implementar extração
            #'numero_certificado': None,  # Implementar extração
        }
        
        return data
    
    def validate_data(self, data: Dict) -> Tuple[bool, List[str]]:
        """
        Valida se todas as normas dos equipamentos estão presentes nas normas verificadas
        
        Args:
            data: Dados extraídos do CCT
            
        Returns:
            Tuple[bool, List[str]]: (sucesso, lista_normas_nao_verificadas)
            - True, [] se todas as normas necessárias estão verificadas
            - False, [normas] se alguma norma necessária não foi verificada
        """
        try:
            # Obter equipamentos únicos
            equipamentos = data.get('tipo_equipamento', [])
            normas_verificadas = data.get('normas_verificadas', [])
            
            if not equipamentos:
                self.log("[AVISO] Nenhum equipamento encontrado para validação")
                return True, []
            
            # Consultar arquivo requisitos.json
            requisitos_file = self.utils_dir / "requisitos.json"
            
            if not requisitos_file.exists():
                self.log(f"[ERRO] Arquivo {requisitos_file} não encontrado")
                return False, ["Arquivo requisitos.json não encontrado"]
            
            with open(requisitos_file, 'r', encoding='utf-8') as f:
                requisitos_data = json.load(f)
            
            # Obter IDs únicos dos equipamentos
            equipamento_ids = set()
            for eq in equipamentos:
                if isinstance(eq, dict) and 'id' in eq:
                    equipamento_ids.add(eq['id'])
            
            # Buscar todas as normas necessárias para os equipamentos
            normas_necessarias = set()
            
            for requisito in requisitos_data:
                if isinstance(requisito, dict):
                    # Verificar se este requisito se aplica a algum dos equipamentos
                    req_equipamento_id = requisito.get('equipamento')
                    if req_equipamento_id in equipamento_ids:
                        # Adicionar normas deste requisito
                        normas_req = requisito.get('norma', [])
                        if isinstance(normas_req, list):
                            normas_necessarias.update(normas_req)
                        elif isinstance(normas_req, str):
                            normas_necessarias.add(normas_req)
            
            # Normalizar normas para comparação
            normas_necessarias_norm = {normalizar(norma) for norma in normas_necessarias}
            normas_verificadas_norm = {normalizar(norma) for norma in normas_verificadas}
            
            # Identificar normas não verificadas            
            normas_nao_verificadas = normas_necessarias_norm - normas_verificadas_norm
            
            # Converter de volta para formato original (sem normalização) para o retorno
            normas_nao_verificadas_originais = []
            for norma_norm in normas_nao_verificadas:
                # Encontrar a norma original correspondente
                for norma_orig in normas_necessarias:
                    if normalizar(norma_orig) == norma_norm:
                        normas_nao_verificadas_originais.append(norma_orig)
                        break
            
            # Resultado da validação
            sucesso = len(normas_nao_verificadas) == 0
            
            '''if sucesso:
                self.log(f"[INFO] Validação SUCESSO: {len(normas_necessarias)} normas necessárias, todas verificadas")
            else:
                self.log(f"[INFO] Validação FALHA: {len(normas_nao_verificadas)} normas não verificadas de {len(normas_necessarias)} necessárias")'''
            
            return sucesso, normas_nao_verificadas_originais
            
        except Exception as e:
            self.log(f"[ERRO] Falha na validação: {e}")
            return False, [f"Erro na validação: {str(e)}"]
    
    def display_results(self, file_name: str, data: Dict, validation: Tuple[bool, List[str]]):
        """Exibe resultados da análise no terminal"""        
        self.log("="*100)
        self.log(f"ARQUIVO: {file_name}")
        self.log("="*100)
        
        self.log("\n[DADOS EXTRAÍDOS]")
        #self.log("-"*100)
        for key, value in data.items():
            if isinstance(value, list):
                if key == 'tipo_equipamento' and value:
                    # Formatação especial para equipamentos (lista de dicionários)
                    equipamentos_str = []
                    for eq in value:
                        if isinstance(eq, dict):
                            nome = eq.get('nome', 'N/A')
                            id_eq = eq.get('id', 'N/A')
                            equipamentos_str.append(f"{nome}")
                        else:
                            equipamentos_str.append(str(eq))
                    value_str = ", ".join(equipamentos_str)
                else:
                    # Formatação padrão para outras listas
                    value_str = ", ".join(str(v) for v in value) if value else "Nenhum encontrado"
            else:
                value_str = value if value else "Não encontrado"
            self.log(f"  {key:20s}: {value_str}")
        
        self.log("\n[VALIDAÇÃO DE NORMAS]")
        #self.log("-"*70)
        sucesso, normas_nao_verificadas = validation
        
        if sucesso:
            self.log("   ✅ Todas as normas necessárias foram verificadas")
        else:
            self.log("   ❌ Algumas normas necessárias não foram verificadas")
            if normas_nao_verificadas:
                self.log(f"   🐛 Normas não verificadas:")
                for norma in normas_nao_verificadas:
                    # Buscar dados da norma em normas.json
                    norma_info = self._get_norma_info(norma)
                    if norma_info:
                        nome = norma_info.get('nome', 'N/A')
                        descricao = norma_info.get('descricao', 'N/A')
                        self.log(f"\t\t• {nome} - {descricao}")
                    else:
                        self.log(f"\t • {norma}")
        
        self.log("="*70)
        if sucesso:
            self.log("Avaliação automática: ✅ Passou")
        else:
            self.log("Avaliação automática: ❌ Falhou")
        self.log("="*70 + "\n")
    
    def run(self):
        """Executa o aplicativo"""
        print("\n")
        print("🤡"*50)
        print(f"θεoγενης - Versão {VERSION}")
        print("-"*100)
        print("Pelo fim do trabalho de presidiários, todo dia é dia de aprender algo novo!")
        print("🤡"*50)
        print("\n")

        # Solicitar diretório
        search_dir = input("Digite o nome do diretório (ou '*' para buscar em todos): ").strip()
        
        if not search_dir:
            self.log("[ERRO] Diretório não pode ser vazio!")
            return
        
        # Buscar arquivos
        cct_files = self.find_cct_files(search_dir)
        
        if not cct_files:
            self.log(f"\n[AVISO] Nenhum arquivo CCT encontrado!")
            return
        
        self.log(f"\n[INFO] {len(cct_files)} arquivo(s) CCT encontrado(s)\n")
        
        # Processar cada arquivo
        for cct_file in cct_files:
            content = self.extract_pdf_content(cct_file)
            
            if not content:
                continue
            
            # Extrair dados
            cct = self.extract_data_from_cct(content)
            validation_results = self.validate_data(cct)
            self.display_results(cct_file.name, cct, validation_results)           
            input("Pressione ENTER para continuar...")
            # self.log(f"\t🎯 [AVISO] Calma, cocada! Análise automática desabilitada este OCD.")
        self.log("\n[INFO] Análise concluída!")


def main():
    """Função principal"""
    try:
        analyzer = CCTAnalyzer(home_dir=r"C:\Users\tbnobrega\OneDrive - ANATEL\Anatel\_ORCN")
        analyzer.run()
    except KeyboardInterrupt:
        log("\n\n[INFO] Aplicativo interrompido pelo usuário")
    except Exception as e:
        log(f"\n[ERRO FATAL] {e}")
        import traceback
        traceback.print_exc()
    finally:
        input("\nPressione ENTER para sair...")


if __name__ == "__main__":
    main()