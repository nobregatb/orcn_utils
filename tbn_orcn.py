import pdfplumber
import pandas as pd
from datetime import datetime
from typing import List, Optional, Any, Union, Dict
import re
import os
import fitz # Para PyMuPDF (necessário para coordenadas e tabelas "stream")
import camelot # Para tabelas com estrutura (lattice)

# --- 2. Funções de Busca Reutilizáveis (MANTIDAS) ---

def buscar_string_apos_prefixo_ate_quebra_linha(texto: str, prefixo: str) -> str:
    """Busca o texto após 'prefixo' até o primeiro '\n'."""
    if prefixo in texto:
        bloco_apos_prefixo = texto.split(prefixo, 1)[-1].strip()
        return bloco_apos_prefixo.split('\n', 1)[0].strip()
    return ""

def buscar_datetime_apos_prefixo(texto: str, prefixo: str) -> Optional[datetime]:
    """Busca a data (DD/MM/AAAA) imediatamente após o prefixo."""
    if prefixo in texto:
        bloco_apos_prefixo = texto.split(prefixo, 1)[-1].strip()
        data_pattern = r'(\d{1,2}[\/-]\d{1,2}[\/-]\d{4})' 
        match = re.search(data_pattern, bloco_apos_prefixo)
        if match:
            data_string_crua = match.group(1).replace('-', '/')
            try:
                return datetime.strptime(data_string_crua, '%d/%m/%Y')
            except ValueError:
                return None
    return None

# --- NOVAS FUNÇÕES DE TABELA COM COORDENADAS (Para Camelot) ---

def get_tag_coordinates(pdf_path: str, tag: str, start_page: int = 1) -> Optional[Dict[str, Any]]:
    """Busca a primeira ocorrência da TAG e retorna suas coordenadas e dimensões da página."""
    try:
        with fitz.open(pdf_path) as doc:
            for page_num in range(start_page - 1, len(doc)):
                page = doc.load_page(page_num)
                text_instances = page.search_for(tag)
                
                if text_instances:
                    rect = text_instances[0]
                    return {
                        'page': page_num + 1,
                        'x0': rect.x0, 'y0': rect.y0, 'x1': rect.x1, 'y1': rect.y1,
                        'width': page.rect.width,    
                        'height': page.rect.height   
                    }
        return None
    except Exception as e:
        return None


def extrair_tabela_camelot_segmentada(
    pdf_path: str, 
    tag_inicio: str, 
    tag_fim: Optional[str] = None
) -> pd.DataFrame:
    """
    Usa o Camelot (flavor='lattice') para extrair tabelas entre TAGs, 
    suportando segmentos da tabela em páginas diferentes.
    """
    coords_inicio = get_tag_coordinates(pdf_path, tag_inicio)
    if not coords_inicio:
        print(f"AVISO Camelot: TAG de início '{tag_inicio}' não encontrada.")
        return pd.DataFrame()

    page_num_inicio = coords_inicio['page']
    
    # 1. ENCONTRAR COORDENADAS E PÁGINAS (Com documentação fechada)
    if tag_fim:
        coords_fim = get_tag_coordinates(pdf_path, tag_fim, start_page=1)
        page_num_fim = coords_fim['page'] if coords_fim else None
    else:
        page_num_fim = None

    # 2. CALCULAR RANGE DE PÁGINAS (Abrindo documento para obter contagem total)
    with fitz.open(pdf_path) as doc_temp:
        if page_num_fim is not None:
            pages_to_extract = list(range(page_num_inicio, page_num_fim + 1))
        else:
            pages_to_extract = list(range(page_num_inicio, len(doc_temp) + 1))

    if not pages_to_extract:
        return pd.DataFrame()

    # 3. EXTRAÇÃO: ABRIR O DOCUMENTO UMA ÚNICA VEZ PARA COLETAR AS DIMENSÕES DA PÁGINA
    table_settings = []
    
    # ABRIMOS O DOCUMENTO COM FITZ AQUI
    with fitz.open(pdf_path) as doc:
        for i, page_num in enumerate(pages_to_extract):
            is_first = i == 0
            is_last = i == len(pages_to_extract) - 1
            
            # Carrega a página DENTRO do bloco 'with doc'
            page = doc.load_page(page_num - 1)
            
            # AGORA page NÃO É None
            page_width = page.rect.width 
            page_height = page.rect.height
            
            current_page_top_y = coords_inicio['y1'] + 10 if is_first else 0 
            current_page_bottom_y = page_height # Vai até o final da página por padrão

            if is_last and page_num_fim is not None and coords_fim and coords_fim['page'] == page_num:
                current_page_bottom_y = coords_fim['y0'] - 5 
            
            area_string = f'0,{current_page_top_y},{page_width},{current_page_bottom_y}'
            table_settings.append((str(page_num), [area_string]))
    
    # 4. EXTRAÇÃO COM CAMELOT (NÃO PRECISA DO FITZ AQUI)
    all_dfs = []
    for page_str, areas in table_settings:
        try:
            tables = camelot.read_pdf(
                pdf_path, 
                pages=page_str, 
                flavor='lattice',
                table_areas=areas
            )
            if tables:
                all_dfs.append(tables[0].df)
        except Exception as e:
            print(f"ERRO Camelot na página {page_str}: {e}")

    # 5. Concatena e retorna (lógica de cabeçalho mantida)
    # ... (Restante da lógica de concatenação e cabeçalho)
    if not all_dfs:
        return pd.DataFrame()

    final_df = pd.concat(all_dfs, ignore_index=True)
    new_header = final_df.iloc[0] 
    final_df = final_df[1:].reset_index(drop=True)
    final_df.columns = new_header
    
    return final_df


