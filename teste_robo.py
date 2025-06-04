#!/usr/bin/env python3
"""
Script para testar o robô diretamente via API
"""
import requests
import json
import time


def testar_robo():
    """Testa o robô fazendo requisições diretas"""
    base_url = "http://127.0.0.1:5000"

    print("🤖 TESTANDO ROBÔ DIRETAMENTE VIA API")
    print("=" * 50)

    # 1. Tenta iniciar o robô
    try:
        print("🚀 INICIANDO ROBÔ...")
        data = {"modo": "iniciante", "meta": 20}

        response = requests.post(f"{base_url}/toggle_bot", json=data, timeout=10)

        print(f"Status Code: {response.status_code}")
        print(f"Resposta: {response.text}")

        if response.status_code == 200:
            result = response.json()
            print(f"✅ ROBÔ INICIADO: {result.get('mensagem', 'Sucesso')}")

            # 2. Monitora por 30 segundos
            print("\n📊 MONITORANDO ROBÔ POR 30 SEGUNDOS...")
            for i in range(6):  # 6 x 5 segundos = 30 segundos
                try:
                    status_response = requests.get(f"{base_url}/status_robo", timeout=5)
                    if status_response.status_code == 200:
                        status = status_response.json()
                        print(
                            f"[{i*5}s] Status: {status.get('status_operacao', 'N/A')} | "
                            f"Ativo: {status.get('ativo', False)} | "
                            f"Mensagem: {status.get('mensagem_usuario', 'N/A')}"
                        )
                    else:
                        print(
                            f"[{i*5}s] Erro ao obter status: {status_response.status_code}"
                        )
                except Exception as e:
                    print(f"[{i*5}s] Erro: {e}")

                time.sleep(5)

        else:
            print(f"❌ ERRO AO INICIAR ROBÔ: {response.text}")

    except Exception as e:
        print(f"❌ Erro na requisição: {e}")


if __name__ == "__main__":
    testar_robo()
