#!/usr/bin/env python3
"""
Script para testar se a rota /toggle_bot está funcionando
"""

import requests
import json

def test_toggle_bot():
    url = "http://127.0.0.1:5000/toggle_bot"
    
    # Dados para enviar
    data = {
        "modo": "iniciante",
        "meta": 20
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        print("🔄 Testando rota /toggle_bot...")
        print(f"📤 Enviando: {data}")
        
        response = requests.post(url, json=data, headers=headers)
        
        print(f"📥 Status Code: {response.status_code}")
        print(f"📥 Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ Rota funcionando!")
        else:
            print(f"❌ Erro: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Erro na requisição: {e}")

if __name__ == "__main__":
    test_toggle_bot()