def buscar_tabela_sem_grade_pymupdf(pdf_path: str, tag_inicio: str) -> pd.DataFrame:
    """
    Lê uma tabela sem grade (apenas texto) usando o método stream do PyMuPDF
    e assume que a tabela começa logo após a TAG_INICIO.
    """
    coords = get_tag_coordinates(pdf_path, tag_inicio)
    if not coords:
        print(f"AVISO fitz: TAG de início '{tag_inicio}' não encontrada.")
        return pd.DataFrame()

    page_num = coords['page']
    
    try:
        with fitz.open(pdf_path) as doc:
            page = doc.load_page(page_num - 1)
            
            # Definindo a área (após a TAG_INICIO e até o final da página ou TAG_FIM)
            # Usamos a altura da página como limite inferior (pode ser ajustado se tiver TAG de fim)
            top_y = coords['y1'] + 10 
            rect = fitz.Rect(0, top_y, coords['width'], coords['height'])
            
            # Extração da tabela usando o método 'stream' (ideal para tabelas sem linhas)
            # Tenta inferir colunas por alinhamento vertical
            tables = page.find_tables(
                tables={
                    "strategy": "stream",
                    "rect": rect,
                    "vertical_strategy": "lines", # Tenta usar linhas verticais para colunas (se houver)
                    "horizontal_strategy": "text" # Tenta usar espaços entre texto para linhas
                }
            )

            if not tables:
                print(" -> PyMuPDF: Nenhuma tabela (stream) encontrada na área especificada.")
                return pd.DataFrame()
            
            # tables[0].to_pandas() já retorna o DataFrame
            return tables[0].to_pandas() 
            
    except Exception as e:
        print(f"ERRO PyMuPDF: Falha ao extrair tabela sem grade. {e}")
        return pd.DataFrame()
# --- 1. Classes de Configuração de Empresa (Mantidas) ---
class ConfigEmpresaBase:
    TAGS_BLOCO_SERIAL: Dict[str, str] = {}
    NOME: str = "BASE"
    IDENTIFICADOR_CNPJ: str = ""

