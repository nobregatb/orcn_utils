from core.downloader import baixar_documentos
from core.analyzer import analisar_requerimento
from core.menu import exibir_menu
from core.log_print import log_info, log_erro, log_erro_critico
from core.const import OPCOES_MENU, SEPARADOR_MENOR

def main():
    while True:
        try:
            opcao = exibir_menu()
            
            if opcao == OPCOES_MENU['download']:
                log_info("Iniciando download de documentos...")
                baixar_documentos()
                log_info("\n" + SEPARADOR_MENOR)
                log_info("Pressione ENTER para voltar ao menu...")
                input()
                
            elif opcao == OPCOES_MENU['analise']:
                log_info("Iniciando análise de requerimentos...")
                analisar_requerimento()
                log_info("\n" + SEPARADOR_MENOR)
                log_info("Pressione ENTER para voltar ao menu...")
                input()
                
            elif opcao == OPCOES_MENU['sair']:
                log_info("Encerrando aplicação...")
                log_info("Ate logo!")
                break
                
        except KeyboardInterrupt:
            log_erro("\nOperação cancelada pelo usuário.")
            log_info("Encerrando aplicação...")
            break
        except Exception as e:
            log_erro_critico(f"Erro crítico no main: {str(e)}")
            log_info("ERRO - Erro inesperado. Retornando ao menu...")
            log_info("Pressione ENTER para continuar...")
            input()

if __name__ == "__main__":
    main()