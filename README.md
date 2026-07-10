# OLT FastAPI Service
Идея заимствована из https://github.com/Cepat-Kilat-Teknologi/snmp-olt-zte
Python/FastAPI сервис для опроса OLT и ONU. Исходно был сделан как перенос логики из Cepat-Kilat-Teknologi/snmp-olt-zte `GetByBoardIDPonIDAndOnuID`, `GetByBoardIDAndPonID` и оптимизированного варианта `GetByBoardIDAndPonIDNew`, затем был расширен CLI-опросом, кешем, auto-detect vendor и vendor/inventory архитектурой.

Сейчас сервис умеет:
- получать детальную информацию по одной ONU по SNMP;
- получать детальную информацию по ONU по SNMP через port-формат `gpon-olt_1/1/1`;
- получать список ONU на PON двумя способами: `onus` и `onus-new`;
- получать данные по CLI через SSH или Telnet;
- делать fallback на CLI в `/onu`, если SNMP вернул timeout;
- кешировать ответы в Redis;
- определять vendor по явному параметру, через Zabbix или через SNMP `sysObjectID`.

## Endpoints

- `GET /health`
- `GET /onu`
- `GET /onup`
- `GET /onudebug`
- `GET /onus`
- `GET /onus-new`
- `GET /onucli`
- `DELETE /cache/invalidate`
- `DELETE /cache/clear`

### `/onu`

Получение подробной информации по одной ONU.

Пример:

```bash
curl "http://127.0.0.1:8000/onu?olt_ip=10.5.0.21&board_id=1&pon_id=1&onu_id=125"
```

Параметры:
- `olt_ip` обязательный
- `board_id` обязательный
- `pon_id` обязательный
- `onu_id` обязательный
- `vendor` необязательный, явный override vendor
- `nocache` необязательный, `true` пропускает чтение из кеша и обновляет его после запроса
- `debug` необязательный, включает debug headers по vendor resolution

Особенность:
- если SNMP на первом запросе имени ONU вернул timeout, сервис пытается получить данные через CLI fallback;
- для ZTE fallback transport по умолчанию: `telnet`.

### `/onup`

Получение подробной информации по одной ONU через port-строку.

Пример:

```bash
curl "http://127.0.0.1:8000/onup?olt_ip=10.5.0.21&port=gpon-olt_1/1/1&onu_id=125"
```

Параметры:
- `olt_ip` обязательный
- `port` обязательный, формат `gpon-olt_<shelf>/<slot>/<port>` или bare `1/1/1`
- `onu_id` обязательный
- `vendor` необязательный, явный override vendor
- `nocache` необязательный, `true` пропускает чтение из кеша и обновляет его после запроса
- `debug` необязательный, включает debug headers по vendor resolution

Особенность:
- `port` разбирается внутри ZTE adapter;
- для ZTE SNMP OID индекс считается через байты: `type/shelf/slot/port`;
- `type` сейчас сохраняется в port-строке как резерв для будущих vendor-variants.
- если префикс не передан, ZTE использует default `gpon-olt`.

### `/onudebug`

Debug-версия `/onup`.

Возвращает:
- обычные данные ONU из `/onup`;
- список `field -> oid` для всех SNMP-полей, которые читает `/onup`;
- raw вывод CLI-команд для ZTE:
  - `sh gpon onu detail-info gpon-onu_<port>:<onu_id>`
  - `sh pon power attenuation gpon-onu_<port>:<onu_id>`

Пример:

```bash
curl "http://127.0.0.1:8000/onudebug?olt_ip=10.5.0.21&port=1/2/10&onu_id=46"
```

Это удобно, когда нужно сравнить:
- какой SNMP OID был построен;
- что в ответ вернул SNMP;
- что при этом видит CLI.

### `/onus`

Получение списка ONU на PON. После walk по именам делает batched `get_many` по 4 OID на каждую ONU.

Пример:

```bash
curl "http://127.0.0.1:8000/onus?olt_ip=10.5.0.21&board_id=1&pon_id=1"
```

### `/onus-new`

Получение списка ONU на PON через несколько table walk и merge результатов в памяти.

Пример:

```bash
curl "http://127.0.0.1:8000/onus-new?olt_ip=10.5.0.21&board_id=1&pon_id=1"
```

Разница с `/onus`:
- `/onus` делает `1 walk + 4 get на ONU`;
- `/onus-new` делает несколько `walk` по таблицам и затем склеивает данные.

Это нужно для сравнения производительности и поведения на реальных OLT.

### `/onucli`

CLI-опрос по одной ONU.

Пример:

```bash
curl "http://127.0.0.1:8000/onucli?olt_ip=10.5.0.21&board_id=1&pon_id=1&onu_id=125&access=telnet"
```

Параметры:
- все параметры `/onu`
- `access` со значениями `ssh` или `telnet`

Для ZTE CLI внутри адаптера по-прежнему используется интерфейс вида `gpon-onu_1/<board>/<pon>:<onu>` после нормализации port-данных.

### `/cache/invalidate`

Удаляет ключи кеша для конкретного OLT/PON и, при наличии `onu_id`, также для одной ONU.

Примеры:

```bash
curl -X DELETE "http://127.0.0.1:8000/cache/invalidate?olt_ip=10.5.0.21&board_id=1&pon_id=1"
curl -X DELETE "http://127.0.0.1:8000/cache/invalidate?olt_ip=10.5.0.21&board_id=1&pon_id=1&onu_id=125"
```

### `/cache/clear`

Полностью очищает кеш по префиксу `REDIS_PREFIX`.

```bash
curl -X DELETE "http://127.0.0.1:8000/cache/clear"
```

## Vendor Resolution

Если `vendor` не передан явно, используется следующая цепочка:

1. `ZabbixInventory`
2. `SNMPPlatformInventory`
3. `DEFAULT_VENDOR`

### 1. ZabbixInventory

Если заданы `ZABBIX_URL` и `ZABBIX_TOKEN`, сервис:
- ищет хост по `olt_ip` через `hostinterface.get`;
- собирает уникальные `hostid`;
- если найден ровно один хост, читает `tags` и `inheritedTags`;
- ищет тег `vendor`;
- прогоняет значение через `VendorRegistry`.

### 2. SNMPPlatformInventory

Если Zabbix не дал результата:
- сервис опрашивает `.1.3.6.1.2.1.1.2.0`;
- получает `sysObjectID`;
- ищет его в `data/platforms.csv`;
- если строка найдена, сначала пробует определить vendor по `full_name`, затем по `vendor`;
- значения из CSV нормализуются в lower case.

### 3. DEFAULT_VENDOR

Если inventory ничего не нашел, используется `DEFAULT_VENDOR`.

## Debug Headers

Если передать `debug=true`, сервис вернет заголовки:
- `X-Vendor-Debug`
- `X-Resolved-Vendor`
- `X-Vendor-Source`

Пример:

```bash
curl -i "http://127.0.0.1:8000/onu?olt_ip=10.5.0.21&board_id=1&pon_id=1&onu_id=125&debug=true"
```

`X-Vendor-Debug` содержит JSON с деталями резолва, например:

```json
{"requested_vendor":null,"resolved_vendor":"zte","source":"zabbix","zabbix_enabled":true,"zabbix_host_count":1,"zabbix_vendor_tag":"zte","inventory_lookup_value":"zte","inventory_oid":null,"note":"vendor tag found in zabbix host tags"}
```

## CLI Polling

CLI реализован только внутри vendor adapter для ZTE.

Команды:
- `show pon onu information gpon-onu_1/<board>/<pon>:<onu>`
- `show pon power olt-rx gpon-onu_1/<board>/<pon>:<onu>`
- `show pon power onu-rx gpon-onu_1/<board>/<pon>:<onu>`
- `show gpon onu state gpon-olt_1/<board>/<pon> <onu>`
- `show gpon remote-onu interface eth gpon-onu_1/<board>/<pon>:<onu>`
- `show gpon remote-onu model gpon-onu_1/<board>/<pon>:<onu>`

Парсинг делается через TextFSM шаблоны в `app/vendors/zte/textfsm_templates/`.

## Cache

Если `REDIS_HOST` задан, сервис кеширует:
- `/onu`
- `/onup`
- `/onudebug`
- `/onus`
- `/onus-new`
- `/onucli`

Особенности:
- при недоступном Redis сервис не падает, просто работает без кеша;
- `nocache=true` отключает чтение из кеша, но после успешного запроса значение все равно перезаписывается в кеш;
- ключи включают vendor, а для `/onucli` еще и тип доступа;
- для `/onup` и `/onudebug` ключ включает `port`.

## Environment Variables

Обязательные:
- `SNMP_COMMUNITY`

Основные:
- `SNMP_PORT=161`
- `SNMP_TIMEOUT=2`
- `SNMP_RETRIES=1`
- `OLT_TIMEZONE=Asia/Jakarta`
- `DEFAULT_VENDOR=zte`

CLI:
- `CLI_USERNAME`
- `CLI_PASSWORD`
- `CLI_SECRET`
- `CLI_SSH_PORT=22`
- `CLI_TELNET_PORT=23`
- `CLI_TIMEOUT=10`

