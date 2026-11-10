# High-Level Design
## Сервис автоматического составления расписания занятий

## 1. Общая архитектура

Система строится как веб-приложение с отдельным процессом выполнения длительных расчётов.

Основные компоненты:

- **Frontend** — React + MUI;
- **Backend API** — Python + FastAPI;
- **ORM** — SQLAlchemy;
- **основная БД** — PostgreSQL;
- **брокер сообщений** — Kafka;
- **оперативное состояние расчётов** — Redis;
- **файловое хранилище** — MinIO;
- **процесс расчёта расписания** — Scheduler Worker;
- **локальное окружение и развёртывание** — Docker Compose.

Backend реализуется как модульное приложение. Бизнес-логика не размещается в FastAPI-обработчиках и отделяется от HTTP, SQLAlchemy, Kafka, Redis и MinIO через прикладные интерфейсы.

```mermaid
%%{init: {"flowchart": {"useMaxWidth": false, "htmlLabels": true, "curve": "basis"}, "themeVariables": {"fontSize": "18px"}}}%%
flowchart TB
    U[Пользователь]
    F[React + MUI]
    API[FastAPI Backend]
    W[Scheduler Worker]

    U --> F
    F -->|REST / JSON| API
    API -->|Задания| K[Kafka]
    K --> W

    API --> PG[(PostgreSQL)]
    API --> R[(Redis)]
    API --> M[(MinIO)]
    API --> E[Сервис электронной почты]

    W --> PG
    W --> R
    W --> M
```

### Назначение компонентов

| Компонент | Назначение |
|---|---|
| React + MUI | Пользовательский интерфейс, ввод данных, просмотр и редактирование расписания, отображение прогресса расчёта |
| FastAPI | HTTP API, авторизация, управление проектами и исходными данными, валидация запросов, запуск расчётов, импорт и экспорт |
| SQLAlchemy | Доступ Backend и Scheduler Worker к PostgreSQL |
| PostgreSQL | Постоянное хранение пользователей, проектов, исходных данных, ограничений, заданий и результатов расчётов |
| Kafka | Передача длительных задач построения и оптимизации расписания от Backend к Scheduler Worker |
| Redis | Текущий прогресс длительного расчёта, запросы на отмену и другое краткоживущее состояние |
| Scheduler Worker | Выполнение комбинаторного поиска, оптимизации и автоматической корректировки расписания |
| MinIO | Хранение загруженных пользователем файлов и созданных системой файлов выгрузок |
| Сервис электронной почты | Отправка сообщений для восстановления пароля |
| Docker Compose | Запуск всех внутренних компонентов системы в едином окружении |

---

## 2. Развёртывание

Docker Compose поднимает следующие контейнеры:

```text
frontend
backend
scheduler-worker
postgres
redis
kafka
minio
```

Backend и Scheduler Worker используют один программный пакет доменной и прикладной логики, но запускаются как разные процессы.

Kafka используется как брокер для асинхронных расчётных задач. Scheduler Worker получает задания из Kafka и выполняет их независимо от жизненного цикла HTTP-запроса.

Redis не используется как постоянное хранилище. После завершения расчёта постоянные результаты сохраняются в PostgreSQL.

MinIO используется как S3-совместимое объектное хранилище. В PostgreSQL хранятся метаданные файлов и ссылки на объекты MinIO.

---

## 3. Основные модули системы

### 3.1. Frontend

Frontend разделяется на функциональные области:

- `Auth` — регистрация, вход, восстановление пароля;
- `Projects` — список проектов, создание, открытие и удаление;
- `ProjectEditor` — редактирование преподавателей, аудиторий, групп, подгрупп, потоков и учебной нагрузки;
- `Constraints` — обязательные ограничения и критерии оптимизации;
- `Generation` — запуск расчёта, прогресс, отмена;
- `ScheduleViewer` — просмотр нечётной и чётной недель, переключение TOP-N вариантов;
- `ScheduleEditor` — ручное редактирование и отображение конфликтов;
- `ImportExport` — загрузка исходных файлов, история загруженных файлов и выгрузок.

Frontend не содержит бизнес-правил составления расписания. Все проверки, влияющие на допустимость результата, выполняются Backend или Scheduler Worker.

### 3.2. Backend

Backend состоит из следующих прикладных модулей:

#### Auth

Отвечает за:

- регистрацию;
- авторизацию;
- access/refresh JWT;
- завершение сессии;
- восстановление пароля;
- проверку прав доступа к проекту.

#### Projects

Отвечает за:

- создание проекта;
- обязательное имя проекта;
- получение списка проектов;
- сохранение и удаление проекта;
- проверку принадлежности проекта пользователю.

#### AcademicData

Отвечает за CRUD-операции и локальную валидацию:

- преподавателей;
- дисциплин;
- аудиторий;
- групп;
- подгрупп;
- потоков;
- учебной нагрузки;
- доступности;
- предпочтений преподавателей.

