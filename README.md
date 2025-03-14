# Скрипт автосбора результатов работы конкурсантов.

- Проверка Qemu машин через guest-agent exec
- Проверка EcoRouter через websocket консоль
- Протестировано в Proxmox 8+
- Успешно применено при оценке 1 и 2 модуля регионального чемпионата Рязанской области 2025

## Как запустить
- Установить python
- Установать зависимости
`pip install -r /path/to/requirements.txt`
- В Proxmox рекомендуется создать отдельного пользователя с правами администратора, в скрипте используется логин и пароль (апи токен не подходит в связи с особенностями работы консоли), указать их в переменных api_user и api_password.
- Заменить переменные PVE_DOMAIN и PVE_PORT на свои.
- При запуске скрипта указать название узла proxmox, номер рабочего места участника.

### ИД виртуальных машин на рабочих местах
В скрипте переменная place_vm_shift позволяет указать смещение ИД у виртуальных машин на стендах.
Для каждой машины автоматически назначается ИД у стенда участника:
`place_vm_shift + user_id + machine_number`
Переменная machine_number берется из файла json с критериями оценки, зависит от того на какой поиции стоит машина.
