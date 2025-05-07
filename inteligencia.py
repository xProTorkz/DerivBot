import json
import os
from typing import Dict, Any
from datetime import datetime

# Diretório para armazenar os dados de memória
MEMORIA_DIR = "memoria"


def _criar_diretorio_memoria():
    """Cria o diretório de memória se não existir"""
    if not os.path.exists(MEMORIA_DIR):
        os.makedirs(MEMORIA_DIR)


def _obter_arquivo_memoria(cliente_id: str) -> str:
    """Retorna o caminho do arquivo de memória para um cliente"""
    return os.path.join(MEMORIA_DIR, f"{cliente_id}.json")


def carregar_memoria(cliente_id: str) -> Dict[str, Any]:
    """
    Carrega os dados de memória de um cliente
    Args:
        cliente_id: Identificador do cliente
    Returns:
        Dicionário com os dados de memória
    """
    try:
        _criar_diretorio_memoria()
        arquivo = _obter_arquivo_memoria(cliente_id)

        if not os.path.exists(arquivo):
            return {
                "historico": [],
                "ultima_atualizacao": datetime.now().isoformat(),
                "estatisticas": {
                    "total_operacoes": 0,
                    "lucro_total": 0.0,
                    "assertividade": 0.0,
                },
            }

        with open(arquivo, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception as e:
        print(f"Erro ao carregar memória: {e}")
        return {
            "historico": [],
            "ultima_atualizacao": datetime.now().isoformat(),
            "estatisticas": {
                "total_operacoes": 0,
                "lucro_total": 0.0,
                "assertividade": 0.0,
            },
        }


def salvar_memoria(cliente_id: str, dados: Dict[str, Any]) -> bool:
    """
    Salva os dados de memória de um cliente
    Args:
        cliente_id: Identificador do cliente
        dados: Dicionário com os dados a serem salvos
    Returns:
        True se salvou com sucesso, False caso contrário
    """
    try:
        _criar_diretorio_memoria()
        arquivo = _obter_arquivo_memoria(cliente_id)

        # Carrega dados existentes
        dados_existentes = carregar_memoria(cliente_id)

        # Atualiza dados
        dados_existentes["historico"].append(dados)
        dados_existentes["ultima_atualizacao"] = datetime.now().isoformat()

        # Atualiza estatísticas
        historico = dados_existentes["historico"]
        total_ops = len(historico)
        lucro_total = sum(op.get("lucro", 0) for op in historico)
        ops_lucro = sum(1 for op in historico if op.get("lucro", 0) > 0)

        dados_existentes["estatisticas"] = {
            "total_operacoes": total_ops,
            "lucro_total": lucro_total,
            "assertividade": (ops_lucro / total_ops * 100) if total_ops > 0 else 0,
        }

        # Salva dados atualizados
        with open(arquivo, "w", encoding="utf-8") as f:
            json.dump(dados_existentes, f, indent=4, ensure_ascii=False)

        return True

    except Exception as e:
        print(f"Erro ao salvar memória: {e}")
        return False


def limpar_memoria(cliente_id: str) -> bool:
    """
    Limpa os dados de memória de um cliente
    Args:
        cliente_id: Identificador do cliente
    Returns:
        True se limpou com sucesso, False caso contrário
    """
    try:
        arquivo = _obter_arquivo_memoria(cliente_id)
        if os.path.exists(arquivo):
            os.remove(arquivo)
        return True
    except Exception as e:
        print(f"Erro ao limpar memória: {e}")
        return False
