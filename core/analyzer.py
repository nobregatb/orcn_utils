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

import pymupdf as fitz
PYMUPDF_DISPONIVEL = True

try:    
    OCR_DISPONIVEL = True
    # Configurar caminho do Tesseract se necessário
    try:
        pytesseract.pytesseract.tesseract_cmd = r"C:\Users\tbnobrega\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
    except:
        pass
except ImportError:
    OCR_DISPONIVEL = False

def latex_escape_path(caminho: str) -> str:
    """Escapa caracteres especiais do LaTeX dentro de um caminho de arquivo."""
    caminho = caminho.replace("\\", "/")  # usa / para evitar confusão
    # escapa caracteres especiais
    return re.sub(r'([_&#%{}$^~\\])', r'\\\1', caminho)

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
    """Normaliza string removendo acentos e convertendo para lowercase."""
    if isinstance(s, str):
        s = s.strip().lower()
        s = ''.join(
            c for c in unicodedata.normalize('NFD', s)
            if unicodedata.category(c) != 'Mn'
        )
    return s


def normalizar_dados(dados):
    """Normaliza todos os dados string em um dicionário."""
    for k, v in dados.items():
        if isinstance(v, list):
            dados[k] = [normalizar(item) if isinstance(item, str) else item for item in v]
        elif isinstance(v, str):
            dados[k] = normalizar(v)
    return dados


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
            
            log_info(f"Extraindo conteúdo de: {pdf_path.name}")
            
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

    def extract_ocd_from_content(self, content: str) -> Optional[str]:
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

    def get_ocd_name(self, cnpj: Optional[str]) -> str:
        """Obtém nome do OCD a partir do CNPJ consultando ocds.json"""
        if not cnpj:
            return "[ERRO] CNPJ não informado"
        
        ocds_file = self.utils_dir / "ocds.json"
        
        try:
            if ocds_file.exists():
                with open(ocds_file, 'r', encoding='utf-8') as f:
                    ocds_data = json.load(f)
                
                ocd_info = buscar_valor(ocds_data, 'cnpj', cnpj, 'nome')
                if ocd_info:
                    return ocd_info

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
        Define os padrões de extração para cada OCD.
        """
        return {
            "moderna": {
                "start_pattern": r'acima\s+discriminado\(s\)\s+está\(ão\)\s+em\s+conformidade\s+com\s+os\s+documentos\s+normativos\s+indicados\.',
                "end_pattern": r'Diretor\s+de\s+Tecnologia',
                "processing_type": "custom",
                "custom_patterns": ['ATO', 'RESOLUÇÃO']
            },
            "ncc": {
                "start_pattern": r'Regulation\s+Applicable',
                "end_pattern": r'Conforme\s+os\s+termos\s+do\s+Ato\s+de\s+Designação\s+nº\s+16\.955',
                "processing_type": "custom",
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
                "processing_type": "custom",
                "custom_patterns": ['ATO', 'RESOLUÇÃO']
            },
            "icc": {
                "start_pattern": r'Regulation\s+Applicable',
                "end_pattern": r'O\s+organismo\s+ICC\s+no\s+uso\s+das\s+atribuições\s+que\s+lhe\s+confere\s+o\s+Ato\s+de\s+Designação',
                "processing_type": "custom",
                "custom_patterns": ['ATO', 'RESOLUÇÃO']
            },
            "master": {
                "start_pattern": r'Reference\s+Standards',
                "end_pattern": r'LABORATÓRIOS\s+DE\s+ENSAIOS',
                "processing_type": "custom",
                "custom_patterns": ['ATO', 'RESOLUÇÃO']
            },
            "ocp-teli": {
                "start_pattern": r'Regulamentos\s+Aplicáveis:',
                "end_pattern": r'OCD\s+designado\s+pelo\s+Ato\s+nº\s+19\.434',
                "processing_type": "custom",
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
                "processing_type": "custom",
                "custom_patterns": ['ATO', 'RESOLUÇÃO']
            },
            "qc": {
                "start_pattern": r'Certification\s+programor\s+regulation',
                "end_pattern": r'Emissão',
                "processing_type": "custom",
                "custom_patterns": ['ATO', 'RESOLUÇÃO']
            },
            "versys": {
                "start_pattern": r'Applicable\s+Standards:',
                "end_pattern": r'Data\s+Certificação',
                "processing_type": "custom",
                "custom_patterns": ['ATO', 'RESOLUÇÃO']
            },
            "cpqd": {
                "start_pattern": r'Documentos\s+normativos/\s+Technical\s+Standards:',
                "end_pattern": r'Relatório\s+de\s+Conformidade\s+/\s+Report\s+Number:',
                "processing_type": "custom",
                "custom_patterns": ['ATO', 'RESOLUÇÃO']
            },
            "associação lmp certificações": {
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

    def extract_normas_verificadas(self, content: str, nome_ocd: str) -> List[str]:
        """
        Extrai normas verificadas baseado no OCD específico.
        """
        normas = []
        ocd_patterns = self._get_ocd_patterns()
        
        ocd_key = nome_ocd.lower()
        ocd_config = ocd_patterns.get(ocd_key)

        if ocd_key == 'ocp-teli':
            x = 1
        
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

    def extract_data_from_cct(self, content: str) -> Dict:
        """
        Extrai todas as variáveis necessárias do CCT.
        """
        nome_ocd = self.extract_ocd_from_content(content)
        tipo_equipamento = self.extract_tipo_equipamento(content)
        
        if nome_ocd:
            normas_verificadas = self.extract_normas_verificadas(content, nome_ocd)
        else:
            normas_verificadas = []
            
        data = {
            'nome_ocd': nome_ocd,
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
        #self.pasta_base = Path("downloads")  # Pasta onde estão os requerimentos
        home_dir = r'C:\Users\tbnobrega\OneDrive - ANATEL\Anatel\_ORCN'
        self.pasta_base = Path(home_dir + r'\Requerimentos')
        self.pasta_resultados = Path(home_dir + r'\resultados_analise')
        #self.pasta_resultados = Path("resultados_analise")
        self.pasta_resultados.mkdir(exist_ok=True)
        
        # Carregar configurações
        self.regras = self._carregar_json("utils/regras.json")
        self.equipamentos = self._carregar_json("utils/equipamentos.json")
        self.requisitos = self._carregar_json("utils/requisitos.json")
        self.normas = self._carregar_json("utils/normas.json")
        self.ocds = self._carregar_json("utils/ocds.json")
        
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
        print("\n" + "="*60)
        print("🔍 ANÁLISE DE REQUERIMENTOS ORCN")
        print("="*60)
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
            print("❌ Nenhum requerimento encontrado na pasta de downloads.")
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
            if item.is_dir() and item.name.startswith("_"):
                requerimentos.append(item.name)
        
        return sorted(requerimentos)
    
    def _analisar_documento(self, caminho_documento: Path, tipo_documento: str) -> Dict:
        """
        Analisa um documento específico baseado no seu tipo.
        """
        log_info(f"Analisando documento: {caminho_documento.name} (Tipo: {tipo_documento})")
        
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
            # Análise baseada no tipo de documento
            if tipo_documento == "CCT":
                resultado = self._analisar_cct(caminho_documento, resultado)
            elif tipo_documento == "RACT":
                resultado = self._analisar_ract(caminho_documento, resultado)
            elif tipo_documento == "Manual":
                resultado = self._analisar_manual(caminho_documento, resultado)
            elif tipo_documento == "Relatorio_Ensaio":
                resultado = self._analisar_relatorio_ensaio(caminho_documento, resultado)
            elif tipo_documento == "ART":
                resultado = self._analisar_art(caminho_documento, resultado)
            elif tipo_documento == "Fotos":
                resultado = self._analisar_fotos(caminho_documento, resultado)
            elif tipo_documento == "Contrato_Social":
                resultado = self._analisar_contrato_social(caminho_documento, resultado)
            else:
                resultado["observacoes"].append(f"Tipo de documento não reconhecido: {tipo_documento}")
                
        except Exception as e:
            log_erro(f"Erro ao analisar {caminho_documento.name}: {str(e)}")
            resultado["status"] = "ERRO"
            resultado["nao_conformidades"].append(f"Erro no processamento: {str(e)}")
        
        return resultado
    
    def _determinar_tipo_documento(self, nome_arquivo: str) -> str:
        """Determina o tipo de documento baseado no nome do arquivo."""
        nome_lower = nome_arquivo.lower()
        
        if "cct" in nome_lower:
            return "CCT"
        elif "ract" in nome_lower:
            return "RACT"
        elif "manual" in nome_lower:
            return "Manual"
        elif "ensaio" in nome_lower:
            return "Relatorio_Ensaio"
        elif "art" in nome_lower:
            return "ART"
        elif "foto" in nome_lower:
            return "Fotos"
        elif "contrato" in nome_lower or "social" in nome_lower:
            return "Contrato_Social"
        elif "selo" in nome_lower:
            return "Contrato_Social"
        else:
            return "Outros"
    
    def _analisar_cct(self, caminho: Path, resultado: Dict) -> Dict:
        """Análise específica para Certificado de Conformidade Técnica."""
        try:
            log_info(f"Iniciando análise detalhada de CCT: {caminho.name}")
            
            # Instanciar CCTAnalyzer integrado
            utils_dir = Path(__file__).parent.parent / "utils"
            cct_analyzer = CCTAnalyzerIntegrado(utils_dir)
            
            # Extrair conteúdo do PDF
            conteudo = cct_analyzer.extract_pdf_content(caminho)
            
            if not conteudo:
                resultado["status"] = "ERRO"
                resultado["nao_conformidades"].append("Falha na extração do conteúdo do PDF")
                resultado["observacoes"].append("PDF pode estar corrompido ou protegido")
                return resultado
            
            # Extrair dados do CCT usando a lógica especializada
            dados_cct = cct_analyzer.extract_data_from_cct(conteudo)
            
            if not dados_cct:
                resultado["status"] = "ERRO"
                resultado["nao_conformidades"].append("Falha na extração de dados do CCT")
                return resultado
            
            # Validar dados extraídos
            validacao = cct_analyzer.validate_data(dados_cct)
            sucesso_validacao, normas_nao_verificadas = validacao
            
            # Processar resultados da análise
            nome_ocd = dados_cct.get('nome_ocd', 'N/A')
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
            
            log_info(f"Análise CCT concluída - Status: {resultado['status']}")
            
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
            if caminho.suffix.lower() == '.pdf':
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
            log_info(f"Análise RACT concluída - Status: {resultado['status']}")
            
        except Exception as e:
            log_erro(f"Erro durante análise de RACT: {str(e)}")
            resultado["status"] = "ERRO"
            resultado["nao_conformidades"].append(f"Erro crítico na análise: {str(e)}")
        
        return resultado
    
    def _analisar_manual(self, caminho: Path, resultado: Dict) -> Dict:
        """Análise específica para Manual do Produto."""
        try:
            log_info(f"Iniciando análise de Manual: {caminho.name}")
            
            # Verificações básicas do arquivo
            if not caminho.exists():
                resultado["status"] = "ERRO"
                resultado["nao_conformidades"].append("Arquivo de Manual não encontrado")
                return resultado
            
            conformidades = []
            nao_conformidades = []
            
            # Verificar nomenclatura
            nome_arquivo = caminho.name.lower()
            if "manual" in nome_arquivo:
                conformidades.append("Nomenclatura 'Manual' identificada no nome do arquivo")
            else:
                nao_conformidades.append("Palavra 'Manual' não encontrada no nome do arquivo")
            
            # Verificar formato
            if caminho.suffix.lower() == '.pdf':
                conformidades.append("Formato PDF adequado")
            else:
                nao_conformidades.append("Manual não está em formato PDF")
            
            # Verificar tamanho (manuais muito pequenos podem ser inadequados)
            tamanho_mb = caminho.stat().st_size / (1024 * 1024)
            resultado["observacoes"].append(f"Tamanho do arquivo: {tamanho_mb:.2f} MB")
            
            if tamanho_mb > 0.1:  # Pelo menos 100KB
                conformidades.append("Tamanho do arquivo adequado")
            else:
                nao_conformidades.append("Arquivo muito pequeno para ser um manual completo")
            
            # Análise de conteúdo do PDF
            try:                
                with fitz.open(caminho) as doc:
                    total_paginas = len(doc)
                    resultado["observacoes"].append(f"Total de páginas: {total_paginas}")
                    
                    if total_paginas >= 2:
                        conformidades.append(f"Manual com {total_paginas} páginas")
                    elif total_paginas == 1:
                        resultado["observacoes"].append("Manual de apenas 1 página - verificar se está completo")
                    else:
                        nao_conformidades.append("Manual vazio ou corrompido")
                        return resultado
                    
                    # Extrair texto para análise de conteúdo
                    texto_completo = ""
                    for pagina_num in range(min(3, total_paginas)):  # Analisar até 3 primeiras páginas
                        texto_completo += str(doc[pagina_num].get_text()).lower() + "\n"
                    
                    # Verificar elementos essenciais de um manual
                    elementos_essenciais = {
                        "especificações": ["especificação", "características", "dados técnicos"],
                        "instalação": ["instalação", "instalação", "montagem", "setup"],
                        "operação": ["operação", "uso", "funcionamento", "utilização"],
                        "segurança": ["segurança", "cuidado", "atenção", "aviso", "perigo"],
                        "conformidade": ["anatel", "conformidade", "certificação", "homologação"]
                    }
                    
                    elementos_encontrados = []
                    for categoria, termos in elementos_essenciais.items():
                        if any(termo in texto_completo for termo in termos):
                            elementos_encontrados.append(categoria)
                    
                    if len(elementos_encontrados) >= 3:
                        conformidades.append(f"Elementos essenciais encontrados: {', '.join(elementos_encontrados)}")
                    elif len(elementos_encontrados) >= 1:
                        resultado["observacoes"].append(f"Alguns elementos encontrados: {', '.join(elementos_encontrados)}")
                        resultado["observacoes"].append("Manual pode estar incompleto - verificar conteúdo")
                    else:
                        nao_conformidades.append("Poucos elementos técnicos identificados no manual")
                    
                    # Verificar se contém informações do produto
                    if any(termo in texto_completo for termo in ["modelo", "produto", "equipamento", "dispositivo"]):
                        conformidades.append("Informações do produto identificadas")
                    else:
                        nao_conformidades.append("Informações específicas do produto não identificadas")
                    
                    # Verificar idioma (português)
                    palavras_portugues = ["o", "a", "de", "da", "do", "para", "com", "em", "é", "são"]
                    palavras_encontradas_pt = sum(1 for palavra in palavras_portugues if palavra in texto_completo)
                    
                    if palavras_encontradas_pt >= 5:
                        conformidades.append("Manual em português identificado")
                    else:
                        resultado["observacoes"].append("Verificar se manual está em português")
                        
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
            
            # Determinar status final
            if nao_conformidades:
                if any("erro" in nc.lower() or "corrompido" in nc.lower() for nc in nao_conformidades):
                    resultado["status"] = "ERRO"
                elif any("não identificad" in nc.lower() or "incompleto" in nc.lower() for nc in nao_conformidades):
                    resultado["status"] = "INCONCLUSIVO"
                else:
                    resultado["status"] = "NAO_CONFORME"
            else:
                resultado["status"] = "CONFORME"
            
            resultado["observacoes"].append(f"Análise de Manual concluída - Status: {resultado['status']}")
            log_info(f"Análise de Manual concluída - Status: {resultado['status']}")
            
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
    
    def _analisar_requerimento_individual(self, nome_requerimento: str) -> Dict:
        """Analisa todos os documentos de um requerimento específico."""
        tempo_inicio_req = datetime.now()
        log_info(f"Iniciando análise do requerimento: {nome_requerimento}")
        
        pasta_requerimento = self.pasta_base / nome_requerimento
        if not pasta_requerimento.exists():
            log_erro(f"Pasta do requerimento não encontrada: {pasta_requerimento}")
            return {}
        
        resultado_requerimento = {
            "numero_requerimento": nome_requerimento,
            "timestamp_analise": datetime.now().isoformat(),
            "tempo_inicio_analise": tempo_inicio_req.isoformat(),
            "documentos_analisados": [],
            "resumo_status": {
                "CONFORME": 0,
                "NAO_CONFORME": 0,
                "INCONCLUSIVO": 0,
                "ERRO": 0
            },
            "observacoes_gerais": []
        }
        
        # Buscar todos os arquivos PDF na pasta
        arquivos_pdf = list(pasta_requerimento.glob("*.pdf"))
        
        if not arquivos_pdf:
            resultado_requerimento["observacoes_gerais"].append("Nenhum arquivo PDF encontrado")
            return resultado_requerimento
        
        log_info(f"Encontrados {len(arquivos_pdf)} arquivos PDF para análise")
        
        # Analisar cada documento
        for arquivo in arquivos_pdf:
            tipo_doc = self._determinar_tipo_documento(arquivo.name)
            if tipo_doc != "CCT":
                continue
            resultado_doc = self._analisar_documento(arquivo, tipo_doc)
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
    
    def _escapar_latex(self, texto: str) -> str:
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

    def _gerar_relatorio_latex(self) -> str:
        """Gera relatório em LaTeX com todos os resultados da análise."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_arquivo = f"relatorio_analise_{timestamp}.tex"
        caminho_relatorio = self.pasta_resultados / nome_arquivo
        
        # Calcular estatísticas gerais
        total_requerimentos = len(self.resultados_analise)
        total_documentos = sum(len(req.get("documentos_analisados", [])) for req in self.resultados_analise)
        
        status_geral = {"CONFORME": 0, "NAO_CONFORME": 0, "INCONCLUSIVO": 0, "ERRO": 0}
        for req in self.resultados_analise:
            for status, count in req.get("resumo_status", {}).items():
                if status in status_geral:
                    status_geral[status] += count
        
        # Calcular tempos de análise e compilação
        tempo_analise_formatado = "N/A"
        
        if self.tempo_inicio_analise and self.tempo_fim_analise:
            tempo_total_analise = self.tempo_fim_analise - self.tempo_inicio_analise
            tempo_analise_formatado = str(tempo_total_analise)#.split('.')[0]  # Remove microsegundos
        
        # Preparar textos que precisam ser escapados
        data_analise = self._escapar_latex(datetime.now().strftime("%d/%m/%Y às %H:%M:%S"))
        
        # Preparar textos com acentos para LaTeX
        sumario_executivo = "Sumário"
        estatisticas_gerais = "Estatísticas Gerais"
        analise_detalhada = "Análise Detalhada por Requerimento"
        conclusoes_recomendacoes = "Conclusões e Recomendações"
        recomendacoes = "Recomendações"
        nao_conformes = "Não Conformes"
        nao_conforme_rec = "Não Conforme"
        relatorio_texto = "Este relatório apresenta os resultados da análise automatizada"
        
        # Conteúdo do relatório LaTeX
        agora = "Processamento em: " + datetime.now().strftime("%H:%M:%S %d/%m/%Y")

        latex_content = f"""\\documentclass[12pt,a4paper]{{article}}
\\usepackage[utf8]{{inputenc}} % interpreta o arquivo .tex como UTF-8 
\\usepackage[T1]{{fontenc}}      % usa codificação de fonte T1 (suporta acentos latinos)
\\usepackage{{lmodern}}          % usa uma fonte moderna com suporte a T1
\\usepackage[portuguese]{{babel}}
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

\\geometry{{margin=1.5cm}}
\\pagestyle{{fancy}}
\\fancyhf{{}}
\\fancyhead[L]{{ORCN/SOR/Anatel}}
\\fancyhead[R]{{{agora}}}
\\fancyfoot[C]{{\\thepage}}
\\setcounter{{tocdepth}}{2}

\\title{{\\Large\\textbf{{Análise Automatizada de Requerimentos no SCH}}}}
\\author{{Teógenes Brito da Nóbrega\\\\ \href{{mailto:tbnobrega@anatel.gov.br}}{{tbnobrega@anatel.gov.br}} }}
%\\date{{{agora}}}
\\date{{}}

\\begin{{document}}

\\maketitle

%\\tableofcontents

\\section{{{sumario_executivo}}}

{relatorio_texto} de requerimentos do sistema SCH da ANATEL, 
realizada em {data_analise}.

\\subsection{{{estatisticas_gerais}}}

\\begin{{itemize}}
    \\item \\textbf{{Total de Requerimentos Analisados:}} {total_requerimentos}
    \\item \\textbf{{Total de Documentos Processados:}} {total_documentos}
    \\item \\textbf{{Documentos Conformes:}} {status_geral['CONFORME']} ({status_geral['CONFORME']/max(total_documentos,1)*100:.1f}\\%)
    \\item \\textbf{{Documentos {nao_conformes}:}} {status_geral['NAO_CONFORME']} ({status_geral['NAO_CONFORME']/max(total_documentos,1)*100:.1f}\\%)
    \\item \\textbf{{Documentos Inconclusivos:}} {status_geral['INCONCLUSIVO']} ({status_geral['INCONCLUSIVO']/max(total_documentos,1)*100:.1f}\\%)
    \\item \\textbf{{Documentos com Erro:}} {status_geral['ERRO']} ({status_geral['ERRO']/max(total_documentos,1)*100:.1f}\\%)
\\end{{itemize}}

\\subsection{{Informações de Tempo}}

\\begin{{itemize}}
    \\item \\textbf{{Tempo Total de Análise:}} {tempo_analise_formatado}
    \\item {agora}
\\end{{itemize}}

%\\newpage

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
\\textcolor{{orange}}{{E}} & \\textcolor{{orange}}{{ERRO}} \\\\
\\hline
\\end{{tabular}}
\\caption{{Legenda dos status utilizados nas tabelas de análise}}
\\end{{table}}

"""
        
        # Adicionar seção para cada requerimento
        for i, req in enumerate(self.resultados_analise, 1):
            numero_req = self._escapar_latex(req.get("numero_requerimento", f"Requerimento_{i}"))
            documentos = req.get("documentos_analisados", [])
            tempo_analise_req = req.get("tempo_total_analise_formatado", "N/A")
            #resumo = req.get("resumo_status", {})
            #timestamp_analise = self._escapar_latex(req.get('timestamp_analise', 'N/A'))
            
            latex_content += f"""
\\subsection{{Requerimento: {numero_req}}}
A seguir, os detalhes da análise dos documentos associados a este requerimento.

\\textbf{{Tempo de Análise:}} {tempo_analise_req}

\\subsubsection{{Documentos Analisados}}

\\begin{{longtable}}{{|p{{6cm}}|p{{10cm}}|}}
\\hline
\\textbf{{Documento}} & \\textbf{{Observações}} \\\\
\\hline
\\endhead
"""
            
            for doc in documentos:
                nome = self._escapar_latex(doc.get("nome_arquivo", "N/A"))
                tipo = self._escapar_latex(doc.get("tipo", "N/A"))
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
                elif status == "ERRO":
                    status_colorido = "\\textcolor{red}{E}"
                else:
                    status_colorido = "\\textcolor{red}{E}"
                
                # Escapar observações e limitar tamanho
                observacoes_raw = "; ".join(doc.get("observacoes", []))
                nao_conformidades_raw = "; ".join(doc.get("nao_conformidades", []))
                #if len(observacoes_raw) > 100:  
                #    observacoes_raw = observacoes_raw[:100] + "..."
                #observacoes = self._escapar_latex(observacoes_raw)
                nao_conformidades = self._escapar_latex(nao_conformidades_raw)
                
                # Extrair informações de dados_extraidos se disponível
                dados_extraidos = doc.get("dados_extraidos", {})
                info_adicional = ""
                
                if dados_extraidos:
                    equipamentos = dados_extraidos.get("equipamentos", [])
                    normas_verificadas = dados_extraidos.get("normas_verificadas", [])
                    
                    if equipamentos:
                        equipamentos_escapados = [self._escapar_latex(eq) for eq in equipamentos]
                        info_adicional += r"\newline" + f"\\textbf{{Equipamentos:}} {', '.join(equipamentos_escapados)}."
                    
                    if normas_verificadas:
                        normas_escapadas = [self._escapar_latex(norma) for norma in normas_verificadas]
                        info_adicional += r"\newline" + f"\\textbf{{Normas verificadas:}} {', '.join(normas_escapadas)}."

                # Combinar informações
                info_completa = info_adicional +  r"\newline" + f"\\textbf{{{nao_conformidades}}}"  if info_adicional else nao_conformidades
                
                latex_content += f"\\href{{run:{caminho_normalizado}}}{{{nome}}} & [{status_colorido}] {info_completa} \\\\ \\hline"

            latex_content += """\\end{longtable}

"""
        
        # Finalizar o documento
        latex_content += f"""
\\section{{{conclusoes_recomendacoes}}}

\\subsection{{Principais Achados}}
\\begin{{itemize}}
    \\item A análise automatizada identificou padrões de conformidade nos documentos processados
    \\item Documentos com status ``Inconclusivo'' requerem revisão manual adicional
    \\item Documentos com ``Erro'' precisam ser reprocessados ou verificados manualmente
\\end{{itemize}}

\\subsection{{{recomendacoes}}}
\\begin{{itemize}}
    \\item Revisar manualmente todos os documentos marcados como ``{nao_conforme_rec}''
    \\item Investigar a causa dos erros de processamento para melhorar o sistema
    \\item Considerar atualização das regras de análise baseada nos resultados
\\end{{itemize}}

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
                        caminho_pdf = caminho_latex_absoluto.replace('.tex', '.pdf')
                        log_info(f"PDF gerado com sucesso: {caminho_pdf}")
                        # Mantém apenas .tex, .pdf e .json
                        exts_permitidas = {".tex", ".pdf", ".json"}                    
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