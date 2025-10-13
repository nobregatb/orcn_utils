from rich.console import Console
#console = Console()

def log_info(mensagem):
    print(f"{mensagem}")
    
def log_erro(e):
    print(f"[Erro] {e}")

def log_erro_critico(e):
    print(f"[Erro Crítico] {e}")
