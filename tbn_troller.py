"""
Analisador de Certificados de Conformidade Técnica (CCT)
Sistema de extração e validação de dados de arquivos PDF
"""
import unicodedata
import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pymupdf4llm
from json_logic import jsonLogic

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

class CCTAnalyzer:
    """Classe principal para análise de certificados CCT"""
    
    def __init__(self, home_dir: Optional[str] = None):
        # self.base_dir = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
        # Alternativa: permite especificar diretório customizado
        #home_dir = Path(base_dir)
        if home_dir:
            self.base_dir = Path(home_dir)  / "Requerimentos"
            self.utils_dir = Path(home_dir) / "utils"
        else:
            self.base_dir = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
            self.utils_dir = self.base_dir / "utils"        
        
        self.ocd_data: Dict = {}
        self.rules: Dict = {}
        self._setup_directories()
        self._load_configurations()
    
    def _setup_directories(self):
        """Cria diretório utils se não existir"""
        self.utils_dir.mkdir(exist_ok=True)
        print(f"[INFO] Diretório utils: {self.utils_dir}")
    
    def _load_configurations(self):
        """Carrega configurações de OCDs e regras"""
        # Carregar dados de OCDs
        ocd_file = self.utils_dir / "ocd_cnpj.json"
        if ocd_file.exists():
            with open(ocd_file, 'r', encoding='utf-8') as f:
                self.ocd_data = json.load(f)
            print(f"[INFO] {len(self.ocd_data)} OCDs carregados")
        else:
            print(f"[AVISO] Arquivo {ocd_file} não encontrado. Criando exemplo...")
            self._create_example_ocd_file(ocd_file)
        
        # Carregar regras de validação
        rules_file = self.utils_dir / "regras.json"
        if rules_file.exists():
            with open(rules_file, 'r', encoding='utf-8') as f:
                self.rules = json.load(f)
            print(f"[INFO] {len(self.rules)} regras carregadas")
        else:
            print(f"[AVISO] Arquivo {rules_file} não encontrado. Criando exemplo...")
            self._create_example_rules_file(rules_file)
    
    def _create_example_ocd_file(self, file_path: Path):
        """Cria arquivo de exemplo com CNPJs e OCDs"""
        example_data = {
            "44458010000140": {
                "nome": "Moderna Tecnologia LTDA",
                "extractor": "default"
            },
            "00000000000000": {
                "nome": "DESCONHEÇIDO",
                "extractor": "xyz_custom"
            }
        }
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(example_data, f, indent=2, ensure_ascii=False)
        self.ocd_data = example_data
        print(f"[INFO] Arquivo de exemplo criado: {file_path}")
    
    def _create_example_rules_file(self, file_path: Path):
        """Cria arquivo de exemplo com regras jsonLogic"""
        example_rules = {
            "validade_cct": {
                "description": "Verifica se CCT possui data de validade válida",
                "rule": {
                    "and": [
                        {"!!": {"var": "data_emissao"}},
                        {"!!": {"var": "data_validade"}}
                    ]
                }
            },
            "tipo_equipamento_valido": {
                "description": "Verifica se tipo de equipamento está presente",
                "rule": {
                    "!!": {"var": "tipo_equipamento"}
                }
            }
        }
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(example_rules, f, indent=2, ensure_ascii=False)
        self.rules = example_rules
        print(f"[INFO] Arquivo de regras criado: {file_path}")
    
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
            print(f"[INFO] Buscando CCTs em todos os subdiretórios de {self.base_dir}...")
            for pdf_file in self.base_dir.rglob("*.pdf"):
                if pattern in pdf_file.name:
                    files.append(pdf_file)
        else:
            target_dir = self.base_dir / search_dir
            if not target_dir.exists():
                print(f"[ERRO] Diretório não encontrado: {target_dir}")
                return []
            
            print(f"[INFO] Buscando CCTs em {target_dir}...")
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
            print(f"[INFO] Extraindo conteúdo de: {pdf_path.name}")
            content = pymupdf4llm.to_markdown(str(pdf_path))
            return content
        except Exception as e:
            print(f"[ERRO] Falha ao extrair {pdf_path.name}: {e}")
            return None
    
    def extract_cnpj_from_content(self, content: str) -> Optional[str]:
        """Extrai CNPJ do conteúdo do PDF"""
        import re
        # Padrão CNPJ: XX.XXX.XXX/XXXX-XX
        pattern = r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}'
        match = re.search(pattern, content)
        if match:
            cnpj = match.group(0).replace('.', '').replace('/', '').replace('-', '')
            return cnpj
        return None
    
    def get_ocd_name(self, cnpj: Optional[str]) -> str:
        """Obtém nome do OCD a partir do CNPJ"""
        if not cnpj:
            return "OCD Desconhecido"
        
        ocd_info = self.ocd_data.get(cnpj)
        if ocd_info:
            return ocd_info.get('nome', 'OCD Desconhecido')
        return f"OCD não cadastrado (CNPJ: {cnpj})"
    
    def extract_tipo_equipamento(self, content: str, ocd_name: str) -> List[str]:
        """
        Extrai tipos de equipamento do conteúdo
        Cada OCD pode ter método específico de extração
        """
        # Método padrão - busca por palavras-chave comuns
        equipamentos = []
        keywords = [
            'Transceptor de Radiação Restrita', 'Sistema de Identificação por Radiofrequências'
        ]

        keywords_lower = [kw.lower() for kw in keywords]

        content_lower = content.lower()
        for idx, keyword in enumerate(keywords_lower):
            if keyword in content_lower:
                equipamentos.append(keyword)
        
        # Aqui você pode adicionar métodos específicos por OCD
        # if "moderna" in ocd_name:
        #     equipamentos.extend(self._extract_moderna_specific(content))

        return list(set(equipamentos))  # Remove duplicatas
    
    def extract_normas_aplicaveis(self, content: str, nome_ocd: str) -> List[str]:
        """
        Extrai normas técnicas aplicáveis do conteúdo do CCT
        Cada OCD pode ter método específico de extração
        """
        import re
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
        cnpj = self.extract_cnpj_from_content(content)
        nome_ocd = self.get_ocd_name(cnpj)
        tipo_equipamento = self.extract_tipo_equipamento(content, nome_ocd)
        normas_aplicaveis = self.extract_normas_aplicaveis(content, nome_ocd)
        
        # Extração de outras variáveis (exemplo)
        data = {
            'cnpj': cnpj,
            'nome_ocd': nome_ocd,
            'tipo_equipamento': tipo_equipamento,
            'normas_aplicaveis': normas_aplicaveis,
            'data_emissao': None,  # Implementar extração
            'data_validade': None,  # Implementar extração
            'numero_certificado': None,  # Implementar extração
        }
        
        return data
    
    def validate_data(self, data: Dict) -> Dict[str, bool]:
        """
        Valida dados extraídos usando regras jsonLogic
        
        Args:
            data: Dados extraídos do CCT
        
        Returns:
            Dicionário com resultados das validações
        """
        results = {}
        
        data_norm = normalizar_dados(data)

        for rule_name, rule_config in self.rules.items():
            try:
                rule = rule_config.get('rule', {})
                result = jsonLogic(normalizar_dados(rule), data_norm)
                results[rule_name] = bool(result)
            except Exception as e:
                print(f"[ERRO] Falha ao aplicar regra '{rule_name}': {e}")
                results[rule_name] = False
        
        return results
    
    def display_results(self, file_name: str, data: Dict, validation: Dict[str, bool]):
        """Exibe resultados da análise no terminal"""
        print("\n" + "="*70)
        print(f"ARQUIVO: {file_name}")
        print("="*70)
        
        print("\n[DADOS EXTRAÍDOS]")
        print("-"*70)
        for key, value in data.items():
            if isinstance(value, list):
                value_str = ", ".join(value) if value else "Nenhum encontrado"
            else:
                value_str = value if value else "Não encontrado"
            print(f"  {key:20s}: {value_str}")
        
        print("\n[VALIDAÇÕES]")
        print("-"*70)
        all_passed = True
        for rule_name, passed in validation.items():
            status = "✓ PASSOU" if passed else "✗ FALHOU"
            print(f"  {rule_name:30s}: {status}")
            if not passed:
                all_passed = False
                if rule_name in self.rules:
                    desc = self.rules[rule_name].get('description', '')
                    print(f"    → {desc}")
        
        print("\n" + "="*70)
        if all_passed:
            print("RESULTADO FINAL: ✓ TODAS AS VALIDAÇÕES PASSARAM")
        else:
            print("RESULTADO FINAL: ✗ ALGUMAS VALIDAÇÕES FALHARAM")
        print("="*70 + "\n")
    
    def run(self):
        """Executa o aplicativo"""
        print("="*70)
        print(f"  ANALISADOR DE CCT - Versão {VERSION}")
        print("="*70)
        print()
        
        # Solicitar diretório
        search_dir = input("Digite o nome do diretório (ou '*' para buscar em todos): ").strip()
        
        if not search_dir:
            print("[ERRO] Diretório não pode ser vazio!")
            return
        
        # Buscar arquivos
        cct_files = self.find_cct_files(search_dir)
        
        if not cct_files:
            print(f"\n[AVISO] Nenhum arquivo CCT encontrado!")
            return
        
        print(f"\n[INFO] {len(cct_files)} arquivo(s) CCT encontrado(s)\n")
        
        # Processar cada arquivo
        for cct_file in cct_files:
            content = self.extract_pdf_content(cct_file)
            
            if not content:
                continue
            
            # Extrair dados
            data = self.extract_data_from_cct(content)
            
            # Validar dados
            validation_results = self.validate_data(data)
            
            # Exibir resultados
            self.display_results(cct_file.name, data, validation_results)
        
        print("\n[INFO] Análise concluída!")


def main():
    """Função principal"""
    try:
        analyzer = CCTAnalyzer(home_dir=r"C:\Users\tbnobrega\OneDrive - ANATEL\Anatel\_ORCN")
        analyzer.run()
    except KeyboardInterrupt:
        print("\n\n[INFO] Aplicativo interrompido pelo usuário")
    except Exception as e:
        print(f"\n[ERRO FATAL] {e}")
        import traceback
        traceback.print_exc()
    finally:
        input("\nPressione ENTER para sair...")


if __name__ == "__main__":
    main()