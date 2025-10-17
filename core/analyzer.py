from pdf2image import convert_from_path
import pytesseract
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple#, Any 
import subprocess

from core.log_print import log_info, log_erro, log_erro_critico
from core.const import (
    TESSERACT_PATH, JSON_FILES, GIT_COMMANDS, GIT_TIMEOUT, VERSAO_PADRAO,
    TBN_FILES_FOLDER, SEPARADOR_LINHA, SEPARADOR_MENOR, REQUERIMENTOS_DIR_PREFIX,
    UTILS_DIR, EXT_PDF, EXT_JSON, EXT_TEX, EXT_XLSX, GLOB_PDF,
    STATUS_CONFORME, STATUS_NAO_CONFORME, STATUS_INCONCLUSIVO, STATUS_ERRO, STATUS_PROCESSADO,
    VALOR_NAO_DISPONIVEL, ENCODING_UTF8, PALAVRAS_CHAVE_MANUAL,
    TIPOS_DOCUMENTOS
)

# Constantes para tipos de documento (chaves da estrutura TIPOS_DOCUMENTOS)
TIPO_CCT = 'cct'
TIPO_RACT = 'ract'
TIPO_MANUAL = 'manual'
TIPO_RELATORIO_ENSAIO = 'relatorio_ensaio'
TIPO_ART = 'art'
TIPO_FOTOS = 'fotos'
TIPO_CONTRATO_SOCIAL = 'contrato_social'
TIPO_OUTROS = 'outros'
from core.utils import (
    formatar_cnpj, desformatar_cnpj, latex_escape_path, escapar_latex, buscar_valor,
    normalizar, normalizar_dados, obter_versao_git, carregar_json, salvar_json, validar_cnpj, fullpath_para_req
)

