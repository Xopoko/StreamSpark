# Предложенный патч (кандидаты на удаление, confidence >= 60%)

Ниже — агрегированный список элементов, помеченных vulture (confidence >= 60%). Это не изменения в репозитории — только предложение. Для каждого элемента указано: файл, имя символа/атрибута/переменной/функции и краткая рекомендация.

Общая рекомендация:
- Вручную проверить пункты, связанные с маршрутами (routes) и тестами — возможно, маршруты регистрируются динамически или используются через импорт/фреймворк.
- Можно безопасно удалить переменные с 100% confidence (обычно это локальные/ненужные переменные).
- Перед непосредственным удалением я предлагаю: создать ветку, закоммитить изменения, прогнать тесты, запустить vulture повторно.

--- Список кандидатов ---

config.py
- donationalerts_api_base (attribute) — удалить / проверить использование в OAuth / clients
- donationalerts_expires_at (attribute) — удалить / проверить
- donationalerts_token_type (attribute) — удалить / проверить
- video_duration_seconds (attribute) — удалить / проверить
- video_aspect_ratio (attribute) — удалить / проверить
- video_resolution (attribute) — удалить / проверить
- validate (method) — проверить; если не используется — удалить

config_storage.py
- get_app_config (method) — проверить / возможно удалить
- set_app_config (method) — проверить / возможно удалить
- description (variable) — пометка 100% — удалить
- value_type (variable) — 100% — удалить
- set_user_oauth_token (method) — проверить
- user_id (variable) — 100% — удалить (в местах где локальная переменная неиспользуемая)
- get_user_oauth_token (method) — проверить
- ensure_user_exists (method) — проверить
- email (variable) — 100% — удалить
- init_user_config (method) — проверить
- get_config (method) — проверить
- set_config (method) — проверить; description/value_type/user_id — 100% локальные переменные
- get_all_config (method) — проверить
- delete_config (method) — проверить
- create_user (method) — проверить
- get_user_by_email, get_user_by_id (methods) — проверить
- get_exchange_rate, set_exchange_rate (methods) — проверить
- cache_minutes / source (variables) — 100% — удалить
- config_storage (variable) — 60% — проверить

main_fastapi.py
- test_donation (function) — тестовый/отладочный хэндлер — удалить или оставить для ручного тестирования

routes/api_generation.py
- generation_status (function) — проверить регистрацию маршрутов; если не зарегистрирован — удалить
- get_system_prompt (function) — проверить
- set_system_prompt (function) — проверить
- generate_custom_video (function) — проверить
- generate_veo_video (function) — проверить

routes/api_logs.py
- get_logs (function) — проверить регистрацию/импорт

routes/api_polling.py
- get_donations (function) — проверить
- test_donation_alerts (function) — тестовый — удалить/переименовать в тест/утилиту

routes/api_settings.py
- get_settings (function)
- set_donation_alerts_token (function)
- connection_status (function)
- get_threshold (function)
- set_threshold (function)
- get_access_token_status (function)
- set_access_token (function)
- aiml_status (function)
(все — проверить регистрацию в main/fastapi; если маршруты подключаются динамически — оставить)

routes/api_videos.py
- get_recent_videos (function)
- get_all_videos (function)
- delete_video (function)
- play_in_obs (function)
(проверить регистрацию/использование)

routes/donation_alerts_oauth.py
- da_oauth_debug (function)
- da_oauth_login (function)
- da_oauth_callback (function)
- donationalerts_token_type (attribute)
- donationalerts_expires_at (attribute)
- da_disconnect (function)
(проверить взаимодействие с OAuth; возможно используются/требуют сохранения)

routes/pages.py
- index (function)
- dashboard (function)
- landing (function)
(вероятно, шаблонные маршруты — проверить регистрацию)

routes/widget_videos.py
- widget_page (function)
- get_latest_video (function)
- serve_video (function)
(проверить использование в шаблонах/внешних виджетах)

services/donation_alerts_poller.py
- last_donation_id (attribute) — проверить; возможно состояние poller — удалить если нет использования
- _refresh_access_token (method) — приватный метод: проверить — возможно вызывается через имя строкой; осторожно

tests/conftest.py
- _running (attribute) — проверить — может использоваться тестовой фикстурой

tests/test_aiml_client.py
- chunk_size (variable) — 100% — удалить/рефактор
- timeout (variable) — 100% — удалить/рефактор
- stream (variable) — 100% — удалить/рефактор

tests/test_api_logs.py
- unused import logging_utils (90%) — удалить импорт если не нужен

tests/test_api_settings.py
- _token (attribute) — проверить фикстуры/тесты

tests/test_currency_converter.py
- множество временных переменных timeout/expires/cur (высокая confidence) — удалить/очистить тесты

tests/test_donation_alerts.py
- timeout/cur — удалить/очистить тесты

tests/test_donation_alerts_oauth.py
- donationalerts_token_type / donationalerts_expires_at / _token — проверить тестовую фикстуру; возможно безопасно удалить

tests/test_obs_widget.py
- file (variable) — 60% — проверить/удалить

---

# Предлагаемые действия (рабочий процесс)
1. Вы подтвердите, что хотите патч для всех записей с confidence >= 60% (вы выбрали вариант B).
2. Я подготовлю подробный патч (diff) в виде отдельного файла и представлю его здесь для просмотра (не буду применять).
   - В патче я помечу: "DELETE" для функций/методов/атрибутов, "REMOVE VAR" для переменных с 100%, "REVIEW" для маршрутов/методов которые требуют ручной проверки.
3. После вашего одобрения я могу:
   - создать ветку, применить патч, выполнить тесты и показать результаты (или откатить при ошибках),
   - либо применить только часть изменений по вашему выбору.

# Следующие шаги
- [ ] Подтвердите: формировать и показать готовый diff-патч (применение — отдельно).
- [ ] Если нужно — укажите исключения (файлы/функции, которые обязательно нужно оставить).
