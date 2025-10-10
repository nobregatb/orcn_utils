"""
Analisador de Certificados de Conformidade Técnica (CCT)
Sistema de extração e validação de dados de arquivos PDF
"""
from datetime import datetime
import unicodedata
import re
#import sys
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
            content = pymupdf4llm.to_markdown(str(pdf_path))
            #llama_reader = pymupdf4llm.LlamaMarkdownReader()
            #llama_docs = llama_reader.load_data(str(pdf_path))

            return content
        except Exception as e:
            self.log(f"[ERRO] Falha ao extrair {pdf_path.name}: {e}")
            return None
    
    def extract_ocd_from_content(self, content: str) -> Optional[str]:
        if re.search("Associação NCC Certificações do Brasil", content, re.IGNORECASE):
            return "NCC"
        elif re.search("BRICS Certificações de Sistemas de Gestões e Produtos", content, re.IGNORECASE):
            return "BRICS"
        elif re.search("ABCP Certificadora de Produtos LTDA", content, re.IGNORECASE):
            return "ABCP"
        elif re.search("ACERT ORGANISMO DE CERTIFICACAO DE PRODUTOS EM SISTEMAS", content, re.IGNORECASE):
            return "ACERT"
        elif re.search("SGS do Brasil Ltda.", content, re.IGNORECASE):
            return "SGS"
        elif re.search("BraCert – BRASIL CERTIFICAÇÕES LTDA", content, re.IGNORECASE):
            return "BraCert"
        elif re.search("CCPE – CENTRO DE CERTIFICAÇÃO", content, re.IGNORECASE):
            return "CCPE"        
        elif re.search("OCD-Eldorado", content, re.IGNORECASE):
            return "Eldorado"
        elif re.search("organismo ICC no uso das atribuições que lhe confere o Ato de Designação N° 696", content, re.IGNORECASE):
            return "ICC"
        elif re.search("Moderna Tecnologia LTDA", content, re.IGNORECASE):
            return "Moderna"
        elif re.search("Master Associação de Avaliação de Conformidade", content, re.IGNORECASE):
            return "Master"  
        elif re.search("OCP-TELI", content, re.IGNORECASE):            
            return "OCP-TELI"
        elif re.search("Certificado: TÜV", content, re.IGNORECASE):            
            return "TUV"
        elif re.search("UL do Brasil Ltda, Organismo de Certificação Designado", content, re.IGNORECASE):            
            return "UL"
        elif re.search("QC Certificações", content, re.IGNORECASE):            
            return "QC"
        elif re.search("Associação Versys de Tecnologia", content, re.IGNORECASE):            
            return "Versys"
        elif re.search("CPQD", content, re.IGNORECASE):
            return "CPQD"         
        else:
            return "[ERRO] OCD não identificado"
         
    
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
                    nome_equipamento = equipamento['nome']
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
            
    def extract_normas_verificadas(self, content: str, nome_ocd: str) -> List[str]:
        """
        Extrai normas técnicas aplicáveis do conteúdo do CCT
        Cada OCD pode ter método específico de extração
        """
        #import re
        normas = []
        
        # Método específico para Moderna
        if "moderna" in nome_ocd.lower():
            # Busca entre "Techinical Standard(s) Applicable" e o texto da Moderna/ANATEL
            start_pattern = r'Techinical\s+Standard\(s\)\s+Applicable'
            end_pattern = r'A\s+Moderna\s+Tecnologia,\s+organismo\s+designado\s+pela\s+Agência\s+Nacional\s+de\s+Telecomunicações\s+-\s+ANATEL,\s+por\s+intermédio\s+do\s+Ato\s+n°6247'
            
            # Encontra as posições de início e fim
            start_match = re.search(start_pattern, content, re.IGNORECASE)
            end_match = re.search(end_pattern, content, re.IGNORECASE)
            
            if start_match and end_match:
                # Extrai o texto entre as duas strings
                start_pos = start_match.end()
                end_pos = end_match.start()
                normas_section = content[start_pos:end_pos]
                
                # Divide em linhas e processa cada uma
                lines = normas_section.split('\n')
                for line in lines:
                    line = line.strip()
                    if line:  # Se a linha não está vazia
                        # Remove pontos entre números (ex: 802.11 -> 80211, mas mantém : em anos)
                        # Primeiro preserva anos com dois pontos
                        temp_line = re.sub(r'(\d{4})', r'YEAR\1YEAR', line)
                        # Remove pontos entre dígitos
                        temp_line = re.sub(r'(\d)\.(\d)', r'\1\2', temp_line)
                        # Restaura os anos
                        cleaned_line = re.sub(r'YEAR(\d{4})YEAR', r'\1', temp_line)
                        
                        # Adiciona a norma limpa se contém padrões reconhecíveis
                        if any(pattern in cleaned_line.upper() for pattern in ['ATO', 'RESOLUÇÃO']):
                            # Processa atos e resoluções: remove texto entre tipo e numeral
                            # Ex: "Ato Nº 17087 de" -> "ato17087"
                            # Ex: "Resolução Nº 680" -> "resolucao680"
                            
                            # Padrão para capturar tipo + texto intermediário + numeral
                            match_ato = re.search(r'(ato)\s+[^\d]*(\d+)', cleaned_line, re.IGNORECASE)
                            match_resolucao = re.search(r'(resolução)\s+[^\d]*(\d+)', cleaned_line, re.IGNORECASE)
                            
                            if match_ato:
                                tipo = match_ato.group(1).lower()
                                numero = match_ato.group(2)
                                norma_formatada = f"{tipo}{numero}"
                                normas.append(norma_formatada)
                            elif match_resolucao:
                                tipo = match_resolucao.group(1).lower().replace('ção', 'cao')  # resolução -> resolucao
                                numero = match_resolucao.group(2)
                                norma_formatada = f"{tipo}{numero}"
                                normas.append(norma_formatada)
                            else:
                                # Se não conseguiu processar, adiciona a linha original limpa
                                normas.append(cleaned_line)
        
        # Método padrão para outros OCDs
        else:
            # Busca por padrões comuns de normas em qualquer lugar do texto
            norma_patterns = [
                r'ABNT\s+NBR\s+\d+(?::\d{4})?',
                r'ANSI/IEEE\s+Std\s+[\d\.\-]+',
                r'IEEE\s+Std\s+[\d\.\-]+',
                r'IEC\s+\d+(?:-\d+)?(?::\d{4})?',
                r'CISPR\s+\d+(?::\d{4})?',
                r'FCC\s+CFR\s+Title\s+\d+\s+Part\s+\d+'
            ]
            
            for pattern in norma_patterns:
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
            
            #TEOGENES - para testes, processar apenas Moderna
            if cct['nome_ocd'] == "Moderna":
            # Validar dados
                validation_results = self.validate_data(cct)

                # Exibir resultados
                self.display_results(cct_file.name, cct, validation_results)
            else:
                self.log(f"\t🎯 [AVISO] Calma, cocada! Análise automática desabilitada este OCD.")
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