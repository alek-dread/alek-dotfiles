# Дополнительные настройки

Снимок оформления исходной системы на 23 октября 2026. `install.sh`
не устанавливает эти файлы. Выбирай и переноси нужное вручную.

- `home/`: настройки GTK 2/3/4 (Adwaita dark, Paper, Iosevka, без эффектов),
  цвета Arthur для Neovim и выбор темы для существующей установки LazyVim.
  Глобальные GTK-настройки влияют также на приложения вне Hyprland.
- `firefox/userChrome.css`: небольшие скругления вкладок и элементов интерфейса.
  Помести в `chrome/` нужного профиля, включи
  `toolkit.legacyUserProfileCustomizations.stylesheets` в `about:config`
  и перезапусти Firefox.
- `workstation/local.lua`: монитор DP-1 1920×1080@144 и программный курсор RX 470;
  при необходимости перенеси в `~/.config/hypr/local.lua`.
- `workstation/env-hyprland.local`: программное кодирование и запрет VA-API
  после сбоя VCE на RX 470; путь назначения — `~/.config/uwsm/env-hyprland.local`.
- `workstation/record-settings.json`: личный выбор записи звука (микрофон + система).
  Общая установка сохраняет исходное значение «без звука».
- `workstation/desktop-power-menu`: вариант меню для уже настроенных профилей
  `xeon-eco`, `xeon-balanced`, `xeon-performance` в TuneD/LACT, требует PyYAML.
  Это снимок помощника; сами системные профили здесь не поставляются.
  Основной `home/.local/bin/desktop-power-menu` работает с доступными профилями
  запущенного системного менеджера питания.

## Greeter

`greeter/etc/` и `greeter/usr/` повторяют системные пути исходного ПК:
вход через greetd → Cage → gtkgreet-controls → UWSM.
CSS использует Arthur; только надпись FEDORA и версия — голубые `#87ceeb`.
`config.toml` ссылается на `gtkgreet-controls` и отдельный скрипт запуска;
одного CSS недостаточно для воспроизведения этого экрана входа.

В `greeter/source/` сохранены исходный архив с лицензией,
RPM spec версии `0.8.20261017-2.local` и патч цвета надписи.
Патч уже включён в архив, повторно применять его не нужно.
Сборка RPM из каталога репозитория:

```sh
rpmbuild -ba optional/greeter/source/gtkgreet-controls.spec \
  --define "_sourcedir $PWD/optional/greeter/source"
```

Это материалы для ручной настройки greetd. Установщик репозитория использует
существующий экран входа и добавляет отдельную сессию **Hyprland (Alek)**.
