#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para mover requerimentos baseado na planilha ORCN.xlsx
Lê a coluna B da aba "Requerimentos-Análise" e move as pastas correspondentes
de Requerimentos/ para req_analisados/

Formato esperado:
- Planilha: XXXXX/AA (ex: 12345/24)
- Diretório: AA.XXXXX (ex: 24.12345)

Autor: Teógenes Brito da Nóbrega
"""

import pandas as pd
import shutil
from pathlib import Path
import logging
from datetime import datetime
import sys

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('move_requerimentos.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Configurar encoding para Windows
import os
if os.name == 'nt':  # Windows
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())

def configurar_caminhos():
    """Configura os caminhos base do sistema."""
    base_orcn = Path(r"C:\Users\tbnobrega\OneDrive - ANATEL\Anatel\_ORCN")
    
    caminhos = {
        'planilha': base_orcn / "ORCN.xlsx",
        'pasta_origem': base_orcn / "Requerimentos",
        'pasta_destino': base_orcn / "req_analisados"
    }
    
    return caminhos

def validar_caminhos(caminhos):
    """Valida se os caminhos existem."""
    erros = []
    
    if not caminhos['planilha'].exists():
        erros.append(f"Planilha não encontrada: {caminhos['planilha']}")
    
    if not caminhos['pasta_origem'].exists():
        erros.append(f"Pasta de origem não encontrada: {caminhos['pasta_origem']}")
    
    # Criar pasta de destino se não existir
    caminhos['pasta_destino'].mkdir(exist_ok=True)
    logger.info(f"Pasta de destino verificada/criada: {caminhos['pasta_destino']}")
    
    if erros:
        for erro in erros:
            logger.error(erro)
        return False
    
    return True

def ler_planilha(caminho_planilha):
    """Lê a planilha ORCN.xlsx e extrai os requerimentos da coluna B."""
    try:
        logger.info(f"Lendo planilha: {caminho_planilha}")
        
        # Ler a aba "Requerimentos-Análise"
        df = pd.read_excel(caminho_planilha, sheet_name="Requerimentos-Análise")
        
        # Extrair coluna B (índice 1, assumindo que A=0, B=1)
        # Verificar se existe a coluna B
        if df.shape[1] < 2:
            logger.error("Planilha não possui coluna B")
            return []
        
        # Pegar valores da coluna B, removendo valores nulos/vazios
        coluna_b = df.iloc[:, 1].dropna()  # Segunda coluna (índice 1)
        
        # Filtrar apenas valores que parecem ser requerimentos (formato XXXXX/AA)
        requerimentos = []
        for valor in coluna_b:
            if isinstance(valor, str) and '/' in valor:
                partes = valor.strip().split('/')
                if len(partes) == 2:
                    try:
                        numero = partes[0].strip()
                        ano = partes[1].strip()
                        
                        # Validar formato básico
                        if numero.isdigit() and ano.isdigit() and len(ano) == 2:
                            requerimentos.append(valor.strip())
                    except:
                        continue
        
        logger.info(f"Encontrados {len(requerimentos)} requerimentos na planilha")
        return requerimentos
        
    except Exception as e:
        logger.error(f"Erro ao ler planilha: {str(e)}")
        return []

def converter_formato(req_planilha):
    """
    Converte formato da planilha (XXXXX/AA) para formato do diretório (AA.XXXXX).
    
    Args:
        req_planilha: String no formato "XXXXX/AA" (ex: "12345/24")
    
    Returns:
        String no formato "AA.XXXXX" (ex: "24.12345")
    """
    try:
        partes = req_planilha.split('/')
        numero = partes[0].strip()
        ano = partes[1].strip()
        
        # Converter para formato de diretório
        formato_diretorio = f"{ano}.{numero}"
        return formato_diretorio
        
    except:
        logger.error(f"Erro ao converter formato: {req_planilha}")
        return None

def encontrar_pasta_requerimento(pasta_origem, nome_diretorio):
    """Encontra a pasta correspondente ao requerimento."""
    try:
        # Buscar pasta exata
        pasta_req = pasta_origem / nome_diretorio
        if pasta_req.exists() and pasta_req.is_dir():
            return pasta_req
        
        # Buscar pasta com prefixo _ (formato alternativo)
        pasta_req_alt = pasta_origem / f"_{nome_diretorio}"
        if pasta_req_alt.exists() and pasta_req_alt.is_dir():
            return pasta_req_alt
        
        return None
        
    except Exception as e:
        logger.error(f"Erro ao buscar pasta {nome_diretorio}: {str(e)}")
        return None

def mover_requerimento(pasta_origem, pasta_destino, criar_backup=True):
    """Move uma pasta de requerimento com backup opcional."""
    try:
        nome_pasta = pasta_origem.name
        destino_final = pasta_destino / nome_pasta
        
        # Verificar se já existe no destino
        if destino_final.exists():
            if criar_backup:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_nome = f"{nome_pasta}_backup_{timestamp}"
                backup_destino = pasta_destino / backup_nome
                
                logger.warning(f"Pasta já existe no destino. Criando backup: {backup_nome}")
                shutil.move(str(destino_final), str(backup_destino))
            else:
                logger.warning(f"Pasta já existe no destino, pulando: {nome_pasta}")
                return False
        
        # Mover pasta
        shutil.move(str(pasta_origem), str(destino_final))
        logger.info(f"✅ Movido: {pasta_origem.name} → {destino_final}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro ao mover {pasta_origem.name}: {str(e)}")
        return False

def processar_requerimentos(requerimentos, caminhos):
    """Processa a lista de requerimentos e move as pastas correspondentes."""
    logger.info(f"Iniciando processamento de {len(requerimentos)} requerimentos")
    
    estatisticas = {
        'processados': 0,
        'movidos': 0,
        'nao_encontrados': 0,
        'erros': 0
    }
    
    reqs_nao_encontrados = []
    
    for req_planilha in requerimentos:
        logger.info(f"Processando: {req_planilha}")
        estatisticas['processados'] += 1
        
        # Converter formato
        nome_diretorio = converter_formato(req_planilha)
        if not nome_diretorio:
            logger.error(f"❌ Formato inválido: {req_planilha}")
            estatisticas['erros'] += 1
            continue
        
        # Encontrar pasta
        pasta_req = encontrar_pasta_requerimento(caminhos['pasta_origem'], nome_diretorio)
        
        if not pasta_req:
            logger.warning(f"⚠️ Pasta não encontrada: {nome_diretorio} (de {req_planilha})")
            reqs_nao_encontrados.append(req_planilha)
            estatisticas['nao_encontrados'] += 1
            continue
        
        # Mover pasta
        if mover_requerimento(pasta_req, caminhos['pasta_destino']):
            estatisticas['movidos'] += 1
        else:
            estatisticas['erros'] += 1
    
    # Relatório final
    logger.info("\n" + "="*50)
    logger.info("RELATÓRIO FINAL")
    logger.info("="*50)
    logger.info(f"📊 Requerimentos processados: {estatisticas['processados']}")
    logger.info(f"✅ Pastas movidas com sucesso: {estatisticas['movidos']}")
    logger.info(f"⚠️ Pastas não encontradas: {estatisticas['nao_encontrados']}")
    logger.info(f"❌ Erros durante processamento: {estatisticas['erros']}")
    
    if reqs_nao_encontrados:
        logger.info(f"\n📝 Requerimentos não encontrados:")
        for req in reqs_nao_encontrados:
            logger.info(f"   - {req}")
    
    return estatisticas

def main():
    """Função principal do script."""
    logger.info("="*60)
    logger.info("SCRIPT DE MOVIMENTAÇÃO DE REQUERIMENTOS ORCN")
    logger.info("="*60)
    
    try:
        # Configurar caminhos
        caminhos = configurar_caminhos()
        logger.info(f"Planilha: {caminhos['planilha']}")
        logger.info(f"Origem: {caminhos['pasta_origem']}")
        logger.info(f"Destino: {caminhos['pasta_destino']}")
        
        # Validar caminhos
        if not validar_caminhos(caminhos):
            logger.error("❌ Validação de caminhos falhou. Encerrando.")
            return
        
        # Ler planilha
        requerimentos = ler_planilha(caminhos['planilha'])
        if not requerimentos:
            logger.error("❌ Nenhum requerimento encontrado na planilha. Encerrando.")
            return
        
        # Mostrar prévia
        logger.info(f"\n📋 Requerimentos encontrados na planilha ({len(requerimentos)}):")
        for i, req in enumerate(requerimentos[:10], 1):  # Mostrar apenas os 10 primeiros
            nome_dir = converter_formato(req)
            logger.info(f"   {i:2d}. {req} → {nome_dir}")
        
        if len(requerimentos) > 10:
            logger.info(f"   ... e mais {len(requerimentos) - 10} requerimentos")
        
        # Confirmar operação
        resposta = input(f"\n❓ Confirma a movimentação de {len(requerimentos)} requerimentos? (s/N): ").strip().lower()
        
        if resposta not in ['s', 'sim', 'y', 'yes']:
            logger.info("❌ Operação cancelada pelo usuário.")
            return
        
        # Processar requerimentos
        logger.info("\n🚀 Iniciando movimentação...")
        estatisticas = processar_requerimentos(requerimentos, caminhos)
        
        logger.info(f"\n🎉 Processamento concluído!")
        
    except KeyboardInterrupt:
        logger.info("\n❌ Operação interrompida pelo usuário (Ctrl+C)")
    except Exception as e:
        logger.error(f"❌ Erro crítico: {str(e)}")

if __name__ == "__main__":
    main()