#### Constraints

Отвечает за:

- дополнительные обязательные ограничения;
- критерии оптимизации;
- порядок приоритетов критериев.

#### Scheduling

Отвечает за:

- подготовку снимка исходных данных для расчёта;
- проверку предельных размеров;
- создание задания;
- отправку задания в Kafka;
- получение состояния расчёта;
- отмену расчёта;
- получение результатов;
- запуск полной повторной оптимизации;
- запуск оптимизации с минимизацией изменений;
- автоматическую корректировку после ручного изменения.

#### ScheduleValidation

Отвечает за проверку построенного или загруженного расписания:

- пересечения групп;
- пересечения подгрупп;
- конфликт группы с её подгруппами;
- пересечения преподавателей;
- пересечения аудиторий;
- доступность преподавателей и аудиторий;
- соответствие аудитории занятию;
- выполнение учебной нагрузки;
- дополнительные обязательные ограничения.

#### ImportExport

Отвечает за:

- приём `.xlsx`, `.ods`, `.csv`, `.json`;
- сопоставление полей;
- разбор импортируемых данных;
- создание файлов выгрузки;
- хранение истории загруженных файлов;
- хранение истории выгрузок;
- взаимодействие с MinIO.

### 3.3. Scheduler Worker

Scheduler Worker содержит прикладной слой выполнения расчётов и независимое ядро планировщика.

Основные операции:

- построение одного оптимального расписания;
- построение `TOP-N`;
- полная оптимизация существующего расписания;
- оптимизация с минимизацией изменений;
- автоматическая корректировка после зафиксированного пользователем изменения.

Worker получает из PostgreSQL неизменяемый набор входных данных, соответствующий заданию, и передаёт его в Scheduler Core.

Во время работы Worker:

1. обновляет прогресс в Redis;
2. периодически проверяет флаг отмены;
3. сохраняет найденные итоговые варианты в PostgreSQL;
4. завершает задание соответствующим состоянием.

### 3.4. Scheduler Core

Scheduler Core не зависит от FastAPI, SQLAlchemy, Kafka, Redis и MinIO.

Вход Scheduler Core представляет собой доменную модель:

- временная модель;
- преподаватели и их возможности;
- аудитории;
- группы, подгруппы и потоки;
- учебная нагрузка;
- ограничения;
- критерии оптимизации;
- режим результата.

Выход:

- один вариант расписания;
- набор `TOP-N`;
- информация об отсутствии допустимого решения;
- диагностические данные о найденных противоречиях.

Для лабораторного элемента учебной нагрузки хранится требуемое количество преподавателей:

- для лекции — `1`;
- для практики — `1`;
- для лабораторной работы — положительное целое число, заданное пользователем.

Конкретная стратегия поиска инкапсулируется за интерфейсом планировщика и может изменяться без изменения HTTP API и остальных модулей системы.

---

## 4. Взаимодействие компонентов при построении расписания

```mermaid
%%{init: {"sequence": {"useMaxWidth": false, "diagramMarginX": 30, "actorMargin": 55, "messageMargin": 30}, "themeVariables": {"fontSize": "17px"}}}%%
sequenceDiagram
    participant F as React
    participant A as FastAPI
    participant P as PostgreSQL
    participant K as Kafka

    F->>A: POST /projects/{id}/generation-jobs
    A->>P: Проверка проекта и создание задания
    A->>K: Публикация schedule.generate
    A-->>F: job_id
```

```mermaid
%%{init: {"sequence": {"useMaxWidth": false, "diagramMarginX": 30, "actorMargin": 55, "messageMargin": 30}, "themeVariables": {"fontSize": "17px"}}}%%
sequenceDiagram
    participant K as Kafka
    participant W as Scheduler Worker
    participant P as PostgreSQL
    participant R as Redis
    participant A as FastAPI
    participant F as React

    W->>K: Получение задания
    W->>P: Загрузка снимка данных проекта
    W->>R: progress = 0

    loop Расчёт
        W->>R: Обновление progress
        W->>R: Проверка cancel_requested
    end

    W->>P: Сохранение расписаний и статуса completed
    W->>R: progress = 100

    F->>A: GET /generation-jobs/{job_id}
    A->>R: Получение оперативного прогресса
    A->>P: Получение постоянного статуса
    A-->>F: status + progress

    F->>A: GET /generation-jobs/{job_id}/schedules
    A->>P: Получение результатов
    A-->>F: Расписания
```

### Отмена расчёта

Frontend отправляет команду отмены в Backend. Backend устанавливает в Redis флаг `cancel_requested`.

Scheduler Worker проверяет этот флаг во время расчёта. После обнаружения флага Worker прекращает поиск и переводит задание в состояние `cancelled`.

Незавершённый результат не заменяет ранее сохранённое расписание.

---

## 5. Kafka

Kafka используется только для задач, которые не должны выполняться внутри HTTP-запроса.

Основной топик:

```text
schedule.jobs
```

