from pathlib import Path

from core.log_print import log_info

# Pasta que contém os subdiretórios
pasta = Path(r"C:\Users\tbnobrega\OneDrive - ANATEL\Anatel\_ORCN\req_inbox")


def perguntar_operacao() -> str:
    """Pergunta se o "_" deve ser acrescentado ou removido; repete até receber A ou R."""
    while True:
        resposta = input(
            'Deseja acrescentar "_" (A) ou remover "_" (R) no início dos nomes dos subdiretórios? '
        ).strip().upper()
        if resposta in ("A", "R"):
            return resposta
        log_info("Opção inválida. Digite A ou R.")


operacao = perguntar_operacao()

# Lista fixa para que um diretório renomeado não seja processado novamente.
for subdiretorio in list(pasta.iterdir()):
    if not subdiretorio.is_dir():
        continue

    if operacao == "A" and not subdiretorio.name.startswith("_"):
        novo_nome = subdiretorio.with_name("_" + subdiretorio.name)
    elif operacao == "R" and subdiretorio.name.startswith("_"):
        # Remove todos os "_" do início do nome.
        nome_sem_prefixo = subdiretorio.name.lstrip("_")
        if not nome_sem_prefixo:
            log_info(f"{subdiretorio.name} ignorado: o nome só contém '_'")
            continue
        novo_nome = subdiretorio.with_name(nome_sem_prefixo)
    else:
        continue

    if novo_nome.exists():
        log_info(f"{subdiretorio.name} ignorado: {novo_nome.name} já existe")
        continue

    subdiretorio.rename(novo_nome)
    log_info(f"{subdiretorio.name} -> {novo_nome.name}")

log_info("Renomeação concluída.")