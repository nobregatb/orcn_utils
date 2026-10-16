import sys


def _imprimir(mensagem):
    texto = str(mensagem)
    try:
        print(texto)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "utf-8"
        print(texto.encode(encoding, errors="backslashreplace").decode(encoding))

def log_info(mensagem):
    _imprimir(mensagem)
    
def log_erro(e):
    _imprimir(f"[Erro] {e}")

def log_erro_critico(e):
    _imprimir(f"[Erro Crítico] {e}")
