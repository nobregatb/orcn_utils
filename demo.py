import pymupdf4llm
import json
import re

def extrair_dados_com_regex(texto_pdf):
    """
    Extrai dados usando expressões regulares (método offline).
    """
    resultado = {
        'modelos': None,
        'tipo_de_produto': None,
        'normas_tecnicas_aplicaveis': []
    }
    
    # Extrai Modelo(s)
    match_modelo = re.search(r'Modelo\(s\):\s*\n?\s*(.+?)(?:\n|Tipo de Produto)', texto_pdf, re.IGNORECASE | re.DOTALL)
    if match_modelo:
        resultado['modelos'] = match_modelo.group(1).strip()
    
    # Extrai Tipo de Produto
    match_tipo = re.search(r'Tipo de Produto:\s*\n?\s*(.+?)(?:\n|Serviço)', texto_pdf, re.IGNORECASE)
    if match_tipo:
        resultado['tipo_de_produto'] = match_tipo.group(1).strip()
    
    # Extrai Normas Técnicas Aplicáveis
    normas_section = re.search(
        r'Norma\(s\)\s+Técnica\(s\)\s+Aplicável\(eis\)(.*?)(?:Diretor de Tecnologia|Características Técnicas|Campinas)',
        texto_pdf,
        re.IGNORECASE | re.DOTALL
    )
    
    if normas_section:
        normas_texto = normas_section.group(1)
        
        # Encontra todos os Atos
        atos = re.findall(
            r'(Ato\s+N[oº°]\s*[\d.]+.*?(?:de\s+\d{1,2}\s+de\s+\w+\s+de\s+\d{4}).*?["""].*?["""])',
            normas_texto,
            re.IGNORECASE | re.DOTALL
        )
        
        for ato in atos:
            ato_limpo = ' '.join(ato.split())
            ato_limpo = ato_limpo.replace('"', '"').replace('"', '"')
            # Remove quebras de linha extras
            ato_limpo = re.sub(r'\s+', ' ', ato_limpo)
            resultado['normas_tecnicas_aplicaveis'].append(ato_limpo)
        
        # Busca por Resoluções e Anexos
        resolucoes = re.findall(
            r'((?:Anexo à )?Resolução\s+N[oº°]\s*[\d.]+.*?(?:de\s+\d{1,2}\s+de\s+\w+\s+de\s+\d{4}).*?["""].*?["""])',
            normas_texto,
            re.IGNORECASE | re.DOTALL
        )
        
        for resolucao in resolucoes:
            resolucao_limpa = ' '.join(resolucao.split())
            resolucao_limpa = resolucao_limpa.replace('"', '"').replace('"', '"')
            resolucao_limpa = re.sub(r'\s+', ' ', resolucao_limpa)
            resultado['normas_tecnicas_aplicaveis'].append(resolucao_limpa)
    
    return resultado


def extrair_dados_com_ollama(texto_pdf):
    """
    Extrai dados usando Ollama (LLM local) - requer Ollama instalado.
    Instale com: curl -fsSL https://ollama.com/install.sh | sh
    E baixe um modelo: ollama pull llama2
    """
    try:
        import requests
        
        prompt = f"""Analise o seguinte certificado de conformidade técnica e extraia as informações em formato JSON.

Texto do certificado:
{texto_pdf}  # Limita o tamanho para evitar erros

Extraia APENAS estes campos e retorne um JSON válido:
1. "modelos": Os modelos listados no certificado
2. "tipo_de_produto": O(s) tipo(s) de produto identificado(s) no certificado
3. "normas_tecnicas_aplicaveis": Lista de normas técnicas (Atos, Resoluções)

Formato esperado:
{{"modelos": "...", "tipo_de_produto": "...", "normas_tecnicas_aplicaveis": ["..."]}}

Retorne APENAS o JSON, sem explicações."""

        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                'model': 'tinyllama',
                'prompt': prompt,
                'stream': False
            },
            timeout=80
        )
        
        if response.status_code == 200:
            resultado = response.json()
            resposta_texto = resultado.get('response', '')
            
            # Extrai JSON da resposta
            json_match = re.search(r'\{.*\}', resposta_texto, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
        
        # Se falhar, usa regex
        print("Ollama não retornou resultado válido, usando regex...")
        return extrair_dados_com_regex(texto_pdf)
        
    except Exception as e:
        print(f"Erro ao usar Ollama: {e}")
        print("Usando extração com regex...")
        return extrair_dados_com_regex(texto_pdf)


def extrair_dados_certificado(pdf_path, metodo='regex'):
    """
    Extrai dados estruturados de um certificado de conformidade técnica PDF.
    
    Args:
        pdf_path (str): Caminho para o arquivo PDF
        metodo (str): 'regex' (padrão, offline) ou 'ollama' (requer Ollama instalado)
        
    Returns:
        dict: Dicionário com os dados extraídos
    """
    # Extrai o texto do PDF usando pymupdf4llm
    texto_pdf = pymupdf4llm.to_markdown(pdf_path)
    
    if metodo == 'ollama':
        return extrair_dados_com_ollama(texto_pdf)
    else:
        return extrair_dados_com_regex(texto_pdf)


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
    pdf_file = "C:\\Users\\tbnobrega\\OneDrive - ANATEL\\Anatel\\_ORCN\\Requerimentos\\25.06062\\6970-25_CERT_CONFORMIDADE.pdf"
    
    # Método 1: Usando regex (offline, sem dependências extras)
    print("=== Usando REGEX (offline) ===")
    dados = extrair_dados_certificado(pdf_file, metodo='regex')
    print(json.dumps(dados, ensure_ascii=False, indent=2))
    
    # Método 2: Usando Ollama (requer instalação)
    print("\n=== Usando OLLAMA (LLM local) ===")
    dados = extrair_dados_certificado(pdf_file, metodo='ollama')
    print(json.dumps(dados, ensure_ascii=False, indent=2))
    
    x = 1
    # Salvar em arquivo
    # extrair_e_salvar_json(pdf_file, "dados_certificado.json", metodo='regex')