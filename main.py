from core.downloader import baixar_documentos
from core.analyzer import analisar_requerimento
from core.menu import exibir_menu
from core.log_print import log_info, log_erro, log_erro_critico
from core.const import OPCOES_MENU, SEPARADOR_MENOR

def obter_tipo_download():
    """
    Pergunta ao usuário o tipo de download a ser realizado.
    
    Returns:
        bool: True para retornos para estudo, False para requerimentos em análise
    """
    log_info("\n" + SEPARADOR_MENOR)
    log_info("TIPO DE DOWNLOAD")
    log_info(SEPARADOR_MENOR)
    log_info("\nEscolha o tipo de download:")
    log_info("1. Retornos para estudo")
    log_info("2. Requerimentos em análise")
    
    while True:
        try:
            opcao = input("\nDigite sua opção (1/2): ").strip()
            
            if opcao == "1":
                log_info("Selecionado: Retornos para estudo")
                return True
            elif opcao == "2":
                log_info("Selecionado: Requerimentos em análise")
                return False
            else:
                log_info("Opção inválida. Digite 1 ou 2.")
                
        except KeyboardInterrupt:
            log_info("\nOperação cancelada pelo usuário.")
            return None
        except Exception as e:
            log_erro(f"Erro inesperado na seleção de tipo: {str(e)}")
            log_info("Erro inesperado. Tente novamente.")

def main():
    while True:
        try:
            opcao = exibir_menu()
            
            if opcao == OPCOES_MENU['download']:
                log_info("Iniciando download de documentos...")
                
                # Obter tipo de download do usuário
                retorno_para_estudo = obter_tipo_download()
                
                # Se usuário cancelou a seleção, volta ao menu principal
                if retorno_para_estudo is None:
                    continue
                
                baixar_documentos(retorno_para_estudo)
                print("\n" + SEPARADOR_MENOR)
                print("Pressione ENTER para voltar ao menu...")
                input()
                
            elif opcao == OPCOES_MENU['analise']:
                log_info("Iniciando análise de requerimentos...")
                analisar_requerimento()
                print("\n" + SEPARADOR_MENOR)
                print("Pressione ENTER para voltar ao menu...")
                input()
                
            elif opcao == OPCOES_MENU['sair']:
                log_info("Encerrando aplicação...")
                print("Ate logo!")
                break
                
        except KeyboardInterrupt:
            log_erro("\nOperação cancelada pelo usuário.")
            print("Encerrando aplicação...")
            break
        except Exception as e:
            log_erro_critico(f"Erro crítico no main: {str(e)}")
            print("ERRO - Erro inesperado. Retornando ao menu...")
            print("Pressione ENTER para continuar...")
            input()

if __name__ == "__main__":
    main()