Типы сообщений:

```text
GENERATE
REOPTIMIZE_FULL
REOPTIMIZE_MIN_CHANGES
AUTO_REPAIR
```

Минимальный состав сообщения:

```json
{
  "job_id": "...",
  "project_id": "...",
  "job_type": "GENERATE"
}
```

Полный набор исходных данных не передаётся через Kafka. Worker загружает данные из PostgreSQL по `job_id` и `project_id`.

Worker должен обрабатывать повторную доставку одного `job_id` без создания дублирующего результата.

---

## 6. Redis

Redis хранит только оперативное состояние.

Пример ключей:

```text
schedule-job:{job_id}:progress
schedule-job:{job_id}:cancel
```

`progress` содержит текущую оценку выполнения расчёта.

`cancel` содержит запрос на остановку расчёта.

Потеря данных Redis не должна приводить к потере проекта или готовых расписаний. Постоянный статус задания хранится в PostgreSQL.

---

## 7. MinIO

MinIO хранит файлы двух категорий.

### Загруженные файлы

Сохраняется оригинальный файл, загруженный пользователем:

- `.xlsx`;
- `.ods`;
- `.csv`;
- `.json`.

После разбора файла структурированные данные сохраняются в PostgreSQL. Исходный объект остаётся в MinIO и доступен в истории загрузок проекта.

### История выгрузок

Каждая сформированная пользователем выгрузка сохраняется как отдельный объект MinIO.

Для выгрузки в PostgreSQL хранятся:

- проект;
- пользователь;
- формат;
- тип выгрузки;
- дата создания;
- ключ объекта MinIO;
- имя файла;
- размер;
- связанное расписание при наличии.

Пользователь может повторно скачать ранее сформированный файл без повторной генерации.

Frontend не обращается к MinIO напрямую. Доступ к файлам выполняется через Backend с проверкой принадлежности проекта текущему пользователю.

---

## 8. Авторизация

Используется схема:

```text
access JWT + refresh token
```

### Access token

Используется для авторизации API-запросов и имеет короткий срок жизни.

### Refresh token

Используется для получения нового access token.

Refresh-сессии хранятся в PostgreSQL и могут быть отозваны при выходе пользователя.

Пароли не хранятся в открытом виде. Для хранения используется адаптивное криптографическое хеширование.

Backend проверяет принадлежность проекта пользователю до выполнения любой операции с проектом, расписанием или связанным файлом.

---

## 9. Модель данных

### 9.1. ER-диаграммы

На диаграммах показаны поля таблиц PostgreSQL, первичные (PK), внешние (FK) и уникальные (UK) ключи. Все поля обязательны (NOT NULL), кроме явно отмеченных как nullable. Тип varchar_array обозначает массив PostgreSQL VARCHAR(9)[]; jsonb — структурированные данные. Названия сущностей даны в единственном числе, таблиц — в подпунктах ниже.

Таблицы users, user_sessions и projects уже реализованы в ORM. Остальные таблицы описывают целевую модель, миграции которой ещё не выполнены. Повторно встречающиеся на разных диаграммах сущности показаны с одним PK: их полный состав полей приведён в основной группе.

#### 9.1.1. Пользователь, проект и учебные данные

