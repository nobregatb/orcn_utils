
import fitz
import pymupdf4llm
import json
import re
import time
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import os

def find_cct_files(home_dir: str) -> List[Path]:
    """
    Encontra arquivos PDF de CCT no diretório especificado
    
    Args:
        search_dir: Nome do diretório ou '*' para busca recursiva
    
    Returns:
        Lista de caminhos para arquivos CCT encontrados
    """
    pattern = "[Manual do Produto]"
    files = []
    
    diretorio =  Path(home_dir)

    for pdf_file in diretorio.rglob("*.pdf"):
        if pattern in pdf_file.name:
            files.append(pdf_file)

    
    return files

def extrair_dados_do_manual(texto_pdf):
    """
    Extrai dados usando Ollama (LLM local) - requer Ollama instalado.
    Instale com: curl -fsSL https://ollama.com/install.sh | sh
    E baixe um modelo: ollama pull tinyllama
    """
    try:
        import requests
        
        prompt = f"""Analise o seguinte manual do(s) equipamento(s) e extraia as informações em formato JSON.

Texto do manual:
{texto_pdf}

Extraia APENAS estes campos e retorne um JSON válido:
1. "modelos": Os modelos listados no manual
2. "tipo_de_produto": O(s) tipo(s) de produto identificado(s) no manual

Formato esperado:
{{"modelos": "...", "tipo_de_produto": "..."}}

Retorne APENAS o JSON, sem explicações. """

        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                'model': 'tinyllama', # 'mistral',
                'prompt': prompt,
                'stream': False
            },
            timeout=120
        )
        
        if response.status_code == 200:
            resultado = response.json()
            resposta_texto = resultado.get('response', '')
            
            # Extrai JSON da resposta
            json_match = re.search(r'\{.*\}', resposta_texto, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
        
    except Exception as e:
        print(f"Erro ao usar Ollama: {e}")

def extrair_dados_documento_llm(pdf_path, documento):
    # Extrai o texto do PDF usando pymupdf4llm
    pdf = fitz.open(pdf_path)
    texto_pdf = ""
    for pagina in pdf:
        texto_pdf += pagina.get_text() + "\n"
    pdf.close()  
    if documento == 'manual':
        return extrair_dados_do_manual(texto_pdf)
    elif documento == 'CCT':
        return extrair_dados_do_cct(texto_pdf)


def extrair_e_salvar_json(pdf_path, output_json_path=None, metodo='regex'):
    """
    Extrai dados do PDF e salva em arquivo JSON.
    
    Args:
        pdf_path (str): Caminho para o arquivo PDF
        output_json_path (str, optional): Caminho para salvar o JSON
        metodo (str): 'regex' ou 'ollama'
        
    Returns:
        dict: Dicionário com os dados extraídos
    """
    dados = extrair_dados_certificado(pdf_path, metodo)
    
    if output_json_path:
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
        print(f"Dados salvos em: {output_json_path}")
    
    return dados


# Exemplo de uso
if __name__ == "__main__":
    search_dir = "C:\\Users\\tbnobrega\\OneDrive - ANATEL\\Anatel\\_ORCN\\Requerimentos"    

    files = find_cct_files(search_dir)

    for file in files:
        print("\n=== Usando OLLAMA (manual) ===")
        print("-"*50)
        print(f"Processando arquivo: {file}")        
        # Marca o tempo de início
        tempo_inicio = time.time()        
        dados = extrair_dados_documento_llm(file, documento='manual')        
        # Calcula o tempo decorrido
        tempo_fim = time.time()
        tempo_decorrido = tempo_fim - tempo_inicio        
        
        # Imprime cada chave e valor em linhas separadas
        if dados:
            for key, value in dados.items():
                print(f"{key}: {value}")
        else:
            print("Nenhum dado extraído")
        
        print(f"Tempo de execução: {tempo_decorrido:.2f} segundos")
        print("-"*50)
    
    x = 1
    # Salvar em arquivo
    # extrair_e_salvar_json(pdf_file, "dados_certificado.json", metodo='regex')