#!/bin/bash
# Скрипт для ожидания готовности PostgreSQL

set -e

host="db"
port="5432"
dbname="attendance_db"
username="postgres"
password="1234"

echo "Ждем готовности PostgreSQL..."

# Установка переменных окружения для подключения
export PGPASSWORD="$password"

# Повторяем попытки подключения каждые 2 секунды до успешного подключения
# Используем psql с конкретной командой проверки
until PGPASSWORD="$password" psql -h "$host" -p "$port" -U "$username" -d "$dbname" -c "SELECT 1;" > /dev/null 2>&1
do
    echo "База данных недоступна, ждем 2 секунды..."
    sleep 2
done

echo "База данных готова!"

# Выполняем инициализацию
python init_db.py

# Запускаем основное приложение
exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload