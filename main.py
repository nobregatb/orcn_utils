from core.downloader import baixar_documentos
from core.analyzer import analisar_requerimento
from core.menu import exibir_menu
from core.log_print import log_info, log_erro, log_erro_critico

def main():
    while True:
        try:
            opcao = exibir_menu()
            
            if opcao == "D":
                log_info("Iniciando download de documentos...")
                baixar_documentos()
                print("\n" + "="*50)
                print("Pressione ENTER para voltar ao menu...")
                input()
                
            elif opcao == "A":
                log_info("Iniciando análise de requerimentos...")
                analisar_requerimento()
                print("\n" + "="*50)
                print("Pressione ENTER para voltar ao menu...")
                input()
                
            elif opcao == "S":
                log_info("Encerrando aplicação...")
                print("👋 Até logo!")
                break
                
        except KeyboardInterrupt:
            log_erro("\nOperação cancelada pelo usuário.")
            print("👋 Encerrando aplicação...")
            break
        except Exception as e:
            log_erro_critico(f"Erro crítico no main: {str(e)}")
            print("❌ Erro inesperado. Retornando ao menu...")
            print("Pressione ENTER para continuar...")
            input()

if __name__ == "__main__":
    main()