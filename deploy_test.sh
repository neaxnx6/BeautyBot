#!/bin/bash
set -e

echo "🧪 Установка ТЕСТОВОГО BeautyBot..."

# Обновление системы
echo "📦 Обновление системы..."
apt update && apt upgrade -y

# Установка зависимостей
echo "🐍 Установка Python..."
apt install python3.10 python3.10-venv python3-pip git -y

# Клонирование репозитория в отдельную папку
echo "📥 Клонирование репозитория..."
cd ~
git clone https://github.com/neaxnx6/BeautyBot.git BeautyBot_Test
cd BeautyBot_Test

# Создание виртуального окружения
echo "🔧 Создание venv..."
python3 -m venv venv
source venv/bin/activate

# Установка зависимостей
echo "📚 Установка библиотек..."
pip install --upgrade pip
pip install -r requirements.txt

# Создание .env для ТЕСТОВОГО бота
echo "⚙️ Настройка .env..."
cat > .env << 'EOF'
BOT_TOKEN=8356957924:AAF7fFtzal1aZzLGz3EgduvS3JobBimBD4U
ADMIN_ID=1039375051
EOF

# Изменение имени БД на тестовую
echo "🗄️ Настройка тестовой БД..."
sed -i 's/DB_NAME = "beautybot.db"/DB_NAME = "beautybot_test.db"/' database/setup.py

# Тест
echo "🧪 Тестовый запуск..."
timeout 3 python bot.py || true

echo ""
echo "✅ Готово! Тестовый бот установлен в ~/BeautyBot_Test"
echo ""
echo "📌 Следующий шаг: настроить systemd service"
echo "   sudo nano /etc/systemd/system/beautybot_test.service"
