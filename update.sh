#!/bin/bash
# Скрипт обновления BeautyBot на VPS

set -e

echo "🔄 Обновление BeautyBot..."

cd ~/BeautyBot

# Остановка бота
echo "⏸️  Остановка бота..."
sudo systemctl stop beautybot

# Обновление кода
echo "📥 Получение обновлений из GitHub..."
git pull

# Обновление зависимостей (если изменились)
echo "📚 Проверка зависимостей..."
source venv/bin/activate
pip install -r requirements.txt --upgrade

# Запуск бота
echo "▶️  Запуск бота..."
sudo systemctl start beautybot

# Проверка статуса
sleep 2
sudo systemctl status beautybot --no-pager

echo ""
echo "✅ Обновление завершено!"
echo ""
echo "📊 Логи: sudo journalctl -u beautybot -f"
