# -*- coding: utf-8 -*-
"""
Script para preencher o log de downloads com requerimentos já baixados.
Marca os requerimentos especificados como concluídos no log.
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# Adiciona o diretório raiz ao path para imports
sys.path.append(str(Path(__file__).parent))

from core.utils import (
    marcar_requerimento_concluido, get_download_log_path,
    carregar_log_downloads
)
from core.log_print import log_info


def preencher_log_requerimentos_baixados():
    """Preenche o log com requerimentos que já foram baixados."""
    
    # Lista de requerimentos já baixados (formato original: XXXXX/25)
    requerimentos_baixados = [
        "07339/25", "07347/25", "07334/25", "07345/25", "07300/25", "07337/25", "07328/25", "07330/25", "07333/25", "07329/25", "06702/25", "07317/25", "07312/25", "07311/25", "07310/25", "07305/25", "07304/25", "07302/25", "07301/25", "07292/25", "07296/25", "07295/25", "07287/25", "07289/25", "07293/25", "07291/25", "07290/25", "07278/25", "07256/25", "07286/25", "07285/25", "07283/25", "07284/25", "07282/25", "07281/25", "07262/25", "07276/25", "07279/25"
    ]
    
    print("📋 PREENCHIMENTO DO LOG DE DOWNLOADS")
    print("=" * 45)
    
    # Converte para formato padrão do sistema (XXXXX/2025)
    requerimentos_formatados = []
    for req in requerimentos_baixados:
        # Converte de XXXXX/25 para XXXXX/2025
        num, ano_curto = req.split("/")
        req_formatado = f"{num}/{ano_curto}"
        requerimentos_formatados.append(req_formatado)
    
    print(f"🔄 Convertendo {len(requerimentos_baixados)} requerimentos para formato padrão...")
    
    # Verifica se já existe log
    log_path = get_download_log_path()
    log_existente = carregar_log_downloads()
    
    if log_existente:
        print(f"📋 Log existente encontrado com {len(log_existente)} requerimento(s)")
        print("⚠️  Os requerimentos especificados serão adicionados/atualizados")
    else:
        print("📝 Criando novo arquivo de log")
    
    # Marca cada requerimento como concluído
    sucessos = 0
    for req_original, req_formatado in zip(requerimentos_baixados, requerimentos_formatados):
        # Usa um número padrão de arquivos baixados (5) para requerimentos já processados
        if marcar_requerimento_concluido(req_formatado, 5):
            print(f"✅ {req_original} -> {req_formatado} marcado como concluído")
            sucessos += 1
        else:
            print(f"❌ Erro ao marcar {req_original} -> {req_formatado}")
    
    print("\n" + "=" * 45)
    print(f"📊 RESUMO:")
    print(f"  • Total de requerimentos: {len(requerimentos_baixados)}")
    print(f"  • Marcados com sucesso: {sucessos}")
    print(f"  • Falhas: {len(requerimentos_baixados) - sucessos}")
    
    if sucessos > 0:
        print(f"✅ Log salvo em: {log_path}")
        
        # Mostra alguns exemplos do log criado
        log_final = carregar_log_downloads()
        print(f"\n📋 Exemplos do log criado:")
        count = 0
        for req, status in log_final.items():
            if count < 3:  # Mostra apenas os primeiros 3
                print(f"  {req}: {status}")
                count += 1
        if len(log_final) > 3:
            print(f"  ... e mais {len(log_final) - 3} requerimento(s)")
    
    print("\n🎉 Processo concluído!")
    print("💡 Agora quando executar o download, estes requerimentos serão pulados automaticamente.")


if __name__ == "__main__":
    preencher_log_requerimentos_baixados()