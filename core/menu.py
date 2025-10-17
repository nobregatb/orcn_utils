# main.py
#import msvcrt as getch
#from rich.console import Console
#console = Console()

from core.const import TITULO_APLICACAO, DESCRICOES_MENU, OPCOES_MENU
from core.log_print import log_info

def exibir_menu():
    #console.clear() # Limpa a tela de forma elegante e cross-platform
    log_info(f"{TITULO_APLICACAO}\n")
    log_info("Opções: \n")
    log_info(f"  {OPCOES_MENU['download']}. {DESCRICOES_MENU['D']}\n")
    log_info(f"  {OPCOES_MENU['analise']}. {DESCRICOES_MENU['A']}\n")
    log_info(f"  {OPCOES_MENU['sair']}. {DESCRICOES_MENU['S']}\n")
    
    while True:
        try:
            #console.print("[bold cyan]Escolha uma opção (D, A, S): ", end="", highlight=False)
            resposta = input("\nEscolha uma opção (D, A, S):  ").strip().upper()
            
            # Validar entrada
            if resposta in [OPCOES_MENU['download'], OPCOES_MENU['analise'], OPCOES_MENU['sair']]:
                return resposta
            else:
                log_info("ERRO - Opcao invalida! Digite D, A ou S.")
                
        except KeyboardInterrupt:
            log_info("\nERRO - Operacao cancelada pelo usuario.")
            return OPCOES_MENU['sair']  # Sair quando cancelado
        except Exception as e:
            log_info(f"ERRO - Erro inesperado: {str(e)}")
            log_info("Tente novamente ou pressione Ctrl+C para sair.")
            #resposta = getch.getch()
            #return resposta.decode('UTF-8').upper()