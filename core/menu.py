# main.py
#import msvcrt as getch
#from rich.console import Console
#console = Console()

def exibir_menu():
    #console.clear() # Limpa a tela de forma elegante e cross-platform
    print("*** # ORCN - Download e análise de processos ***\n")
    print("Opções: \n")
    print("  D. Baixar documentos (SCH ANATEL)\n")
    print("  A. Analisar requerimento(s) (Análise automatizada)\n")
    print("  S. Sair\n")
    
    while True:
        try:
            #console.print("[bold cyan]Escolha uma opção (D, A, S): ", end="", highlight=False)
            resposta = input("\nEscolha uma opção (D, A, S):  ").strip().upper()
            
            # Validar entrada
            if resposta in ['D', 'A', 'S']:
                return resposta
            else:
                print("❌ Opção inválida! Digite D, A ou S.")
                
        except KeyboardInterrupt:
            print("\n❌ Operação cancelada pelo usuário.")
            return 'S'  # Sair quando cancelado
        except Exception as e:
            print(f"❌ Erro inesperado: {str(e)}")
            print("Tente novamente ou pressione Ctrl+C para sair.")
            #resposta = getch.getch()
            #return resposta.decode('UTF-8').upper()