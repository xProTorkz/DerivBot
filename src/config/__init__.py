# Módulo de configuração
try:
    from src.config.config import *
except (ImportError, ModuleNotFoundError):
    from config.config import *

