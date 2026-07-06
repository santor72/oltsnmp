# AGENTS.md

Этот файл нужен как рабочая памятка для дальнейшей разработки `python_fastapi`.

## Goal

Сервис опрашивает OLT/ONU и выдает HTTP API. Архитектура уже подготовлена не только под ZTE, но и под дальнейшее добавление других вендоров и inventory sources.

Текущий приоритет архитектуры:
- не смешивать FastAPI route-логику с vendor-specific кодом;
- держать SNMP/CLI/Inventory по разным слоям;
- расширять проект через адаптеры и провайдеры, а не через `if vendor == ...` по всему коду.

## Current State

Сейчас реализовано:
- vendor adapter: только `ZTEAdapter`
- inventory providers:
  - `ZabbixInventory`
  - `SNMPPlatformInventory`
  - `InventoryChain`
- сервисные endpoints:
  - `/onu`
  - `/onus`
  - `/onus-new`
  - `/onucli`
  - `/cache/invalidate`
  - `/cache/clear`
- Redis cache
- CLI fallback из `/onu` при SNMP timeout
- Debug headers по vendor resolution

## Important Architectural Rules

### 1. Vendor-specific код должен жить внутри vendor module

Не выносить наружу:
- SNMP OID формулы конкретного вендора
- CLI команды конкретного вендора
- TextFSM шаблоны конкретного вендора
- device_type для `netmiko`
- vendor-specific transport defaults

Сейчас все это для ZTE должно жить в:
- `app/vendors/zte/adapter.py`
- `app/vendors/zte/oid.py`
- `app/vendors/zte/cli_transport.py`
- `app/vendors/zte/cli_parser.py`
- `app/vendors/zte/textfsm_templates/`

### 2. API слой не должен знать детали vendor detection

`app/main.py` должен только:
- собрать зависимости;
- вызвать `VendorResolver`;
- работать с кешем;
- вернуть HTTP response.

Нельзя снова тащить в routes:
- прямой вызов Zabbix API;
- прямой вызов SNMP `sysObjectID`;
- разбор `platforms.csv`.

### 3. VendorResolver должен оставаться тонким

Его задача:
- explicit vendor override;
- inventory lookup;
- fallback to default vendor.

Он не должен содержать тяжелую бизнес-логику конкретного inventory source.

### 4. Inventory должен расширяться через provider chain

Новые источники определения vendor нужно добавлять как отдельные провайдеры, а не переписывать `VendorResolver`.

Текущий контракт:
- `InventoryProvider.lookup_vendor(olt_ip) -> InventoryLookupResult`

## Current File Map

### API and app wiring

- `app/main.py`
- `app/config.py`
- `app/models.py`
- `app/cache.py`

### Core

- `app/core/provider.py`
- `app/core/registry.py`
- `app/core/vendor_resolver.py`

### Service layer

- `app/services/onu_service.py`

### Inventory layer

- `app/inventory/provider.py`
- `app/inventory/chain.py`
- `app/inventory/zabbix.py`
- `app/inventory/snmp_platform.py`

### Vendor layer

- `app/vendors/zte/adapter.py`
- `app/vendors/zte/oid.py`
- `app/vendors/zte/cli_transport.py`
- `app/vendors/zte/cli_parser.py`
- `app/vendors/zte/textfsm_templates/*`

### Data

- `data/platforms.csv`

### Tests

- `tests/test_service.py`
- `tests/test_oid.py`
- `tests/test_cli_parser.py`
- `tests/test_vendor_resolver.py`
- `tests/test_zabbix_inventory.py`
- `tests/test_snmp_platform_inventory.py`
- `tests/test_inventory_chain.py`
- `tests/test_transformers.py`

## How Vendor Resolution Works

Если `vendor` передан явно в query:
- он идет в `VendorRegistry`
- inventory пропускается

Если `vendor` не передан:
- `VendorResolver` вызывает `InventoryChain`
- порядок сейчас такой:
  1. `ZabbixInventory`
  2. `SNMPPlatformInventory`
- если оба не дали match:
  - используется `DEFAULT_VENDOR`

Debug информация уходит в response headers:
- `X-Vendor-Debug`
- `X-Resolved-Vendor`
- `X-Vendor-Source`

А при `DEBUG=1` также пишется в container logs.

## How Zabbix Inventory Works

`ZabbixInventory`:
- использует `zabbix-utils`
- делает lookup по `hostinterface.get(filter={"ip": olt_ip})`
- затем `host.get(... selectTags="extend", selectInheritedTags="extend")`
- ищет tag `vendor`
- прогоняет найденное значение через `VendorRegistry`

Важно:
- для решения используется число уникальных `hostid`, а не количество интерфейсов;
- timeout настраивается через `ZABBIX_TIMEOUT`;
- если пакет `zabbix-utils` отсутствует, lookup вернет miss с note об ошибке.

