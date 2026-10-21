from pdf2image import convert_from_path
import pymupdf as fitz
import pytesseract
import json
import math
import re
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set#, Any 
import subprocess
from pydantic import ValidationError

from core.utils import (
    extrair_normas_por_padrao, processar_requerimentos_excel, extract_pdf_content_from_ocr,
    carregar_json_com_fallback
)
from core.log_print import log_info, log_erro, log_erro_critico
from core.const import (
    TESSERACT_PATH, JSON_FILES, GIT_COMMANDS, GIT_TIMEOUT, VERSAO_PADRAO,
    TBN_FILES_FOLDER, SEPARADOR_LINHA, SEPARADOR_MENOR, REQUERIMENTOS_DIR_INBOX, REQUERIMENTOS_DIR_REPORT,
    UTILS_DIR, EXT_PDF, EXT_JSON, EXT_TEX, GLOB_PDF,
    STATUS_CONFORME, STATUS_NAO_CONFORME, STATUS_INCONCLUSIVO, STATUS_ERRO, STATUS_PROCESSADO,
    VALOR_NAO_DISPONIVEL, ENCODING_UTF8, PALAVRAS_CHAVE_MANUAL,
    CERTIFICA_TIPO_ANEXO_REAPROVEITAMENTO,
    TIPOS_DOCUMENTOS, MIN_FILE_SIZE, MIN_CARACTERES_PAGINA_TEXTO, CERTIFICA_CABECALHO_MODELOS,
    CERTIFICA_CABECALHO_FREQUENCIAS
)
from core.regras_uso_faixa import HomologacaoProduto, parse_valor_numerico

# Constantes para tipos de documento (chaves da estrutura TIPOS_DOCUMENTOS)
TIPO_CCT = 'cct'
TIPO_RACT = 'ract'
TIPO_MANUAL = 'manual'
TIPO_RELATORIO_ENSAIO = 'relatorio_ensaio'
TIPO_ART = 'art'
TIPO_FOTOS = 'fotos'
TIPO_FOTOS_EXTERNAS = 'fotos_externas'
TIPO_CONTRATO_SOCIAL = 'contrato_social'
TIPO_OUTROS = 'outros'

FRASE_PRODUTO_NAO_ACABADO_FOTOS_EXTERNAS = (
    "Por se tratar de produto não acabado, o produto sob homologação é "
    "integralmente identificado pelas fotos internas, cujo arquivo está "
    "anexado no campo respectivo"
)
EXIGENCIA_CORRIGIR_FOTOS_EXTERNAS = (
    "Corrigir  “Fotos Externas do Produto”, conforme orientação passada por "
    "meio do item 6.6.3.2. I  do Ato nº 4083, de 31 de julho de 2020."
)
ID_NORMA_SAR = "ato17865"
FRASE_NAO_VAREJO = "Este certificado não se aplica para comercialização do produto no varejo"
TEXTO_NAO_VAREJO = (
    f"{FRASE_NAO_VAREJO}, sendo destinado exclusivamente para assistência "
    "técnica ou cumprimento de garantias ao consumidor."
)
CAMPOS_SAR = {
    "SAR (W/kg) Cabeça",
    "SAR (W/kg) Tronco",
    "SAR (W/Kg) Membro",
}
MESES_PORTUGUES = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}


