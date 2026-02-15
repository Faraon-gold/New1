// Общие скрипты для системы учёта посещаемости

// Функция для получения cookie
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Добавляем CSRF защиту к каждому запросу
document.addEventListener('DOMContentLoaded', function() {
    // Здесь можно добавить общие скрипты для всей системы
    console.log('Система учёта посещаемости загружена');
});