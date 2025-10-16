#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste de integração para o processamento automático de arquivos JSON de requerimentos
e atualização do arquivo ocds.json.

Autor: TBN
Data: 17/01/2025
"""

import json
import os
from pathlib import Path
from datetime import datetime

def criar_teste_requerimento_json():
    """Cria um arquivo JSON de teste para simular um requerimento com dados de OCD."""
    
    # Dados de teste do requerimento
    dados_teste = {
        "numero_requerimento": "2025.12345",
        "data_solicitacao": "15/01/2025",
        "solicitante": {
            "nome": "Empresa Teste LTDA",
            "cnpj": "12.345.678/0001-90"
        },
        "ocd": {
            "CNPJ": "35.983.502/0001-64",
            "Nome": "INSTITUTO DE PESQUISAS TECNOLÓGICAS DO ESTADO DE SÃO PAULO S.A. - IPT",
            "Data do Certificado": "20/01/2025",
            "Endereço": "AV. PROF. ALMEIDA PRADO, 532 - CIDADE UNIVERSITÁRIA",
            "Cidade": "SÃO PAULO",
            "UF": "SP",
            "Telefone": "(11) 3767-4000"
        },
        "equipamentos": [
            {
                "tipo": "Equipamento de Radiocomunicação",
                "modelo": "TX-5000",
                "fabricante": "TesteCorp"
            }
        ],
        "observacoes": "Teste de integração automática com atualização de OCDS"
    }
    
    # Criar pasta de teste se não existir
    pasta_teste = Path("C:/Users/tbnobrega/Desktop/orcn_utils/tbn_files/requerimentos/2025.12345")
    pasta_teste.mkdir(parents=True, exist_ok=True)
    
    # Salvar arquivo JSON de teste
    arquivo_json = pasta_teste / "2025.12345.json"
    with open(arquivo_json, 'w', encoding='utf-8') as f:
        json.dump(dados_teste, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Arquivo de teste criado: {arquivo_json}")
    print(f"📊 Dados do OCD no teste:")
    print(f"   - CNPJ: {dados_teste['ocd']['CNPJ']}")
    print(f"   - Nome: {dados_teste['ocd']['Nome']}")
    print(f"   - Data: {dados_teste['ocd']['Data do Certificado']}")
    
    return arquivo_json

def verificar_ocds_antes_depois():
    """Verifica o estado do arquivo ocds.json antes e depois do teste."""
    
    ocds_file = Path("C:/Users/tbnobrega/Desktop/orcn_utils/utils/ocds.json")
    
    if ocds_file.exists():
        with open(ocds_file, 'r', encoding='utf-8') as f:
            dados_ocds = json.load(f)
        
        print(f"📁 Estado atual do ocds.json:")
        print(f"   - Total de registros: {len(dados_ocds)}")
        
        # Verificar se o CNPJ de teste já existe
        cnpj_teste = "35.983.502/0001-64"
        registro_existente = None
        
        for ocd in dados_ocds:
            if ocd.get("cnpj") == cnpj_teste:
                registro_existente = ocd
                break
        
        if registro_existente:
            print(f"   - CNPJ {cnpj_teste} encontrado:")
            print(f"     Nome: {registro_existente.get('nome')}")
            print(f"     Data: {registro_existente.get('data_atualizacao')}")
        else:
            print(f"   - CNPJ {cnpj_teste} não encontrado (será adicionado)")
            
        return dados_ocds
    else:
        print("❌ Arquivo ocds.json não encontrado!")
        return None

def main():
    """Função principal do teste de integração."""
    
    print("🔍 TESTE DE INTEGRAÇÃO - Processamento automático de JSON")
    print("=" * 60)
    
    # 1. Verificar estado inicial do ocds.json
    print("\n1️⃣ Verificando estado inicial do ocds.json...")
    dados_iniciais = verificar_ocds_antes_depois()
    
    # 2. Criar arquivo de teste
    print("\n2️⃣ Criando arquivo JSON de teste...")
    arquivo_teste = criar_teste_requerimento_json()
    
    # 3. Instruções para o usuário
    print("\n3️⃣ Próximos passos:")
    print("   📝 Execute o AnalisadorRequerimentos no requerimento 2025.12345")
    print("   📝 O sistema deve automaticamente:")
    print("      - Detectar o arquivo 2025.12345.json")
    print("      - Extrair dados do OCD")
    print("      - Atualizar ocds.json com data mais recente (20/01/2025)")
    print("   📝 Verifique o arquivo ocds.json após a execução")
    
    print("\n4️⃣ Para testar, execute:")
    print("   python main.py")
    print("   # Depois selecione a opção de análise de requerimentos")
    print("   # E analise o requerimento 2025.12345")
    
    print("\n✅ Teste preparado com sucesso!")

if __name__ == "__main__":
    main()