# alek-dotfiles

Мой рабочий стол на **Fedora 44 + Hyprland**: тема Arthur, Waybar, Fuzzel,
Mako, Alacritty, блокировка экрана, скриншоты и запись видео.
Без зазоров, скруглений и анимаций. Клавиатура US/RU, переключение Alt+Shift.

Установка от обычного пользователя:

```sh
./install.sh
```

После выхода выбери **Hyprland (Alek)** на экране входа.
Установщик добавляет пакеты и отдельную сессию рядом с GNOME.
При конфликте существующих конфигов он останавливается без перезаписи.

| Клавиши | Действие |
| --- | --- |
| Super+Shift+Enter | Терминал |
| Super+P / Super+E | Приложения / файлы |
| Super+1…9 | Рабочие столы |
| Super+Alt+L | Блокировка |
| Print / Ctrl+Print | Скриншот области / экранов |
| Super+Print | Запись области / остановка |
| Super+Shift+Print | Настройки записи |
| Super+Shift+E | Меню сессии |
| Super+F1 | Все сочетания клавиш |

[Подробности установки](docs/installation.md) ·
[Оформление](home/.config/desktop-design/DESIGN.md) ·
[Greeter, GTK, Firefox и настройки моего ПК](optional/README.md)

Проверка: `python3 -m unittest discover -s tests -v`.