Redis:
- `REDIS_HOST`
- `REDIS_PORT=6379`
- `REDIS_PASSWORD`
- `REDIS_DB=0`
- `REDIS_PREFIX=zte-olt-fastapi`
- `CACHE_TTL_ONU=60`
- `CACHE_TTL_ONUS=300`
- `CACHE_TTL_ONUS_NEW=300`
- `CACHE_TTL_ONUCLI=60`

Zabbix:
- `ZABBIX_URL`
- `ZABBIX_TOKEN`
- `ZABBIX_TIMEOUT=5`

Debug:
- `DEBUG=0`

Полный пример есть в `.env.example`.

## Local Run

```bash
cd python_fastapi
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. uvicorn app.main:app --reload
```

Минимально нужен `SNMP_COMMUNITY`.

## Docker

```bash
cd python_fastapi
cp .env.example .env
docker compose up --build
```

В образ копируются:
- `app/`
- `data/`
- `requirements.txt`

### Доступ из контейнера к localhost хоста

В контейнере `localhost` указывает на сам контейнер, а не на хост-машину.

Для Docker Desktop обычно можно использовать:

```env
ZABBIX_URL=http://host.docker.internal/zabbix/api_jsonrpc.php
```

Если нужен Linux-хост, удобно добавить `extra_hosts` в compose:

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

## Project Structure

```text
python_fastapi/
  app/
    core/
      provider.py
      registry.py
      vendor_resolver.py
    inventory/
      chain.py
      provider.py
      snmp_platform.py
      zabbix.py
    services/
      onu_service.py
    vendors/zte/
      adapter.py
      cli_parser.py
      cli_transport.py
      oid.py
      textfsm_templates/
    cache.py
    config.py
    main.py
    models.py
    snmp_client.py
    transformers.py
  data/
    platforms.csv
  tests/
  Dockerfile
  docker-compose.yaml
  requirements.txt
```

## Architecture

### API Layer

`app/main.py`

Отвечает за:
- FastAPI routes;
- построение зависимостей;
- применение кеша;
- выдачу debug headers;
- конвертацию ошибок в HTTP status codes.

### Service Layer

`app/services/onu_service.py`

Отвечает за:
- работу через `VendorRegistry`;
- fallback на CLI при SNMP timeout в `/onu`.

### Vendor Layer

Сейчас реализован только `ZTEAdapter`.

Отвечает за:
- ZTE OID mapping;
- ZTE CLI transport;
- ZTE CLI parsing;
- преобразование сырых SNMP/CLI значений в API модели.

### Inventory Layer

Отвечает за auto-detect vendor.

Сейчас есть:
- `ZabbixInventory`
- `SNMPPlatformInventory`
- `InventoryChain`

### Core Layer

- `VendorProvider` задает контракт vendor adapter;
- `VendorRegistry` сопоставляет `vendor_tags` с адаптером;
- `VendorResolver` оркестрирует выбор vendor.

## Extending the Project

### Добавить нового vendor

1. Создать новый adapter по контракту `VendorProvider`.
2. Добавить `vendor_tags`.
3. Реализовать SNMP и, при необходимости, CLI transport/parser внутри vendor-модуля.
4. Подключить adapter в `main.py` через `VendorRegistry`.
5. При необходимости добавить новые записи в `platforms.csv`.

### Добавить новый inventory provider

1. Реализовать `lookup_vendor(olt_ip) -> InventoryLookupResult`.
2. Добавить provider в `InventoryChain` в нужном порядке.
3. Добавить тесты.

## Tests

```bash
cd python_fastapi
PYTHONPATH=. python3 -m unittest discover -s tests -v
python3 -m py_compile app/core/*.py app/services/*.py app/vendors/zte/*.py app/inventory/*.py app/*.py tests/*.py
```

Тестами покрыты:
- OID генерация;
- преобразование значений;
- сервисный слой;
- TextFSM parser;
- `VendorResolver`;
- `ZabbixInventory`;
- `SNMPPlatformInventory`;
- `InventoryChain`.

## Dependencies

- `fastapi`
- `uvicorn`
- `pysnmp`
- `netmiko`
- `textfsm`
- `redis`
- `zabbix-utils`

## Current Limitations

- Сейчас реализован только один vendor adapter: ZTE.
- `SNMPPlatformInventory` зависит от качества `data/platforms.csv`.
- `/onu` fallback на CLI включен только для timeout, а не для всех SNMP ошибок.
- Для CLI используются ZTE-specific команды и шаблоны.

## Notes

- `pon_id` обязателен, потому что и SNMP OID, и CLI interface naming зависят от пары `board_id + pon_id`.
- `onu` и `onucli` возвращают согласованную верхнеуровневую структуру, но `onucli` всегда содержит `cli_details`, а `onu` содержит их только при fallback.
- В debug-логах полезно различать количество интерфейсов Zabbix и количество уникальных `hostid`: для выбора vendor используется именно уникальный хост.
