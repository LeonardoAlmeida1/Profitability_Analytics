from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent

MODO = os.getenv("RENTABILIDADE_MODO", "demo").lower()

if MODO == "real":
    DADOS_DIR = BASE_DIR / "dados"
else:
    DADOS_DIR = BASE_DIR / "dados_demo"