# CineFlow Studio: Быстрый старт (RU)

CineFlow Studio — режиссёрская среда для ИИ-кинопроизводства внутри вашей IDE
(Cursor, Claude Code, Kimi, Trae, Cline): MCP-сервер + скилл режиссёра +
генерация через локальный ComfyUI и/или облако CineFlow.

---

## 0. Установка с нуля: просто киньте ссылку в чат IDE

На машине, где ничего не стоит, откройте чистый чат в Cursor (или другой IDE с
агентом) и отправьте одну строку:

```
Установи CineFlow Studio из https://github.com/MilayaMariyaAi/cineflow-studio
по инструкции из README — сделай всё сам, спрашивай только токен.
```

Агент прочитает README этого репозитория и выполнит раздел «Установка агентом
(сделай за меня)»: сам поставит uv, сам развернёт MCP-сервер и скилл, сам
пропишет конфиги IDE, спросит у вас только персональный токен CineFlow.

Токен: на cineflow.aimari.ru войдите в аккаунт, создайте токен
(POST /me/tokens), скопируйте cfp_... и вставьте агенту. Он один раз
показывается и хранится только у вас.

Проверка: спросите агента «статус CineFlow» — он ответит статусом биллинга
(«Community» без подписки, с подпиской — ваш план).

---

## 1. Установка агентом (сделай за меня) — то, что выполняет агент

**Агент, действуй по шагам; ничего не спрашивай, кроме токена из шага 4.**

1. **Проверь окружение.** Нужны uv (поставь: `pip install uv` или официальный
   инсталлятор) и Git. Python отдельный не нужен — uv принесёт свой.
2. **Проверь сервер и MCP без установки:**
   `uvx --from git+https://github.com/MilayaMariyaAi/cineflow-studio cineflow-mcp`
   должен стартовать и ждать stdio (ошибки импорта быть не должно).
3. **Разложи скилл и конфиги:** в папке проекта пользователя выполни
   `uvx --from git+https://github.com/MilayaMariyaAi/cineflow-studio cineflow-setup`.
   Он установит скилл режиссёра в каталоги IDE (.cursor/skills/,
   .claude/skills/, .kimi/skills/, .agents/skills/, .kimi-code/skills/)
   и пропишет mcp.json.
4. **mcp.json — заменить запуск на git-вариант** (PyPI-версии ещё нет):
   в .cursor/mcp.json (и других) поставь команду `uvx` с аргументами
   `["--from", "git+https://github.com/MilayaMariyaAi/cineflow-studio", "cineflow-mcp"]`
   и переменными окружения `CINEFLOW_CLOUD_URL=https://cineflow.aimari.ru`
   и `CINEFLOW_API_KEY=<cfp_... от пользователя>`.
5. **Токен (единственный вопрос пользователю):** попроси зайти на
   cineflow.aimari.ru, создать токен (POST /me/tokens) и вставить cfp_...
   в env из шага 4. Больше ничего не нужно.
6. **Перезапусти IDE** (или перезагрузи окно) и проверь вызовом
   cineflow_billing_status: у пользователя без подписки — честный
   community-ответ; с подпиской — план и права с сервера.

Дальше пользователь просто кидает книгу/сценарий в чат: скилл ведёт агента по
флоу «книга -> сцены -> кадры -> рендер на его GPU».

---

## 2. Ручная установка (без агента)

```bash
pip install uv                       # один раз
uvx --from git+https://github.com/MilayaMariyaAi/cineflow-studio cineflow-setup
```

Затем впиши mcp.json из шага 4 выше (подставив свой cfp_...) и перезапусти
IDE. После первого публичного PyPI-релиза этот шаг сокращается до
`pip install cineflow-studio && cineflow-setup`.

---

## 3. Что где после установки

- .cursor/skills/cineflow/SKILL.md (и 4 другие IDE) — скилл: протокол работы агента
- .cursor/mcp.json — запуск MCP-сервера + токен
- ComfyUI/ — установщик моделей и лаунчер под ваш GPU (создаёт cineflow-setup)
- storage/projects/ — локальный store проектов (в cloud-режиме истина — на сервере)

Модели весят десятки ГБ; cineflow_installer_audit покажет, чего не хватает
под ваш профиль, а ComfyUI/install_cineflow_models.bat докачает.