class ConfigModerna(ConfigEmpresaBase):
    NOME = 'moderna'
    IDENTIFICADOR_CNPJ = "CNPJ: 44.458.010/0001-40"
    TAGS_BLOCO_SERIAL = {
        'equipamentos': "2 - Identificação do Produto", 
        'caracteristicas': "3 - Características Técnicas Básicas",
        'entidades': "4 - Entidades Envolvidas",
        'requisitos': "5 - Norma(s) Técnica(s) Aplicável(eis)",
        'laboratorios': "Relatório(s) de Testes e Laboratório(S)",
        'infos': "7 - Informações Adicionais",
        'ensaios': "9 - ENSAIOS REALIZADOS E RESULTADOS APRESENTADOS",
        'comentarios': "12 - COMENTÁRIOS ADICIONAIS",
        'laudo': "13 - LAUDO CONCLUSIVO",
        'especialistas': "16 - APROVAÇÃO DOS ESPECIALISTAS",
    }
    ORDEM_CHAVES = ['equipamentos', 'caracteristicas', 'entidades', 'requisitos', 'laboratorios', 'infos', 'ensaios', 'comentarios', 'laudo', 'especialistas']

CONFIGS = {'moderna': ConfigModerna}


# --- 3. Classe Ract e Lógica de Processamento Central ---

