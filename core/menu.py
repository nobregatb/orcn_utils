# main.py
#import msvcrt as getch
#from rich.console import Console
#console = Console()

from core.const import TITULO_APLICACAO, DESCRICOES_MENU, OPCOES_MENU

def exibir_menu():
    #console.clear() # Limpa a tela de forma elegante e cross-platform
    print(f"{TITULO_APLICACAO}\n")
    print("Opções: \n")
    print(f"  {OPCOES_MENU['download']}. {DESCRICOES_MENU['D']}\n")
    print(f"  {OPCOES_MENU['analise']}. {DESCRICOES_MENU['A']}\n")
    print(f"  {OPCOES_MENU['sair']}. {DESCRICOES_MENU['S']}\n")
    
    while True:
        try:
            #console.print("[bold cyan]Escolha uma opção (D, A, S): ", end="", highlight=False)
            resposta = input("\nEscolha uma opção (D, A, S):  ").strip().upper()
            
            # Validar entrada
            if resposta in [OPCOES_MENU['download'], OPCOES_MENU['analise'], OPCOES_MENU['sair']]:
                return resposta
            else:
                print("ERRO - Opcao invalida! Digite D, A ou S.")
                
        except KeyboardInterrupt:
            print("\nERRO - Operacao cancelada pelo usuario.")
            return OPCOES_MENU['sair']  # Sair quando cancelado
        except Exception as e:
            print(f"ERRO - Erro inesperado: {str(e)}")
            print("Tente novamente ou pressione Ctrl+C para sair.")
            #resposta = getch.getch()
            #return resposta.decode('UTF-8').upper()