#!/bin/bash

# Скрипт для генерации диаграмм Graphviz
# Генерирует PNG, SVG и PDF версии всех .dot файлов

echo "🚀 Генерация диаграмм для Telegram бота..."
echo "=========================================="

# Проверяем наличие Graphviz
if ! command -v dot &> /dev/null; then
    echo "❌ Graphviz не установлен!"
    echo "Установите Graphviz:"
    echo "  macOS: brew install graphviz"
    echo "  Ubuntu: sudo apt-get install graphviz"
    echo "  Windows: choco install graphviz"
    exit 1
fi

echo "✅ Graphviz найден: $(dot -V | head -n1)"
echo ""

# Создаем папку для изображений
mkdir -p diagrams

# Счетчики
total_files=0
successful_generations=0

# Функция для генерации диаграммы
generate_diagram() {
    local file=$1
    local base_name=$(basename "$file" .dot)
    
    echo "📊 Генерация: $base_name"
    
    # PNG
    if dot -Tpng "$file" -o "diagrams/${base_name}.png" 2>/dev/null; then
        echo "  ✅ PNG: diagrams/${base_name}.png"
        ((successful_generations++))
    else
        echo "  ❌ Ошибка генерации PNG"
    fi
    
    # SVG
    if dot -Tsvg "$file" -o "diagrams/${base_name}.svg" 2>/dev/null; then
        echo "  ✅ SVG: diagrams/${base_name}.svg"
        ((successful_generations++))
    else
        echo "  ❌ Ошибка генерации SVG"
    fi
    
    # PDF
    if dot -Tpdf "$file" -o "diagrams/${base_name}.pdf" 2>/dev/null; then
        echo "  ✅ PDF: diagrams/${base_name}.pdf"
        ((successful_generations++))
    else
        echo "  ❌ Ошибка генерации PDF"
    fi
    
    echo ""
}

# Обрабатываем все .dot файлы
for file in *.dot; do
    if [[ -f "$file" ]]; then
        ((total_files++))
        generate_diagram "$file"
    fi
done

# Проверяем результаты
if [[ $total_files -eq 0 ]]; then
    echo "❌ Не найдено файлов .dot в текущей директории"
    exit 1
fi

echo "=========================================="
echo "📈 Результаты генерации:"
echo "  📁 Файлов .dot: $total_files"
echo "  🎯 Успешных генераций: $successful_generations"
echo "  📊 Ожидаемых файлов: $((total_files * 3))"
echo ""

# Показываем созданные файлы
echo "📂 Созданные файлы в папке diagrams/:"
ls -la diagrams/ 2>/dev/null || echo "  Папка diagrams/ пуста"

echo ""
echo "🎉 Генерация завершена!"
echo ""
echo "💡 Советы по использованию:"
echo "  • PNG - для презентаций и документов"
echo "  • SVG - для веб-страниц (масштабируемый)"
echo "  • PDF - для печати и архивирования"
echo ""
echo "📖 Подробная документация: DIAGRAMS_README.md" 