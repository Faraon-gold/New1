#!/usr/bin/env python
"""
Тестирование фикса аутентификации
"""

import asyncio
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
import time
import requests


def test_auth():
    """Тестирование аутентификации"""
    import subprocess
    import sys
    
    # Запуск сервера в отдельном процессе
    process = subprocess.Popen([sys.executable, "-c", """
import uvicorn
from main import app
uvicorn.run(app, host='127.0.0.1', port=8001)
"""], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Ждем пока сервер запустится
    time.sleep(5)
    
    try:
        # Тестируем успешную аутентификацию
        response = requests.post('http://127.0.0.1:8001/login', 
                               json={'login': 'admin', 'password': 'admin123'})
        print(f"Статус код: {response.status_code}")
        print(f"Ответ: {response.json()}")
        
        if response.status_code == 200 and response.json().get('success'):
            print("✓ Успешная аутентификация!")
        else:
            print("✗ Ошибка аутентификации!")
            
        # Тестируем неправильные учетные данные
        response_fail = requests.post('http://127.0.0.1:8001/login', 
                                   json={'login': 'admin', 'password': 'wrongpassword'})
        print(f"\nСтатус код (неправильный пароль): {response_fail.status_code}")
        
        if response_fail.status_code == 401:
            print("✓ Корректная обработка неправильных учетных данных!")
        else:
            print("✗ Некорректная обработка неправильных учетных данных!")
            
    except Exception as e:
        print(f"Ошибка при тестировании: {e}")
    finally:
        # Останавливаем процесс
        process.terminate()
        process.wait()


if __name__ == "__main__":
    test_auth()