## How SNMP Platform Inventory Works

`SNMPPlatformInventory`:
- опрашивает `.1.3.6.1.2.1.1.2.0`
- нормализует `sysObjectID`
- ищет его в `data/platforms.csv`
- сначала пытается резолвить vendor через `full_name.lower()`
- если не получилось, через `vendor.lower()`

Важно:
- `platforms.csv` должен попадать в Docker image;
- `Dockerfile` уже копирует `data/`;
- если CSV структура изменится, придется обновить `_load_platforms`.

## How ZTE Adapter Works

### SNMP detail

`ZTEAdapter.get_onu()`:
- сначала делает direct `get` по name OID;
- если timeout, исключение уходит в сервисный слой, где может сработать CLI fallback;
- затем отдельными `get` собирает detail-поля.

### List mode 1

`ZTEAdapter.get_onus()`:
- `walk` по именам ONU;
- затем `get_many` по 4 OID на каждую ONU.

### List mode 2

`ZTEAdapter.get_onus_new()`:
- несколько `walk` по разным таблицам;
- merge по `onu_id`.

### CLI mode

`ZTEAdapter.get_onu_cli()`:
- собирает ZTE-specific команды;
- вызывает `ZTECLITransport`;
- парсит ответы через TextFSM.

## How CLI Works

`ZTECLITransport`:
- работает через `netmiko`
- поддерживает `ssh` и `telnet`
- device types зашиты внутри vendor transport:
  - `zte_zxros`
  - `zte_zxros_telnet`

Это правильно и не должно снова возвращаться в общий слой.

## Cache Rules

Redis cache keys включают:
- endpoint type
- vendor
- `olt_ip`
- `board_id`
- `pon_id`
- `onu_id`, если применимо
- `access` для `/onucli`

Параметр `nocache=true`:
- пропускает чтение из кеша;
- но после запроса значение все равно обновляется в кеше.

## Debug and Observability

Есть 2 независимых механизма:

### Response debug

`debug=true` в HTTP query:
- включает debug headers
- не меняет body response

### Runtime debug

`DEBUG=1` в environment:
- включает логи inventory resolution в stdout/stderr контейнера

Если нужен новый debug-путь, лучше не ломать response schema. Предпочтительный формат:
- headers для on-demand диагностики
- logs для runtime tracing

## Common Pitfalls

### 1. Не использовать `localhost` внутри контейнера для доступа к хосту

Нужно использовать:
- `host.docker.internal` на Docker Desktop
- или `extra_hosts` с `host-gateway`

### 2. Не забывать про `data/platforms.csv` в Docker image

Если меняется Dockerfile, нужно убедиться, что:
- `COPY data ./data`
остается на месте.

### 3. Не переносить vendor-specific CLI обратно в общий слой

`cli_client.py` уже был убран из общего слоя. Не возвращать такую архитектуру.

### 4. Не тащить inventory-логику в `VendorResolver`

Новый inventory source должен быть отдельным provider.

### 5. Не смешивать две модели списка ONU

`/onus` и `/onus-new` сейчас специально существуют параллельно для сравнения.
Не заменять одну другой без явного решения.

## Safe Extension Patterns

### Добавление нового vendor adapter

Нужно:
1. создать `app/vendors/<vendor>/`
2. реализовать adapter по `VendorProvider`
3. задать `vendor_tags`
4. подключить в `VendorRegistry`
5. добавить тесты

### Добавление нового inventory source

Нужно:
1. реализовать `lookup_vendor`
2. вернуть `InventoryLookupResult`
3. добавить provider в `InventoryChain` в правильном порядке
4. покрыть тестами miss/match/error/timeout

### Добавление новых CLI команд для ZTE

Нужно:
1. обновить `ZTEAdapter.get_onu_cli`
2. добавить или изменить TextFSM template
3. обновить `parse_onu_cli_outputs`
4. обновить тесты parser

## Recommended Validation Commands

После заметных изменений запускать:

```bash
cd python_fastapi
PYTHONPATH=. python3 -m unittest discover -s tests -v
python3 -m py_compile app/core/*.py app/services/*.py app/vendors/zte/*.py app/inventory/*.py app/*.py tests/*.py
```

Если менялись зависимости или Docker packaging:

```bash
cd python_fastapi
docker compose build app
docker compose up -d
```

## Current Dependencies

- `fastapi`
- `uvicorn[standard]`
- `pysnmp`
- `netmiko`
- `textfsm`
- `redis`
- `zabbix-utils`

## Good Next Steps

Логичные будущие задачи:
- добавить второй vendor adapter;
- сделать inventory source configuration более явной;
- добавить endpoint для диагностики inventory resolution отдельно от ONU API;
- покрыть integration-style тестами комбинации `debug + inventory + cache`;
- при необходимости вынести `platforms.csv` в управляемую внутреннюю базу данных или API.