def _extrair_datas_documento(texto: str) -> List[datetime]:
    """Extrai datas válidas em dd/mm/aaaa ou por extenso em português."""
    texto_normalizado = unicodedata.normalize("NFD", texto.lower())
    texto_normalizado = "".join(
        caractere
        for caractere in texto_normalizado
        if unicodedata.category(caractere) != "Mn"
    )
    datas = []

    padroes = (
        (r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", "numerica"),
        (r"\b(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})\b", "extenso"),
    )
    for padrao, formato in padroes:
        for correspondencia in re.finditer(padrao, texto_normalizado):
            primeiro, segundo, ano = correspondencia.groups()
            try:
                if formato == "numerica":
                    dia, mes = int(primeiro), int(segundo)
                else:
                    dia = int(primeiro)
                    mes = MESES_PORTUGUES.get(segundo, 0)
                if mes:
                    datas.append(datetime(int(ano), mes, dia))
            except ValueError:
                continue

    return datas


def _chave_selecao_documento(
    tipo_documento: str,
    data_conteudo: Optional[datetime],
    data_nome_arquivo: datetime,
) -> Tuple[datetime, datetime]:
    """Prioriza a data do PDF em CCT/RACT e mantém a data do nome nos empates."""
    if tipo_documento in (TIPO_CCT, TIPO_RACT):
        return data_conteudo or datetime.min, data_nome_arquivo
    return data_nome_arquivo, datetime.min


from core.utils import (
    formatar_cnpj, desformatar_cnpj, latex_escape_path, escapar_latex, buscar_valor,
    normalizar, normalizar_dados, obter_versao_git, carregar_json, salvar_json, validar_cnpj, fullpath_para_req,
    contar_ocorrencias_palavra_chave, extrair_contextos_palavra_chave
)


PALAVRAS_CHAVE_MANUAL_NORMALIZADAS = {
    normalizar(palavra): regra for palavra, regra in PALAVRAS_CHAVE_MANUAL.items()
}

# Preserva a forma original cadastrada para exibição em relatórios e PDF.
PALAVRAS_CHAVE_MANUAL_ORIGINAIS = {
    normalizar(palavra): palavra for palavra in PALAVRAS_CHAVE_MANUAL.keys()
}


def _pdf_requer_ocr(pdf) -> bool:
    """Indica PDF sem texto útil: vazio ou majoritariamente digitalizado (páginas-imagem com pouco texto)."""
    if len(pdf) == 0:
        return True
    textos = [str(pagina.get_text("text")).strip() for pagina in pdf]
    if sum(len(texto) for texto in textos) < MIN_FILE_SIZE:
        return True
    # A assinatura digital adiciona texto a PDFs digitalizados, então o total de caracteres não basta.
    paginas_digitalizadas = sum(
        1 for pagina, texto in zip(pdf, textos)
        if len(texto) < MIN_CARACTERES_PAGINA_TEXTO and pagina.get_images()
    )
    return paginas_digitalizadas * 2 >= len(pdf)


def _ignora_espacos(palavra: str) -> bool:
    return bool(PALAVRAS_CHAVE_MANUAL_NORMALIZADAS.get(palavra, {}).get("ignorar_espacos", False))


PYMUPDF_DISPONIVEL = True

try:    
    OCR_DISPONIVEL = True
    # Configurar caminho do Tesseract se necessário
    try:
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
    except:
        pass
except ImportError:
    OCR_DISPONIVEL = False

# ================================
# NOTA: Funções utilitárias movidas para core/utils.py
# ================================


class CCTAnalyzerIntegrado:
    """
    Versão integrada do CCTAnalyzer com todas as funcionalidades necessárias.
    Esta classe incorpora toda a lógica de análise de CCT sem dependências externas.
    """
    
    def __init__(self, utils_dir: Path):
        self.utils_dir = utils_dir
        
    def extract_pdf_content(self, pdf_path: Path) -> Optional[str]:
        """
        Extrai conteúdo de PDF usando PyMuPDF ou OCR como fallback.
        """
        try:
            if not PYMUPDF_DISPONIVEL:
                log_erro("PyMuPDF não disponível. Tentando OCR...")
                return extract_pdf_content_from_ocr(pdf_path)
            
            #log_info(f"Extraindo conteúdo de: {pdf_path.name}")
            
            with fitz.open(pdf_path) as pdf:
                content = ""                              
                for pagina in pdf:
                    content += str(pagina.get_text("text")) + "\n"
                if _pdf_requer_ocr(pdf):
                    #log_info(f"PDF aparentemente vazio, tentando OCR: {pdf_path.name}")
                    content = extract_pdf_content_from_ocr(pdf_path)
                
            return content
            
        except Exception as e:
            log_erro(f"Falha ao extrair {pdf_path.name}: {e}")
            return None

    '''def extract_ocd_from_content(self, content: str) -> Optional[str]:
        """
        Identifica o OCD baseado no conteúdo do certificado.
        Retorna nomes padronizados em lowercase.
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
    '''
    def get_ocd_name(self, cnpj: Optional[str]) -> str:
        """Obtém nome do OCD a partir do CNPJ consultando ocds.json"""
        if not cnpj:
            return "[ERRO] CNPJ não informado"
        
        ocds_file = self.utils_dir / "ocds.json"
        
        try:
            if ocds_file.exists():
                with open(ocds_file, 'r', encoding='utf-8') as f:
                    ocds_data = json.load(f)
                
                # Normalizar CNPJ de entrada (remover formatação se houver)
                cnpj_numeros = desformatar_cnpj(cnpj)
                cnpj_formatado = formatar_cnpj(cnpj_numeros)
                
                # Buscar por CNPJ formatado ou por números
                for ocd in ocds_data:
                    cnpj_ocd = ocd.get('cnpj')
                    if cnpj_ocd:
                        # Comparar tanto com formato quanto com números
                        if cnpj_ocd == cnpj_formatado or desformatar_cnpj(cnpj_ocd) == cnpj_numeros:
                            return ocd.get('nome', f"[ERRO] Nome não encontrado para CNPJ: {cnpj}")

            return f"[ERRO] OCD não cadastrado (CNPJ: {cnpj})"
            
        except Exception as e:
            log_erro(f"Falha ao consultar ocds.json: {e}")
            return f"[ERRO] OCD não cadastrado (CNPJ: {cnpj})"

    def extract_tipo_equipamento(self, content: str) -> List[Dict]:
        """
        Extrai tipos de equipamento consultando equipamentos.json e buscando matches no conteúdo.
        """
        equipamentos_encontrados = []
        equipamentos_file = self.utils_dir / "equipamentos.json"
        
        try:
            if not equipamentos_file.exists():
                log_erro(f"Arquivo {equipamentos_file} não encontrado")
                return []
                
            with open(equipamentos_file, 'r', encoding='utf-8') as f:
                equipamentos_data = json.load(f)
            
            content_normalizado = re.sub(
                r"\s+", " ", normalizar(content).replace("\n", " ")
            ).strip()
            correspondencias = []
            for equipamento in equipamentos_data:
                if isinstance(equipamento, dict) and 'nome' in equipamento:
                    nome_equipamento = equipamento['nome']
                    nome_normalizado = re.sub(
                        r"\s+", " ", normalizar(nome_equipamento)
                    ).strip()
                    if not nome_normalizado:
                        continue

                    ocorrencias = list(re.finditer(
                        rf"(?<!\w){re.escape(nome_normalizado)}(?!\w)",
                        content_normalizado
                    ))
                    if ocorrencias:
                        correspondencias.append(
                            (equipamento, len(nome_normalizado), ocorrencias)
                        )

            for equipamento, tamanho_nome, ocorrencias in correspondencias:
                ocorrencias_independentes = [
                    ocorrencia
                    for ocorrencia in ocorrencias
                    if not any(
                        tamanho_outro_nome > tamanho_nome
                        and any(
                            outra.start() <= ocorrencia.start()
                            and ocorrencia.end() <= outra.end()
                            for outra in outras_ocorrencias
                        )
                        for outro_equipamento, tamanho_outro_nome, outras_ocorrencias
                        in correspondencias
                        if outro_equipamento is not equipamento
                    )
                ]
                ja_existe = any(
                    item.get("nome") == equipamento.get("nome")
                    for item in equipamentos_encontrados
                )
                if ocorrencias_independentes and not ja_existe:
                    equipamentos_encontrados.append(equipamento)
            
            return equipamentos_encontrados
            
        except Exception as e:
            log_erro(f"Falha ao consultar equipamentos.json: {e}")
            return []

    def _get_ocd_patterns(self) -> Dict[str, Dict]:
        """
        Define os padrões de extração para cada OCD usando CNPJ como chave.
        """
        return {
            #DEKRA CERTIFICATION B.V.
            "26.600.714/0001-24": {
                "start_pattern": r"Reference\s+Standards",
                "end_pattern": r"Certificação\s+Inicial",
                "processing_type": "custom",
                "custom_patterns": ['ATO', 'RESOLUÇÃO']
            },
            #PCN DO BRASIL TELECOMUNICAÇÕES
            "32.193.729/0001-18": {
                "start_pattern": r"Regulation\s+applied\s+to\s+the\s+product",
                "end_pattern": r"5\s*-\s*RELAÇÃO\s+DE\s+LABORATÓRIO",
                "processing_type": "custom",
                "custom_patterns": ['ATO', 'RESOLUÇÃO']
            },
            # Moderna Tecnologia LTDA
            "44.458.010/0001-40": {
                "start_pattern": r'Fabricante',
                "end_pattern": r'Diretor\s+de\s+Tecnologia',
                "processing_type": "custom",
                "custom_patterns": ['ATO', 'RESOLUÇÃO']
            },
            # Associação NCC Certificações do Brasil
            "04.192.889/0001-07": {
                "start_pattern": r'Regulation\s+Applicable',
                "end_pattern": r'Conforme\s+os\s+termos\s+do\s+Ato\s+de\s+Designação\s+nº\s+16\.955',
                "processing_type": "custom",
                "custom_patterns": ['ATO', 'RESOLUÇÃO']
            },
            # Brics Certificacoes de Sistemas de Gestao e Produtos Ltda
            "16.884.899/0001-92": {
                "start_pattern": r'Documento\s+Normativo:',
                "end_pattern": r'Tipo\s+de\s+Produto',
                "processing_type": "custom",
                "custom_patterns": ['ATO', 'RESOLUÇÃO']
            },
            # ABCP Certificadora de Produtos LTDA (estimativa baseada no nome)
            "00.000.000/0001-01": {
                "start_pattern": r'Normas?\s+Verificadas?',
                "end_pattern": r'ABCP\s+Certificadora',
                "processing_type": "regex_patterns"
            },
            # ACERT ORGANISMO DE CERTIFICACAO (estimativa baseada no nome)
            "00.000.000/0001-02": {
                "start_pattern": r'Standards?\s+(?:Applied|Verified)',
                "end_pattern": r'ACERT\s+ORGANISMO',
                "processing_type": "regex_patterns"
            },
            # SGS do Brasil Ltda (estimativa baseada no nome)
            "00.000.000/0001-03": {
                "start_pattern": r'Technical\s+Standards?',
                "end_pattern": r'SGS\s+do\s+Brasil',
                "processing_type": "regex_patterns"
            },
            # BraCert – BRASIL CERTIFICAÇÕES LTDA (estimativa baseada no nome)
            "00.000.000/0001-04": {
                "start_pattern": r'Normas?\s+Aplicadas?',
                "end_pattern": r'BraCert.*BRASIL\s+CERTIFICAÇÕES',
                "processing_type": "regex_patterns"
            },
            # CCPE – CENTRO DE CERTIFICAÇÃO (estimativa baseada no nome)
            "00.000.000/0001-05": {
                "start_pattern": r'Technical\s+Standards?',
                "end_pattern": r'CCPE.*CENTRO\s+DE\s+CERTIFICAÇÃO',
                "processing_type": "regex_patterns"
            },
            # OCD-Eldorado (estimativa baseada no nome)
            "00.000.000/0001-06": {
                "start_pattern": r'NORMAS\s+APLICÁVEIS/\s+APPLICABLE\s+STANDARDS',
                "end_pattern": r'O\s+OCD-Eldorado\s+atribui\s+a\s+certificação\s-aos\s+produtos\s+mencionados\s+acima',
                "processing_type": "custom",
                "custom_patterns": ['ATO', 'RESOLUÇÃO']
            },
            # Organismo ICC (estimativa baseada no nome)
            "00.000.000/0001-07": {
                "start_pattern": r'Regulation\s+Applicable',
                "end_pattern": r'O\s+organismo\s+ICC\s+no\s+uso\s+das\s+atribuições\s+que\s+lhe\s+confere\s+o\s+Ato\s+de\s+Designação',
                "processing_type": "custom",
                "custom_patterns": ['ATO', 'RESOLUÇÃO']
            },
            # Master Associação de Avaliação de Conformidade
            "07.832.680/0001-59": {
                "start_pattern": r'Reference\s+Standards',
                "end_pattern": r'LABORATÓRIOS\s+DE\s+ENSAIOS',
                "processing_type": "custom",
                "custom_patterns": ['ATO', 'RESOLUÇÃO']
            },
            # OCP-TELI - ORGANIZAÇÃO CERTIFICADORA DE PRODUTOS DE TELECOMUNICAÇÕES E INFORMÁTICA
            "04.538.402/0001-03": {
                "start_pattern": r'Regulamentos\s+Aplicáveis:',
                "end_pattern": r'OCD\s+designado\s+pelo\s+Ato\s+nº\s+19\.434',
                "processing_type": "custom",
                "custom_patterns": ['ATO', 'RESOLUÇÃO']
            },
            # TÜV (estimativa baseada no nome)
            "00.000.000/0001-08": {
                "start_pattern": r'Standards?\s+Applied',
                "end_pattern": r'TÜV',
                "processing_type": "regex_patterns"
            },
            # UL do Brasil Ltda
            "02.839.483/0001-48": {
                "start_pattern": r'normative\s+documents',
                "end_pattern": r'e\s+atesta\s+que\s+o\s+produto\s+para\s+telecomunicações\s+está\s+em\s+conformidade',
                "processing_type": "custom",
                "custom_patterns": ['ATO', 'RESOLUÇÃO']
            },
            # UL do Brasil Certificações
            "04.830.102/0001-95": {
                "start_pattern": r'normative\s+documents',
                "end_pattern": r'e\s+atesta\s+que\s+o\s+produto\s+para\s+telecomunicações\s+está\s+em\s+conformidade',
                "processing_type": "custom",
                "custom_patterns": ['ATO', 'RESOLUÇÃO']
            },
            # QC Certificações (estimativa baseada no nome)
            "00.000.000/0001-09": {
                "start_pattern": r'Certification\s+programor\s+regulation',
                "end_pattern": r'Emissão',
                "processing_type": "custom",
                "custom_patterns": ['ATO', 'RESOLUÇÃO']
            },
            # Associação Versys de Tecnologia
            "26.352.661/0001-70": {
                "start_pattern": r'Applicable\s+Standards:',
                "end_pattern": r'Data\s+Certificação',
                "processing_type": "custom",
                "custom_patterns": ['ATO', 'RESOLUÇÃO']
            },
            # FUNDACAO CENTRO DE PESQUISA E DESENVOLVIMENTO DE TELECOMUNICACOES- CPQD.
            "02.641.663/0001-10": {
                "start_pattern": r'Technical\s+Standards:',
                "end_pattern": r'Relatório\s+de\s+Conformidade\s',
                "processing_type": "custom",
                "custom_patterns": ['ATO', 'RESOLUÇÃO']
            },
            # Associação LMP Certificações (estimativa baseada no nome)
            "00.000.000/0001-10": {
                "start_pattern": r'Certificamos\s+que\s+o\s+produto\s+está\s+em\s+conformidade\s+com\s+as\s+seguintes\s+referências:',
                "end_pattern": r'Organismo\s+de\s+Certificação\s+Designado\s+pela\s+ANATEL\s+—\s+Agência\s+Nacional\s+de\s+Telecomunicações',
                "processing_type": "custom",
                "custom_patterns": ['ATO', 'RESOLUÇÃO'] 
            }
        }

    def _extract_normas_by_pattern(self, content: str) -> List[str]:
        """
        Extrai normas usando a função centralizada.
        """
        return extrair_normas_por_padrao(content)

    def extract_normas_verificadas(self, content: str, cnpj_ocd: str) -> List[str]:
        """
        Extrai normas verificadas baseado no CNPJ do OCD específico.
        """
        normas = []
        ocd_patterns = self._get_ocd_patterns()
        
        # Normalizar CNPJ (remover formatação se houver)
        cnpj_normalizado = desformatar_cnpj(cnpj_ocd) if cnpj_ocd else ""
        cnpj_formatado = formatar_cnpj(cnpj_normalizado) if cnpj_normalizado else ""
        
        # Buscar configuração por CNPJ formatado
        ocd_config = ocd_patterns.get(cnpj_formatado)
        
        if ocd_config:
            normas = self._extract_normas_by_pattern(content)
        else:
            # Fallback: buscar padrões gerais
            norma_patterns = [
                r'ATO\s*(?:Nº|N°|NO|nº|n°|no)?\s*\d+[\d\w\.\-/]*',
                r'RESOLUÇÃO\s*(?:Nº|N°|NO|nº|n°|no)?\s*\d+[\d\w\.\-/]*'
            ]
            
            for pattern in norma_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                normas.extend(matches)
        
        return list(set(normas))  # Remove duplicatas

    def extract_data_from_cct(self, content: str, cnpj_ocd: str, nome_ocd: str | None) -> Dict:
        """
        Extrai todas as variáveis necessárias do CCT.
        """
        tipo_equipamento = self.extract_tipo_equipamento(content)
        
        if cnpj_ocd:
            normas_verificadas = self._extract_normas_by_pattern(content)#, cnpj_ocd)
        else:
            normas_verificadas = []
            
        data = {
            'cnpj_ocd': cnpj_ocd,
            'nome_ocd': nome_ocd or 'N/A',
            'tipo_equipamento': tipo_equipamento,
            'normas_verificadas': normas_verificadas,
            'conteudo_extraido': len(content) > 0,
            'timestamp_extracao': datetime.now().isoformat()
        }
        
        return data

    def validate_data(self, data: Dict) -> Tuple[bool, List[str]]:
        """
        Valida se todas as normas dos equipamentos estão presentes nas normas verificadas.
        """
        try:
            tipo_equipamento = data.get('tipo_equipamento', [])
            normas_verificadas = data.get('normas_verificadas', [])
            
            if not tipo_equipamento:
                return False, ["Nenhum equipamento identificado"]
            
            if not normas_verificadas:
                return False, ["Nenhuma norma verificada encontrada"]
            
            # Carregar requisitos
            requisitos_file = self.utils_dir / "requisitos.json"
            
            if not requisitos_file.exists():
                return True, []  # Se não há arquivo de requisitos, considera válido
            
            with open(requisitos_file, 'r', encoding='utf-8') as f:
                requisitos_data = json.load(f)
            
            normas_nao_verificadas = []
            
            for equipamento in tipo_equipamento:
                equipamento_id = equipamento.get('id')
                if not equipamento_id:
                    continue
                
                # Buscar normas necessárias para este equipamento
                for req in requisitos_data:
                    if req.get('equipamento') == equipamento_id:
                        normas_necessarias = req.get('norma', [])
                        
                        for norma_necessaria in normas_necessarias:
                            # Verificar se a norma está nas verificadas
                            norma_encontrada = False
                            for norma_verificada in normas_verificadas:
                                if norma_necessaria.lower() in norma_verificada.lower():
                                    norma_encontrada = True
                                    break
                            
                            if not norma_encontrada:
                                if norma_necessaria not in normas_nao_verificadas:
                                    normas_nao_verificadas.append(norma_necessaria)
            
            return len(normas_nao_verificadas) == 0, normas_nao_verificadas
            
        except Exception as e:
            log_erro(f"Erro na validação de dados: {e}")
            return False, [f"Erro na validação: {str(e)}"]


class AnalisadorRequerimentos:
    """
    Classe principal para análise de requerimentos ORCN.
    Gerencia a análise de documentos e geração de relatórios.
    """
    
    def __init__(self):
        # Usar constante centralizada para diretório base
        self.pasta_base = Path(TBN_FILES_FOLDER) / REQUERIMENTOS_DIR_INBOX
        self.pasta_resultados = Path(TBN_FILES_FOLDER) / REQUERIMENTOS_DIR_REPORT
        self.pasta_resultados.mkdir(exist_ok=True)
        
        # Carregar configurações
        self.regras = carregar_json_com_fallback(JSON_FILES['regras'])
        self.equipamentos = carregar_json_com_fallback(JSON_FILES['equipamentos'])
        self.familias_equipamentos = carregar_json_com_fallback(JSON_FILES['familias_equipamentos'])
        self.requisitos = carregar_json_com_fallback(JSON_FILES['requisitos'])
        self.normas = carregar_json_com_fallback(JSON_FILES['normas'])
        self.ocds = carregar_json_com_fallback(JSON_FILES['ocds'])
        
        # Resultados da análise
        self.resultados_analise = []
        
        # Cache para CCTAnalyzer (instanciado sob demanda)
        self._cct_analyzer = None
        
        # Variáveis de timing
        self.tempo_inicio_analise = None
        self.tempo_fim_analise = None

    def _extrair_data_mais_recente_pdf(self, caminho: Path) -> Optional[datetime]:
        """Retorna a data mais recente encontrada no texto ou OCR do PDF."""
        try:
            with fitz.open(caminho) as pdf:
                texto = "\n".join(str(pagina.get_text("text")) for pagina in pdf)
                if _pdf_requer_ocr(pdf):
                    texto_ocr = extract_pdf_content_from_ocr(caminho)
                    if texto_ocr:
                        texto = texto_ocr
        except Exception as erro:
            log_erro(f"Falha ao extrair datas de {caminho.name}: {erro}")
            return None

        datas = _extrair_datas_documento(texto)
        return max(datas) if datas else None
    
    def _obter_escopo_analise(self) -> str:
        """
        Pergunta ao usuário se a análise será de um requerimento específico ou todos.
        """
        log_info("\n" + SEPARADOR_LINHA)
        log_info("🔍 ANÁLISE DE REQUERIMENTOS ORCN")
        log_info(SEPARADOR_LINHA)
        log_info("\nEscolha o escopo da análise:")
        log_info("1. Analisar um requerimento específico")
        log_info("2. Analisar todos os requerimentos (*)")
        log_info("3. Voltar ao menu principal")

        resposta = "CANCELAR"
        
        try:
            opcao = input("\nDigite sua opção (1/2/3): ").strip()
            if opcao == "1":
                resposta = self._selecionar_requerimento_especifico()
            elif opcao == "2":
                resposta = "*"
            elif opcao == "3":
                resposta = "CANCELAR"
            else:
                log_info("❌ Opção inválida. Digite 1, 2 ou 3.")
        except KeyboardInterrupt:
            log_info("\n❌ Operação cancelada pelo usuário.")
            resposta = "CANCELAR"
        except Exception as e:
            log_erro(f"Erro inesperado na seleção de escopo: {str(e)}")
            log_info("❌ Erro inesperado. Retornando ao menu principal.")
            resposta = "CANCELAR"
        return resposta
    
    def _selecionar_requerimento_especifico(self) -> str:
        """Permite ao usuário selecionar um requerimento específico."""
        requerimentos = self._listar_requerimentos()
        
        if not requerimentos:
            log_info("❌ Nenhum requerimento encontrado na pasta de requerimentos.")
            resposta = "CANCELAR"
        
        log_info(f"\n📁 Requerimentos disponíveis ({len(requerimentos)}):")
        for i, req in enumerate(requerimentos, 1):
            log_info(f"{i:2d}. {req}")
        log_info(f"{len(requerimentos)+1:2d}. Cancelar e voltar")
        
        opcao = ""
        resposta = "CANCELAR"
        try:
            opcao = input(f"\nSelecione o requerimento (1-{len(requerimentos)+1}): ").strip()
            
            # Verificar se é cancelamento
            if opcao.lower() in ['c', 'cancelar', 'voltar', '0']:
                return resposta
            
            indice = int(opcao) - 1
            
            # Verificar se é a opção de cancelar (último número)
            if indice == len(requerimentos):
                return resposta
            
            # Verificar se é um requerimento válido
            if 0 <= indice < len(requerimentos):
                resposta = requerimentos[indice]
            else:
                log_info(f"❌ Número inválido. Digite um número entre 1 e {len(requerimentos)+1}, ou 'c' para cancelar.")
                
        except ValueError:
            if opcao.lower() in ['c', 'cancelar', 'voltar']:
                return resposta
            log_info("❌ Digite um número válido ou 'c' para cancelar.")
        except KeyboardInterrupt:
            log_info("\n❌ Operação cancelada pelo usuário.")
            return resposta
        return resposta

    def _listar_requerimentos(self) -> List[str]:
        """Lista todos os requerimentos disponíveis."""
        if not self.pasta_base.exists():
            return []
        
        requerimentos = []
        for item in self.pasta_base.iterdir():
            if item.is_dir() and item.name.startswith("_"):
                requerimentos.append(item.name[1:])
        
        return sorted(requerimentos)

    def _analisar_documento(
        self,
        caminho_documento: Path,
        tipo_documento: str,
        dados_ocd: Dict,
        dados_requerimento: Optional[Dict] = None
    ) -> Dict:
        """
        Analisa um documento específico baseado no seu tipo.
        """
        #info = re.findall(r'\[(.*?)\]', caminho_documento.name)
        #log_info(f"Analisando documento: {info[:2]}")
        
        resultado = {
            "nome_arquivo": caminho_documento.name,
            "tipo": tipo_documento,
            "caminho": str(caminho_documento),
            "timestamp": datetime.now().isoformat(),
            "status": "INCONCLUSIVO",
            "conformidades": [],
            "nao_conformidades": [],
            "observacoes": []
        }
        
        try:
            # Análise baseada no tipo de documento usando constantes unificadas
            if tipo_documento == TIPO_CCT:
                resultado = self._analisar_cct(
                    caminho_documento, resultado, dados_ocd, dados_requerimento
                )
            elif tipo_documento == TIPO_RACT:
                resultado = self._analisar_ract(caminho_documento, resultado)
            elif tipo_documento == TIPO_MANUAL:
                resultado = self._analisar_keywords(caminho_documento, resultado)
            elif tipo_documento == TIPO_RELATORIO_ENSAIO:
                resultado = self._analisar_relatorio_ensaio(caminho_documento, resultado)
            elif tipo_documento == TIPO_ART:
                resultado = self._analisar_art(caminho_documento, resultado)
            elif tipo_documento in (TIPO_FOTOS, TIPO_FOTOS_EXTERNAS):
                resultado = self._analisar_fotos(caminho_documento, resultado)
            elif tipo_documento == TIPO_CONTRATO_SOCIAL:
                resultado = self._analisar_contrato_social(caminho_documento, resultado)
            elif tipo_documento == TIPO_OUTROS:
                resultado = self._analisar_keywords(caminho_documento, resultado)    
            else:
                resultado["observacoes"].append(f"Tipo de documento não reconhecido: {tipo_documento}")
                
        except Exception as e:
            log_erro(f"Erro ao analisar {caminho_documento.name}: {str(e)}")
            resultado["status"] = STATUS_ERRO
            resultado["nao_conformidades"].append(f"Erro no processamento: {str(e)}")
        
        return resultado
    
    def _determinar_tipo_documento(self, nome_arquivo: str) -> Tuple[str, datetime]:
        """Determina o tipo e a data dos nomes SCH e Certifica."""
        data_padrao = datetime(1900, 1, 1)
        
        # Extrair o primeiro termo entre colchetes
        match = re.search(r'\[([^\]]+)\]', nome_arquivo)

        # SCH inclui texto após a data; Certifica acrescenta hora no formato HHhMMmSSs.
        match_data = re.search(
            r'^\[[^\]]+\]\[(\d{4}\.\d{2}\.\d{2})(?:\s+(\d{2})h(\d{2})m(\d{2})s)?(?:\s*-\s*[^\]]+)?\]',
            nome_arquivo
        )
        if not match_data:
            data_documento = data_padrao
        else:
            try:
                data_formatada = match_data.group(1)
                if match_data.group(2):
                    data_formatada += f" {match_data.group(2)}h{match_data.group(3)}m{match_data.group(4)}s"
                    formato_data = "%Y.%m.%d %Hh%Mm%Ss"
                else:
                    formato_data = "%Y.%m.%d"
                data_documento = datetime.strptime(data_formatada, formato_data)
            except ValueError:
                data_documento = data_padrao

        if match:
            tipo_extraido = match.group(1).lower().strip()

            if tipo_extraido == normalizar("Fotos Externas do Produto"):
                return TIPO_FOTOS_EXTERNAS, data_documento
            
            # Primeira passada: verificar correspondências exatas com 'nome' ou 'nome_curto'
            for tipo_chave, tipo_info in TIPOS_DOCUMENTOS.items():
                nome_completo = tipo_info.get('botao_pdf', '').lower()
                nome_curto = tipo_info.get('nome_curto', '').lower().strip()
                
                # Certifica prefixa os nomes de CCT/RACT com a sigla e não usa o rótulo SCH.
                if (
                    tipo_extraido == nome_completo
                    or tipo_extraido == nome_curto
                    or (
                        tipo_chave in (TIPO_CCT, TIPO_RACT)
                        and tipo_extraido.startswith(f"{nome_curto} - ")
                    )
                ):
                    return tipo_chave, data_documento
        
        # Fallback final para "outros" se não encontrar correspondência
        return TIPO_OUTROS, data_documento
    
    def _analisar_cct(
        self,
        caminho: Path,
        resultado: Dict,
        dados_ocd: Dict,
        dados_requerimento: Optional[Dict] = None
    ) -> Dict:
        """Análise específica para Certificado de Conformidade Técnica."""
        try:
            #log_info(f"Iniciando análise detalhada de CCT: {caminho.name}")
            
            # Instanciar CCTAnalyzer integrado
            utils_dir = Path(__file__).parent.parent / UTILS_DIR
            cct_analyzer = CCTAnalyzerIntegrado(utils_dir)
            
            # Extrair conteúdo do PDF
            conteudo = cct_analyzer.extract_pdf_content(caminho)
            
            if not conteudo:
                resultado["status"] = STATUS_ERRO
                resultado["nao_conformidades"].append("Falha na extração do conteúdo do PDF")
                resultado["observacoes"].append("PDF pode estar corrompido ou protegido")
                return resultado

            modelos_json = self._extrair_modelos_json(dados_requerimento)
            modelos_encontrados = [
                modelo for modelo in modelos_json
                if re.search(rf"(?<!\w){re.escape(modelo)}(?!\w)", conteudo)
            ]
            modelos_nao_encontrados = [
                modelo for modelo in modelos_json if modelo not in modelos_encontrados
            ]
            
            # Extrair dados do CCT usando a lógica especializada
            cnpj_ocd = dados_ocd.get('CNPJ', '') if dados_ocd else ''
            nome_ocd = dados_ocd.get('Nome', 'N/A') if dados_ocd else 'N/A'
            dados_cct = cct_analyzer.extract_data_from_cct(conteudo, cnpj_ocd, nome_ocd)
            
            if not dados_cct:
                resultado["status"] = STATUS_ERRO
                resultado["nao_conformidades"].append("Falha na extração de dados do CCT")
                return resultado
            
            # Validar dados extraídos
            validacao = cct_analyzer.validate_data(dados_cct)
            sucesso_validacao, normas_nao_verificadas = validacao

            # Extrair e contar palavras-chave no conteúdo do CCT para manter a contagem consolidada por documento.
            texto_normalizado = normalizar(conteudo).replace("\n", " ")
            texto_normalizado = re.sub(r'\s+', ' ', texto_normalizado).strip()
            palavras_chave_manual = list(PALAVRAS_CHAVE_MANUAL_NORMALIZADAS.keys())
            palavras_chave_manual = sorted(palavras_chave_manual)
            palavras_encontradas = {}
            palavras_nao_encontradas = []
            palavras_encontradas_com_normas = {}
            palavras_evidencias = {}

            for palavra in palavras_chave_manual:
                ignorar_espacos = _ignora_espacos(palavra)
                contador = contar_ocorrencias_palavra_chave(texto_normalizado, palavra, ignorar_espacos)
                if contador > 0:
                    palavras_encontradas[palavra] = contador
                    palavras_evidencias[palavra] = extrair_contextos_palavra_chave(
                        texto_normalizado, palavra, ignorar_espacos=ignorar_espacos)
                    regra_palavra = PALAVRAS_CHAVE_MANUAL_NORMALIZADAS.get(palavra, {})
                    normas_associadas = regra_palavra.get("normas", [])
                    efeito_regra = str(regra_palavra.get("efeito", "aplica")).lower()
                    if normas_associadas:
                        palavras_encontradas_com_normas[palavra] = {
                            "contador": contador,
                            "normas": normas_associadas,
                            "efeito": efeito_regra
                        }
                else:
                    palavras_nao_encontradas.append(palavra)
            
            # Processar resultados da análise
            #nome_ocd = dados_cct.get('nome_ocd', 'N/A')
            tipo_equipamento = dados_cct.get('tipo_equipamento', [])
            normas_verificadas = dados_cct.get('normas_verificadas', [])
            # Detecta frase de vínculo da validade do certificado diretamente no texto do CCT.
            contem_vinculo_homologacao = ("vinculado" in texto_normalizado) or ("vinculada" in texto_normalizado)
            contem_frase_nao_varejo = (
                re.sub(r"\s+", "", normalizar(FRASE_NAO_VAREJO))
                in re.sub(r"\s+", "", texto_normalizado)
            )
            
            # Adicionar informações detalhadas ao resultado
            resultado["dados_extraidos"] = {
                "nome_ocd": nome_ocd,
                "quantidade_equipamentos": len(tipo_equipamento),
                "equipamentos": [eq.get('nome', 'N/A') for eq in tipo_equipamento] if tipo_equipamento else [],
                "quantidade_normas": len(normas_verificadas),
                "normas_verificadas": normas_verificadas,
                "palavras_encontradas": palavras_encontradas,
                "palavras_nao_encontradas": palavras_nao_encontradas,
                "palavras_encontradas_com_normas": palavras_encontradas_com_normas,
                "palavras_evidencias": palavras_evidencias,
                "contem_vinculo_homologacao": contem_vinculo_homologacao,
                "contem_frase_nao_varejo": contem_frase_nao_varejo,
                "modelos_json": modelos_json,
                "modelos_encontrados_no_cct": modelos_encontrados,
                "modelos_nao_encontrados_no_cct": modelos_nao_encontrados
            }
            
            # Observações detalhadas
            resultado["observacoes"].extend([
                f"OCD identificado: {nome_ocd}",
                f"Equipamentos encontrados: {len(tipo_equipamento)}",
                f"Normas verificadas: {len(normas_verificadas)}"
            ])
            
            # Verificações de conformidade
            conformidades = []
            nao_conformidades = []
            
            # Verificar se OCD foi identificado
            if nome_ocd and nome_ocd != 'N/A' and not nome_ocd.startswith('[ERRO]'):
                conformidades.append("OCD identificado corretamente")
            else:
                nao_conformidades.append("OCD não identificado ou inválido")
            
            # Verificar se equipamentos foram encontrados
            if tipo_equipamento and len(tipo_equipamento) > 0:
                conformidades.append(f"{len(tipo_equipamento)} equipamento(s) identificado(s)")
                
                # Listar equipamentos para auditoria
                for i, equip in enumerate(tipo_equipamento, 1):
                    nome_equip = equip.get('nome', 'Nome não disponível')
                    id_equip = equip.get('id', 'ID não disponível')
                    resultado["observacoes"].append(f"Equipamento {i}: {nome_equip} (ID: {id_equip})")
            else:
                nao_conformidades.append("Nenhum equipamento identificado")
            
            # Verificar se normas foram encontradas
            if normas_verificadas and len(normas_verificadas) > 0:
                conformidades.append(f"{len(normas_verificadas)} norma(s) verificada(s)")
                
                # Listar primeiras 5 normas para auditoria
                for i, norma in enumerate(normas_verificadas[:5], 1):
                    resultado["observacoes"].append(f"Norma {i}: {norma}")
                
                if len(normas_verificadas) > 5:
                    resultado["observacoes"].append(f"... e mais {len(normas_verificadas) - 5} norma(s)")
            else:
                nao_conformidades.append("Nenhuma norma verificada encontrada")

            # Registrar palavras-chave identificadas no CCT para manter a rastreabilidade da contagem.
            if palavras_encontradas:
                palavras_ordenadas = sorted(palavras_encontradas.items(), key=lambda x: x[1], reverse=True)
                for i, (palavra, contador) in enumerate(palavras_ordenadas[:5], 1):
                    resultado["observacoes"].append(f"Palavra {i}: {palavra} (x{contador})")
                if len(palavras_encontradas) > 5:
                    resultado["observacoes"].append(f"... e mais {len(palavras_encontradas) - 5} palavra(s)")
            else:
                resultado["observacoes"].append("⚠️ Nenhuma palavra-chave específica foi identificada no CCT")
            
            # Validação de requisitos (normas necessárias vs verificadas)
            if sucesso_validacao:
                conformidades.append("Todas as normas necessárias foram verificadas")
                resultado["observacoes"].append("✅ Validação de normas: PASSOU")
            else:
                if normas_nao_verificadas:
                    nao_conformidades.append(f"Normas não verificadas: {', '.join(normas_nao_verificadas)}")
                    resultado["observacoes"].append(f"X Validação de normas: FALHOU")
                    resultado["observacoes"].append(f"Normas em falta: {', '.join(normas_nao_verificadas)}")
                else:
                    nao_conformidades.append("Falha na validação de normas (motivo não especificado)")
            
            # Atualizar listas de conformidade
            resultado["conformidades"].extend(conformidades)
            resultado["nao_conformidades"].extend(nao_conformidades)
            
            # Determinar status final
            if nao_conformidades:
                if "OCD não identificado" in str(nao_conformidades) or \
                   "Nenhum equipamento identificado" in str(nao_conformidades) or \
                   "Nenhuma norma verificada encontrada" in str(nao_conformidades):
                    resultado["status"] = "INCONCLUSIVO"
                else:
                    resultado["status"] = "NAO_CONFORME"
            else:
                resultado["status"] = "CONFORME"
            
            # Adicionar timestamp de processamento
            resultado["observacoes"].append(f"Análise CCT concluída em {datetime.now().strftime('%H:%M:%S')}")
            
            #log_info(f"Análise CCT concluída - Status: {resultado['status']}")
            
        except Exception as e:
            log_erro(f"Erro durante análise de CCT: {str(e)}")
            resultado["status"] = "ERRO"
            resultado["nao_conformidades"].append(f"Erro crítico na análise: {str(e)}")
            resultado["observacoes"].append("Falha na execução da análise especializada de CCT")
        
        return resultado
    
    def _extract_normas_from_ract(self, content: str) -> List[str]:
        """
        Extrai normas verificadas do conteúdo de um RACT usando a função centralizada.
        
        Args:
            content: Conteúdo do RACT extraído do PDF
            
        Returns:
            Lista de normas encontradas
        """
        return extrair_normas_por_padrao(content)

    def _analisar_ract(self, caminho: Path, resultado: Dict) -> Dict:
        """Análise específica para Relatório de Avaliação da Conformidade Técnica."""
        try:
            #log_info(f"Iniciando análise de RACT: {caminho.name}")
            
            # Inicializar campo normas_verificadas se não existir
            if "normas_verificadas" not in resultado:
                resultado["normas_verificadas"] = []
            
            # Verificações básicas do arquivo
            if not caminho.exists():
                resultado["status"] = "ERRO"
                resultado["nao_conformidades"].append("Arquivo RACT não encontrado")
                return resultado
            
            # Verificar tamanho do arquivo
            #tamanho_mb = caminho.stat().st_size / (1024 * 1024)
            #resultado["observacoes"].append(f"Tamanho do arquivo: {tamanho_mb:.2f} MB")
            
            # Análise específica para RACT
            conformidades = []
            nao_conformidades = []
            
            # Verificar nomenclatura do arquivo
            nome_arquivo = caminho.name.lower()
            if "ract" in nome_arquivo or "relatório" in nome_arquivo or "avaliação" in nome_arquivo:
                conformidades.append("Nomenclatura do arquivo adequada")
            else:
                nao_conformidades.append("Nomenclatura do arquivo pode não estar adequada")
            
            # Verificar se é PDF
            if caminho.suffix.lower() == EXT_PDF:
                conformidades.append("Formato PDF correto")
            else:
                nao_conformidades.append("Arquivo não está em formato PDF")
            
            # Tentar extrair conteúdo básico do PDF para validações adicionais
            try:
                
                with fitz.open(caminho) as doc:
                    total_paginas = len(doc)
                    resultado["observacoes"].append(f"Total de páginas: {total_paginas}")
                    
                    if total_paginas > 0:
                        conformidades.append(f"Documento contém {total_paginas} página(s)")
                        
                        # Extrair texto completo do manual para análise
                        texto_completo = ""
                        for pagina_num in range(total_paginas):  # Analisar todas as páginas
                            texto_completo += str(doc[pagina_num].get_text()).lower() + "\n"
                        
                        if _pdf_requer_ocr(doc):
                            #log_info(f"PDF aparentemente vazio, tentando OCR: {pdf_path.name}")
                            texto_ocr = extract_pdf_content_from_ocr(caminho)
                            if texto_ocr:
                                texto_completo = texto_ocr.lower()

                        # Usar palavras-chave definidas em const.py
                        palavras_chave_manual = list(PALAVRAS_CHAVE_MANUAL_NORMALIZADAS.keys())
                        palavras_chave_manual = sorted(palavras_chave_manual)                           
                        
                        # Contar ocorrências de cada palavra-chave
                        palavras_encontradas = {}
                        palavras_nao_encontradas = []
                        palavras_encontradas_com_normas = {}  # Nova estrutura para palavras com normas
                        palavras_evidencias = {}
                        
                        for palavra in palavras_chave_manual:
                            ignorar_espacos = _ignora_espacos(palavra)
                            contador = contar_ocorrencias_palavra_chave(texto_completo, palavra, ignorar_espacos)
                            if contador > 0:
                                palavras_encontradas[palavra] = contador
                                palavras_evidencias[palavra] = extrair_contextos_palavra_chave(
                                    texto_completo, palavra, ignorar_espacos=ignorar_espacos)
                                # Buscar normas associadas à palavra
                                regra_palavra = PALAVRAS_CHAVE_MANUAL_NORMALIZADAS.get(palavra, {})
                                normas_associadas = regra_palavra.get("normas", [])
                                efeito_regra = str(regra_palavra.get("efeito", "aplica")).lower()
                                if normas_associadas:
                                    palavras_encontradas_com_normas[palavra] = {
                                        "contador": contador,
                                        "normas": normas_associadas,
                                        "efeito": efeito_regra
                                    }
                            else:
                                palavras_nao_encontradas.append(palavra)
                        
                        # Extrair normas verificadas do conteúdo completo
                        normas_verificadas = self._extract_normas_from_ract(texto_completo)
                        resultado["normas_verificadas"] = normas_verificadas
                        
                        # CORREÇÃO: Adicionar também ao dados_extraidos para consistência
                        resultado["dados_extraidos"] = {
                            "normas_verificadas": normas_verificadas,
                            "quantidade_normas": len(normas_verificadas),
                            "palavras_encontradas": palavras_encontradas,
                            "palavras_nao_encontradas": palavras_nao_encontradas,
                            "palavras_encontradas_com_normas": palavras_encontradas_com_normas,
                            "palavras_evidencias": palavras_evidencias
                        }
                        
                        if normas_verificadas:
                            conformidades.append(f"{len(normas_verificadas)} norma(s) verificada(s) encontrada(s)")
                            #log_info(f"Normas encontradas no RACT: {normas_verificadas}")                        
                            
                    else:
                        nao_conformidades.append("Documento PDF vazio ou corrompido")
                        
            except ImportError:
                resultado["observacoes"].append("PyMuPDF não disponível - análise de conteúdo limitada")
            except Exception as e:
                nao_conformidades.append(f"Erro na análise do conteúdo PDF: {str(e)}")
            
            # Verificar data de modificação do arquivo (freshness)
            data_modificacao = datetime.fromtimestamp(caminho.stat().st_mtime)
            dias_desde_modificacao = (datetime.now() - data_modificacao).days
            
            resultado["observacoes"].append(f"Última modificação: {data_modificacao.strftime('%d/%m/%Y %H:%M')}")
            
            if dias_desde_modificacao <= 365:  # Arquivo modificado no último ano
                conformidades.append("Arquivo relativamente recente")
            else:
                resultado["observacoes"].append(f"Arquivo modificado há {dias_desde_modificacao} dias - verificar se está atualizado")
            
            # Atualizar listas de conformidade
            resultado["conformidades"].extend(conformidades)
            resultado["nao_conformidades"].extend(nao_conformidades)
            
            # Determinar status final
            if nao_conformidades:
                if any("erro" in nc.lower() or "corrompido" in nc.lower() for nc in nao_conformidades):
                    resultado["status"] = "ERRO"
                elif any("não identificada" in nc.lower() for nc in nao_conformidades):
                    resultado["status"] = "INCONCLUSIVO"
                else:
                    resultado["status"] = "NAO_CONFORME"
            else:
                resultado["status"] = "CONFORME"
            
            resultado["observacoes"].append(f"Análise RACT concluída - Status: {resultado['status']}")
            #log_info(f"Análise RACT concluída - Status: {resultado['status']}")
            
        except Exception as e:
            log_erro(f"Erro durante análise de RACT: {str(e)}")
            resultado["status"] = "ERRO"
            resultado["nao_conformidades"].append(f"Erro crítico na análise: {str(e)}")
        
        return resultado
    
    def _analisar_keywords(self, caminho: Path, resultado: Dict) -> Dict:
        """Análise específica para Manual do Produto."""
        try:
            #log_info(f"Iniciando análise de Manual: {caminho.name}")
            
            # Verificações básicas do arquivo
            if not caminho.exists():
                resultado["status"] = "ERRO"
                resultado["nao_conformidades"].append("Arquivo de Manual não encontrado")
                return resultado
            
            conformidades = []
            nao_conformidades = []
          
            # Análise de conteúdo do PDF
            try:                
                with fitz.open(caminho) as doc:
                    total_paginas = len(doc)
                    resultado["observacoes"].append(f"Total de páginas: {total_paginas}")
                    
                    if total_paginas == 0:
                        nao_conformidades.append("Manual vazio ou corrompido")
                        return resultado
                    
                    # Extrair texto completo do manual para análise
                    texto_completo = ""
                    for pagina_num in range(total_paginas):  # Analisar todas as páginas
                        texto_completo += str(doc[pagina_num].get_text()).lower() + "\n"
                    
                    # Usar palavras-chave definidas em const.py
                    palavras_chave_manual = list(PALAVRAS_CHAVE_MANUAL_NORMALIZADAS.keys())
                    palavras_chave_manual = sorted(palavras_chave_manual)                    
                    
                    # Contar ocorrências de cada palavra-chave
                    palavras_encontradas = {}
                    palavras_nao_encontradas = []
                    palavras_encontradas_com_normas = {}  # Nova estrutura para palavras com normas
                    palavras_evidencias = {}
                    
                    for palavra in palavras_chave_manual:
                        ignorar_espacos = _ignora_espacos(palavra)
                        contador = contar_ocorrencias_palavra_chave(texto_completo, palavra, ignorar_espacos)
                        if contador > 0:
                            palavras_encontradas[palavra] = contador
                            palavras_evidencias[palavra] = extrair_contextos_palavra_chave(
                                texto_completo, palavra, ignorar_espacos=ignorar_espacos)
                            # Buscar normas associadas à palavra
                            regra_palavra = PALAVRAS_CHAVE_MANUAL_NORMALIZADAS.get(palavra, {})
                            normas_associadas = regra_palavra.get("normas", [])
                            efeito_regra = str(regra_palavra.get("efeito", "aplica")).lower()
                            if normas_associadas:
                                palavras_encontradas_com_normas[palavra] = {
                                    "contador": contador,
                                    "normas": normas_associadas,
                                    "efeito": efeito_regra
                                }
                        else:
                            palavras_nao_encontradas.append(palavra)
                    
                    # Armazenar resultados da análise de palavras-chave nos dados extraídos
                    resultado["dados_extraidos"] = {
                        "palavras_encontradas": palavras_encontradas,
                        "palavras_nao_encontradas": palavras_nao_encontradas,
                        "palavras_encontradas_com_normas": palavras_encontradas_com_normas,
                        "palavras_evidencias": palavras_evidencias
                    }
                        
            except ImportError:
                resultado["observacoes"].append("PyMuPDF não disponível - análise de conteúdo limitada")
            except Exception as e:
                nao_conformidades.append(f"Erro na análise do conteúdo: {str(e)}")
            
            # Verificar data do arquivo
            data_modificacao = datetime.fromtimestamp(caminho.stat().st_mtime)
            resultado["observacoes"].append(f"Data de modificação: {data_modificacao.strftime('%d/%m/%Y %H:%M')}")
            
            # Atualizar listas
            resultado["conformidades"].extend(conformidades)
            resultado["nao_conformidades"].extend(nao_conformidades)
            
            # Determinar status final - apenas para erros técnicos
            if any("erro" in nc.lower() or "corrompido" in nc.lower() for nc in nao_conformidades):
                resultado["status"] = "ERRO"
            else:
                resultado["status"] = "PROCESSADO"  # Status neutro para manuais
            
            resultado["observacoes"].append(f"Análise de Manual concluída - Status: {resultado['status']}")
            #log_info(f"Análise de Manual concluída  {resultado['status']}")
            
        except Exception as e:
            log_erro(f"Erro durante análise de Manual: {str(e)}")
            resultado["status"] = "ERRO"
            resultado["nao_conformidades"].append(f"Erro crítico na análise: {str(e)}")
        
        return resultado
    
    def _analisar_relatorio_ensaio(self, caminho: Path, resultado: Dict) -> Dict:
        """
        Análise específica para Relatório de Ensaio.
        
        Verifica:
        1. Presença do solicitante ou fabricante no PDF
        2. Presença do laboratório (nome e/ou CNPJ) no PDF
        3. Lista as normas encontradas no PDF
        
        Args:
            caminho: Path para o arquivo PDF do relatório
            resultado: Dicionário com resultado parcial da análise
            
        Returns:
            Dict atualizado com resultado da análise
        """
        try:
            # Instanciar CCTAnalyzer integrado para extração de PDF
            utils_dir = Path(__file__).parent.parent / UTILS_DIR
            cct_analyzer = CCTAnalyzerIntegrado(utils_dir)
            
            # Extrai o conteúdo do PDF usando extract_pdf_content (com fallback OCR)
            texto_pdf = cct_analyzer.extract_pdf_content(caminho)
            if not texto_pdf:
                resultado["status"] = STATUS_ERRO
                resultado["observacoes"].append("❌ Erro ao extrair conteúdo do PDF")
                return resultado
            
            # Normaliza o texto para comparações
            texto_normalizado = normalizar(texto_pdf)
            
            # Obtém dados do JSON do requerimento
            nome_requerimento = str(caminho.parent.name)
            pasta_requerimento = caminho.parent
            dados_req = self._processar_dados_requerimento_json(nome_requerimento, pasta_requerimento)
            
            if not dados_req:
                resultado["observacoes"].append("⚠️ Dados do requerimento não disponíveis para validação")
            
            problemas = []
            
            # ============================================
            # 1. VERIFICAR SOLICITANTE OU FABRICANTE
            # ============================================
            solicitante_encontrado = False
            fabricante_encontrado = False            
            if dados_req:
                dados_solicitante = dados_req.get("solicitante", {})
                dados_fabricante = dados_req.get("fabricante", {})                
                # Verifica solicitante
                if dados_solicitante and isinstance(dados_solicitante, dict):
                    nome_solicitante = dados_solicitante.get("Nome", "")
                    cnpj_solicitante = dados_solicitante.get("CPF/CNPJ", "")                   
                    if nome_solicitante:
                        nome_normalizado = normalizar(nome_solicitante)
                        contador = texto_normalizado.count(nome_normalizado)
                        if contador > 0:
                            solicitante_encontrado = True
                
                # Se solicitante não foi encontrado, verifica fabricante
                if not solicitante_encontrado and dados_fabricante and isinstance(dados_fabricante, dict):
                    nome_fabricante = dados_fabricante.get("Nome", "")                    
                    if nome_fabricante:
                        nome_normalizado = normalizar(nome_fabricante)
                        contador = texto_normalizado.count(nome_normalizado)
                        if contador > 0:
                            fabricante_encontrado = True
                
                # Avaliação da verificação de solicitante/fabricante
                if solicitante_encontrado:
                    resultado["observacoes"].append("✅ Solicitante identificado no relatório")
                elif fabricante_encontrado:
                    resultado["observacoes"].append("✅ Fabricante identificado no relatório")
                else:
                    problemas.append("Solicitante/Fabricante não identificado no relatório")
                    resultado["observacoes"].append("❌ Nem solicitante nem fabricante foram identificados no relatório")
            
            # ============================================
            # 2. VERIFICAR LABORATÓRIO
            # ============================================
            laboratorio_encontrado = False
            
            if dados_req:
                dados_lab = dados_req.get("lab", {})
                
                if dados_lab and isinstance(dados_lab, dict):
                    nome_lab = dados_lab.get("Nome", "")                    
                    # Verifica nome do laboratório
                    if nome_lab:
                        nome_lab_normalizado = normalizar(nome_lab)
                        contador = texto_normalizado.count(nome_lab_normalizado)
                        if contador > 0:
                            laboratorio_encontrado = True
                            resultado["observacoes"].append(f"✅ Laboratório identificado (nome): {nome_lab}")                                                    
                    
                    if not laboratorio_encontrado:
                        problemas.append(f"Laboratório não identificado: {nome_lab}")
                        resultado["observacoes"].append(f"❌ Laboratório não identificado no relatório")
                else:
                    resultado["observacoes"].append("⚠️ Dados do laboratório não disponíveis no JSON")
            
            # ============================================
            # 3. VERIFICAR MODELOS
            # ============================================
            modelo_encontrado = False
            modelos_identificados = []
            lista_modelos = []  # Inicializar sempre
            
            if dados_req:
                # Buscar modelos nos dados do requerimento - pode estar no nível raiz ou dentro de "requerimento"
                modelos_req = dados_req.get("modelos", "")
                if not modelos_req and "requerimento" in dados_req:
                    modelos_req = dados_req["requerimento"].get("modelos", "")
                
                if modelos_req and isinstance(modelos_req, str):
                    # Se modelos vem como string, separar por vírgulas ou outros delimitadores
                    lista_modelos = [m.strip() for m in re.split(r'[,;/\|]', modelos_req) if m.strip()]
                elif modelos_req and isinstance(modelos_req, list):
                    # Se modelos já é uma lista
                    lista_modelos = [str(m).strip() for m in modelos_req if str(m).strip()]
                
                # Verificar cada modelo no texto do relatório
                for modelo in lista_modelos:
                    if modelo:  # Verificar se não é string vazia
                        modelo_normalizado = normalizar(modelo)
                        contador = texto_normalizado.count(modelo_normalizado)
                        if contador > 0:
                            modelo_encontrado = True
                            modelos_identificados.append(modelo)
                
                # Avaliar resultado da verificação de modelos
                if modelo_encontrado:
                    resultado["observacoes"].append(f"✅ Modelo(s) identificado(s) no relatório: {', '.join(modelos_identificados)}")
                else:
                    if lista_modelos:
                        problemas.append(f"Modelo(s) não identificado(s) no relatório: {', '.join(lista_modelos)}")
                        resultado["observacoes"].append(f"❌ Nenhum modelo identificado no relatório (esperados: {', '.join(lista_modelos)})")
                    else:
                        resultado["observacoes"].append("⚠️ Nenhum modelo especificado no requerimento para validação")
            else:
                resultado["observacoes"].append("⚠️ Dados do requerimento não disponíveis para validação de modelos")
            
            # ============================================
            # 3. LISTAR NORMAS VERIFICADAS (Atos e Resoluções ANATEL)
            # ============================================
            ''' normas_verificadas = self._extract_normas_from_ract(texto_pdf)
            
            if normas_verificadas:
                resultado["observacoes"].append(f"📋 Normas verificadas: {', '.join(sorted(set(normas_verificadas)))}")
                resultado["normas_verificadas"] = sorted(set(normas_verificadas))
            else:
                resultado["observacoes"].append("⚠️ Nenhuma norma ANATEL identificada no relatório")
                resultado["normas_verificadas"] = []'''
            
            # ============================================
            # ARMAZENAR DADOS EXTRAÍDOS PARA RELATÓRIO
            # ============================================
            resultado["dados_extraidos"] = {
                "solicitante_identificado": solicitante_encontrado,
                "fabricante_identificado": fabricante_encontrado,
                "laboratorio_identificado": laboratorio_encontrado,
                "modelo_identificado": modelo_encontrado,
                "nome_solicitante": dados_req.get("solicitante", {}).get("Nome", "") if dados_req else "",
                "nome_fabricante": dados_req.get("fabricante", {}).get("Nome", "") if dados_req else "",
                "nome_laboratorio": dados_req.get("lab", {}).get("Nome", "") if dados_req else "",
                "modelos_esperados": lista_modelos,
                "modelos_identificados": modelos_identificados
            }
            
            # ============================================
            # DEFINIR STATUS FINAL
            # ============================================
            if problemas:
                resultado["status"] = STATUS_NAO_CONFORME
                resultado["problemas"] = problemas
            else:
                resultado["status"] = STATUS_CONFORME
                resultado["observacoes"].append("✅ Relatório de Ensaio validado com sucesso")
            
            return resultado
            
        except Exception as e:
            log_erro(f"Erro ao analisar relatório de ensaio {caminho.name}: {str(e)}")
            resultado["status"] = STATUS_ERRO
            resultado["observacoes"].append(f"❌ Erro durante análise: {str(e)[:100]}")
            return resultado
    
    def _analisar_art(self, caminho: Path, resultado: Dict) -> Dict:
        """Análise específica para ART."""
        resultado["observacoes"].append("Análise de ART: Verificando responsáveis técnicos")
        resultado["status"] = "CONFORME"  # Temporário
        return resultado
    
    def _analisar_fotos(self, caminho: Path, resultado: Dict) -> Dict:
        """Análise específica para Fotos do Produto."""
        resultado["observacoes"].append("Análise de Fotos: Verificando conformidade visual")
        with fitz.open(caminho) as pdf:
            texto = "\n".join(str(pagina.get_text("text")) for pagina in pdf)
            if _pdf_requer_ocr(pdf):
                texto_ocr = extract_pdf_content_from_ocr(caminho)
                if texto_ocr:
                    texto = texto_ocr

        texto_normalizado = re.sub(r"\s+", "", normalizar(texto))
        frase_normalizada = re.sub(
            r"\s+",
            "",
            normalizar(FRASE_PRODUTO_NAO_ACABADO_FOTOS_EXTERNAS)
        )
        resultado["dados_extraidos"] = {
            "contem_frase_produto_nao_acabado_ato4083":
                frase_normalizada in texto_normalizado
        }
        resultado["status"] = "CONFORME"  # Temporário
        return resultado
    
    def _analisar_contrato_social(self, caminho: Path, resultado: Dict) -> Dict:
        """Análise específica para Contrato Social."""
        resultado["observacoes"].append("Análise de Contrato Social: Validando dados da empresa")
        resultado["status"] = "CONFORME"  # Temporário
        return resultado

    def _extrair_modelos_json(self, dados_requerimento: Optional[Dict]) -> List[str]:
        """Extrai modelos declarados no JSON do requerimento, preservando a grafia."""
        if not isinstance(dados_requerimento, dict):
            return []

        modelos = dados_requerimento.get("modelos")
        if modelos is None:
            requerimento = dados_requerimento.get("requerimento", {})
            modelos = requerimento.get("modelos") if isinstance(requerimento, dict) else None

        if isinstance(modelos, str):
            valores = re.split(r"[,;/|]", modelos)
        elif isinstance(modelos, list):
            valores = []
            for modelo in modelos:
                if isinstance(modelo, dict):
                    valor = modelo.get(CERTIFICA_CABECALHO_MODELOS)
                    if valor is None:
                        valor = modelo.get("Modelo")
                    if valor is not None:
                        valores.append(valor)
                else:
                    valores.append(modelo)
        else:
            valores = []

        modelos_unicos = []
        for valor in valores:
            modelo = str(valor).strip() if valor is not None else ""
            if modelo and modelo not in modelos_unicos:
                modelos_unicos.append(modelo)
        return modelos_unicos

    @staticmethod
    def _tem_nome_comercial_invalido(dados_requerimento: Optional[Dict]) -> bool:
        if not isinstance(dados_requerimento, dict):
            return False

        modelos = dados_requerimento.get("modelos")
        if modelos is None:
            requerimento = dados_requerimento.get("requerimento", {})
            modelos = requerimento.get("modelos") if isinstance(requerimento, dict) else None
        if not isinstance(modelos, list):
            return False

        for modelo in modelos:
            if not isinstance(modelo, dict):
                continue
            nome_comercial = modelo.get("Nome Comercial")
            if nome_comercial is None:
                continue
            nome_normalizado = re.sub(r"\s+", " ", str(nome_comercial)).strip().casefold()
            nome_sem_acentos = "".join(
                caractere
                for caractere in unicodedata.normalize("NFD", nome_normalizado)
                if not unicodedata.combining(caractere)
            )
            if nome_sem_acentos in {"-", "n/a", "na", "nao aplicavel"}:
                return True
        return False

    @staticmethod
    def _contem_medicao_sar(valor: object) -> bool:
        def valor_numerico(conteudo: object) -> bool:
            if isinstance(conteudo, bool):
                return False
            if isinstance(conteudo, int):
                return True
            if isinstance(conteudo, float):
                return math.isfinite(conteudo)
            if isinstance(conteudo, str):
                valor_convertido = parse_valor_numerico(conteudo)
                return valor_convertido is not None and math.isfinite(valor_convertido)
            return False

        if isinstance(valor, dict):
            return any(
                (
                    chave in CAMPOS_SAR
                    and valor_numerico(conteudo)
                )
                or AnalisadorRequerimentos._contem_medicao_sar(conteudo)
                for chave, conteudo in valor.items()
            )
        if isinstance(valor, list):
            return any(
                AnalisadorRequerimentos._contem_medicao_sar(item)
                for item in valor
            )
        return False

    @staticmethod
    def _tabela_para_registros(tabela: Any) -> List[Any]:
        """Converte uma tabela [cabeçalho, linha, ...] em lista de dicts; aceita lista de dicts já pronta."""
        if not isinstance(tabela, list) or not tabela:
            return []
        if all(isinstance(linha, dict) for linha in tabela):
            return tabela
        cabecalho = tabela[0]
        if not isinstance(cabecalho, list):
            return []
        # Nos subprodutos a coluna se chama "Tecnologias"; o modelo de validação usa "Tecnologia"
        cabecalho = ["Tecnologia" if coluna == "Tecnologias" else coluna for coluna in cabecalho]
        return [
            dict(zip(cabecalho, linha)) if isinstance(linha, list) and len(linha) == len(cabecalho) else linha
            for linha in tabela[1:]
            if linha and (not isinstance(linha, list) or any(linha))
        ]

    def _validar_caracteristicas_tecnicas_json(
        self,
        dados_requerimento: Optional[Dict],
        normas_referencia: Set[str]
    ) -> List[Dict[str, str]]:
        """Aplica as regras de uso de faixa às características técnicas dos produtos do JSON."""
        caracteristicas = (
            dados_requerimento.get("caracteristicas_tecnicas")
            if isinstance(dados_requerimento, dict) else None
        )
        produtos = caracteristicas.get("produtos") if isinstance(caracteristicas, dict) else None
        if produtos is None and isinstance(dados_requerimento, dict):
            # Mantém a análise de requerimentos gravados antes da mudança de estrutura.
            subprodutos = caracteristicas.get("subprodutos") if isinstance(caracteristicas, dict) else None
            frequencias = dados_requerimento.get("frequencias")
            if isinstance(subprodutos, list) or isinstance(frequencias, list):
                produto = dados_requerimento.get("produto")
                nome_produto = (
                    str(produto.get("Produto") or "").strip()
                    if isinstance(produto, dict) else ""
                )
                produtos = [{
                    "nome": nome_produto or "Produto principal",
                    "caracteristicas": frequencias if isinstance(frequencias, list) else [],
                }]
                if isinstance(subprodutos, list):
                    produtos.extend(subprodutos)

        if not isinstance(produtos, list) or not produtos:
            return [{
                "faixa": "Características técnicas",
                "valida": "inconclusiva",
                "mensagem": "Nenhuma característica técnica de produto foi encontrada no JSON do requerimento."
            }]

        resultado = []
        for indice, produto in enumerate(produtos, 1):
            nome = str(produto.get("nome", "")).strip() if isinstance(produto, dict) else ""
            nome = nome or f"Produto {indice}"
            registros = (
                self._tabela_para_registros(produto.get("caracteristicas"))
                if isinstance(produto, dict) else []
            )
            if not registros:
                resultado.append({
                    "faixa": nome,
                    "valida": "inconclusiva",
                    "mensagem": "Nenhuma característica técnica válida foi encontrada para o produto."
                })
                continue
            for validacao in self._validar_registros_frequencia(registros, normas_referencia):
                validacao["faixa"] = f"{nome} ({validacao['faixa']})"
                resultado.append(validacao)
        return resultado

    @staticmethod
    def _formatar_validacao_frequencias_latex(validacoes: List[Dict[str, str]]) -> str:
        """Lista em LaTeX as validações não conformes; 'OK' quando todas foram validadas."""
        nao_conformes = [validacao for validacao in validacoes if validacao["valida"] != "sim"]
        if not nao_conformes:
            return "\\textcolor{blue}{OK}\n"
        latex = "\n\\begin{itemize}\n"
        for validacao in nao_conformes:
            faixa = escapar_latex(validacao["faixa"])
            mensagem = escapar_latex(validacao["mensagem"])
            latex += f"    \\item {faixa}: \\textcolor{{red}}{{Não conforme}} -- {mensagem}\n"
        return latex + "\\end{itemize}\n"

    def _validar_registros_frequencia(
        self,
        frequencias: List[Any],
        normas_referencia: Set[str]
    ) -> List[Dict[str, str]]:
        """Valida cada registro de frequência pelas regras de uso de faixa."""
        resultado = []
        for indice, frequencia in enumerate(frequencias, 1):
            if not isinstance(frequencia, dict):
                resultado.append({
                    "faixa": f"Frequência {indice}",
                    "valida": "não",
                    "mensagem": "Registro de frequência inválido no JSON."
                })
                continue

            frequencia_validacao = dict(frequencia)
            faixa = frequencia.get("Faixa de Frequências Tx (MHz)")
            if faixa is None:
                faixa = frequencia.get(CERTIFICA_CABECALHO_FREQUENCIAS)
                if faixa is not None:
                    frequencia_validacao["Faixa de Frequências Tx (MHz)"] = faixa
            faixa_exibicao = str(faixa).strip() if faixa is not None else f"Frequência {indice}"

            try:
                HomologacaoProduto.model_validate({
                    "normas_referencia": sorted(normas_referencia),
                    "frequencias": [frequencia_validacao]
                }, context={"normas_referencia": sorted(normas_referencia)})
            except ValidationError as erro:
                mensagens = [
                    item["msg"].removeprefix("Value error, ")
                    for item in erro.errors()
                ]
                resultado.append({
                    "faixa": faixa_exibicao,
                    "valida": "não",
                    "mensagem": "; ".join(mensagens)
                })
            else:
                resultado.append({
                    "faixa": faixa_exibicao,
                    "valida": "sim",
                    "mensagem": "Frequência validada pelas regras de uso de faixa."
                })

        return resultado

    def _processar_dados_requerimento_json(self, nome_requerimento: str, pasta_requerimento: Path) -> Optional[Dict]:
        """
        Busca e processa o arquivo JSON do requerimento para extrair informações
        e atualizar o arquivo ocds.json se necessário.
        
        Args:
            nome_requerimento: Nome do requerimento (ex: "2025.12345")
            pasta_requerimento: Path para a pasta do requerimento
            
        Returns:
            Dict com dados do requerimento ou None se não encontrado
        """
        if nome_requerimento.startswith("_"):
            arquivo_json_req = pasta_requerimento / f"{nome_requerimento[1:]}.json"
        else:
            arquivo_json_req = pasta_requerimento / f"{nome_requerimento}.json"
        
        if not arquivo_json_req.exists():
            log_info(f"Arquivo JSON do requerimento não encontrado: {arquivo_json_req.name}")
            return None
            
        try:
            # Carregar dados do arquivo JSON do requerimento
            dados_req = carregar_json(arquivo_json_req)
            if not dados_req or not isinstance(dados_req, dict):
                log_erro(f"Arquivo JSON inválido ou vazio: {arquivo_json_req.name}")
                return None
                
            #log_info(f"Dados do requerimento carregados de: {arquivo_json_req.name}")
            
            # Validação crítica dos dados essenciais do JSON
            from core.utils import validar_dados_criticos
            requerimento_json = dados_req.get("requerimento")
            dados_ocd = dados_req.get("ocd")
            dados_lab = dados_req.get("lab")
            dados_fabricante = dados_req.get("fabricante")
            dados_solicitante = dados_req.get("solicitante")
            
            # Validar apenas os dados que estão presentes no JSON
            validar_dados_criticos(
                requerimento_json=requerimento_json,
                dados_ocd=dados_ocd,
                dados_lab=dados_lab,
                dados_fabricante=dados_fabricante,
                dados_solicitante=dados_solicitante,
                nome_requerimento=nome_requerimento,
                contexto="análise de documentos"
            )
            
      
            return dados_req
            
        except Exception as e:
            log_erro(f"Erro ao processar arquivo JSON do requerimento {arquivo_json_req.name}: {str(e)}")
            return None

    def _completar_ocd_certifica(self, dados_req: Optional[Dict]) -> None:
        """
        O Certifica não informa Nome/CNPJ do OCD no JSON. Quando ausentes, identifica o OCD em
        ocds.json: a "sigla" deve constar em requerimento["num_cct"] ou o "email" em
        ocd["E-mail do Contato"] (texto normalizado; basta um dos dois).
        """
        if not dados_req or not isinstance(dados_req, dict) or not isinstance(self.ocds, list):
            return
        dados_ocd = dados_req.get("ocd")
        if not isinstance(dados_ocd, dict) or dados_ocd.get("CNPJ"):
            return

        num_cct = normalizar(str((dados_req.get("requerimento") or {}).get("num_cct", "")))
        email_contato = normalizar(str(dados_ocd.get("E-mail do Contato", "")))

        for ocd in self.ocds:
            sigla = normalizar(str(ocd.get("sigla", "")).strip())
            email = normalizar(str(ocd.get("email", "")).strip())
            achou_sigla = bool(sigla) and sigla in num_cct
            achou_email = bool(email) and email in email_contato
            if (achou_sigla or achou_email) and ocd.get("cnpj"):
                dados_ocd["CNPJ"] = ocd["cnpj"]
                dados_ocd["Nome"] = ocd.get("nome", "")
                return

    def _atualizar_ocds_json(self, dados_ocd: Dict) -> None:
        """
        Atualiza o arquivo utils/ocds.json com informações do OCD se a data for mais recente.
        
        Args:
            dados_ocd: Dicionário com dados do OCD do requerimento
        """
        try:
            cnpj_ocd = dados_ocd.get("CNPJ")
            nome_ocd = dados_ocd.get("Nome")
            data_certificado = dados_ocd.get("Data do Certificado")
            
            if not cnpj_ocd or not nome_ocd:
                log_info("CNPJ ou Nome do OCD não informados, ignorando atualização")
                return
                
            # Carregar arquivo ocds.json atual
            ocds_file = Path(__file__).parent.parent / UTILS_DIR / "ocds.json"
            dados_ocds = carregar_json(ocds_file)
            
            if not dados_ocds or not isinstance(dados_ocds, list):
                log_erro("Falha ao carregar arquivo ocds.json ou formato inválido")
                return
                
            # Procurar registro existente por CNPJ
            registro_encontrado = False
            data_req_datetime = None
            dados_modificados = False  # Controle para indicar se houve modificação
            
            # Converter data do certificado para comparação
            if data_certificado:
                try:
                    data_req_datetime = datetime.strptime(data_certificado, "%d/%m/%Y")
                except ValueError:
                    log_erro(f"Formato de data inválido no OCD: {data_certificado}")
                    return
            
            for i, ocd in enumerate(dados_ocds):
                if ocd.get("cnpj") == cnpj_ocd:
                    registro_encontrado = True
                    
                    # Verificar se a data do requerimento é mais recente
                    data_atual_str = ocd.get("data_atualizacao")
                    if data_atual_str and data_req_datetime:
                        try:
                            data_atual_datetime = datetime.strptime(data_atual_str, "%d/%m/%Y")
                            
                            if data_req_datetime > data_atual_datetime:
                                # Atualizar registro existente
                                dados_ocds[i]["nome"] = nome_ocd
                                dados_ocds[i]["data_atualizacao"] = data_certificado
                                dados_modificados = True
                                #log_info(f"OCD atualizado: {nome_ocd} (CNPJ: {cnpj_ocd}) - Nova data: {data_certificado}")
                            #else:
                            #    log_info(f"OCD não atualizado: data atual ({data_atual_str}) é mais recente que a do requerimento ({data_certificado})")
                                
                        except ValueError:
                            log_erro(f"Erro ao converter data de atualização: {data_atual_str}")
                    break
            
            # Se não encontrou o registro, adicionar novo
            if not registro_encontrado and data_certificado:
                novo_registro = {
                    "cnpj": cnpj_ocd,
                    "nome": nome_ocd,
                    "sigla": "",
                    "email": "",
                    "data_atualizacao": data_certificado
                }
                dados_ocds.append(novo_registro)
                #dados_modificados = True
                log_info(f"Novo OCD adicionado: {nome_ocd} (CNPJ: {cnpj_ocd})")
            
            # Salvar arquivo somente se houve modificação
            #if dados_modificados:
                # inutil = salvar_json(dados_ocds, ocds_file)
                #if salvar_json(dados_ocds, ocds_file):
                    #log_info("Arquivo ocds.json atualizado com sucesso")
                #else:
                    #log_erro("Falha ao salvar arquivo ocds.json atualizado")
            #else:
            #    log_info("Nenhuma modificação necessária no arquivo ocds.json")
                
        except Exception as e:
            log_erro(f"Erro ao atualizar ocds.json: {str(e)}")

    def _analisar_requerimento_individual(self, nome_requerimento: str) -> Dict:
        """Analisa todos os documentos de um requerimento específico."""
        tempo_inicio_req = datetime.now()
        #log_info(f"Iniciando análise do requerimento: {nome_requerimento}")
        pasta_req = "_" + nome_requerimento
        pasta_requerimento = self.pasta_base / pasta_req
        if not pasta_requerimento.exists():
            log_erro(f"Pasta do requerimento não encontrada: {pasta_requerimento}")
            return {}
        
        # Processar arquivo JSON do requerimento e atualizar OCDS se necessário
        dados_req_json = self._processar_dados_requerimento_json(nome_requerimento, pasta_requerimento)
        self._completar_ocd_certifica(dados_req_json)

        #if dados_req_json is not None:
        #    log_info(f"OCD: {dados_req_json['ocd']}")

        resultado_requerimento = {
            "numero_requerimento": nome_requerimento,
            "timestamp_analise": datetime.now().isoformat(),
            "tempo_inicio_analise": tempo_inicio_req.isoformat(),
            "documentos_analisados": [],
            "resumo_status": {
                "CONFORME": 0,
                "NAO_CONFORME": 0,
                "INCONCLUSIVO": 0,
                "ERRO": 0,
                "PROCESSADO": 0
            },
            "observacoes_gerais": [],
            "dados_requerimento": dados_req_json  # Adicionar dados do JSON se disponível
        }
        
        # Buscar todos os arquivos PDF na pasta
        arquivos_pdf = list(pasta_requerimento.glob(GLOB_PDF))
        tipo_reaproveitamento = normalizar(CERTIFICA_TIPO_ANEXO_REAPROVEITAMENTO)

        if not arquivos_pdf:
            resultado_requerimento["observacoes_gerais"].append("Nenhum arquivo PDF encontrado")
            return resultado_requerimento

        resultado_requerimento["possui_anexo_reaproveitamento"] = any(
            tipo_reaproveitamento in normalizar(arquivo.name)
            for arquivo in arquivos_pdf
        )
        
        log_info(f"Encontrados {len(arquivos_pdf)} arquivos PDF passíveis de análise")

        # Selecionar os documentos mais recentes para CCT, RACT e Fotos Externas.
        docs_mais_recentes: Dict[
            str, Optional[Tuple[Path, str, datetime, Optional[datetime]]]
        ] = {
            TIPO_CCT: None,
            TIPO_RACT: None,
            TIPO_FOTOS_EXTERNAS: None
        }
        docs_demais_tipos: List[Tuple[Path, str, datetime]] = []

        for arquivo in arquivos_pdf:
            tipo_doc, data_doc = self._determinar_tipo_documento(arquivo.name)

            if tipo_doc not in docs_mais_recentes:
                continue

            data_conteudo = (
                self._extrair_data_mais_recente_pdf(arquivo)
                if tipo_doc in (TIPO_CCT, TIPO_RACT)
                else None
            )
            atual = docs_mais_recentes[tipo_doc]
            chave_candidata = _chave_selecao_documento(
                tipo_doc, data_conteudo, data_doc
            )
            chave_atual = (
                _chave_selecao_documento(tipo_doc, atual[3], atual[2])
                if atual is not None
                else None
            )
            if atual is None:
                docs_mais_recentes[tipo_doc] = (
                    arquivo, tipo_doc, data_doc, data_conteudo
                )
            elif chave_candidata > chave_atual:
                docs_mais_recentes[tipo_doc] = (
                    arquivo, tipo_doc, data_doc, data_conteudo
                )

        docs_para_processar = list(docs_demais_tipos)
        for tipo_doc in [TIPO_CCT, TIPO_RACT, TIPO_FOTOS_EXTERNAS]:
            doc_recente = docs_mais_recentes[tipo_doc]
            if doc_recente is not None:
                arquivo, tipo, data_nome, _ = doc_recente
                docs_para_processar.append((arquivo, tipo, data_nome))

        for doc_info in docs_para_processar:
            arquivo, tipo_doc, _ = doc_info

            # Extrair dados do OCD do JSON do requerimento
            dados_ocd = dados_req_json.get('ocd', {}) if dados_req_json else {}
            resultado_doc = self._analisar_documento(
                arquivo, tipo_doc, dados_ocd, dados_req_json
            )
            resultado_requerimento["documentos_analisados"].append(resultado_doc)

            # Atualizar contadores de status
            status = resultado_doc["status"]
            if status in resultado_requerimento["resumo_status"]:
                resultado_requerimento["resumo_status"][status] += 1
        
        # Calcular tempo de análise do requerimento
        tempo_fim_req = datetime.now()
        tempo_analise_req = tempo_fim_req - tempo_inicio_req
        resultado_requerimento["tempo_fim_analise"] = tempo_fim_req.isoformat()
        resultado_requerimento["tempo_total_analise_segundos"] = tempo_analise_req.total_seconds()
        resultado_requerimento["tempo_total_analise_formatado"] = str(tempo_analise_req)#.split('.')[0]  # Remove microsegundos
        
        log_info(f"Análise do requerimento {nome_requerimento} concluída em {resultado_requerimento['tempo_total_analise_formatado']}")
        return resultado_requerimento
    
    def _obter_nome_completo_ocd(self, nome_ocd_extraido: str) -> str:
        """Obtém o nome completo do OCD consultando ocds.json."""
        if not nome_ocd_extraido or nome_ocd_extraido == 'N/A' or nome_ocd_extraido.startswith('[ERRO]'):
            return "OCD não identificado"
        
        try:
            ocds_file = Path(__file__).parent.parent / UTILS_DIR / "ocds.json"
            
            if not ocds_file.exists():
                return nome_ocd_extraido
            
            with open(ocds_file, 'r', encoding='utf-8') as f:
                ocds_data = json.load(f)
            
            # Normalizar o nome extraído para comparação
            nome_normalizado = nome_ocd_extraido.lower().strip()
            
            # Buscar por correspondência parcial no nome
            for ocd in ocds_data:
                nome_completo = ocd.get('nome', '')
                if nome_completo:
                    nome_completo_normalizado = nome_completo.lower().strip()
                    
                    # Verificar correspondências específicas primeiro
                    if nome_normalizado == nome_completo_normalizado:
                        return nome_completo
                    
                    # Verificar se o nome extraído está contido no nome completo
                    if nome_normalizado in nome_completo_normalizado:
                        return nome_completo
            
            # Segunda passada: buscar palavras-chave importantes (>= 4 caracteres)
            # apenas se não encontrou correspondência direta
            palavras_extraidas = [p for p in nome_normalizado.split() if len(p) >= 4]
            if palavras_extraidas:
                for ocd in ocds_data:
                    nome_completo = ocd.get('nome', '')
                    if nome_completo:
                        nome_completo_normalizado = nome_completo.lower().strip()
                        # Verificar se TODAS as palavras importantes estão presentes
                        if all(palavra in nome_completo_normalizado for palavra in palavras_extraidas):
                            return nome_completo
            
            # Se não encontrou correspondência, retorna o nome extraído
            return nome_ocd_extraido
            
        except Exception as e:
            log_erro(f"Erro ao consultar ocds.json: {str(e)}")
            return nome_ocd_extraido

    def _coletar_todas_palavras_chave_globais(self) -> Tuple[Set[str], Set[str]]:
        """
        Coleta todas as palavras-chave encontradas e não encontradas em todos os requerimentos.
        
        Returns:
            Tuple[Set[palavras_encontradas], Set[palavras_nao_encontradas]]
        """
        todas_palavras_encontradas = set()
        todas_palavras_nao_encontradas = set()
        
        try:
            for req in self.resultados_analise:
                documentos = req.get("documentos_analisados", [])
                for doc in documentos:
                    dados_extraidos = doc.get("dados_extraidos", {})
                    
                    # Coletar palavras encontradas
                    palavras_encontradas = dados_extraidos.get("palavras_encontradas", {})
                    todas_palavras_encontradas.update(palavras_encontradas.keys())
                    
                    # Coletar palavras não encontradas
                    palavras_nao_encontradas = dados_extraidos.get("palavras_nao_encontradas", [])
                    todas_palavras_nao_encontradas.update(palavras_nao_encontradas)
                    
        except Exception as e:
            log_erro(f"Erro ao coletar palavras-chave globais: {str(e)}")
        
        return todas_palavras_encontradas, todas_palavras_nao_encontradas

    def _coletar_equipamentos_unicos(self) -> Dict[str, Dict]:
        """Coleta todos os equipamentos únicos encontrados na análise."""
        equipamentos_unicos = {}
        
        for req in self.resultados_analise:
            documentos = req.get("documentos_analisados", [])
            for doc in documentos:
                dados_extraidos = doc.get("dados_extraidos", {})
                equipamentos = dados_extraidos.get("equipamentos", [])
                
                # equipamentos é uma lista de nomes (strings)
                for nome_equipamento in equipamentos:
                    if isinstance(nome_equipamento, str) and nome_equipamento.strip():
                        # Buscar o ID correspondente no arquivo equipamentos.json
                        eq_id = self._buscar_id_equipamento_por_nome(nome_equipamento)
                        if eq_id:
                            equipamentos_unicos[eq_id] = {
                                'nome': nome_equipamento,
                                'id': eq_id
                            }
        
        return equipamentos_unicos

    def _preparar_equipamentos_lista_relatorio(
        self, equipamentos_encontrados: List[str]
    ) -> Tuple[List[str], Dict[str, str]]:
        familias_por_nome = {
            equipamento.get("nome", "").strip().casefold(): equipamento
            for equipamento in self.familias_equipamentos
            if isinstance(equipamento, dict) and equipamento.get("nome")
        }
        familias_por_id = {
            equipamento.get("id"): equipamento
            for equipamento in self.familias_equipamentos
            if isinstance(equipamento, dict) and equipamento.get("id")
        }
        equipamentos_por_id = {
            equipamento.get("id"): equipamento
            for equipamento in self.equipamentos
            if isinstance(equipamento, dict) and equipamento.get("id")
        }

        equipamentos_unicos = {}
        for equipamento in equipamentos_encontrados:
            if not isinstance(equipamento, str) or not equipamento.strip():
                continue

            nome_equipamento = equipamento.strip()
            nome_normalizado = nome_equipamento.casefold()
            familia = familias_por_nome.get(nome_normalizado)
            equipamento_id = None

            if familia is None:
                equipamento_id = self._buscar_id_equipamento_por_nome(nome_equipamento)
                familia = familias_por_id.get(equipamento_id)

            equipamento_catalogado = equipamentos_por_id.get(equipamento_id)
            if familia:
                chave = ("familia", familia["id"])
                nome_exibicao = familia["nome"]
            elif equipamento_catalogado:
                chave = ("equipamento", equipamento_catalogado["nome"].strip().casefold())
                nome_exibicao = equipamento_catalogado["nome"]
            else:
                chave = ("nao_catalogado", nome_normalizado)
                nome_exibicao = nome_equipamento

            if chave not in equipamentos_unicos:
                equipamentos_unicos[chave] = {
                    "nome": nome_exibicao,
                    "aliases": set()
                }
            equipamentos_unicos[chave]["aliases"].add(nome_equipamento)

        nomes_equipamentos = []
        equipamentos_rotulos = {}
        for indice, equipamento in enumerate(equipamentos_unicos.values(), 1):
            nomes_equipamentos.append(equipamento["nome"])
            for alias in equipamento["aliases"]:
                equipamentos_rotulos[alias] = f"[E{indice}]"

        return nomes_equipamentos, equipamentos_rotulos

    def _buscar_id_equipamento_por_nome(self, nome_equipamento: str) -> Optional[str]:
        """Busca o ID de um equipamento pelo seu nome no arquivo equipamentos.json."""
        try:
            nome_normalizado = nome_equipamento.lower().strip()
            
            for equipamento in self.equipamentos:
                nome_json = equipamento.get('nome', '').lower().strip()
                if nome_normalizado == nome_json:
                    return equipamento.get('id')
                    
            # Se não encontrou correspondência exata, buscar por similaridade
            for equipamento in self.equipamentos:
                nome_json = equipamento.get('nome', '').lower().strip()
                # Verificar se o nome extraído está contido no nome do JSON ou vice-versa
                if (nome_normalizado in nome_json) or (nome_json in nome_normalizado):
                    return equipamento.get('id')
                    
            # Se ainda não encontrou, tentar buscar por palavras-chave significativas
            palavras_extraidas = [p for p in nome_normalizado.split() if len(p) >= 4]
            if palavras_extraidas:
                for equipamento in self.equipamentos:
                    nome_json = equipamento.get('nome', '').lower().strip()
                    if any(palavra in nome_json for palavra in palavras_extraidas):
                        return equipamento.get('id')
            
            log_erro(f"ID não encontrado para equipamento: {nome_equipamento}")
            return None
            
        except Exception as e:
            log_erro(f"Erro ao buscar ID do equipamento '{nome_equipamento}': {str(e)}")
            return None

    def _obter_requisitos_para_equipamento(self, equipamento_id: str) -> List[Dict]:
        """Obtém os requisitos legais aplicáveis para um equipamento específico."""
        requisitos = []
        
        try:
            # Buscar normas requeridas para o equipamento
            normas_requeridas = []
            for req in self.requisitos:
                if req.get('equipamento') == equipamento_id:
                    normas_requeridas = req.get('norma', [])
                    break
            
            # Para cada norma requerida, buscar os detalhes no arquivo normas.json
            for norma_id in normas_requeridas:
                for norma in self.normas:
                    if norma.get('id') == norma_id:
                        requisitos.append({
                            'id': norma.get('id', ''),
                            'nome': norma.get('nome', ''),
                            'descricao': norma.get('descricao', ''),
                            'url': norma.get('url', '')
                        })
                        break
        
        except Exception as e:
            log_erro(f"Erro ao obter requisitos para equipamento {equipamento_id}: {str(e)}")
        
        return requisitos

    def _coletar_normas_aplicaveis_requerimento(self, req_dados: Dict, tipo_documento: Optional[str] = None) -> Dict[str, List[str]]:
        """
        Coleta normas aplicáveis a um requerimento, mapeando origens (palavras-chave e equipamentos).
        Quando tipo_documento é informado, consolida apenas documentos daquele tipo.
        
        Returns:
            Dict[norma_id, List[motivadores]]
        """
        normas_aplicaveis = {}
        
        try:
            documentos = req_dados.get("documentos_analisados", [])
            
            # 1. Consolidar palavras-chave de todos os documentos (sem duplicatas)
            palavras_consolidadas = {}
            for doc in documentos:
                # Permite segregar os contadores por tipo de arquivo (ex.: RACT x CCT).
                if tipo_documento and doc.get("tipo") != tipo_documento:
                    continue

                dados_extraidos = doc.get("dados_extraidos", {})
                palavras_com_normas = dados_extraidos.get("palavras_encontradas_com_normas", {})
                
                for palavra, info in palavras_com_normas.items():
                    contador = info.get("contador", 0)
                    normas = info.get("normas", [])
                    efeito = str(info.get("efeito", "aplica")).lower()
                    
                    if palavra not in palavras_consolidadas:
                        palavras_consolidadas[palavra] = {"contador": 0, "normas": set(), "efeito": "aplica"}
                    
                    # Somar contadores de todos os documentos
                    palavras_consolidadas[palavra]["contador"] += contador
                    # Adicionar normas (set evita duplicatas)
                    palavras_consolidadas[palavra]["normas"].update(normas)
                    # Se qualquer ocorrência marcar desobrigação, a palavra consolida como desobriga.
                    if efeito == "desobriga":
                        palavras_consolidadas[palavra]["efeito"] = "desobriga"
            
            # Gerar motivadores para palavras-chave consolidadas
            normas_desobrigadas = {}
            for palavra, info in palavras_consolidadas.items():
                contador_total = info["contador"]
                normas = info["normas"]
                efeito = info.get("efeito", "aplica")
                
                for norma_id in normas:
                    motivador = f"{palavra} (x{contador_total})"
                    if efeito == "desobriga":
                        if norma_id not in normas_desobrigadas:
                            normas_desobrigadas[norma_id] = []
                        normas_desobrigadas[norma_id].append(motivador)
                    else:
                        if norma_id not in normas_aplicaveis:
                            normas_aplicaveis[norma_id] = []
                        # Exibir multiplicidade em todos os casos para manter rastreabilidade por tipo (x1, x2, ...).
                        normas_aplicaveis[norma_id].append(motivador)
            
            # 2. Coletar normas de tipos de equipamentos (sem duplicatas)
            # Regras de equipamento devem permanecer no escopo do requerimento,
            # independentemente do tipo (RACT/CCT), para manter consistência entre tabelas.
            equipamentos_encontrados = set()
            for doc in documentos:
                dados_extraidos = doc.get("dados_extraidos", {})
                equipamentos = dados_extraidos.get("equipamentos", [])
                for eq_nome in equipamentos:
                    eq_id = self._buscar_id_equipamento_por_nome(eq_nome)
                    if eq_id:
                        equipamentos_encontrados.add((eq_id, eq_nome))
            
            # Para cada equipamento, buscar suas normas
            for eq_id, eq_nome in equipamentos_encontrados:
                requisitos_eq = self._obter_requisitos_para_equipamento(eq_id)
                for req in requisitos_eq:
                    norma_id = req.get('id', '')
                    if norma_id:
                        if norma_id not in normas_aplicaveis:
                            normas_aplicaveis[norma_id] = []
                        # Evitar duplicatas de equipamentos
                        if eq_nome not in normas_aplicaveis[norma_id]:
                            normas_aplicaveis[norma_id].append(eq_nome)

            # Remove normas desobrigadas por palavras-chave, mesmo quando vieram de equipamento.
            for norma_id in normas_desobrigadas.keys():
                if norma_id in normas_aplicaveis:
                    normas_aplicaveis.pop(norma_id, None)
            
        except Exception as e:
            log_erro(f"Erro ao coletar normas aplicáveis: {str(e)}")
        
        return normas_aplicaveis

    def _coletar_normas_verificadas_requerimento(self, req_dados: Dict) -> Set[str]:
        """
        Coleta todas as normas que foram verificadas nos documentos do requerimento.
        Automaticamente inclui no arquivo normas.json as normas que não estiverem cadastradas.
        
        Returns:
            Set[norma_id] das normas que foram efetivamente verificadas
        """
        normas_verificadas = set()
        novas_normas = {}
        numero_requerimento = req_dados.get("numero_requerimento", "N/A")
        
        try:
            documentos = req_dados.get("documentos_analisados", [])
            
            # Criar set com IDs das normas já existentes para verificação rápida
            normas_existentes_ids = {norma['id'] for norma in self.normas}
            
            for doc in documentos:
                dados_extraidos = doc.get("dados_extraidos", {})
                normas_doc = dados_extraidos.get("normas_verificadas", [])
                
                # Adicionar todas as normas verificadas deste documento
                for norma_original in normas_doc:
                    if isinstance(norma_original, str) and norma_original.strip():
                        # Normalizar o ID da norma
                        norma_id = self._normalizar_id_norma(norma_original.strip())
                        
                        if norma_id:
                            normas_verificadas.add(norma_id)
                            
                            # Verificar se a norma não existe no arquivo normas.json
                            if norma_id not in normas_existentes_ids and norma_id not in novas_normas:
                                novas_normas[norma_id] = self._criar_entrada_norma(norma_id, numero_requerimento)
                                log_info(f"Nova norma identificada: {norma_id} (do requerimento {numero_requerimento})")
            
            # Atualizar arquivo normas.json se há normas novas
            if novas_normas:
                log_info(f"Atualizando normas.json com {len(novas_normas)} nova(s) norma(s) do requerimento {numero_requerimento}")
                if self._atualizar_arquivo_normas(novas_normas):
                    # Atualizar o set de normas existentes
                    normas_existentes_ids.update(novas_normas.keys())
                else:
                    log_erro(f"Falha ao atualizar normas.json com normas do requerimento {numero_requerimento}")
                    
        except Exception as e:
            log_erro(f"Erro ao coletar normas verificadas: {str(e)}")
        
        return normas_verificadas

    def _coletar_normas_verificadas_por_tipo(self, req_dados: Dict, tipo_documento: str) -> Set[str]:
        """
        Coleta as normas verificadas apenas para um tipo de documento (ex.: CCT, RACT).

        Returns:
            Set[norma_id] das normas verificadas para o tipo informado
        """
        normas_verificadas_tipo = set()

        try:
            documentos = req_dados.get("documentos_analisados", [])

            for doc in documentos:
                if doc.get("tipo") != tipo_documento:
                    continue

                dados_extraidos = doc.get("dados_extraidos", {})
                normas_doc = dados_extraidos.get("normas_verificadas", [])

                for norma_original in normas_doc:
                    if isinstance(norma_original, str) and norma_original.strip():
                        norma_id = self._normalizar_id_norma(norma_original.strip())
                        if norma_id:
                            normas_verificadas_tipo.add(norma_id)

        except Exception as e:
            log_erro(f"Erro ao coletar normas verificadas por tipo ({tipo_documento}): {str(e)}")

        return normas_verificadas_tipo

    def _coletar_normas_revogadas(
        self,
        normas_verificadas_por_tipo: Dict[str, Set[str]]
    ) -> List[str]:
        """Retorna nomes únicos de normas revogadas citadas no RACT ou no CCT."""
        normas_revogadas = {}
        for tipo_documento in (TIPO_RACT, TIPO_CCT):
            normas_tipo = normas_verificadas_por_tipo.get(tipo_documento.upper(), set())
            for norma_id in normas_tipo:
                detalhes_norma = self._obter_detalhes_norma(norma_id)
                status_norma = (detalhes_norma.get("status") or "").strip().casefold()
                nome_norma = (detalhes_norma.get("nome") or "").strip()

                # Cadastros provisórios não confirmam que a norma citada foi revogada.
                if (
                    status_norma in {"revogado", "revogada"}
                    and nome_norma
                    and not nome_norma.casefold().startswith("norma (")
                ):
                    normas_revogadas[norma_id] = nome_norma

        return sorted(normas_revogadas.values(), key=str.casefold)

    def _coletar_palavras_chave_consolidadas(self, req_dados: Dict) -> Tuple[Dict[str, int], List[str]]:
        """
        Coleta e consolida todas as palavras-chave encontradas e não encontradas nos documentos do requerimento.
        
        Returns:
            Tuple[Dict[palavra, total_ocorrencias], List[palavras_nao_encontradas]]
        """
        palavras_consolidadas = {}
        palavras_nao_encontradas_set = set()
        
        try:
            documentos = req_dados.get("documentos_analisados", [])
            
            for doc in documentos:
                dados_extraidos = doc.get("dados_extraidos", {})
                palavras_encontradas = dados_extraidos.get("palavras_encontradas", {})
                palavras_com_normas = dados_extraidos.get("palavras_encontradas_com_normas", {})
                palavras_nao_encontradas = dados_extraidos.get("palavras_nao_encontradas", [])
                
                # Somar ocorrências de cada palavra encontrada
                for palavra, contador in palavras_encontradas.items():
                    if palavra in palavras_consolidadas:
                        palavras_consolidadas[palavra] += contador
                    else:
                        palavras_consolidadas[palavra] = contador

                # Garante contabilização de palavras com efeito "desobriga" mesmo em dados legados
                # onde "palavras_encontradas" pode não ter sido preenchido corretamente.
                for palavra, info in palavras_com_normas.items():
                    efeito = str(info.get("efeito", "aplica")).lower()
                    contador = int(info.get("contador", 0) or 0)
                    if efeito == "desobriga" and contador > 0 and palavra not in palavras_encontradas:
                        if palavra in palavras_consolidadas:
                            palavras_consolidadas[palavra] += contador
                        else:
                            palavras_consolidadas[palavra] = contador
                
                # Coletar palavras não encontradas (usar set para evitar duplicatas)
                for palavra in palavras_nao_encontradas:
                    palavras_nao_encontradas_set.add(palavra)
                        
        except Exception as e:
            log_erro(f"Erro ao consolidar palavras-chave: {str(e)}")
        
        return palavras_consolidadas, sorted(list(palavras_nao_encontradas_set))

    def _indica_alteracao_homologacao(
        self,
        req_dados: Dict,
        palavras_consolidadas: Dict[str, int],
    ) -> bool:
        """Identifica indicação de alteração de homologação por palavra-chave ou anexo."""
        palavras_reaproveitamento = {
            normalizar("reaproveitar"),
            normalizar("reaproveitando"),
            normalizar("reutilizar"),
            normalizar("reutilizando"),
        }
        if palavras_reaproveitamento.intersection(palavras_consolidadas):
            return True

        return bool(req_dados.get("possui_anexo_reaproveitamento", False))

    def _normalizar_id_norma(self, norma_original: str) -> Optional[str]:
        """
        Converte uma norma encontrada para o formato de ID usado no normas.json
        
        Exemplos:
        - "Ato 1234" -> "ato1234"  
        - "Resolução 715" -> "resolucao715"
        - "ABNT NBR 7866" -> "abnt_nbr_7866"
        - "IEC 61300" -> "iec61300"
        """
        
        norma_clean = norma_original.strip()
        
        # Padrões para normalização
        patterns = [
            # Atos da ANATEL
            (r'(?:ato|act)\s*n?°?\s*(\d+)', r'ato\1'),
            
            # Resoluções da ANATEL
            (r'(?:resolução|resolution)\s*n?°?\s*(\d+)', r'resolucao\1'),
            
            # ABNT NBR
            (r'abnt\s+nbr\s+(\d+)(?:\:?\d{4})?', r'abnt_nbr_\1'),
            
            # IEC
            (r'iec\s+(\d+)(?:-\d+)?(?:\:?\d{4})?', r'iec\1'),
            
            # CISPR
            (r'cispr\s+(\d+)(?:\:?\d{4})?', r'cispr\1'),
            
            # ITU-T G.xxx
            (r'itu-?t\s+g\.?(\d+)', r'itu_g\1'),
            
            # ITU-R M.xxx
            (r'itu-?r\s+m\.?(\d+)(?:-\d+)?', r'itu_r_m\1'),
            
            # ETSI TS
            (r'etsi\s+ts\s+(\d+)\s+(\d+)-(\d+)', r'etsi_ts_\1_\2'),
            
            # IETF RFC
            (r'(?:ietf\s+)?rfc\s*(\d+)', r'ietf_rfc\1'),
            
            # IEEE
            (r'ieee\s+std\s+([\d\.]+)', r'ieee_std_\1'),
        ]
        
        # Aplicar padrões de normalização
        for pattern, replacement in patterns:
            match = re.search(pattern, norma_clean, re.IGNORECASE)
            if match:
                resultado = re.sub(pattern, replacement, norma_clean, flags=re.IGNORECASE).lower()
                # Limpar caracteres especiais e espaços
                resultado = re.sub(r'[^\w]', '_', resultado)
                resultado = re.sub(r'_+', '_', resultado)
                resultado = resultado.strip('_')
                return resultado
        
        # Se não encontrou padrão conhecido, criar ID genérico
        id_generico = re.sub(r'[^\w\s]', '', norma_clean)  # Remove caracteres especiais
        id_generico = re.sub(r'\s+', '_', id_generico)      # Substitui espaços por underscore
        id_generico = id_generico.lower().strip('_')
        
        if id_generico and len(id_generico) > 2:
            return id_generico
        
        return None

    def _criar_entrada_norma(self, norma_id: str, numero_requerimento: str) -> Dict:
        """Cria uma nova entrada de norma com os parâmetros solicitados"""
        return {
            "id": norma_id,
            "nome": f"Norma ({norma_id}) citada no requerimento {numero_requerimento}",
            "descricao": f"Norma precisando de definição detalhada. Citada no requerimento {numero_requerimento}.",
            "url": "a definir",
            "entidade": "Anatel",
            "status": "revogado"
        }

    def _atualizar_arquivo_normas(self, novas_normas: Dict) -> bool:
        """Atualiza o arquivo normas.json com as novas normas"""
        from datetime import datetime
        import shutil
        
        if not novas_normas:
            return True
            
        try:
            # Converter normas existentes para dicionário usando ID como chave
            normas_existentes = {norma['id']: norma for norma in self.normas}
            
            # Combinar normas existentes com novas
            todas_normas = {**normas_existentes, **novas_normas}
            
            # Converter de volta para lista ordenada por ID
            normas_lista = list(todas_normas.values())
            normas_lista.sort(key=lambda x: x['id'])
            
            # Fazer backup do arquivo original
            normas_path = JSON_FILES['normas']        
            
            # Salvar arquivo atualizado
            with open(normas_path, 'w', encoding='utf-8') as f:
                json.dump(normas_lista, f, indent=2, ensure_ascii=False)
            
            # Atualizar cache interno
            self.normas = normas_lista
            
            #log_info(f"Arquivo normas.json atualizado com {len(novas_normas)} nova(s) norma(s)")
            #log_info(f"Total de normas no arquivo: {len(normas_lista)}")
            return True
            
        except Exception as e:
            log_erro(f"Erro ao atualizar arquivo normas.json: {str(e)}")
            return False

    def _obter_detalhes_norma(self, norma_id: str) -> Dict[str, str]:
        """Obtém detalhes de uma norma pelo seu ID do arquivo normas.json."""
        try:
            for norma in self.normas:
                if norma.get('id') == norma_id:
                    return {
                        'nome': norma.get('nome', norma_id),
                        'descricao': norma.get('descricao', ''),
                        'url': norma.get('url', ''),
                        'status': norma.get('status', '')
                    }
        except Exception as e:
            log_erro(f"Erro ao buscar detalhes da norma {norma_id}: {str(e)}")
        
        # Retornar informações mínimas se não encontrar
        return {
            'nome': norma_id,
            'descricao': 'Norma não encontrada na base de dados',
            'url': '',
            'status': ''
        }

    def _gerar_secao_requisitos_legais(self, equipamentos_unicos: Dict[str, Dict]) -> str:
        """Gera a seção de requisitos legais com subseções por tipo de equipamento."""
        if not equipamentos_unicos:
            return "Nenhum equipamento identificado na análise."
        
        secao_latex = ""
        
        # Ordenar equipamentos por nome para apresentação consistente
        equipamentos_ordenados = sorted(equipamentos_unicos.items(), 
                                      key=lambda x: x[1]['nome'])
        
        for eq_id, eq_info in equipamentos_ordenados:
            nome_equipamento = escapar_latex(eq_info['nome'])
            requisitos = self._obter_requisitos_para_equipamento(eq_id)
            
            secao_latex += f"\\subsubsection{{{nome_equipamento}}}\n\n"
            
            if requisitos:
                secao_latex += "\\begin{itemize}\n"
                
                for req in requisitos:
                    nome_norma = escapar_latex(req['nome'])
                    descricao = escapar_latex(req['descricao'])
                    url = req['url']
                    
                    if url:
                        # Criar hyperlink para a norma
                        secao_latex += f"    \\item \\href{{{url}}}{{{nome_norma}}} - {descricao}\n"
                    else:
                        # Sem hyperlink se não há URL
                        secao_latex += f"    \\item {nome_norma} - {descricao}\n"
                
                secao_latex += "\\end{itemize}\n\n"
            else:
                secao_latex += "\\textit{Nenhum requisito específico identificado para este equipamento.}\n\n"
        
        return secao_latex

    @staticmethod
    def _construir_secao_exigencias(
        dados_requerimento: Optional[Dict],
        cct_contem_ipv6: bool,
        cct_contem_produto_nao_acabado: bool,
        cct_contem_palavra_vinculado: bool,
        caracteristicas_nao_conformes: List[Dict[str, str]],
        modelos_nao_encontrados: Optional[List[str]] = None,
        exigencias_assinatura: Optional[List[str]] = None,
        normas_revogadas: Optional[List[str]] = None,
        cct_desobriga_sar: bool = False,
        exigir_correcao_fotos_externas: bool = False,
        cct_contem_frase_nao_varejo: bool = False
    ) -> str:
        """Monta as exigências quando as declarações do CCT faltam no JSON do produto."""
        if modelos_nao_encontrados is None:
            modelos_nao_encontrados = []
        if exigencias_assinatura is None:
            exigencias_assinatura = []
        if normas_revogadas is None:
            normas_revogadas = []
        if not isinstance(dados_requerimento, dict):
            dados_requerimento = {}
        exigir_avaliacao_sar = (
            not AnalisadorRequerimentos._contem_medicao_sar(dados_requerimento)
            and not cct_desobriga_sar
        )
        exigir_nome_comercial_valido = AnalisadorRequerimentos._tem_nome_comercial_invalido(
            dados_requerimento
        )

        produto_requerimento = dados_requerimento.get("produto", {})
        if not isinstance(produto_requerimento, dict):
            produto_requerimento = {}
        especificacoes_adicionais = produto_requerimento.get("Especificações Adicionais", "")
        if not isinstance(especificacoes_adicionais, str):
            especificacoes_adicionais = ""
        especificacoes_adicionais_normalizadas = re.sub(
            r"\s+", " ", especificacoes_adicionais
        ).casefold()

        regras_exigencias = [
            (
                cct_contem_ipv6,
                "Implementa protocolo IPv6",
                "Que o produto Implementa protocolo IPv6;",
            ),
            (
                cct_contem_produto_nao_acabado,
                "Produto não acabado cuja integração em outros equipamentos pode requerer nova avaliação",
                "Que se trada de Produto não acabado cuja integração em outros equipamentos pode requerer nova avaliação;",
            ),
            (
                cct_contem_palavra_vinculado,
                "A validade deste certificado está vinculada à vigência da homologação ANATEL do módulo de RF incorporado ao produto",
                "Que a validade deste certificado está vinculada à vigência da homologação ANATEL do módulo de RF incorporado ao produto",
            ),
            (
                cct_contem_frase_nao_varejo,
                TEXTO_NAO_VAREJO,
                TEXTO_NAO_VAREJO,
            ),
        ]
        especificacoes_sem_espacos = re.sub(r"\s+", "", especificacoes_adicionais).casefold()
        exigencias = [
            sugestao
            for condicao_cct, frase_obrigatoria, sugestao in regras_exigencias
            if condicao_cct
            and re.sub(r"\s+", "", frase_obrigatoria).casefold() not in especificacoes_sem_espacos
        ]

        tem_exigencias = bool(
            exigencias
            or exigir_avaliacao_sar
            or modelos_nao_encontrados
            or exigir_nome_comercial_valido
            or caracteristicas_nao_conformes
            or exigencias_assinatura
            or normas_revogadas
            or exigir_correcao_fotos_externas
        )
        cor_exigencia = "red" if tem_exigencias else "blue"
        secao_latex = (
            "\\begin{itemize}\n"
            "\\item Exigência:\n"
            f"{{\\color{{{cor_exigencia}}}\n"
        )
        if tem_exigencias:
            secao_latex += "\\begin{enumerate}\n"
            if exigencias:
                secao_latex += "    \\item Incluir no campo Produto | Especificações Adicionais a informação:\n"
                secao_latex += "    \\begin{itemize}\n"
                for exigencia in exigencias:
                    secao_latex += f"        \\item {escapar_latex(exigencia)}\n"
                secao_latex += "    \\end{itemize}\n"
            if exigir_correcao_fotos_externas:
                secao_latex += (
                    "    \\item "
                    f"{escapar_latex(EXIGENCIA_CORRIGIR_FOTOS_EXTERNAS)}\n"
                )
            if exigir_avaliacao_sar:
                secao_latex += (
                    "    \\item "
                    "No caso de dispensa de ensaios de SAR - previstos no"
                    "Ato nº 17865, de 30 de dezembro de 2023 - observar o "
                    "Ato nº 4083, especificamente no item 6.6.8.3. Basta copiar e colar "
                    "a opção de texto pertinente no CCT.\n"
                )
            if modelos_nao_encontrados:
                modelos_pendentes = ", ".join(
                    escapar_latex(modelo) for modelo in modelos_nao_encontrados
                )
                secao_latex += (
                    "    \\item Informar nome(s) do(s) modelo(s) conforme CCT. "
                    f"(Modelos não encontrados no CCT: {modelos_pendentes})\n"
                )
            if exigir_nome_comercial_valido:
                secao_latex += (
                    "    \\item Informar nome comercial válido para o(s) modelo(s).\n"
                )
            for nome_norma in normas_revogadas:
                secao_latex += f"    \\item {escapar_latex(nome_norma)}\n"
            if caracteristicas_nao_conformes:
                secao_latex += "    \\item Corrigir as características técnicas:\n"
                secao_latex += "    \\begin{itemize}\n"
                for validacao in caracteristicas_nao_conformes:
                    faixa = escapar_latex(validacao["faixa"])
                    mensagem = escapar_latex(validacao["mensagem"])
                    secao_latex += (
                        f"        \\item {faixa}: "
                        f"\\textcolor{{red}}{{Não conforme}} -- {mensagem}\n"
                    )
                secao_latex += "    \\end{itemize}\n"
            for exigencia in exigencias_assinatura:
                secao_latex += f"    \\item {escapar_latex(exigencia)}\n"
            secao_latex += "\\end{enumerate}\n"
        else:
            secao_latex += "\\textit{Nenhuma identificada.}\n"
        secao_latex += "}\n\\end{itemize}\n\n"
        return secao_latex

    @staticmethod
    def _pdf_tem_assinatura_digital(caminho_pdf: Path) -> Optional[bool]:
        """Verifica se o PDF contém uma assinatura digital incorporada."""
        try:
            with fitz.open(caminho_pdf) as pdf:
                for pagina in pdf:
                    for campo in pagina.widgets() or ():
                        if campo.field_type != fitz.PDF_WIDGET_TYPE_SIGNATURE:
                            continue

                        xref_campo = campo.xref
                        xrefs_visitados: Set[int] = set()
                        while xref_campo not in xrefs_visitados:
                            xrefs_visitados.add(xref_campo)
                            tipo_valor, valor = pdf.xref_get_key(xref_campo, "V")
                            if tipo_valor == "xref":
                                referencia = re.match(r"(\d+)\s+\d+\s+R$", valor)
                                if referencia:
                                    xref_assinatura = int(referencia.group(1))
                                    tipo_intervalo, intervalo = pdf.xref_get_key(
                                        xref_assinatura, "ByteRange"
                                    )
                                    tipo_conteudo, conteudo = pdf.xref_get_key(
                                        xref_assinatura, "Contents"
                                    )
                                    valores_intervalo = re.findall(r"\d+", intervalo)
                                    if (
                                        tipo_intervalo == "array"
                                        and len(valores_intervalo) >= 4
                                        and len(valores_intervalo) % 2 == 0
                                        and any(int(valor) > 0 for valor in valores_intervalo)
                                        and tipo_conteudo in ("string", "hex string")
                                        and any(caractere != "\x00" for caractere in conteudo)
                                    ):
                                        return True
                                break
                            if tipo_valor == "dict":
                                intervalo = re.search(
                                    r"/ByteRange\s*\[([^\]]+)\]", valor
                                )
                                conteudo = re.search(
                                    r"/Contents\s*<([0-9A-Fa-f\s]+)>", valor
                                )
                                valores_intervalo = (
                                    re.findall(r"\d+", intervalo.group(1))
                                    if intervalo else []
                                )
                                if (
                                    len(valores_intervalo) >= 4
                                    and len(valores_intervalo) % 2 == 0
                                    and any(int(valor) > 0 for valor in valores_intervalo)
                                    and conteudo
                                    and any(
                                        caractere != "0"
                                        for caractere in conteudo.group(1)
                                        if not caractere.isspace()
                                    )
                                ):
                                    return True
                                break
                            if tipo_valor != "null":
                                break

                            tipo_pai, pai = pdf.xref_get_key(xref_campo, "Parent")
                            referencia_pai = (
                                re.match(r"(\d+)\s+\d+\s+R$", pai)
                                if tipo_pai == "xref" else None
                            )
                            if not referencia_pai:
                                break
                            xref_campo = int(referencia_pai.group(1))

            return False
        except Exception as e:
            log_erro(f"Falha ao verificar assinatura digital em {caminho_pdf}: {e}")
            return None

    def _gerar_tabela_normativos_latex(
        self,
        normas_aplicaveis_por_tipo: Dict[str, Dict[str, List[str]]],
        normas_verificadas_por_tipo: Dict[str, Set[str]],
        equipamentos_rotulos: Dict[str, str],
        medicao_sar_identificada: bool = False
    ) -> str:
        """Gera uma tabela única com observações e status RACT/CCT de cada norma."""
        tipos_documento = ("RACT", "CCT")
        normas_para_tabela = set()
        if medicao_sar_identificada:
            normas_para_tabela.add(ID_NORMA_SAR)
        for tipo in tipos_documento:
            normas_aplicaveis_tipo = normas_aplicaveis_por_tipo.get(tipo, {})
            normas_para_tabela.update(normas_aplicaveis_tipo)
            normas_verificadas_tipo = normas_verificadas_por_tipo.get(tipo, set())
            for norma_id in normas_verificadas_tipo:
                detalhes_norma = self._obter_detalhes_norma(norma_id)
                status_norma = (detalhes_norma.get("status") or "").strip().lower()
                if status_norma in ["revogada", "revogado"]:
                    normas_para_tabela.add(norma_id)

        if not normas_para_tabela:
            return ""

        detalhes_normas = {
            norma_id: self._obter_detalhes_norma(norma_id)
            for norma_id in normas_para_tabela
        }
        normas_ordenadas = sorted(
            normas_para_tabela,
            key=lambda norma_id: (
                1 if (
                    (detalhes_normas[norma_id].get("status") or "").strip().lower()
                    not in ["revogada", "revogado"]
                    and any(
                        norma_id in normas_verificadas_por_tipo.get(tipo, set())
                        for tipo in tipos_documento
                    )
                ) else 0,
                (detalhes_normas[norma_id].get("nome") or norma_id).lower()
            )
        )

        latex = (
            "\\begin{itemize}\n"
            "\\item Normativos:\n"
            "\\begin{longtable}{p{0.45\\textwidth}p{0.30\\textwidth}p{0.12\\textwidth}}\n"
            "\\hline\n"
            "\\textbf{Norma} & \\textbf{Observação} & \\textbf{Status} \\\\\n"
            "\\hline\n"
            "\\endhead\n"
        )
        for norma_id in normas_ordenadas:
            detalhes_norma = detalhes_normas[norma_id]
            nome_norma = escapar_latex(detalhes_norma["nome"])
            url_norma = detalhes_norma["url"]
            status_norma = (detalhes_norma.get("status") or "").strip().lower()
            norma_revogada = status_norma in ["revogada", "revogado"]
            # Norma revogada: vermelho só no(s) documento(s) em que ocorre; cinza onde não consta.
            cor_citada = "red" if norma_revogada else "blue"
            def cor_ausente_no_tipo(tipo: str) -> str:
                # Cinza também quando a norma não se aplica ao tipo (ex.: palavra-chave só presente no outro documento).
                if norma_revogada or norma_id not in normas_aplicaveis_por_tipo.get(tipo, {}):
                    return "gray"
                return "red"

            if medicao_sar_identificada and norma_id == ID_NORMA_SAR:
                status_ract = status_cct = "blue"
            else:
                status_ract = (
                    cor_citada if norma_id in normas_verificadas_por_tipo.get("RACT", set())
                    else cor_ausente_no_tipo("RACT")
                )
                status_cct = (
                    cor_citada if norma_id in normas_verificadas_por_tipo.get("CCT", set())
                    else cor_ausente_no_tipo("CCT")
                )
            def formatar_status(cor: str, rotulo: str) -> str:
                texto = f"\\sout{{{rotulo}}}" if cor == "gray" else rotulo
                return f"\\textcolor{{{cor}}}{{{texto}}}"

            status_texto = (
                formatar_status(status_ract, "RACT")
                + "\\textcolor{black}{/}"
                + formatar_status(status_cct, "CCT")
            )

            motivadores = []
            indices_palavras_chave: Dict[str, Tuple[int, str, int]] = {}
            for tipo in tipos_documento:
                for motivador in normas_aplicaveis_por_tipo.get(tipo, {}).get(norma_id, []):
                    correspondencia = re.fullmatch(r"(.+) \(x(\d+)\)", motivador)
                    if correspondencia:
                        palavra, contador = correspondencia.groups()
                        chave = palavra.casefold()
                        if chave in indices_palavras_chave:
                            indice, palavra_existente, contador_existente = (
                                indices_palavras_chave[chave]
                            )
                            contador_existente += int(contador)
                            indices_palavras_chave[chave] = (
                                indice, palavra_existente, contador_existente
                            )
                            motivadores[indice] = (
                                f"{palavra_existente} (x{contador_existente})"
                            )
                        else:
                            indices_palavras_chave[chave] = (
                                len(motivadores), palavra, int(contador)
                            )
                            motivadores.append(motivador)
                    elif motivador not in motivadores:
                        motivadores.append(motivador)

            if not motivadores and norma_revogada:
                motivadores = [status_norma]

            motivadores_formatados = []
            for motivador in motivadores:
                motivador_formatado = motivador
                for nome_equipamento, rotulo_equipamento in equipamentos_rotulos.items():
                    motivador_formatado = motivador_formatado.replace(
                        nome_equipamento, rotulo_equipamento
                    )
                if motivador_formatado not in motivadores_formatados:
                    motivadores_formatados.append(motivador_formatado)
            motivadores_texto = escapar_latex("; ".join(motivadores_formatados))

            nome_norma_formatado = (
                f"\\href{{{url_norma}}}{{{nome_norma}}}" if url_norma else nome_norma
            )
            latex += (
                f"{nome_norma_formatado} & {motivadores_texto} & {status_texto} "
                "\\\\ \\hline\n"
            )

        return latex + "\\end{longtable}\n\\end{itemize}\n\n"

    def _gerar_relatorio_latex(self) -> str:
        """Gera relatório em LaTeX com todos os resultados da análise."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_arquivo = f"relatorio_analise_{timestamp}.tex"
        caminho_relatorio = self.pasta_resultados / nome_arquivo
        
        # Calcular estatísticas gerais
        total_requerimentos = len(self.resultados_analise)
        total_documentos = sum(len(req.get("documentos_analisados", [])) for req in self.resultados_analise)
        
        status_geral = {"CONFORME": 0, "NAO_CONFORME": 0, "INCONCLUSIVO": 0, "ERRO": 0, "PROCESSADO": 0}
        for req in self.resultados_analise:
            for status, count in req.get("resumo_status", {}).items():
                if status in status_geral:
                    status_geral[status] += count
        
        # Calcular tempos de análise e compilação
        tempo_analise_formatado = VALOR_NAO_DISPONIVEL
        
        if self.tempo_inicio_analise and self.tempo_fim_analise:
            tempo_total_analise = self.tempo_fim_analise - self.tempo_inicio_analise
            tempo_analise_formatado = str(tempo_total_analise)#.split('.')[0]  # Remove microsegundos
        
        # Preparar textos que precisam ser escapados
        data_analise = escapar_latex(datetime.now().strftime("%d/%m/%Y às %H:%M:%S"))
        
        # Preparar textos com acentos para LaTeX
        sumario_executivo = "Sumário"
        estatisticas_gerais = "Estatísticas Gerais"
        analise_detalhada = "Análise Detalhada por Requerimento"
        referencias = "Referências"
        normas = "Dispositivos normativos"
        requisitos_legais = "Lista de Requisitos"
        nao_conformes = "Não Conformes"
        nao_conforme_rec = "Não Conforme"

        
        # Conteúdo do relatório LaTeX
        agora = datetime.now().strftime("%H:%M:%S %d/%m/%Y")
        versao_git = 'v. 0.3.2'  # obter_versao_git()
        #utils_dir = Path(__file__).parent.parent / UTILS_DIR
        #classe_path = rf"{Path(__file__).parent.parent / UTILS_DIR / 'IEEEtran'}"
        #latex_content = f"""\\documentclass{{{classe_path}}}
        latex_content = f"""\\documentclass[10pt,a4paper]{{article}}        
\\usepackage[utf8]{{inputenc}} % interpreta o arquivo .tex como UTF-8 
\\usepackage[T1]{{fontenc}}      % usa codificação de fonte T1 (suporta acentos latinos)
\\usepackage{{lmodern}}          % usa uma fonte moderna com suporte a T1
\\usepackage[portuguese,greek,english]{{babel}}
\\usepackage{{textgreek}}
\\usepackage{{geometry}}
\\usepackage{{fancyhdr}}
\\usepackage{{graphicx}}
\\usepackage{{xcolor}}
\\usepackage{{xurl}}
\\usepackage{{datetime2}}
\\usepackage{{booktabs}}
\\usepackage{{longtable}}
\\usepackage{{amssymb}}          % para símbolos matemáticos como checkmark e times
\\usepackage[normalem]{{ulem}}   
\\usepackage[colorlinks=true,
            linkcolor=magenta,
            citecolor=magenta,
            urlcolor=magenta,
            filecolor=magenta]{{hyperref}}
\\hypersetup{{
    pdfnewwindow=true  % Tenta forçar nova janela
}}
\\geometry{{margin=2cm}}
\\pagestyle{{fancy}}
\\fancyhf{{}}
\\fancyhead[L]{{Análise Simplificada Automatizada}}
\\fancyhead[R]{{\\textgreek{{θεoγενης}} - {versao_git}}}
\\fancyfoot[C]{{\\thepage}}
\\setcounter{{tocdepth}}{{2}}
\\setlength{{\\tabcolsep}}{{2pt}}
\\title{{\\Large\\textbf{{Análise Simplificada Automatizada}}}}
\\author{{Teógenes Brito da Nóbrega (\\href{{mailto:tbnobrega@anatel.gov.br}}{{tbnobrega@anatel.gov.br}})}}
%\\date{{{agora}}}
\\date{{}}

\\begin{{document}}

\\maketitle

%\\tableofcontents

\\section{{{sumario_executivo}}}
Este relatório apresenta os resultados da análise automatizada de requerimentos do sistema 
SCH da ANATEL nos termos da Portaria Anatel nº 2257, de 03 de março de 2022 (SEI nº 8121635).
\\subsection{{{estatisticas_gerais}}}
\\begin{{itemize}}
    \\item \\textbf{{Requerimentos analisados:}} {total_requerimentos}
    \\item \\textbf{{Documentos processados:}} {total_documentos}
    %\\item \\textbf{{Documentos Conformes:}} {status_geral['CONFORME']} ({status_geral['CONFORME']/max(total_documentos,1)*100:.1f}\\%)
    %\\item \\textbf{{Documentos {nao_conformes}:}} {status_geral['NAO_CONFORME']} ({status_geral['NAO_CONFORME']/max(total_documentos,1)*100:.1f}\\%)
    %\\item \\textbf{{Documentos Inconclusivos:}} {status_geral['INCONCLUSIVO']} ({status_geral['INCONCLUSIVO']/max(total_documentos,1)*100:.1f}\\%)
    %\\item \\textbf{{Documentos Processados:}} {status_geral['PROCESSADO']} ({status_geral['PROCESSADO']/max(total_documentos,1)*100:.1f}\\%)
    %\\item \\textbf{{Documentos com Erro:}} {status_geral['ERRO']} ({status_geral['ERRO']/max(total_documentos,1)*100:.1f}\\%)
    \\item \\textbf{{Tempo de processamento:}} {tempo_analise_formatado}
    \\item \\textbf{{Data do processamento:}} {agora}
    \\item \\textbf{{Versão do script:}} {{\\textgreek{{θεoγενης - {versao_git}}}}}
\\end{{itemize}}
"""
        
        # Adicionar seção para cada requerimento
        for i, req in enumerate(self.resultados_analise, 1):
            numero_req = fullpath_para_req(req.get("numero_requerimento"))
            documentos = req.get("documentos_analisados", [])
            tempo_analise_req = req.get("tempo_total_analise_formatado", VALOR_NAO_DISPONIVEL)
            #resumo = req.get("resumo_status", {})
            #timestamp_analise = escapar_latex(req.get('timestamp_analise', 'N/A'))
            
            # Obter o nome do OCD e equipamentos do primeiro documento CCT encontrado
            nome_ocd_completo = "OCD não identificado"
            equipamentos_encontrados = []
            
            # Buscar o primeiro CCT com OCD válido
            for doc in documentos:
                if doc.get("tipo") == TIPO_CCT:
                    dados_extraidos = doc.get("dados_extraidos", {})
                    nome_ocd_extraido = dados_extraidos.get("nome_ocd", "N/A")
                    equipamentos_doc = dados_extraidos.get("equipamentos", [])
                    
                    # Coletar equipamentos se disponíveis
                    if equipamentos_doc:
                        equipamentos_encontrados.extend(equipamentos_doc)
                    
                    if nome_ocd_extraido and nome_ocd_extraido != "N/A" and not nome_ocd_extraido.startswith('[ERRO]'):
                        # Se o nome já parece completo (>= 15 caracteres), usar diretamente
                        if len(nome_ocd_extraido) >= 15 and any(palavra in nome_ocd_extraido.lower() for palavra in ['ltda', 'sa', 'associação', 'fundação', 'organização', 'centro']):
                            nome_ocd_completo = nome_ocd_extraido
                        else:
                            nome_ocd_completo = self._obter_nome_completo_ocd(nome_ocd_extraido)
                        break  # Sair do loop após encontrar o primeiro OCD válido
            
            nome_ocd_escapado = escapar_latex(nome_ocd_completo)
            
            # Formatar lista de equipamentos como subitens numerados por ordem de ocorrência distinta.
            nomes_equipamentos, equipamentos_rotulos = (
                self._preparar_equipamentos_lista_relatorio(equipamentos_encontrados)
            )
            if nomes_equipamentos:
                equipamentos_resumo = escapar_latex(
                    ", ".join(nomes_equipamentos)
                )
                equipamentos_itens_latex = "\\begin{itemize}\n"
                for indice, equipamento in enumerate(nomes_equipamentos, 1):
                    equipamento_escapado = escapar_latex(equipamento)
                    # Os colchetes precisam ser impressos como texto literal, não como argumento opcional do \item.
                    equipamentos_itens_latex += f"    \\item[] \\texttt{{[E{indice}]}} - {equipamento_escapado}\n"
                equipamentos_itens_latex += "\\end{itemize}"
            else:
                equipamentos_resumo = "\\textcolor{red}{\\textbf{Equipamento NÃO identificado}} na lista de requisitos ou nos nomes usados no Mosaico"
                equipamentos_itens_latex = "\\textit{Nenhum equipamento identificado.}"
                equipamentos_rotulos = {}

            # Coletar palavras antes do cabeçalho para posicionar o alerta após o OCD.
            palavras_consolidadas, palavras_nao_encontradas = self._coletar_palavras_chave_consolidadas(req)
            alerta_alteracao_homologacao = (
                "\\item \\textcolor{red}{\\textbf{Alterar homologação}}"
                if self._indica_alteracao_homologacao(req, palavras_consolidadas)
                else ""
            )
            
            latex_content += f"""
            \\newpage            
            \\section{{Requerimento {numero_req}}}            
            \\begin{{itemize}}
            \\item OCD: {nome_ocd_escapado}
            {alerta_alteracao_homologacao}
            \\item Equipamento(s):
            {equipamentos_itens_latex}
            \\end{{itemize}}
            """
            '''
            latex_content += """
Lista das palavras-chave \\textcolor{blue}{encontradas (multiplicidade)} neste requerimento: 

"""            
            
            if palavras_consolidadas:
                palavras_formatadas = []
                
                # Palavras encontradas em azul com contador
                palavras_ordenadas = sorted(palavras_consolidadas.items(), key=lambda x: x[1], reverse=True)
                for palavra, contador in palavras_ordenadas:
                    palavra_escapada = escapar_latex(palavra)
                    palavras_formatadas.append(f"    \\item \\textcolor{{blue}}{{{palavra_escapada} (x{contador})}}")
                
                latex_content += "\\begin{itemize}\n"
                latex_content += "\n".join(palavras_formatadas)
                latex_content += "\n\\end{itemize}\n\n"
            else:
                latex_content += "\\textit{Nenhuma palavra-chave específica foi encontrada neste requerimento.}\n\n"

            '''        
            # Coletar normas aplicáveis para este requerimento
            normas_aplicaveis = self._coletar_normas_aplicaveis_requerimento(req)
            normas_verificadas = self._coletar_normas_verificadas_requerimento(req)

            # Verifica se o CCT deste requerimento contém a palavra-chave e.i.r.p.
            cct_contem_eirp = False
            cct_contem_ipv6 = False
            cct_contem_produto_nao_acabado = False
            cct_contem_vinculo_homologacao = False
            cct_contem_palavra_vinculado = False
            cct_contem_frase_nao_varejo = False
            cct_strings_desobrigam_ato17865 = set()

            for doc in documentos:
                if doc.get("tipo") != TIPO_CCT:
                    continue
                dados_extraidos_cct = doc.get("dados_extraidos", {})
                palavras_encontradas_cct = dados_extraidos_cct.get("palavras_encontradas", {})
                palavras_com_normas_cct = dados_extraidos_cct.get("palavras_encontradas_com_normas", {})
                if "e.i.r.p." in palavras_encontradas_cct:
                    cct_contem_eirp = True
                if "ipv6" in palavras_encontradas_cct:
                    cct_contem_ipv6 = True
                if "produto nao acabado" in palavras_encontradas_cct:
                    cct_contem_produto_nao_acabado = True

                if "vinculado" in palavras_encontradas_cct or "vinculada" in palavras_encontradas_cct:
                    cct_contem_palavra_vinculado = True

                if dados_extraidos_cct.get("contem_frase_nao_varejo"):
                    cct_contem_frase_nao_varejo = True

                if dados_extraidos_cct.get("contem_vinculo_homologacao"):
                    cct_contem_vinculo_homologacao = True
                elif "vinculado" in palavras_encontradas_cct or "vinculada" in palavras_encontradas_cct:
                    cct_contem_vinculo_homologacao = True

                # Captura as strings encontradas no CCT que desobrigam especificamente o ato17865.
                for palavra, info_palavra in palavras_com_normas_cct.items():
                    efeito_palavra = str(info_palavra.get("efeito", "aplica")).lower()
                    normas_palavra = [str(n).lower() for n in info_palavra.get("normas", [])]
                    if efeito_palavra == "desobriga" and "ato17865" in normas_palavra:
                        cct_strings_desobrigam_ato17865.add(palavra)

            documento_fotos_externas = next(
                (
                    doc for doc in documentos
                    if doc.get("tipo") == TIPO_FOTOS_EXTERNAS
                ),
                None
            )
            dados_fotos_externas = (
                documento_fotos_externas.get("dados_extraidos", {})
                if documento_fotos_externas else {}
            )
            fotos_externas_contem_frase = dados_fotos_externas.get(
                "contem_frase_produto_nao_acabado_ato4083",
                False
            )
            
            # Debug: Adicionar log para verificar se normas foram encontradas
            #log_info(f"Normas aplicáveis encontradas para {numero_req}: {len(normas_aplicaveis)} normas")
            #if normas_aplicaveis:
                #log_info(f"Normas: {list(normas_aplicaveis.keys())}")
                        
            # Manter as normas aplicáveis e verificadas separadas por documento para avaliar os status.
            normas_aplicaveis_por_tipo = {
                "RACT": self._coletar_normas_aplicaveis_requerimento(req, TIPO_RACT),
                "CCT": self._coletar_normas_aplicaveis_requerimento(req, TIPO_CCT)
            }
            normas_verificadas_por_tipo = {
                "RACT": self._coletar_normas_verificadas_por_tipo(req, TIPO_RACT),
                "CCT": self._coletar_normas_verificadas_por_tipo(req, TIPO_CCT)
            }
            medicao_sar_identificada = self._contem_medicao_sar(
                req.get("dados_requerimento")
            )
            normas_revogadas = self._coletar_normas_revogadas(
                normas_verificadas_por_tipo
            )

            documento_cct = next(
                (doc for doc in documentos if doc.get("tipo") == TIPO_CCT),
                None
            )
            documentos_assinatura = {
                "RACT": next(
                    (doc for doc in documentos if doc.get("tipo") == TIPO_RACT),
                    None
                ),
                "CCT": documento_cct
            }
            status_assinatura = {}
            for tipo_documento, documento in documentos_assinatura.items():
                status_assinatura[tipo_documento] = (
                    self._pdf_tem_assinatura_digital(Path(documento["caminho"]))
                    if documento else False
                )
            exigencias_assinatura = []
            ract_sem_assinatura = status_assinatura["RACT"] is not True
            cct_sem_assinatura = status_assinatura["CCT"] is not True
            if ract_sem_assinatura and cct_sem_assinatura:
                exigencias_assinatura.append(
                    "RACT/CCT não contêm assinaturas válidas."
                )
            elif ract_sem_assinatura:
                exigencias_assinatura.append(
                    "O RACT não contém uma assinatura válida."
                )
            elif cct_sem_assinatura:
                exigencias_assinatura.append(
                    "O CCT não contém uma assinatura válida."
                )
            else:
                latex_content += (
                    "\\begin{itemize}\n"
                    "    \\item Assinatura eletrônica (RACT/CCT): "
                    "\\textcolor{blue}{OK}\n"
                    "\\end{itemize}\n\n"
                )

            dados_cct = documento_cct.get("dados_extraidos", {}) if documento_cct else {}
            modelos_nao_encontrados = []
            status_modelos = None
            if documento_cct is None:
                status_modelos = (
                    "\\textcolor{red}{Não foi possível validar: CCT não encontrado para comparação.}"
                )
            elif "modelos_json" not in dados_cct:
                status_modelos = (
                    "\\textcolor{red}{Não foi possível validar: texto do CCT indisponível.}"
                )
            elif not dados_cct["modelos_json"]:
                status_modelos = (
                    "\\textcolor{red}{Nenhum modelo informado no JSON do requerimento.}"
                )
            else:
                modelos_encontrados = set(dados_cct.get("modelos_encontrados_no_cct", []))
                modelos_nao_encontrados = [
                    modelo for modelo in dados_cct["modelos_json"]
                    if modelo not in modelos_encontrados
                ]
                if not modelos_nao_encontrados:
                    status_modelos = "\\textcolor{blue}{OK}"

            if status_modelos:
                latex_content += (
                    "\\begin{itemize}\n"
                    f"    \\item Modelos: {status_modelos}\n"
                    "\\end{itemize}\n\n"
                )

            caracteristicas_validadas = self._validar_caracteristicas_tecnicas_json(
                req.get("dados_requerimento"),
                set(normas_aplicaveis.keys())
            )
            caracteristicas_nao_conformes = [
                validacao for validacao in caracteristicas_validadas
                if validacao["valida"] != "sim"
            ]
            if not caracteristicas_nao_conformes:
                latex_content += (
                    "\\begin{itemize}\n"
                    "    \\item Características técnicas: "
                    f"{self._formatar_validacao_frequencias_latex(caracteristicas_validadas)}"
                    "\\end{itemize}\n\n"
                )
            latex_content += self._construir_secao_exigencias(
                req.get("dados_requerimento"),
                cct_contem_ipv6,
                cct_contem_produto_nao_acabado,
                cct_contem_palavra_vinculado,
                caracteristicas_nao_conformes,
                modelos_nao_encontrados,
                exigencias_assinatura,
                normas_revogadas,
                cct_desobriga_sar=bool(cct_strings_desobrigam_ato17865),
                exigir_correcao_fotos_externas=(
                    cct_contem_produto_nao_acabado
                    and not fotos_externas_contem_frase
                ),
                cct_contem_frase_nao_varejo=cct_contem_frase_nao_varejo
            )

            tabela_normativos = self._gerar_tabela_normativos_latex(
                normas_aplicaveis_por_tipo,
                normas_verificadas_por_tipo,
                equipamentos_rotulos,
                medicao_sar_identificada=medicao_sar_identificada
            )
            if tabela_normativos:
                latex_content += tabela_normativos

                incluir_br = False
                if cct_contem_eirp:
                    if incluir_br:
                        latex_content += "<br>"
                    latex_content += (
                        "Os valores de potência indicados na(s) faixa(s) de 5150 a 5350 MHz, "
                        "5470 a 5725 MHz e 5925 a 7125 MHz referem-se à potência média E.I.R.P."
                    )
                    incluir_br = True

                '''if cct_contem_produto_nao_acabado:
                    if incluir_br:
                        latex_content += "<br>"
                    latex_content += (
                        "Produto não acabado, de uso interno, cuja integração em outros "
                        "equipamentos passíveis de homologação pode requerer nova avaliação."
                    )
                    incluir_br = True

                if cct_contem_ipv6:
                    if incluir_br:
                        latex_content += "<br>"
                    latex_content += "Suporta protocolo IPv6."
                    incluir_br = True

                if cct_contem_vinculo_homologacao:
                    if incluir_br:
                        latex_content += "<br>"
                    latex_content += (
                        "A validade deste certificado está vinculada à vigência da homologação ANATEL "
                        "HHHH-AA-FFFF, relativa ao módulo de RF modelo XXXX "
                        "incorporado ao produto."
                    )
                    incluir_br = True
                '''
            else:
                latex_content += f"\\textit{{Nenhuma norma específica identificada como requisito identificado para: {equipamentos_resumo}}}\n\n"

        # Coletar todas as palavras-chave globais
        todas_palavras_encontradas, todas_palavras_nao_encontradas = self._coletar_todas_palavras_chave_globais()
        
        # Adicionar seção global de palavras-chave
        latex_content += f"""
\\newpage
\\section{{Palavras-chave}}
Lista completa de todas as palavras-chave identificadas durante a análise dos requerimentos processados.

\\subsection{{Palavras-chave encontradas}}
"""
        
        if todas_palavras_encontradas:
            palavras_encontradas_ordenadas = sorted(todas_palavras_encontradas)
            palavras_encontradas_formatadas = []
            for palavra in palavras_encontradas_ordenadas:
                palavra_escapada = escapar_latex(palavra)
                palavras_encontradas_formatadas.append(palavra_escapada)
            
            latex_content += " ".join(palavras_encontradas_formatadas)
            latex_content += "\n\n"
        else:
            latex_content += "\\textit{Nenhuma palavra-chave foi encontrada nos documentos analisados.}\n\n"
        
        latex_content += """\\subsection{Palavras-chave não encontradas}
"""
        
        if todas_palavras_nao_encontradas:
            palavras_nao_encontradas_ordenadas = sorted(todas_palavras_nao_encontradas)
            palavras_nao_encontradas_formatadas = []
            for palavra in palavras_nao_encontradas_ordenadas:
                palavra_escapada = escapar_latex(palavra)
                palavras_nao_encontradas_formatadas.append(palavra_escapada)
            
            latex_content += " ".join(palavras_nao_encontradas_formatadas)
            latex_content += "\n\n"
        else:
            latex_content += "\\textit{Não há palavras-chave não encontradas.}\n\n"
        
        # Gerar seção de requisitos legais
        equipamentos_unicos = self._coletar_equipamentos_unicos()
        secao_requisitos = self._gerar_secao_requisitos_legais(equipamentos_unicos)
        
        # Finalizar o documento
        latex_content += f"""
\\section{{{referencias}}}
A seguir são apresentados os requisitos legais e normas utilizados como referência na análise dos equipamentos identificados.

\\subsection{{{requisitos_legais}}}
{secao_requisitos}

\\end{{document}}
"""
        
        # Salvar arquivo LaTeX
        try:
            with open(caminho_relatorio, 'w', encoding='utf-8') as f:
                f.write(latex_content)
            log_info(f"Relatório LaTeX gerado: {caminho_relatorio}")
            return str(caminho_relatorio)
        except Exception as e:
            log_erro(f"Erro ao gerar relatório LaTeX: {str(e)}")
            return ""
    
    def _compilar_latex_para_pdf(self, caminho_latex: str) -> str:
        """Compila o arquivo LaTeX para PDF usando pdflatex."""
        caminho_pdf = ""
        caminho_latex_absoluto = ""
        try:
            # Converter para Path absoluto se necessário
            caminho_latex_path = Path(caminho_latex)
            if not caminho_latex_path.is_absolute():
                caminho_latex_path = self.pasta_resultados / caminho_latex_path
            caminho_latex_absoluto = str(caminho_latex_path.resolve())
            
            # Executar pdflatex
            log_info(f"Compilando LaTeX: {caminho_latex_absoluto}")
            resultado = subprocess.run([
                "pdflatex", 
                "-output-directory", str(self.pasta_resultados.resolve()),
                caminho_latex_absoluto
            ], capture_output=True, text=True, cwd=str(self.pasta_resultados.resolve()))
            
            if resultado.returncode == 0:
                resultado = subprocess.run([
                    "pdflatex", 
                    "-output-directory", str(self.pasta_resultados.resolve()),
                    caminho_latex_absoluto
                ], capture_output=True, text=True, cwd=str(self.pasta_resultados.resolve()))

                if resultado.returncode == 0:
                    resultado = subprocess.run([
                        "pdflatex", 
                        "-output-directory", str(self.pasta_resultados.resolve()),
                        caminho_latex_absoluto
                    ], capture_output=True, text=True, cwd=str(self.pasta_resultados.resolve()))
        
                    if resultado.returncode == 0:
                        caminho_pdf = caminho_latex_absoluto.replace(EXT_TEX, EXT_PDF)
                        log_info(f"PDF gerado com sucesso: {caminho_pdf}")
                        # Mantém apenas .tex, .pdf e .json
                        exts_permitidas = {EXT_TEX, EXT_PDF, EXT_JSON}                    
                        for arquivo in self.pasta_resultados.iterdir():
                            if arquivo.is_file() and arquivo.suffix.lower() not in exts_permitidas:
                                log_info(f"Apagando: {arquivo}")
                                arquivo.unlink()  # apaga o arquivo

                    # return caminho_pdf
                else:
                    log_erro(f"Erro na compilação LaTeX: {resultado.stderr}")
                    #return caminho_latex_absoluto  # Retorna o .tex se falhar
       
        except FileNotFoundError:
            log_erro("pdflatex não encontrado. Instale uma distribuição LaTeX (TeX Live, MiKTeX)")
            # Retornar caminho absoluto se disponível, senão o original
            '''try:
                return caminho_latex_absoluto
            except NameError:
                return caminho_latex'''
        except Exception as e:
            log_erro(f"Erro ao compilar LaTeX: {str(e)}")
            # Retornar caminho absoluto se disponível, senão o original
            '''try:
                return caminho_latex_absoluto
            except NameError:
                return caminho_latex'''
        if caminho_pdf != "":
            return caminho_pdf
        else:
            return caminho_latex_absoluto
    
    def _salvar_resultados_json(self) -> str:
        """Salva os resultados da análise em formato JSON."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_arquivo = f"resultados_analise_{timestamp}.json"
        caminho_json = self.pasta_resultados / nome_arquivo
        
        try:
            with open(caminho_json, 'w', encoding='utf-8') as f:
                json.dump(self.resultados_analise, f, indent=2, ensure_ascii=False)
            log_info(f"Resultados JSON salvos: {caminho_json}")
            return str(caminho_json)
        except Exception as e:
            log_erro(f"Erro ao salvar JSON: {str(e)}")
            return ""
    
    def executar_analise(self):
        """Método principal para executar a análise completa."""
        try:
            # Obter escopo da análise
            escopo = self._obter_escopo_analise()
            
            if escopo == "CANCELAR":
                log_info("❌ Análise cancelada pelo usuário.")
                return
            
            # Iniciar cronômetro da análise
            self.tempo_inicio_analise = datetime.now()
            log_info(f"\n🔄 Iniciando análise...")
            
            if escopo == "*":
                # Analisar todos os requerimentos
                requerimentos = self._listar_requerimentos()
                if not requerimentos:
                    log_info("❌ Nenhum requerimento encontrado para análise.")
                    return

                log_info(f"📊 Analisando {len(requerimentos)} requerimentos...")

                for req in requerimentos:
                    log_info(f"  🔍 Analisando: {req}")
                    # só para debug
                    #if req not in ["25.07808"]:
                    #    continue
                    processar_requerimentos_excel(req)                    
                    resultado = self._analisar_requerimento_individual(req)
                    if resultado:
                        self.resultados_analise.append(resultado)
            else:
                # Analisar requerimento específico
                log_info(f"📊 Analisando requerimento: {escopo}")
                resultado = self._analisar_requerimento_individual(escopo)
                if resultado:
                    self.resultados_analise.append(resultado)
            
            if not self.resultados_analise:
                log_info("❌ Nenhum resultado de análise foi gerado.")
                return
            
            # Finalizar cronômetro da análise
            self.tempo_fim_analise = datetime.now()
            tempo_total_analise = self.tempo_fim_analise - self.tempo_inicio_analise
            tempo_analise_formatado = str(tempo_total_analise)#.split('.')[0]  # Remove microsegundos
            log_info(f"\n✅ Análise concluída! Processados {len(self.resultados_analise)} requerimento(s) em {tempo_analise_formatado}")
            
            # Salvar resultados em JSON
            log_info("💾 Salvando resultados JSON...")
            caminho_json = self._salvar_resultados_json()
            
            # Gerar relatório LaTeX
            log_info("📄 Gerando relatório LaTeX...")
            caminho_latex = self._gerar_relatorio_latex()
            
            if caminho_latex:
                # Tentar compilar para PDF
                log_info("🔄 Compilando relatório para PDF...")                
                caminho_pdf = self._compilar_latex_para_pdf(caminho_latex)                
                
                log_info(f"\n🎉 Análise finalizada com sucesso!")
                log_info(f"📁 Resultados salvos em: {self.pasta_resultados}")
                if caminho_json:
                    log_info(f"📊 JSON: {Path(caminho_json).name}")
                if caminho_latex:
                    log_info(f"📄 LaTeX: {Path(caminho_latex).name}")
                    if caminho_pdf != caminho_latex:
                        log_info(f"📋 PDF: {Path(caminho_pdf).name}")
            
        except KeyboardInterrupt:
            log_info("\n❌ Análise interrompida pelo usuário.")
        except Exception as e:
            log_erro_critico(f"Erro crítico na análise: {str(e)}")
            log_info(f"❌ Erro crítico na análise. Verifique os logs.")


def analisar_requerimento():
    """Função principal para análise de requerimentos - compatibilidade com main.py"""
    analisador = AnalisadorRequerimentos()
    analisador.executar_analise()