class Ract:
    """ Objeto final padronizado para armazenar dados de qualquer empresa. """
    def __init__(self):
        self.modelos: List[str] = None
        self.tipo_equipamento: str = None
        self.caracteristicas: pd.DataFrame = None
        self.solicitante: str = None
        self.fabricante: str = None
        self.ensaios: pd.DataFrame = None
        self.data_emissao: datetime = None
        self.empresa: Optional[str] = None # Garantir que o atributo existe
        self.data_string: str = None # Usado apenas para demonstração

    def _identificar_empresa(self, texto: str) -> Optional[ConfigEmpresaBase]:
        for nome, config_class in CONFIGS.items():
            if config_class.IDENTIFICADOR_CNPJ in texto:
                print(f" -> Empresa identificada: '{nome}'.")
                self.empresa = nome
                return config_class
        print(" -> AVISO: Empresa não identificada por CNPJ conhecido.")
        return None

    def extrair_dados_ract(self, pdf_path: str):
        if not os.path.exists(pdf_path):
             print(f"ERRO: Arquivo não encontrado no caminho: {pdf_path}")
             return

        # Etapa 1: Leitura e Pré-processamento com PDFPLUMBER para o texto bruto
        with pdfplumber.open(pdf_path) as pdf:
            texto_completo = ""
            for pagina in pdf.pages:
                texto_completo += pagina.extract_text(force_text=True) + "\n"
        
        texto_processamento = re.sub(r'\n\s*\n', '\n\n', texto_completo).strip()
        config_empresa = self._identificar_empresa(texto_processamento)
        
        if not config_empresa: return

        tags = config_empresa.TAGS_BLOCO_SERIAL
        ordem = config_empresa.ORDEM_CHAVES
        cursor_pos = 0

        for i, chave in enumerate(ordem):
            tag_inicio = tags[chave]
            
            try:
                tag_start_index = texto_processamento.index(tag_inicio, cursor_pos)
            except ValueError:
                print(f"\nAVISO: A TAG de início do bloco '{chave}' ('{tag_inicio}') não foi encontrada.")
                continue

            tag_fim = tags[ordem[i+1]] if i + 1 < len(ordem) else None
            
            # Delimitar o Bloco de Dados Bruto (para extração de texto)
            if tag_fim:
                try:
                    tag_end_index = texto_processamento.index(tag_fim, tag_start_index)
                    bloco_dados_bruto = texto_processamento[tag_start_index + len(tag_inicio) : tag_end_index].strip()
                    cursor_pos = tag_end_index
                except ValueError:
                    bloco_dados_bruto = texto_processamento[tag_start_index + len(tag_inicio):].strip()
                    cursor_pos = len(texto_processamento) 
            else:
                bloco_dados_bruto = texto_processamento[tag_start_index + len(tag_inicio):].strip()
                cursor_pos = len(texto_processamento)

            print(f"\n[BLOCO {chave}] Extraindo dados com a TAG '{tag_inicio}'...")

            # Lógica de Extração Mista
            
            # 1. Extração Simples de String (pdfplumber/texto)
            if chave == 'equipamentos':
                # Modelo(s) e Tipo de Produto na mesma linha do prefixo
                self.modelos = [buscar_string_apos_prefixo_ate_quebra_linha(bloco_dados_bruto, "Modelo(s):")]
                self.tipo_equipamento = buscar_string_apos_prefixo_ate_quebra_linha(bloco_dados_bruto, "Tipo de Produto:")
                print(f" -> Modelo(s): {self.modelos}, Tipo: {self.tipo_equipamento}")
            
            elif chave == 'entidades':
                # Solicitante e Fabricante na mesma linha do prefixo
                self.solicitante = buscar_string_apos_prefixo_ate_quebra_linha(bloco_dados_bruto, "Solicitante:")
                self.fabricante = buscar_string_apos_prefixo_ate_quebra_linha(bloco_dados_bruto, "Fabricante:")
                print(f" -> Solicitante: {self.solicitante}, Fabricante: {self.fabricante}")

            # 2. Extração de Tabela Sem Grade (PyMuPDF/fitz stream)
            elif chave == 'requisitos':
                 # Supondo que a tabela de Requisitos não tem linhas de grade visíveis
                 self.requisitos = buscar_tabela_sem_grade_pymupdf(pdf_path, tag_inicio)
                 print(f" -> Tabela 'requisitos' (PyMuPDF/Stream) extraída. Linhas: {len(self.requisitos) if not self.requisitos.empty else 0}")
            
            # 3. Extração de Tabela Complexa (Camelot lattice)
            elif chave == 'caracteristicas':
                # Supondo que a tabela de Características é complexa e pode estar segmentada
                self.caracteristicas = extrair_tabela_camelot_segmentada(pdf_path, '3 - Características Técnicas Básicas:', '4 - Entidades Envolvidas')
                print(f" -> Tabela 'caracteristicas' (Camelot/Lattice) extraída. Linhas: {len(self.caracteristicas) if not self.caracteristicas.empty else 0}")

            elif chave == 'ensaios':
                # Supondo que a tabela de Ensaios usa Camelot para maior precisão
                self.ensaios = extrair_tabela_camelot_segmentada(pdf_path, tag_inicio, tag_fim)
                print(f" -> Tabela 'ensaios' (Camelot/Lattice) extraída. Linhas: {len(self.ensaios) if not self.ensaios.empty else 0}")
                
            # Extração de Campos de Texto Simples e Data (Continuação)
            elif chave == 'infos':
                self.data_emissao = buscar_datetime_apos_prefixo(bloco_dados_bruto, "Data de Emissão:")
                self.infos = bloco_dados_bruto
                print(f" -> Data de Emissão: {self.data_emissao}")
            
            elif chave == 'comentarios':
                self.comentarios = bloco_dados_bruto
            
            # ... outros blocos de texto
            
            else:
                 self.data_string = bloco_dados_bruto # Apenas para debug
                 print(f"AVISO: Nenhuma lógica definida. Texto salvo: {bloco_dados_bruto[:50]}...")

        print("\nProcesso de extração serial concluído.")


# --- Demonstração de Uso ---

# Etapa 1: Defina o caminho do seu arquivo PDF
# Substitua pelo seu caminho real:
pdf_caminho = r'C:\Users\tbnobrega\OneDrive - ANATEL\Anatel\_ORCN\Requerimentos\_25.06062\6970-25_RACT.pdf'

if __name__ == '__main__':
    ract_obj = Ract()
    
    # Executa a extração
    ract_obj.extrair_dados_ract(pdf_caminho)
    
    # --- Impressão dos Resultados ---
    print("\n" + "="*50)
    print("RESULTADOS FINAIS NO OBJETO RACT")
    print("="*50)
    print(f"Empresa: {ract_obj.empresa}")
    print(f"Modelos: {ract_obj.modelos}")
    print(f"Data de Emissão: {ract_obj.data_emissao}")
    print(f"Solicitante: {ract_obj.solicitante}")
    print("\n[Tabela de Características (Início)]:")
    # Usar .to_string() para exibir o DataFrame sem truncar no console
    print(ract_obj.caracteristicas.head().to_string() if isinstance(ract_obj.caracteristicas, pd.DataFrame) and not ract_obj.caracteristicas.empty else "N/A")    