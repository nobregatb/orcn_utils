from pathlib import Path

# Pasta que contém os subdiretórios
pasta = Path(r"C:\Users\tbnobrega\OneDrive - ANATEL\Anatel\_ORCN\req_inbox")

for subdiretorio in pasta.iterdir():
    if subdiretorio.is_dir() and not subdiretorio.name.startswith("_"):
        novo_nome = subdiretorio.with_name("_" + subdiretorio.name)
        subdiretorio.rename(novo_nome)
        print(f"{subdiretorio.name} -> {novo_nome.name}")

print("Renomeação concluída.")