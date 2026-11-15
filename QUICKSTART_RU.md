# CineFlow Studio: Быстрый старт (RU)

CineFlow Studio — режиссёрская среда для ИИ-кинопроизводства внутри вашей IDE
(Cursor, Claude Code, Kimi, Trae, Cline): MCP-сервер + скилл режиссёра +
генерация через локальный ComfyUI и/или облако CineFlow.

Установка занимает две минуты и не требует Git — всё ставится из PyPI.

---

## 1. Установка

Нужен Python 3.11+ (проверьте: `python --version`).

```bash
# Запуск MCP-сервера без установки (uv/uvx):
uvx cineflow-studio

# Либо полная установка с утилитой настройки:
pip install cineflow-studio
cineflow-setup
```

`cineflow-setup` сделает сам:
1. Установит скилл режиссёра в каталоги вашей IDE (`.cursor/skills/`, `.claude/skills/`, `.kimi/skills/`, …).
2. Впишет MCP-конфиг с командой `uvx cineflow-studio` (`.cursor/mcp.json` и другие).
3. Покажет профиль вашего GPU (RTX 3090/4090 → локальный рендер; без NVIDIA — облачный режим).

---

## 2. Подключение в IDE за 2 минуты

**Cursor:** перезапустите Cursor после `cineflow-setup` — MCP-сервер подхватится автоматически (`.cursor/mcp.json` уже записан).

**Claude Code / Kimi / Trae:** конфиги записаны в рабочем каталоге проекта; откройте проект в IDE.

Проверка: спросите агента «Какие инструменты cineflow тебе доступны?» — он должен перечислить 40+ инструментов `cineflow_*`.

Ручная настройка (если IDE не подхватила):

```json
{
  "mcpServers": {
    "cineflow": { "command": "uvx", "args": ["cineflow-studio"] }
  }
}
```

---

## 3. Режимы

| Режим | Что нужно | Что делает |
|---|---|---|
| **Community (бесплатно)** | Свой GPU + локальный ComfyUI | Всё локально: проекты, раскадровка, рендер |
| **Cloud (ключ CineFlow)** | Ключ `CINEFLOW_API_KEY` | Режиссура на сервере: план, консистентность персонажей, референс-политика; рендер локально |

Ключ ставится в переменную окружения `CINEFLOW_API_KEY` или через инструмент `cineflow_auth` прямо в чате. Тариф и права подтверждает сервер (`cineflow_billing_status` покажет `verified`).

---

## 4. Первый проект

Откройте IDE в рабочем каталоге и напишите агенту:

```
Привет! У меня есть сценарий, давай сделаем проект и видео.
```

Агент-режиссёр (по скиллу CineFlow) сам соберёт вводные, создаст проект
(`cineflow_project_init`), разложит на сцены и кадры, поставит задачи в ComfyUI
и покажет результаты. Для облачного режима: `cineflow_cloud_script_plan`
загрузит сценарий на сервер и соберёт план там.

Модели и ноды ComfyUI ставятся по профилю железа: `cineflow_models_catalog`,
`cineflow_install_node`, `cineflow_generate_dependency_script`.

---

## 5. Обновление

```bash
uvx cineflow-studio@latest          # всегда свежая версия
pip install -U cineflow-studio      # если ставили через pip
```

Список изменений — в CHANGELOG пакета. Лицензия: проприетарная (см. LICENSE).