import pymupdf as fitz
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
                return self.extract_pdf_content_from_ocr(pdf_path)
            
            #log_info(f"Extraindo conteúdo de: {pdf_path.name}")
            
            with fitz.open(pdf_path) as pdf:
                content = ""                              
                for pagina in pdf:
                    content += str(pagina.get_text("text")) + "\n"
                if content.strip() == "":
                    log_info(f"PDF aparentemente vazio, tentando OCR: {pdf_path.name}")
                    content = self.extract_pdf_content_from_ocr(pdf_path)
                
            return content
            
        except Exception as e:
            log_erro(f"Falha ao extrair {pdf_path.name}: {e}")
            return None

    def extract_pdf_content_from_ocr(self, pdf_path: Path) -> Optional[str]:
        """Extrai conteúdo usando OCR como fallback."""
        try:
            if not OCR_DISPONIVEL:
                log_erro("Dependências de OCR não disponíveis (pdf2image, pytesseract)")
                return None
                
            # Converte cada página do PDF em imagem
            paginas = convert_from_path(pdf_path)
            texto_completo = ""

            # Extrai texto de cada página via OCR
            for i, pagina in enumerate(paginas, start=1):
                texto_pagina = pytesseract.image_to_string(pagina, lang='por')
                texto_completo += f"\n--- Página {i} ---\n"
                texto_completo += texto_pagina
                
            return texto_completo
        
        except Exception as e:
            log_erro(f"Falha ao extrair por OCR {pdf_path.name}: {e}")
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
            
            content_normalizado = normalizar(content)
            
            for equipamento in equipamentos_data:
                if isinstance(equipamento, dict) and 'nome' in equipamento:
                    nome_equipamento = equipamento['nome']
                    nome_normalizado = normalizar(nome_equipamento)
                    
                    if nome_normalizado in content_normalizado:
                        ja_existe = any(
                            eq.get('nome') == nome_equipamento 
                            for eq in equipamentos_encontrados
                        )
                        
                        if not ja_existe:
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
            # Moderna Tecnologia LTDA
            "44.458.010/0001-40": {
                "start_pattern": r'acima\s+discriminados?\s+estão?\s+em\s+conformidade\s+com\s+os\s+documentos\s+normativos\s+indicados\.',
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
                "start_pattern": r'Standards?\s+Applied',
                "end_pattern": r'BRICS\s+Certificações',
                "processing_type": "regex_patterns"
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
                "start_pattern": r'Documentos\s+normativos/\s+Technical\s+Standards:',
                "end_pattern": r'Relatório\s+de\s+Conformidade\s+/\s+Report\s+Number:',
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

    def _extract_normas_by_pattern(self, content: str, start_pattern: str, end_pattern: str, 
                                 processing_type: str, custom_patterns: Optional[List[str]] = None) -> List[str]:
        """
        Extrai normas usando padrões específicos de início e fim.
        """
        normas = []
        
        start_match = re.search(start_pattern, content, re.IGNORECASE)
        end_match = re.search(end_pattern, content, re.IGNORECASE)
        
        if start_match and end_match:
            start_pos = start_match.end()
            end_pos = end_match.start()
            normas_section = content[start_pos:end_pos]
            
            if processing_type == "custom" and custom_patterns:
                lines = normas_section.split('\n')
                for line in lines:
                    line = line.strip()
                    for pattern in custom_patterns:
                        if pattern in normas_section.upper():
                            # Regex corrigidanormas_section- o problema era \s+ que exige pelo menos 1 espaço
                            # Mudei para \s* para permitir zero ou mais espaços
                            norma_matches = re.findall(
                                r'(ATO|RESOLUÇÃO|RESOLUÇÕES?)\s*(?:da\s+\w+\s+)?(?:Nº|N°|NO|nº|n°|no)?[\s:]*(\d+)',
                                normas_section,
                                re.IGNORECASE
                            )
                            
                            #print(f"Matches encontrados com regex:")
                            #for i, match in enumerate(norma_matches):
                            #    print(f"  {i+1}. Tipo: '{match[0]}', Número: '{match[1]}'")
                            #print("\n" + "="*80 + "\n")
                            
                            # Processar cada match
                            for tipo, numero in norma_matches:
                                tipo_normalizado = tipo.lower()
                                if 'resolu' in tipo_normalizado:
                                    tipo_normalizado = 'resolucao'
                                else:
                                    tipo_normalizado = 'ato'
                                
                                norma_formatada = f"{tipo_normalizado}{numero}"
                                if norma_formatada not in normas:
                                    normas.append(norma_formatada)
                            
                            break
                                
            elif processing_type == "regex_patterns":
                # Buscar padrões gerais de normas
                norma_patterns = [
                    r'ATO\s*(?:Nº|N°|NO|nº|n°|no)?\s*\d+[\d\w\.\-/]*',
                    r'RESOLUÇÃO\s*(?:Nº|N°|NO|nº|n°|no)?\s*\d+[\d\w\.\-/]*',
                    r'ISO\s*\d+[\d\w\.\-/]*',
                    r'IEC\s*\d+[\d\w\.\-/]*',
                    r'ABNT\s*NBR\s*\d+[\d\w\.\-/]*'
                ]
                
                for pattern in norma_patterns:
                    matches = re.findall(pattern, normas_section, re.IGNORECASE)
                    normas.extend(matches)
        
        return normas

    def extract_normas_verificadas(self, content: str, cnpj_ocd: str) -> List[str]:
        """
        Extrai normas verificadas baseado no CNPJ do OCD específico.
        """
        normas = []
        ocd_patterns = self._get_ocd_patterns()
        
        # Normalizar CNPJ (remover formatação se houver)
        from core.utils import desformatar_cnpj, formatar_cnpj
        cnpj_normalizado = desformatar_cnpj(cnpj_ocd) if cnpj_ocd else ""
        cnpj_formatado = formatar_cnpj(cnpj_normalizado) if cnpj_normalizado else ""
        
        # Buscar configuração por CNPJ formatado
        ocd_config = ocd_patterns.get(cnpj_formatado)
        
        if ocd_config:
            normas = self._extract_normas_by_pattern(
                content,
                ocd_config["start_pattern"],
                ocd_config["end_pattern"],
                ocd_config["processing_type"],
                ocd_config.get("custom_patterns")
            )
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

    def extract_data_from_cct(self, content: str, cnpj_ocd: str, nome_ocd: str = None) -> Dict:
        """
        Extrai todas as variáveis necessárias do CCT.
        """
        tipo_equipamento = self.extract_tipo_equipamento(content)
        
        if cnpj_ocd:
            normas_verificadas = self.extract_normas_verificadas(content, cnpj_ocd)
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
        self.pasta_base = Path(TBN_FILES_FOLDER) / REQUERIMENTOS_DIR_PREFIX
        self.pasta_resultados = Path(TBN_FILES_FOLDER) / 'resultados_analise'
        self.pasta_resultados.mkdir(exist_ok=True)
        
        # Carregar configurações
        self.regras = self._carregar_json(JSON_FILES['regras'])
        self.equipamentos = self._carregar_json(JSON_FILES['equipamentos'])
        self.requisitos = self._carregar_json(JSON_FILES['requisitos'])
        self.normas = self._carregar_json(JSON_FILES['normas'])
        self.ocds = self._carregar_json(JSON_FILES['ocds'])
        
        # Resultados da análise
        self.resultados_analise = []
        
        # Cache para CCTAnalyzer (instanciado sob demanda)
        self._cct_analyzer = None
        
        # Variáveis de timing
        self.tempo_inicio_analise = None
        self.tempo_fim_analise = None
        
    def _carregar_json(self, caminho: str) -> Dict:
        """Carrega arquivo JSON de configuração."""
        try:
            with open(caminho, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            log_erro(f"Arquivo de configuração não encontrado: {caminho}")
            return {}
        except json.JSONDecodeError:
            log_erro(f"Erro ao decodificar JSON: {caminho}")
            return {}
    
    def _obter_escopo_analise(self) -> str:
        """
        Pergunta ao usuário se a análise será de um requerimento específico ou todos.
        """
        print("\n" + SEPARADOR_LINHA)
        print("🔍 ANÁLISE DE REQUERIMENTOS ORCN")
        print(SEPARADOR_LINHA)
        print("\nEscolha o escopo da análise:")
        print("1. Analisar um requerimento específico")
        print("2. Analisar todos os requerimentos (*)")
        print("3. Voltar ao menu principal")

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
                print("❌ Opção inválida. Digite 1, 2 ou 3.")
        except KeyboardInterrupt:
            print("\n❌ Operação cancelada pelo usuário.")
            resposta = "CANCELAR"
        except Exception as e:
            log_erro(f"Erro inesperado na seleção de escopo: {str(e)}")
            print("❌ Erro inesperado. Retornando ao menu principal.")
            resposta = "CANCELAR"
        return resposta
    
    def _selecionar_requerimento_especifico(self) -> str:
        """Permite ao usuário selecionar um requerimento específico."""
        requerimentos = self._listar_requerimentos()
        
        if not requerimentos:
            print("❌ Nenhum requerimento encontrado na pasta de requerimentos.")
            resposta = "CANCELAR"
        
        print(f"\n📁 Requerimentos disponíveis ({len(requerimentos)}):")
        for i, req in enumerate(requerimentos, 1):
            print(f"{i:2d}. {req}")
        print(f"{len(requerimentos)+1:2d}. Cancelar e voltar")
        
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
                print(f"❌ Número inválido. Digite um número entre 1 e {len(requerimentos)+1}, ou 'c' para cancelar.")
                
        except ValueError:
            if opcao.lower() in ['c', 'cancelar', 'voltar']:
                return resposta
            print("❌ Digite um número válido ou 'c' para cancelar.")
        except KeyboardInterrupt:
            print("\n❌ Operação cancelada pelo usuário.")
            return resposta
        return resposta

    def _listar_requerimentos(self) -> List[str]:
        """Lista todos os requerimentos disponíveis."""
        if not self.pasta_base.exists():
            return []
        
        requerimentos = []
        for item in self.pasta_base.iterdir():
            #if item.is_dir() and item.name.startswith("_"):
                requerimentos.append(item.name)
        
        return sorted(requerimentos)

    def _analisar_documento(self, caminho_documento: Path, tipo_documento: str, dados_ocd: Dict) -> Dict:
        """
        Analisa um documento específico baseado no seu tipo.
        """
        info = re.findall(r'\[(.*?)\]', caminho_documento.name)
        log_info(f"Analisando documento: {info[:2]}")
        
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
                resultado = self._analisar_cct(caminho_documento, resultado, dados_ocd)
            elif tipo_documento == TIPO_RACT:
                resultado = self._analisar_ract(caminho_documento, resultado)
            elif tipo_documento == TIPO_MANUAL:
                resultado = self._analisar_keywords(caminho_documento, resultado)
            elif tipo_documento == TIPO_RELATORIO_ENSAIO:
                resultado = self._analisar_relatorio_ensaio(caminho_documento, resultado)
            elif tipo_documento == TIPO_ART:
                resultado = self._analisar_art(caminho_documento, resultado)
            elif tipo_documento == TIPO_FOTOS:
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
    
    def _determinar_tipo_documento(self, nome_arquivo: str) -> str:
        """Determina o tipo de documento baseado no nome do arquivo usando padrões de const.py."""
        nome_lower = nome_arquivo.lower()
        
        # Usar padrões definidos em TIPOS_DOCUMENTOS
        for tipo_chave, tipo_info in TIPOS_DOCUMENTOS.items():
            padroes = tipo_info['padroes']
            for padrao in padroes:
                if padrao in nome_lower:
                    # Retornar a chave do tipo para uso consistente
                    return tipo_chave
        
        # Fallback para "outros" se não encontrar correspondência
        return "outros"
    
    def _analisar_cct(self, caminho: Path, resultado: Dict, dados_ocd: Dict) -> Dict:
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
            
            # Processar resultados da análise
            #nome_ocd = dados_cct.get('nome_ocd', 'N/A')
            tipo_equipamento = dados_cct.get('tipo_equipamento', [])
            normas_verificadas = dados_cct.get('normas_verificadas', [])
            
            # Adicionar informações detalhadas ao resultado
            resultado["dados_extraidos"] = {
                "nome_ocd": nome_ocd,
                "quantidade_equipamentos": len(tipo_equipamento),
                "equipamentos": [eq.get('nome', 'N/A') for eq in tipo_equipamento] if tipo_equipamento else [],
                "quantidade_normas": len(normas_verificadas),
                "normas_verificadas": normas_verificadas
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
    
    def _analisar_ract(self, caminho: Path, resultado: Dict) -> Dict:
        """Análise específica para Relatório de Avaliação da Conformidade Técnica."""
        try:
            log_info(f"Iniciando análise de RACT: {caminho.name}")
            
            # Verificações básicas do arquivo
            if not caminho.exists():
                resultado["status"] = "ERRO"
                resultado["nao_conformidades"].append("Arquivo RACT não encontrado")
                return resultado
            
            # Verificar tamanho do arquivo
            tamanho_mb = caminho.stat().st_size / (1024 * 1024)
            resultado["observacoes"].append(f"Tamanho do arquivo: {tamanho_mb:.2f} MB")
            
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
                        
                        # Extrair texto da primeira página para análise básica
                        primeira_pagina = str(doc[0].get_text())
                        primeira_pagina_lower = primeira_pagina.lower()
                        
                        # Verificar palavras-chave esperadas em RACT
                        palavras_chave = [
                            "relatório", "avaliação", "conformidade", "técnica",
                            "ensaio", "teste", "norma", "equipamento", "anatel"
                        ]
                        
                        palavras_encontradas = []
                        for palavra in palavras_chave:
                            if palavra in primeira_pagina_lower:
                                palavras_encontradas.append(palavra)
                        
                        if palavras_encontradas:
                            conformidades.append(f"Palavras-chave encontradas: {', '.join(palavras_encontradas)}")
                        else:
                            nao_conformidades.append("Poucas palavras-chave técnicas encontradas no documento")
                        
                        # Verificar se contém informações de laboratório/OCD
                        if any(termo in primeira_pagina_lower for termo in ["laboratório", "ocd", "organismo", "certificação"]):
                            conformidades.append("Informações de laboratório/OCD identificadas")
                        else:
                            nao_conformidades.append("Informações de laboratório/OCD não identificadas claramente")
                            
                    else:
                        nao_conformidades.append("Documento PDF vazio ou corrompido")
                        
            except ImportError:
                resultado["observacoes"].append("PyMuPDF não disponível - análise de conteúdo limitada")
            except Exception as e:
                nao_conformidades.append(f"Erro na análise do conteúdo PDF: {str(e)}")
            
            # Verificar data de modificação do arquivo (freshness)
            from datetime import datetime, timedelta
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
            
            # Verificar tamanho do arquivo
            tamanho_mb = caminho.stat().st_size / (1024 * 1024)
            resultado["observacoes"].append(f"Tamanho do arquivo: {tamanho_mb:.2f} MB")
            
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
                    palavras_chave_manual = [palavra.lower() for palavra in PALAVRAS_CHAVE_MANUAL.keys()]
                    palavras_chave_manual = sorted(palavras_chave_manual)                    
                    
                    # Contar ocorrências de cada palavra-chave
                    palavras_encontradas = {}
                    palavras_nao_encontradas = []
                    palavras_encontradas_com_normas = {}  # Nova estrutura para palavras com normas
                    
                    for palavra in palavras_chave_manual:
                        contador = texto_completo.count(palavra)
                        if contador > 0:
                            palavras_encontradas[palavra] = contador
                            # Buscar normas associadas à palavra
                            normas_associadas = PALAVRAS_CHAVE_MANUAL.get(palavra, {}).get("normas", [])
                            if normas_associadas:
                                palavras_encontradas_com_normas[palavra] = {
                                    "contador": contador,
                                    "normas": normas_associadas
                                }
                        else:
                            palavras_nao_encontradas.append(palavra)
                    
                    # Armazenar resultados da análise de palavras-chave nos dados extraídos
                    resultado["dados_extraidos"] = {
                        "palavras_encontradas": palavras_encontradas,
                        "palavras_nao_encontradas": palavras_nao_encontradas,
                        "palavras_encontradas_com_normas": palavras_encontradas_com_normas
                    }
                        
            except ImportError:
                resultado["observacoes"].append("PyMuPDF não disponível - análise de conteúdo limitada")
            except Exception as e:
                nao_conformidades.append(f"Erro na análise do conteúdo: {str(e)}")
            
            # Verificar data do arquivo
            from datetime import datetime
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
        """Análise específica para Relatório de Ensaio."""
        resultado["observacoes"].append("Análise de Relatório de Ensaio: Validando testes realizados")
        resultado["status"] = "CONFORME"  # Temporário
        return resultado
    
    def _analisar_art(self, caminho: Path, resultado: Dict) -> Dict:
        """Análise específica para ART."""
        resultado["observacoes"].append("Análise de ART: Verificando responsáveis técnicos")
        resultado["status"] = "CONFORME"  # Temporário
        return resultado
    
    def _analisar_fotos(self, caminho: Path, resultado: Dict) -> Dict:
        """Análise específica para Fotos do Produto."""
        resultado["observacoes"].append("Análise de Fotos: Verificando conformidade visual")
        resultado["status"] = "CONFORME"  # Temporário
        return resultado
    
    def _analisar_contrato_social(self, caminho: Path, resultado: Dict) -> Dict:
        """Análise específica para Contrato Social."""
        resultado["observacoes"].append("Análise de Contrato Social: Validando dados da empresa")
        resultado["status"] = "CONFORME"  # Temporário
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
            
            # Extrair informações do OCD se disponível
            dados_ocd = dados_req.get("ocd")
            if dados_ocd and isinstance(dados_ocd, dict) and dados_ocd.get("CNPJ"):
                self._atualizar_ocds_json(dados_ocd)
            
            return dados_req
            
        except Exception as e:
            log_erro(f"Erro ao processar arquivo JSON do requerimento {arquivo_json_req.name}: {str(e)}")
            return None

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
                    "data_atualizacao": data_certificado
                }
                dados_ocds.append(novo_registro)
                dados_modificados = True
                log_info(f"Novo OCD adicionado: {nome_ocd} (CNPJ: {cnpj_ocd})")
            
            # Salvar arquivo somente se houve modificação
            if dados_modificados:
                inutil = salvar_json(dados_ocds, ocds_file)
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
        
        pasta_requerimento = self.pasta_base / nome_requerimento
        if not pasta_requerimento.exists():
            log_erro(f"Pasta do requerimento não encontrada: {pasta_requerimento}")
            return {}
        
        # Processar arquivo JSON do requerimento e atualizar OCDS se necessário
        dados_req_json = self._processar_dados_requerimento_json(nome_requerimento, pasta_requerimento)

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
        
        if not arquivos_pdf:
            resultado_requerimento["observacoes_gerais"].append("Nenhum arquivo PDF encontrado")
            return resultado_requerimento
        
        log_info(f"Encontrados {len(arquivos_pdf)} arquivos PDF passíveis de análise")
        
        # Analisar cada documento
        for arquivo in arquivos_pdf:
            tipo_doc = self._determinar_tipo_documento(arquivo.name)
            # Processar todos os tipos de documentos para não perder informações
            if tipo_doc not in [TIPO_CCT, TIPO_MANUAL]:
                continue
            # Extrair dados do OCD do JSON do requerimento
            dados_ocd = dados_req_json.get('ocd', {}) if dados_req_json else {}
            resultado_doc = self._analisar_documento(arquivo, tipo_doc, dados_ocd)
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

    def _coletar_normas_aplicaveis_requerimento(self, req_dados: Dict) -> Dict[str, List[str]]:
        """
        Coleta todas as normas aplicáveis a um requerimento, mapeando suas origens (palavras-chave e equipamentos).
        
        Returns:
            Dict[norma_id, List[motivadores]]
        """
        normas_aplicaveis = {}
        
        try:
            documentos = req_dados.get("documentos_analisados", [])
            #log_info(f"Processando {len(documentos)} documentos para coleta de normas")
            
            # 1. Coletar normas de palavras-chave encontradas
            for doc in documentos:
                dados_extraidos = doc.get("dados_extraidos", {})
                palavras_com_normas = dados_extraidos.get("palavras_encontradas_com_normas", {})
                
                #log_info(f"Documento {doc.get('nome_arquivo', 'N/A')} - palavras com normas: {len(palavras_com_normas)}")
                
                for palavra, info in palavras_com_normas.items():
                    normas = info.get("normas", [])
                    contador = info.get("contador", 0)
                    
                    #log_info(f"Palavra '{palavra}' encontrada {contador}x com normas: {normas}")
                    
                    for norma_id in normas:
                        if norma_id not in normas_aplicaveis:
                            normas_aplicaveis[norma_id] = []
                        normas_aplicaveis[norma_id].append(f"palavra-chave: {palavra} (x{contador})")
            
            # 2. Coletar normas de tipos de equipamentos
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
                        normas_aplicaveis[norma_id].append(f"{eq_nome}")
            
        except Exception as e:
            log_erro(f"Erro ao coletar normas aplicáveis: {str(e)}")
        
        return normas_aplicaveis

    def _obter_detalhes_norma(self, norma_id: str) -> Dict[str, str]:
        """Obtém detalhes de uma norma pelo seu ID do arquivo normas.json."""
        try:
            for norma in self.normas:
                if norma.get('id') == norma_id:
                    return {
                        'nome': norma.get('nome', norma_id),
                        'descricao': norma.get('descricao', ''),
                        'url': norma.get('url', '')
                    }
        except Exception as e:
            log_erro(f"Erro ao buscar detalhes da norma {norma_id}: {str(e)}")
        
        # Retornar informações mínimas se não encontrar
        return {
            'nome': norma_id,
            'descricao': 'Norma não encontrada na base de dados',
            'url': ''
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
        versao_git = obter_versao_git()        

        latex_content = f"""\\documentclass[12pt,a4paper]{{article}}
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
\\usepackage[colorlinks=true,
            linkcolor=blue,
            citecolor=green,
            urlcolor=red,
            filecolor=magenta]{{hyperref}}

\\geometry{{margin=2cm}}
\\pagestyle{{fancy}}
\\fancyhf{{}}
\\fancyhead[L]{{Análise Simplificada Automatizada}}
\\fancyhead[R]{{\\textgreek{{θεoγενης}} - {versao_git}}}
\\fancyfoot[C]{{\\thepage}}
\\setcounter{{tocdepth}}{2}

\\title{{\\Large\\textbf{{Análise Simplificada Automatizada}}}}
\\author{{Teógenes Brito da Nóbrega\\\\\\\\ \\href{{mailto:tbnobrega@anatel.gov.br}}{{tbnobrega@anatel.gov.br}} }}
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
    \\item \\textbf{{Versão do script:}} {{\\textgreek{{θεoγενης}} - {versao_git}}}

\\end{{itemize}}

\\section{{{analise_detalhada}}}
A seguir estão os detalhes da análise para cada requerimento processado.
\\subsection{{Legenda dos Status}}
\\begin{{table}}[h]
\\centering
\\begin{{tabular}}{{|c|l|}}
\\hline
\\textbf{{Sigla}} & \\textbf{{Status}} \\\\
\\hline
\\textcolor{{green}}{{C}} & \\textcolor{{green}}{{CONFORME}}  \\\\
\\hline
\\textcolor{{red}}{{NC}} & \\textcolor{{red}}{{NÃO CONFORME}} \\\\
\\hline
\\textcolor{{blue}}{{I}} & \\textcolor{{blue}}{{INCONCLUSIVO}} \\\\
\\hline
\\textcolor{{purple}}{{P}} & \\textcolor{{purple}}{{PROCESSADO}} \\\\
\\hline
\\textcolor{{orange}}{{E}} & \\textcolor{{orange}}{{ERRO}} \\\\
\\hline
\\end{{tabular}}
\\caption{{Legenda dos status utilizados nas tabelas de análise}}
\\end{{table}}

"""
        
        # Adicionar seção para cada requerimento
        for i, req in enumerate(self.resultados_analise, 1):
            numero_req = fullpath_para_req(req.get("numero_requerimento"))
            documentos = req.get("documentos_analisados", [])
            tempo_analise_req = req.get("tempo_total_analise_formatado", VALOR_NAO_DISPONIVEL)
            #resumo = req.get("resumo_status", {})
            #timestamp_analise = escapar_latex(req.get('timestamp_analise', 'N/A'))
            
            # Obter o nome do OCD do primeiro documento CCT encontrado
            nome_ocd_completo = "OCD não identificado"
            
            # Buscar o primeiro CCT com OCD válido
            for doc in documentos:
                if doc.get("tipo") == TIPO_CCT:
                    dados_extraidos = doc.get("dados_extraidos", {})
                    nome_ocd_extraido = dados_extraidos.get("nome_ocd", "N/A")
                    if nome_ocd_extraido and nome_ocd_extraido != "N/A" and not nome_ocd_extraido.startswith('[ERRO]'):
                        # Se o nome já parece completo (>= 15 caracteres), usar diretamente
                        if len(nome_ocd_extraido) >= 15 and any(palavra in nome_ocd_extraido.lower() for palavra in ['ltda', 'sa', 'associação', 'fundação', 'organização', 'centro']):
                            nome_ocd_completo = nome_ocd_extraido
                        else:
                            nome_ocd_completo = self._obter_nome_completo_ocd(nome_ocd_extraido)
                        break  # Sair do loop após encontrar o primeiro OCD válido
            
            nome_ocd_escapado = escapar_latex(nome_ocd_completo)
            
            latex_content += f"""
\\newpage            
\\subsection{{Requerimento {numero_req}}}
A seguir, os detalhes da análise dos documentos associados a este requerimento, cujo tempo de processamento foi: {tempo_analise_req}.

OCD: {nome_ocd_escapado}

\\subsubsection{{Normas aplicáveis}}

"""
            
            # Coletar normas aplicáveis para este requerimento
            normas_aplicaveis = self._coletar_normas_aplicaveis_requerimento(req)
            
            # Debug: Adicionar log para verificar se normas foram encontradas
            #log_info(f"Normas aplicáveis encontradas para {numero_req}: {len(normas_aplicaveis)} normas")
            #if normas_aplicaveis:
                #log_info(f"Normas: {list(normas_aplicaveis.keys())}")
            
            if normas_aplicaveis:
                latex_content += """\\begin{longtable}{p{5cm}p{11cm}}
\\hline
\\textbf{Norma} & \\textbf{Motivador(es)} \\\\
\\hline
\\endhead
"""
                
                # Ordenar normas alfabeticamente
                for norma_id in sorted(normas_aplicaveis.keys()):
                    detalhes_norma = self._obter_detalhes_norma(norma_id)
                    nome_norma = escapar_latex(detalhes_norma['nome'])
                    url_norma = detalhes_norma['url']
                    
                    motivadores = normas_aplicaveis[norma_id]
                    motivadores_texto = escapar_latex("; ".join(motivadores))
                    
                    if url_norma:
                        # Criar hyperlink para a norma
                        latex_content += f"\\href{{{url_norma}}}{{{nome_norma}}} & {motivadores_texto} \\\\ \\hline"
                    else:
                        # Sem hyperlink se não há URL
                        latex_content += f"{nome_norma} & {motivadores_texto} \\\\ \\hline"
                
                latex_content += """\\end{longtable}
"""
            else:
                latex_content += "\\textit{Nenhuma norma específica identificada para este requerimento.}"

            latex_content += f"""
\\subsubsection{{Documentos Analisados}}

\\begin{{longtable}}{{|p{{6cm}}|p{{10cm}}|}}
\\hline
\\textbf{{Documento}} & \\textbf{{Observações}} \\\\
\\hline
\\endhead
"""
            
            for doc in documentos:
                nome_completo = escapar_latex(doc.get("nome_arquivo", "N/A"))
                tipo = escapar_latex(doc.get("tipo", "N/A"))
                ocorrencias = re.findall(r'\[([^\]]+)\]', nome_completo)
                nome_tabela = nome_completo
                if len(ocorrencias) >= 2:
                    nome_tabela = f"[{tipo}] {ocorrencias[1]}"
                status = doc.get("status", "N/A")
                caminho = doc.get("caminho", "N/A")
                caminho_normalizado = latex_escape_path(caminho)

                # Usar siglas e colorir status
                if status == "CONFORME":
                    status_colorido = "\\textcolor{green}{C}"
                elif status == "NAO_CONFORME":
                    status_colorido = "\\textcolor{red}{NC}"
                elif status == "INCONCLUSIVO":
                    status_colorido = "\\textcolor{orange}{I}"
                elif status == "PROCESSADO":
                    status_colorido = "\\textcolor{purple}{P}"
                elif status == "ERRO":
                    status_colorido = "\\textcolor{red}{E}"
                else:
                    status_colorido = "\\textcolor{red}{E}"
                
                # Escapar observações e limitar tamanho
                observacoes_raw = "; ".join(doc.get("observacoes", []))
                nao_conformidades_raw = "; ".join(doc.get("nao_conformidades", []))
                #if len(observacoes_raw) > 100:  
                #    observacoes_raw = observacoes_raw[:100] + "..."
                #observacoes = escapar_latex(observacoes_raw)
                nao_conformidades = escapar_latex(nao_conformidades_raw)
                
                # Extrair informações de dados_extraidos se disponível
                dados_extraidos = doc.get("dados_extraidos", {})
                info_adicional = ""
                
                if dados_extraidos:
                    equipamentos = dados_extraidos.get("equipamentos", [])
                    normas_verificadas = dados_extraidos.get("normas_verificadas", [])
                    palavras_encontradas = dados_extraidos.get("palavras_encontradas", {})
                    palavras_nao_encontradas = dados_extraidos.get("palavras_nao_encontradas", [])
                    
                    if equipamentos:
                        equipamentos_escapados = [escapar_latex(eq) for eq in equipamentos]
                        info_adicional += r"\newline" + f"\\textbf{{Equipamentos:}} {', '.join(equipamentos_escapados)}."
                    
                    if normas_verificadas:
                        normas_escapadas = [escapar_latex(norma) for norma in normas_verificadas]
                        info_adicional += r"\newline" + f"\\textbf{{Normas verificadas:}} {', '.join(normas_escapadas)}."
                    
                    # Tratamento especial para manuais - exibir palavras-chave com cores
                    if tipo == "manual" and (palavras_encontradas or palavras_nao_encontradas):
                        info_adicional += r"\newline" + "\\textbf{Palavras-chave:} "
                        
                        # Palavras encontradas em verde com contador
                        if palavras_encontradas:
                            palavras_verdes = []
                            for palavra, contador in palavras_encontradas.items():
                                palavra_escapada = escapar_latex(palavra)
                                palavras_verdes.append(f"\\textcolor{{blue}}{{{palavra_escapada} (x{contador})}}")
                            info_adicional += " ".join(palavras_verdes)
                        
                        # Palavras não encontradas em cinza
                        if palavras_nao_encontradas:
                            if palavras_encontradas:  # Se já há palavras verdes, adicionar separador
                                info_adicional += " "
                            palavras_ausentes = []
                            for palavra in palavras_nao_encontradas:
                                palavra_escapada = escapar_latex(palavra)
                                palavras_ausentes.append(f"\\textcolor{{gray}}{{{palavra_escapada}}}")
                            info_adicional += " ".join(palavras_ausentes)

                # Combinar informações
                info_completa = info_adicional +  r"\newline" + f"\\textbf{{{nao_conformidades}}}"  if info_adicional else nao_conformidades
                
                latex_content += f"\\href{{run:{caminho_normalizado}}}{{{nome_tabela}}} & [{status_colorido}] {info_completa} \\\\ \\hline"

            latex_content += """\\end{longtable}

"""
        
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
            print(f"Compilando LaTeX: {caminho_latex_absoluto}")
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
                                print("Apagando:", arquivo)
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
                print("❌ Análise cancelada pelo usuário.")
                return
            
            # Iniciar cronômetro da análise
            self.tempo_inicio_analise = datetime.now()
            print(f"\n🔄 Iniciando análise...")
            
            if escopo == "*":
                # Analisar todos os requerimentos
                requerimentos = self._listar_requerimentos()
                if not requerimentos:
                    print("❌ Nenhum requerimento encontrado para análise.")
                    return
                
                print(f"📊 Analisando {len(requerimentos)} requerimentos...")
                
                for req in requerimentos:
                    print(f"  🔍 Analisando: {req}")
                    resultado = self._analisar_requerimento_individual(req)
                    if resultado:
                        self.resultados_analise.append(resultado)
            else:
                # Analisar requerimento específico
                print(f"📊 Analisando requerimento: {escopo}")
                resultado = self._analisar_requerimento_individual(escopo)
                if resultado:
                    self.resultados_analise.append(resultado)
            
            if not self.resultados_analise:
                print("❌ Nenhum resultado de análise foi gerado.")
                return
            
            # Finalizar cronômetro da análise
            self.tempo_fim_analise = datetime.now()
            tempo_total_analise = self.tempo_fim_analise - self.tempo_inicio_analise
            tempo_analise_formatado = str(tempo_total_analise)#.split('.')[0]  # Remove microsegundos
            
            print(f"\n✅ Análise concluída! Processados {len(self.resultados_analise)} requerimento(s) em {tempo_analise_formatado}")
            
            # Salvar resultados em JSON
            print("💾 Salvando resultados JSON...")
            caminho_json = self._salvar_resultados_json()
            
            # Gerar relatório LaTeX
            print("📄 Gerando relatório LaTeX...")
            caminho_latex = self._gerar_relatorio_latex()
            
            if caminho_latex:
                # Tentar compilar para PDF
                print("🔄 Compilando relatório para PDF...")                
                caminho_pdf = self._compilar_latex_para_pdf(caminho_latex)                
                
                print(f"\n🎉 Análise finalizada com sucesso!")
                print(f"📁 Resultados salvos em: {self.pasta_resultados}")
                if caminho_json:
                    print(f"📊 JSON: {Path(caminho_json).name}")
                if caminho_latex:
                    print(f"📄 LaTeX: {Path(caminho_latex).name}")
                    if caminho_pdf != caminho_latex:
                        print(f"📋 PDF: {Path(caminho_pdf).name}")
            
        except KeyboardInterrupt:
            print("\n❌ Análise interrompida pelo usuário.")
        except Exception as e:
            log_erro_critico(f"Erro crítico na análise: {str(e)}")
            print(f"❌ Erro crítico na análise. Verifique os logs.")


def analisar_requerimento():
    """Função principal para análise de requerimentos - compatibilidade com main.py"""
    analisador = AnalisadorRequerimentos()
    analisador.executar_analise()