#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Gerador de Licenças para DerivBot
---------------------------------
Este script gera e gerencia licenças para o DerivBot com diferentes planos:
- FREE: Acesso limitado por 7 dias
- MENSAL: Acesso por 30 dias
- VITALÍCIO: Acesso permanente

Uso:
    python gerador_licencas.py criar -e email@exemplo.com -p vitalicio
    python gerador_licencas.py listar
    python gerador_licencas.py revogar -c CODIGO_LICENCA
    python gerador_licencas.py atualizar -c CODIGO_LICENCA -p mensal
"""

import os
import sys
import json
import uuid
import string
import random
import argparse
from datetime import datetime, timedelta

# Configurações
LICENCAS_FILE = "data/licencas.json"
PLANOS = {
    "free": {"dias_validade": 7, "limite_operacoes": 100},
    "mensal": {"dias_validade": 30, "limite_operacoes": 1000},
    "vitalicio": {
        "dias_validade": None,  # Sem validade
        "limite_operacoes": None,  # Sem limite
    },
}


def gerar_codigo_licenca(tamanho=15):
    """Gera um código de licença alfanumérico aleatório."""
    caracteres = string.ascii_letters + string.digits
    return "".join(random.choice(caracteres) for _ in range(tamanho))


def gerar_id_licenca(email, nome=None):
    """Gera um ID único para a licença baseado no email, timestamp e um UUID parcial."""
    agora = datetime.now()
    data_formatada = agora.strftime("%y%m%d-%H%M")
    nome_parte = nome.lower().replace(" ", "-") if nome else email.split("@")[0].lower()
    uuid_parte = str(uuid.uuid4())[:6]
    return f"{nome_parte}-{data_formatada}-{uuid_parte}"


def calcular_data_validade(plano):
    """Calcula a data de validade baseada no plano."""
    if plano == "vitalicio":
        return "VITALÍCIO"

    dias = PLANOS[plano]["dias_validade"]
    data_validade = datetime.now() + timedelta(days=dias)
    return data_validade.strftime("%Y-%m-%d")


def carregar_licencas():
    """Carrega o arquivo de licenças ou cria um novo se não existir."""
    if not os.path.exists("data"):
        os.makedirs("data")

    if not os.path.exists(LICENCAS_FILE):
        with open(LICENCAS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=2, ensure_ascii=False)

    with open(LICENCAS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def salvar_licencas(licencas):
    """Salva as licenças no arquivo."""
    with open(LICENCAS_FILE, "w", encoding="utf-8") as f:
        json.dump(licencas, f, indent=2, ensure_ascii=False)


def criar_licenca(email, plano, nome=None):
    """Cria uma nova licença com o plano especificado."""
    if plano not in PLANOS:
        return {"erro": f"Plano inválido. Escolha entre: {', '.join(PLANOS.keys())}"}

    licencas = carregar_licencas()

    # Verifica se o email já possui licença
    for lic in licencas.values():
        if lic.get("email") == email and lic.get("status") in ["ativa", "gerada"]:
            return {"erro": f"O email {email} já possui uma licença ativa ou gerada."}

    # Gera um novo ID e código de licença
    id_licenca = gerar_id_licenca(email, nome)
    codigo_licenca = gerar_codigo_licenca()

    # Calcula a data de validade
    validade = calcular_data_validade(plano)

    # Cria o registro da licença
    licencas[id_licenca] = {
        "codigo_licenca": codigo_licenca,
        "email": email,
        "nome": nome,
        "plano": plano,
        "validade": validade,
        "ativado_em": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "ips": [],
        "hwids": [],
        "status": "gerada",
        "limite_operacoes": PLANOS[plano]["limite_operacoes"],
    }

    salvar_licencas(licencas)

    return {
        "sucesso": True,
        "id_licenca": id_licenca,
        "codigo_licenca": codigo_licenca,
        "email": email,
        "plano": plano,
        "validade": validade,
    }


def listar_licencas(filtro=None):
    """Lista todas as licenças ou filtra por status/plano."""
    licencas = carregar_licencas()

    if not licencas:
        return {"mensagem": "Nenhuma licença encontrada."}

    resultados = licencas

    if filtro and filtro in ["ativa", "revogada", "expirada"]:
        resultados = {k: v for k, v in licencas.items() if v.get("status") == filtro}

    return {"licencas": resultados}


def revogar_licenca(codigo_licenca):
    """Revoga uma licença específica."""
    licencas = carregar_licencas()

    for id_licenca, licenca in licencas.items():
        if licenca.get("codigo_licenca") == codigo_licenca:
            licenca["status"] = "revogada"
            licenca["revogada_em"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            salvar_licencas(licencas)
            return {
                "sucesso": True,
                "mensagem": f"Licença {codigo_licenca} revogada com sucesso.",
            }

    return {"erro": f"Licença com código {codigo_licenca} não encontrada."}


def atualizar_licenca(codigo_licenca, plano=None, validade=None):
    """Atualiza uma licença existente."""
    if plano and plano not in PLANOS:
        return {"erro": f"Plano inválido. Escolha entre: {', '.join(PLANOS.keys())}"}

    licencas = carregar_licencas()

    for id_licenca, licenca in licencas.items():
        if licenca.get("codigo_licenca") == codigo_licenca:
            if plano:
                licenca["plano"] = plano
                licenca["limite_operacoes"] = PLANOS[plano]["limite_operacoes"]
                # Atualiza validade se mudar para um plano não vitalício
                if plano != "vitalicio":
                    licenca["validade"] = calcular_data_validade(plano)
                else:
                    licenca["validade"] = "VITALÍCIO"

            if validade:
                licenca["validade"] = validade

            salvar_licencas(licencas)
            return {
                "sucesso": True,
                "mensagem": f"Licença {codigo_licenca} atualizada com sucesso.",
            }

    return {"erro": f"Licença com código {codigo_licenca} não encontrada."}


def verificar_licencas_expiradas():
    """Verifica e marca licenças expiradas."""
    licencas = carregar_licencas()
    hoje = datetime.now().strftime("%Y-%m-%d")

    alteracoes = False
    for id_licenca, licenca in licencas.items():
        if (
            licenca.get("status") == "ativa"
            and licenca.get("validade") != "VITALÍCIO"
            and licenca.get("validade")
            and licenca.get("validade") < hoje
        ):
            licenca["status"] = "expirada"
            alteracoes = True

    if alteracoes:
        salvar_licencas(licencas)

    return {"mensagem": "Verificação de licenças expiradas concluída."}


def processar_argumentos():
    """Processa os argumentos da linha de comando."""
    parser = argparse.ArgumentParser(
        description="Gerador e Gerenciador de Licenças para DerivBot"
    )
    subparsers = parser.add_subparsers(dest="comando", help="Comandos disponíveis")

    # Comando Criar
    criar_parser = subparsers.add_parser("criar", help="Criar uma nova licença")
    criar_parser.add_argument("-e", "--email", required=True, help="Email do usuário")
    criar_parser.add_argument(
        "-p",
        "--plano",
        required=True,
        choices=PLANOS.keys(),
        help="Plano da licença (free, mensal, vitalicio)",
    )
    criar_parser.add_argument("-n", "--nome", help="Nome do usuário (opcional)")

    # Comando Listar
    listar_parser = subparsers.add_parser("listar", help="Listar licenças")
    listar_parser.add_argument(
        "-f",
        "--filtro",
        choices=["ativa", "revogada", "expirada"],
        help="Filtrar por status",
    )

    # Comando Revogar
    revogar_parser = subparsers.add_parser("revogar", help="Revogar uma licença")
    revogar_parser.add_argument(
        "-c", "--codigo", required=True, help="Código da licença"
    )

    # Comando Atualizar
    atualizar_parser = subparsers.add_parser("atualizar", help="Atualizar uma licença")
    atualizar_parser.add_argument(
        "-c", "--codigo", required=True, help="Código da licença"
    )
    atualizar_parser.add_argument(
        "-p", "--plano", choices=PLANOS.keys(), help="Novo plano da licença"
    )
    atualizar_parser.add_argument(
        "-v", "--validade", help="Nova data de validade (formato: YYYY-MM-DD)"
    )

    # Comando Verificar
    subparsers.add_parser("verificar", help="Verificar licenças expiradas")

    args = parser.parse_args()

    if not args.comando:
        parser.print_help()
        sys.exit(1)

    return args


def main():
    """Função principal do programa."""
    args = processar_argumentos()

    if args.comando == "criar":
        resultado = criar_licenca(args.email, args.plano, args.nome)
        if "erro" in resultado:
            print(f"ERRO: {resultado['erro']}")
        else:
            print(f"✅ Licença criada com sucesso!")
            print(f"ID: {resultado['id_licenca']}")
            print(f"Código: {resultado['codigo_licenca']}")
            print(f"Email: {resultado['email']}")
            print(f"Plano: {resultado['plano'].upper()}")
            print(f"Validade: {resultado['validade']}")

    elif args.comando == "listar":
        resultado = listar_licencas(args.filtro)
        if "mensagem" in resultado:
            print(resultado["mensagem"])
        else:
            print(f"Total de licenças: {len(resultado['licencas'])}")
            print("\nLicenças:")
            for id_licenca, licenca in resultado["licencas"].items():
                status_emoji = "✅" if licenca.get("status") == "ativa" else "❌"
                print(f"\n{status_emoji} {id_licenca}:")
                print(f"  Código: {licenca.get('codigo_licenca')}")
                print(f"  Email: {licenca.get('email')}")
                print(f"  Plano: {licenca.get('plano', 'N/A').upper()}")
                print(f"  Validade: {licenca.get('validade', 'N/A')}")
                print(f"  Status: {licenca.get('status', 'N/A')}")

    elif args.comando == "revogar":
        resultado = revogar_licenca(args.codigo)
        if "erro" in resultado:
            print(f"ERRO: {resultado['erro']}")
        else:
            print(resultado["mensagem"])

    elif args.comando == "atualizar":
        if not args.plano and not args.validade:
            print(
                "ERRO: Você deve especificar pelo menos um parâmetro para atualizar (plano ou validade)."
            )
        else:
            resultado = atualizar_licenca(args.codigo, args.plano, args.validade)
            if "erro" in resultado:
                print(f"ERRO: {resultado['erro']}")
            else:
                print(resultado["mensagem"])

    elif args.comando == "verificar":
        resultado = verificar_licencas_expiradas()
        print(resultado["mensagem"])


if __name__ == "__main__":
    main()