~~~mermaid
erDiagram
    USER ||--o{ PROJECT : owns
    PROJECT ||--o{ TEACHER : contains
    PROJECT ||--o{ SUBJECT : contains
    PROJECT ||--o{ ROOM : contains
    PROJECT ||--o{ STUDENT_GROUP : contains
    PROJECT ||--o{ STUDENT_STREAM : contains
    PROJECT ||--o{ WORKLOAD : contains
    STUDENT_GROUP ||--o{ SUBGROUP : contains
    STUDENT_STREAM ||--o{ STREAM_GROUP : includes
    STUDENT_GROUP ||--o{ STREAM_GROUP : participates
    SUBJECT ||--o{ WORKLOAD : describes
    STUDENT_GROUP |o--o{ WORKLOAD : targets
    SUBGROUP |o--o{ WORKLOAD : targets
    STUDENT_STREAM |o--o{ WORKLOAD : targets

    USER {
        uuid id PK
        varchar email UK
        text password_hash
        timestamp created_at
    }
    PROJECT {
        uuid id PK
        uuid owner_id FK
        varchar name
        varchar_array odd_week_days
        varchar_array even_week_days
        varchar time_mode
        integer time_step_minutes "nullable"
        varchar duration_mode
        integer duration_minutes "nullable"
        timestamp created_at
        timestamp updated_at
    }
    TEACHER {
        uuid id PK
        uuid project_id FK
        varchar full_name
    }
    SUBJECT {
        uuid id PK
        uuid project_id FK
        varchar name
    }
    ROOM {
        uuid id PK
        uuid project_id FK
        varchar name
        integer capacity
        varchar room_type
    }
    STUDENT_GROUP {
        uuid id PK
        uuid project_id FK
        varchar name
        integer student_count
    }
    SUBGROUP {
        uuid id PK
        uuid group_id FK
        varchar name
        integer student_count
    }
    STUDENT_STREAM {
        uuid id PK
        uuid project_id FK
        varchar name
    }
    STREAM_GROUP {
        uuid stream_id PK,FK
        uuid group_id PK,FK
    }
    WORKLOAD {
        uuid id PK
        uuid project_id FK
        uuid subject_id FK
        varchar lesson_type
        varchar lesson_format
        integer occurrences_per_cycle
        integer duration_minutes "nullable"
        integer required_teacher_count
        uuid group_id FK "nullable"
        uuid subgroup_id FK "nullable"
        uuid stream_id FK "nullable"
    }
~~~

#### 9.1.2. Возможности и доступность ресурсов

~~~mermaid
erDiagram
    STUDENT_GROUP ||--o{ GROUP_AVAILABILITY : available
    SUBGROUP ||--o{ SUBGROUP_AVAILABILITY : available
    TEACHER ||--o{ TEACHER_CAPABILITY : can_teach
    SUBJECT ||--o{ TEACHER_CAPABILITY : taught_as
    TEACHER ||--o{ TEACHER_AVAILABILITY : available
    TEACHER ||--o{ TEACHER_PREFERENCE : prefers
    ROOM ||--o{ ROOM_AVAILABILITY : available
    ROOM ||--o{ ROOM_CAPABILITY : supports
    SUBJECT ||--o{ ROOM_CAPABILITY : requires

    TEACHER {
        uuid id PK
    }
    SUBJECT {
        uuid id PK
    }
    ROOM {
        uuid id PK
    }
    STUDENT_GROUP {
        uuid id PK
    }
    SUBGROUP {
        uuid id PK
    }
    GROUP_AVAILABILITY {
        uuid id PK
        uuid group_id FK
        varchar week
        varchar weekday
        time start_time
        time end_time
    }
    SUBGROUP_AVAILABILITY {
        uuid id PK
        uuid subgroup_id FK
        varchar week
        varchar weekday
        time start_time
        time end_time
    }
    TEACHER_CAPABILITY {
        uuid teacher_id PK,FK
        uuid subject_id PK,FK
        varchar lesson_type PK
    }
    TEACHER_AVAILABILITY {
        uuid id PK
        uuid teacher_id FK
        varchar week
        varchar weekday
        time start_time
        time end_time
    }
    TEACHER_PREFERENCE {
        uuid id PK
        uuid teacher_id FK
        varchar week
        varchar weekday
        time start_time
        time end_time
    }
    ROOM_AVAILABILITY {
        uuid id PK
        uuid room_id FK
        varchar week
        varchar weekday
        time start_time
        time end_time
    }
    ROOM_CAPABILITY {
        uuid room_id PK,FK
        uuid subject_id PK,FK
        varchar lesson_type PK
    }
~~~

#### 9.1.3. Расчёты, результаты и файлы

~~~mermaid
erDiagram
    USER ||--o{ USER_SESSION : authenticates
    PROJECT ||--o{ EXTRA_CONSTRAINT : limits
    PROJECT ||--o{ OPTIMIZATION_CRITERION : optimizes
    PROJECT ||--o{ SCHEDULE_JOB : launches
    PROJECT ||--o{ SCHEDULE : contains
    PROJECT ||--o{ STORED_FILE : stores
    USER ||--o{ STORED_FILE : uploaded_by
    SCHEDULE_JOB |o--o{ SCHEDULE : produces
    SCHEDULE ||--o{ SCHEDULE_ENTRY : contains
    WORKLOAD |o--o{ SCHEDULE_ENTRY : generates
    ROOM |o--o{ SCHEDULE_ENTRY : assigned
    SCHEDULE_ENTRY ||--o{ SCHEDULE_ENTRY_TEACHER : assigned
    TEACHER |o--o{ SCHEDULE_ENTRY_TEACHER : leads
    SCHEDULE |o--o{ STORED_FILE : exported_in
    SCHEDULE_JOB |o--o{ STORED_FILE : produced_in

    USER {
        uuid id PK
    }
    PROJECT {
        uuid id PK
    }
    ROOM {
        uuid id PK
    }
    TEACHER {
        uuid id PK
    }
    WORKLOAD {
        uuid id PK
    }
    USER_SESSION {
        uuid id PK
        uuid user_id FK
        text refresh_token_hash UK
        timestamp created_at
        timestamp expires_at
        timestamp revoked_at "nullable"
    }
    EXTRA_CONSTRAINT {
        uuid id PK
        uuid project_id FK
        varchar constraint_type
        jsonb scope
        jsonb parameters
    }
    OPTIMIZATION_CRITERION {
        uuid project_id PK,FK
        varchar criterion_type PK
        integer priority
        boolean is_active
    }
    SCHEDULE_JOB {
        uuid id PK
        uuid project_id FK
        varchar job_type
        varchar status
        varchar result_mode
        integer top_n "nullable"
        timestamp created_at
        timestamp started_at "nullable"
        timestamp finished_at "nullable"
        text error_message "nullable"
    }
    SCHEDULE {
        uuid id PK
        uuid project_id FK
        uuid job_id FK "nullable"
        varchar source
        integer result_index "nullable"
        jsonb criterion_scores "nullable"
        timestamp created_at
    }
    SCHEDULE_ENTRY {
        uuid id PK
        uuid schedule_id FK
        uuid workload_id FK "nullable"
        varchar subject_name "nullable"
        varchar participant_label "nullable"
        varchar lesson_type "nullable"
        varchar lesson_format "nullable"
        varchar week
        varchar weekday
        time start_time
        time end_time
        uuid room_id FK "nullable"
        varchar room_name "nullable"
    }
    SCHEDULE_ENTRY_TEACHER {
        uuid id PK
        uuid entry_id FK
        uuid teacher_id FK "nullable"
        varchar display_name
    }
    STORED_FILE {
        uuid id PK
        uuid project_id FK
        uuid user_id FK
        varchar category
        varchar original_name
        varchar file_format
        text object_key UK
        bigint size_bytes
        timestamp created_at
        uuid schedule_id FK "nullable"
        uuid job_id FK "nullable"
    }
~~~
### 9.2. Пользователь

Таблица users: email уникален, нормализуется удалением пробелов по краям и приведением к нижнему регистру (максимум 254 символа). Пароль хранится только как адаптивный хеш.

Таблица user_sessions: хранится хеш refresh-токена, а не сам токен. При удалении пользователя его сессии и проекты удаляются каскадно. revoked_at заполняется при отзыве сессии.

### 9.3. Проект

Таблица projects: имя непустое, максимум 200 символов. odd_week_days и even_week_days содержат наборы дней двухнедельного цикла; пустые наборы допустимы.

Режим начала занятий: HOUR_START или STEP. Положительное значение time_step_minutes обязательно только при STEP. Режим длительности: UNIFORM или INDIVIDUAL. Положительное duration_minutes обязательно только при UNIFORM.

По умолчанию: понедельник–суббота для обеих недель, HOUR_START, UNIFORM, длительность **100 минут**. Локально корректные, но несовместимые настройки проверяются при построении расписания.

### 9.4. Преподаватели и дисциплины

Таблицы teachers и subjects хранят преподавателей и дисциплины. teacher_capabilities определяет пары «дисциплина + тип занятия», доступные преподавателю; одна пара может быть связана с несколькими преподавателями.

teacher_availability хранит обязательные интервалы доступности, teacher_preferences — необязательные интервалы, учитываемые только при оптимизации. Для интервалов требуется start_time < end_time.

### 9.5. Аудитории

Таблица rooms: вместимость положительна; room_type принимает LECTURE, PRACTICE_UNIVERSAL, PRACTICE_SPECIALIZED, LABORATORY.

room_availability хранит интервалы доступности. room_capabilities задаёт допустимые дисциплины и типы занятий для специализированных и лабораторных аудиторий.

### 9.6. Группы и подгруппы

В student_groups и subgroups количество студентов положительно. Сумма количества студентов всех подгрупп одной группы не может превышать численность группы.

group_availability и subgroup_availability задают **необязательные ограничения доступности** на нечётной и чётной неделе: неделя, день, начало и окончание интервала. Интервалы локально корректны при start_time < end_time. Если для группы или подгруппы интервалы не указаны, она считается доступной в разрешённые проектом учебные дни. Если интервалы указаны, они ограничивают время занятий в пределах этих дней.

Для занятия всей группы проверяется её доступность. Для занятия подгруппы одновременно проверяется доступность родительской группы и самой подгруппы. Для потока проверяется пересечение доступности **всех** входящих в поток групп. Это обеспечивает F_Rule_1 без обязательного ввода интервалов для каждой группы.

### 9.7. Потоки

student_streams хранит потоки. stream_groups связывает существующие группы с потоками с уникальной парой (stream_id, group_id). Потоки формируются вручную.

### 9.8. Учебная нагрузка

В workloads заполнено ровно одно поле из group_id, subgroup_id, stream_id. occurrences_per_cycle и required_teacher_count — положительные целые числа.

lesson_format принимает ONSITE или REMOTE. Для REMOTE аудитория не назначается. В режиме INDIVIDUAL duration_minutes положительно; в режиме UNIFORM используется длительность проекта.

Для лекции или практики required_teacher_count = 1; для лабораторной работы required_teacher_count >= 1.

### 9.9. Дополнительные ограничения

extra_constraints содержит тип, область применения и параметры в структурированном виде. Поддерживаемые типы: MIN_START_TIME, MAX_END_TIME, ALLOWED_DAYS, EVERY_WEEK, CONSECUTIVE, NOT_CONSECUTIVE, MIN_GAP, BEFORE, FIXED_DAY, TIME_RANGE.

### 9.10. Критерии оптимизации

optimization_criteria имеет уникальную пару (project_id, criterion_type). Приоритеты активных критериев одного проекта уникальны, применяются по возрастанию priority.

### 9.11. Задания расчёта

schedule_jobs имеет состояния QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED. Поле top_n обязательно и положительно только в режиме TOP-N. Даты начала и завершения отсутствуют до соответствующего перехода.

### 9.12. Расписания

Каждое schedules принадлежит проекту через обязательный project_id. Поле source принимает GENERATED или IMPORTED. Для GENERATED обязателен job_id, для IMPORTED job_id равен NULL. Значения result_index и criterion_scores обязательны для сгенерированных вариантов, а у импортированного расписания могут отсутствовать. Такое расписание сохраняется независимо от заданий Scheduler Worker.

schedule_entries хранит размещённое занятие и его собственные данные, не только ссылки: неделю, день и время, название дисциплины, обозначение группы/подгруппы/потока, тип и **фактический формат** (ONSITE/REMOTE), отображаемое название аудитории. Для GENERATED workload_id обязателен, а snapshot-поля заполняются из учебной нагрузки. Для IMPORTED workload_id может быть NULL, а отсутствующие в файле описательные поля остаются NULL. Редактирование одного занятия изменяет его запись, **не изменяя** исходный формат всех проведений нагрузки.

При известной аудитории room_id ссылается на rooms; для REMOTE room_id и room_name равны NULL. При неполных данных импортированного очного занятия room_id допускается NULL при сохранённом room_name. schedule_entry_teachers хранит отдельные назначения: display_name обязателен, teacher_id может быть NULL, когда известен только текст из импортированного файла. При привязке к существующему преподавателю обе величины синхронизируются. Повторный teacher_id внутри занятия не допускается.

Проверка расписания использует связанные учебные данные там, где они есть; при недостаточности данных выполняет только применимые проверки (F_Existing_1–F_Existing_4). Минимально необходимую информацию о занятиях нельзя терять при импорте. Для будущих миграций требуется CHECK согласованности source/job_id и ключей/полей формата.

### 9.13. Файлы

stored_files хранит категорию UPLOAD или EXPORT, исходное имя, формат, ссылку на объект MinIO и метаданные. Ссылки на расписание и задание необязательны.

### 9.14. Статус детализации

Реализованные колонки и ограничения users, user_sessions и projects соответствуют ORM в dev. Остальная схема представляет целевой контракт, а не существующие миграции. Правила доступности групп/подгрупп, происхождения расписаний и хранения данных импортированных занятий зафиксированы выше; они ещё не реализованы. Перечень значений типов занятия и структура параметров конкретных дополнительных ограничений потребуют дальнейшей детализации. Этот документ не инициирует миграций.

---

## 10. API

API использует JSON для прикладных запросов и `multipart/form-data` для загрузки файлов.

Основные группы маршрутов:

### Авторизация

```text
POST /auth/register
POST /auth/login
POST /auth/refresh
POST /auth/logout
POST /auth/password-reset/request
POST /auth/password-reset/confirm
```

### Проекты

```text
GET    /projects
POST   /projects
GET    /projects/{project_id}
PATCH  /projects/{project_id}
DELETE /projects/{project_id}
```

### Исходные данные

```text
/projects/{project_id}/teachers
/projects/{project_id}/subjects
/projects/{project_id}/rooms
/projects/{project_id}/groups
/projects/{project_id}/subgroups
/projects/{project_id}/streams
/projects/{project_id}/workloads
```

Для коллекций применяются стандартные операции получения, создания, изменения и удаления.

### Ограничения и оптимизация

```text
/projects/{project_id}/constraints
/projects/{project_id}/optimization-criteria
```

### Построение

```text
POST /projects/{project_id}/generation-jobs
GET  /generation-jobs/{job_id}
POST /generation-jobs/{job_id}/cancel
GET  /generation-jobs/{job_id}/schedules
```

### Расписания

```text
GET   /schedules/{schedule_id}
PATCH /schedules/{schedule_id}/entries/{entry_id}
POST  /schedules/{schedule_id}/validate
POST  /schedules/{schedule_id}/auto-repair
POST  /schedules/{schedule_id}/reoptimize
```

### Импорт и экспорт

```text
POST /projects/{project_id}/imports
GET  /projects/{project_id}/files
POST /projects/{project_id}/exports
GET  /files/{file_id}
DELETE /files/{file_id}
```

### Ошибки API

Ошибки возвращаются в единой форме:

```json
{
  "code": "ROOM_CAPACITY_CONFLICT",
  "message": "Вместимость аудитории недостаточна",
  "details": {}
}
```

---

## 11. Логика эквивалентных оптимальных вариантов

Критерии оптимизации сравниваются по заданному пользователем приоритету.

Если несколько найденных расписаний имеют одинаковый результат по всем выбранным критериям, дополнительная сортировка по содержимому расписания не выполняется.

Их взаимный порядок соответствует порядку получения Scheduler Core.

В режиме одного варианта возвращается первый найденный оптимальный вариант.

В режиме `TOP-N` при наличии большего количества равноценных вариантов сохраняются первые найденные варианты до заполнения `N` мест.

---

## 12. Работа с существующим расписанием

Загруженное расписание сохраняется независимо от результата его проверки.

Если исходных данных недостаточно, Backend выполняет только доступные проверки.

Если при проверке обнаружено хотя бы одно нарушение обязательного ограничения:

1. операция проверки завершается результатом `invalid`;
2. API возвращает список обнаруженных конфликтов;
3. расписание остаётся сохранённым;
4. пользователь может продолжить его редактирование.

Полная оптимизация может полностью изменить расположение занятий в пределах заданных ограничений.

При оптимизации с минимизацией изменений первым критерием является минимальное количество изменений исходных:

- дня;
- времени;
- формата;
- аудитории;
- преподавателей.

После этого применяются пользовательские критерии оптимизации.

---

## 13. Импорт и экспорт

### Импорт

Последовательность:

1. Backend принимает файл.
2. Оригинал сохраняется в MinIO.
3. Метаданные файла сохраняются в PostgreSQL.
4. Backend разбирает файл.
5. Пользователь при необходимости сопоставляет столбцы.
6. Валидные данные сохраняются в PostgreSQL.
7. Ошибочные строки возвращаются пользователю как результат импорта.

Ошибка разбора не удаляет оригинальный файл.

### Экспорт

Последовательность:

1. Пользователь выбирает расписание или полный проект.
2. Backend формирует файл требуемого формата.
3. Файл сохраняется в MinIO.
4. Метаданные добавляются в историю выгрузок.
5. Пользователь получает файл.

---

## 14. Макет интерфейса

### 14.1. Список проектов

```text
┌─────────────────────────────────────────────────────┐
│ Расписание                               Профиль     │
├─────────────────────────────────────────────────────┤
│ Мои проекты                          [Создать проект]│
│                                                     │
│ Университет, осень 2026        [Открыть] [Удалить] │
│ Тестовое расписание             [Открыть] [Удалить] │
└─────────────────────────────────────────────────────┘
```

### 14.2. Редактор проекта

```text
┌──────────────────────────────────────────────────────────────┐
│ Проект: Университет, осень 2026                             │
├──────────────────────────────────────────────────────────────┤
│ Преподаватели │ Аудитории │ Группы │ Нагрузка │ Ограничения │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│                    Данные выбранного раздела                  │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│ [Импорт]                           [Настройки] [Рассчитать]   │
└──────────────────────────────────────────────────────────────┘
```

### 14.3. Расчёт

```text
┌─────────────────────────────────────────────────────┐
│ Построение расписания                               │
├─────────────────────────────────────────────────────┤
│ Статус: выполняется                                 │
│ ███████████████░░░░░░░░░  63%                      │
│                                                     │
│                                      [Отменить]     │
└─────────────────────────────────────────────────────┘
```

### 14.4. Просмотр расписания

```text
┌──────────────────────────────────────────────────────────────┐
│ Вариант 2 из 5                  [←] [→]                      │
│ [Нечётная неделя] [Чётная неделя]                           │
├──────────┬──────────────┬──────────────┬─────────────────────┤
│ Время    │ Понедельник  │ Вторник      │ ...                 │
├──────────┼──────────────┼──────────────┼─────────────────────┤
│ 10:00    │ Физика       │ Математика   │                     │
│          │ 301          │ 302-1        │                     │
│          │ Иванов       │ Петров       │                     │
├──────────┼──────────────┼──────────────┼─────────────────────┤
│ ...                                                          │
├──────────────────────────────────────────────────────────────┤
│ [Проверить] [Оптимизировать] [Экспорт]                       │
└──────────────────────────────────────────────────────────────┘
```

Конфликтное занятие визуально выделяется. При выборе такого занятия отображается список причин конфликта.

---

## 15. Тестируемость

### 15.1. Границы модулей

Бизнес-логика отделена от HTTP и инфраструктуры.

FastAPI routers:

- преобразуют HTTP-запрос в прикладную команду;
- вызывают прикладной сервис;
- преобразуют результат в HTTP-ответ.

В routers не размещаются:

- правила допустимости расписания;
- оптимизация;
- работа с SQLAlchemy-сессиями на уровне бизнес-правил;
- непосредственная работа с Kafka, Redis или MinIO.

Scheduler Core представляет отдельный модуль без инфраструктурных зависимостей.

### 15.2. Точки подмены зависимостей

Прикладные модули используют абстракции:

```text
UserRepository
UserSessionRepository
ProjectRepository
UnitOfWork
AcademicDataRepository
ScheduleRepository
JobRepository
JobPublisher
JobStateStore
ObjectStorage
MailSender
TokenService
ScheduleSolver
Clock
IdGenerator
```

Рабочие реализации:

```text
SQLAlchemy repositories
SqlUnitOfWork
KafkaJobPublisher
RedisJobStateStore
MinioObjectStorage
SMTPMailSender
JwtTokenService
```

В модульных и интеграционных тестах они могут заменяться fake/mock-реализациями.

`UnitOfWork` задаёт границу транзакции прикладного сценария: репозитории пользователей, refresh-сессий и проектов используют одну SQLAlchemy-сессию. Для сохранения изменений требуется явный `commit()`; при выходе из контекста без фиксации незавершённые изменения откатываются, сессия закрывается. Фабрика `Container.uow()` создаёт новый `UnitOfWork` для каждой операции.

### 15.3. Управление состоянием и временем

Текущее время не должно запрашиваться напрямую внутри бизнес-логики.

Для операций, зависящих от времени, используется `Clock`.

Генерация идентификаторов выполняется через `IdGenerator`.

Это позволяет воспроизводимо тестировать:

- срок действия токенов;
- дату создания файлов;
- состояния заданий;
- временные ограничения.

Scheduler Core не использует случайный выбор как источник недетерминированного результата без возможности задать источник случайности извне.

Если стратегия поиска использует псевдослучайность, генератор и seed передаются через абстракцию.

### 15.4. Тестовое окружение

Для интеграционных тестов Docker Compose может поднять:

- PostgreSQL;
- Redis;
- Kafka;
- MinIO.

Frontend и Backend тестируются отдельно.

Сервис электронной почты в тестах заменяется fake-реализацией.

Scheduler Core может тестироваться без запуска Docker-контейнеров.

Тестовые данные создаются программно перед тестом и очищаются после его выполнения.

### 15.5. Наблюдаемость

Backend и Worker используют структурированные логи.

Каждое длительное задание имеет `job_id`, который включается в связанные записи логов.

Для HTTP-запроса используется `request_id`.

Наблюдаемые состояния задания:

```text
QUEUED
RUNNING
COMPLETED
FAILED
CANCELLED
```

Успешность операции определяется через:

- HTTP-код и тело ответа;
- состояние задания;
- сохранённый результат в PostgreSQL;
- состояние файла в MinIO;
- структурированные логи.

---

## 16. Разделение ответственности

#### 16.1. Backend и прикладные модули

```mermaid
%%{init: {"flowchart": {"useMaxWidth": false, "htmlLabels": true, "curve": "basis"}, "themeVariables": {"fontSize": "18px"}}}%%
flowchart TB
    UI[React UI] --> API[FastAPI routers]
    API --> AUTH[Auth]
    API --> PROJ[Projects]
    API --> DATA[Academic Data]
    API --> CONS[Constraints]
    API --> SCHED[Scheduling Application]
    API --> IO[Import / Export]
    API --> VALID[Schedule Validation]

    AUTH --> DB[(PostgreSQL)]
    AUTH --> MAIL[Email Provider]
    PROJ --> DB
    DATA --> DB
    CONS --> DB
    VALID --> DB
    IO --> DB
    IO --> MINIO[(MinIO)]
    SCHED --> DB
    SCHED --> REDIS[(Redis)]
    SCHED --> KAFKA[Kafka]
```

#### 16.2. Worker и вычислительное ядро

```mermaid
%%{init: {"flowchart": {"useMaxWidth": false, "htmlLabels": true, "curve": "basis"}, "themeVariables": {"fontSize": "18px"}}}%%
flowchart TB
    KAFKA[Kafka] --> WAPP[Worker Application]
    WAPP --> CORE[Scheduler Core]
    WAPP --> DB[(PostgreSQL)]
    WAPP --> REDIS[(Redis)]
    WAPP --> MINIO[(MinIO)]
```

---

## 17. Основные технологические решения

| Технология | Причина использования |
|---|---|
| Python | Backend и вычислительная часть реализуются на одном языке; подходит для реализации алгоритмов поиска и оптимизации |
| FastAPI | Типизированный HTTP API, автоматическая OpenAPI-схема, удобная интеграция с Python-моделями |
| SQLAlchemy | Отделение прикладной логики от конкретных SQL-запросов и работа с PostgreSQL |
| PostgreSQL | Реляционные связи между большим числом сущностей и транзакционное постоянное хранение |
| React | Компонентный пользовательский интерфейс для сложных интерактивных форм и расписания |
| MUI | Готовые компоненты интерфейса и единообразное оформление |
| Kafka | Асинхронная передача длительных расчётных задач Scheduler Worker |
| Redis | Быстрое краткоживущее состояние прогресса и отмены расчётов |
| MinIO | Хранение исходных файлов и истории созданных выгрузок отдельно от реляционной БД |
| Docker Compose | Воспроизводимое локальное и тестовое окружение со всеми внутренними зависимостями |

