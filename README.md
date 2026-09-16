# Transcriber Portfolio

Небольшой backend для асинхронного распознавания аудио. Учебная portfolio-версия:
FastAPI принимает файл, Celery обрабатывает его в фоне, PostgreSQL хранит состояние
и JSON с текстом и временными метками. Аудиофайлы лежат в S3-совместимом MinIO.

```text
POST /transcriptions → MinIO (аудио) + PostgreSQL (queued)
                    → Redis → Celery → faster-whisper на CPU
                                     → PostgreSQL (completed / failed)
GET /transcriptions/{job_id}          → статус и результат
```

## Локальный запуск

Нужны Docker с Compose, свободный порт 8000 и интернет для загрузки образов,
Python-пакетов и модели. Первый запрос загружает модель `tiny` в Docker volume;
он выполняется дольше следующих. Качество маленькой модели ограничено.

```sh
cp .env.example .env
docker compose up --build -d
docker compose ps -a
```

В PowerShell вместо `cp` можно использовать `Copy-Item .env.example .env`.
Контейнеры `migrate` и `bucket` должны завершиться с кодом 0; API, worker,
PostgreSQL, Redis и MinIO должны работать.

Откройте [Swagger UI](http://127.0.0.1:8000/docs): загрузите короткую запись речи
через `POST /transcriptions`, скопируйте `job_id` и проверяйте
`GET /transcriptions/{job_id}` до `completed` или `failed`.

```sh
curl -F "file=@sample.wav" http://127.0.0.1:8000/transcriptions
curl http://127.0.0.1:8000/transcriptions/JOB_ID
docker compose logs worker
docker compose down
```

На Windows используйте `curl.exe`. Поддерживаются WAV, MP3, M4A, OGG, FLAC,
до 25 MiB. Расширение проверяется при загрузке, содержимое декодируется worker;
повреждённое аудио заканчивается `failed`. Язык определяется моделью.

Пример результата (содержимое зависит от записи):

```json
{"job_id":"...","status":"completed","result":{"language":"en","segments":[{"start":0.0,"end":1.5,"text":"Hello."}]},"error":null}
```

## Код и решения

- `app/main.py` — загрузка и чтение задания, ответы 400/413/415/503/404.
- `app/worker.py` — одна фоновая задача и временный каталог для аудио.
- `app/audio.py` — вызов faster-whisper; модель загружается один раз на процесс.
- `app/db.py`, `migrations/` — таблица jobs и начальная миграция Alembic.
- `app/storage.py` — обычный boto3-клиент без дополнительного слоя абстракций.

Один worker с concurrency=1 выбран для понятного локального поведения и расхода
памяти. Redis используется только как брокер; результат читается из PostgreSQL.
Миграции запускаются отдельным одноразовым контейнером до API и worker.

## Проверки

Python 3.12:

```sh
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
ruff check .
ruff format --check .
pytest -q
```

Тесты используют SQLite и подмены S3, очереди и распознавания: проверяют состояния,
валидацию, ошибки и выдачу результата без скачивания модели. Они не заменяют
сквозной запуск Docker с настоящей записью. GitHub Actions выполняет эти тесты,
линтер и проверку Compose; ничего не развёртывает.

## Границы демонстрации

Это локальный однопользовательский сервис без авторизации. API опубликован только
на `127.0.0.1`, остальные сервисы доступны только внутри Docker-сети. Значения в
`.env.example` — открытые демонстрационные настройки, не реальные учётные данные.
Не открывайте этот Compose в интернет.

Состояния: `queued → processing → completed | failed`. Нет автоматического
восстановления задач после аварийного завершения worker и нет распределённой
транзакции между PostgreSQL и Redis. При сбое публикации задача помечается failed;
в редком случае неопределённого ответа брокера она уже могла начать обработку.
Для повторной попытки загрузите файл заново. `/health` проверяет только процесс API.

Исходное аудио и результаты сохраняются до удаления локальных volumes.
`docker compose down -v` **удаляет все данные этой демонстрации**, включая модели.
Не загружайте конфиденциальные записи. Диаризация, шумоподавление, веб-панель,
документы и дополнительные модели не входят в эту версию.
