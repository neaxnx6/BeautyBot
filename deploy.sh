#!/bin/bash
# Скрипт деплоя BeautyBot на VPS

set -e

echo "🚀 Установка BeautyBot на VPS..."

# Обновление системы
echo "📦 Обновление системы..."
sudo apt update && sudo apt upgrade -y

# Установка зависимостей
echo "🐍 Установка Python и зависимостей..."
sudo apt install python3.10 python3.10-venv python3-pip git -y

# Клонирование репозитория
echo "📥 Клонирование репозитория..."
cd ~
if [ -d "BeautyBot" ]; then
    echo "⚠️  Директория BeautyBot уже существует"
    read -p "Удалить и клонировать заново? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf BeautyBot
        git clone https://github.com/neaxnx6/BeautyBot.git
    fi
else
    git clone https://github.com/neaxnx6/BeautyBot.git
fi

cd BeautyBot

# Создание виртуального окружения
echo "🔧 Создание виртуального окружения..."
python3 -m venv venv
source venv/bin/activate

# Установка зависимостей Python
echo "📚 Установка зависимостей..."
pip install --upgrade pip
pip install -r requirements.txt

# Настройка .env
echo "⚙️  Настройка .env файла..."
if [ ! -f .env ]; then
    read -p "Введите BOT_TOKEN: " bot_token
    read -p "Введите ADMIN_ID: " admin_id
    
    cat > .env << EOF
BOT_TOKEN=$bot_token
ADMIN_ID=$admin_id
EOF
    echo "✅ .env файл создан"
else
    echo "⚠️  .env файл уже существует, пропускаем"
fi

# Тест запуска
echo "🧪 Тестовый запуск..."
timeout 5 python bot.py || true

echo ""
echo "✅ Установка завершена!"
echo ""
echo "📋 Следующие шаги:"
echo "1. Настроить systemd service: sudo nano /etc/systemd/system/beautybot.service"
echo "2. Запустить службу: sudo systemctl start beautybot"
echo "3. Включить автозапуск: sudo systemctl enable beautybot"
echo ""
echo "📖 Подробная инструкция в implementation_plan.md"
