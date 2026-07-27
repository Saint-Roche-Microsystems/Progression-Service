# progression-service

Servicio FastAPI autónomo dueño de **Statistics, Ranks, Achievements y Ranking** de Fijazo.
Migra la lógica de `domain/services/*` del monolito (cálculo de estadísticas, asignación de
rangos, desbloqueo de logros, cómputo de ranking) sobre su **propia base de datos**.

## Endpoints HTTP

| Método | Ruta                        | Descripción                                   |
| ------ | --------------------------- | --------------------------------------------- |
| GET    | `/statistics/{user_id}`     | Estadísticas de un usuario                    |
| GET    | `/ranks`                    | Catálogo de rangos                            |
| GET    | `/ranks/{user_id}`          | Rango actual + progreso al siguiente          |
| GET    | `/achievements`             | Catálogo de logros                            |
| GET    | `/achievements/{user_id}`   | Logros desbloqueados/pendientes de un usuario |
| GET    | `/ranking`                  | Ranking global paginado                       |
| GET    | `/ranking/top`              | Top de usuarios                               |
| GET    | `/ranking/{user_id}`        | Posición de un usuario                        |
| POST   | `/internal/recalculate/{user_id}` | Recálculo stats→ranks→logros→ranking    |
| GET    | `/health`                   | Healthcheck                                   |

El arranque **no** ejecuta ningún recálculo masivo (ver T-029): abre la conexión, asegura
los índices y levanta el consumer de RabbitMQ. La carga inicial se hace con
`scripts/backfill_progression.py`, que publica un evento histórico por usuario.

## Consumer de eventos (`progression.recalc`)

El recálculo normal **no se dispara por HTTP**: llega por RabbitMQ. bets-service publica
cada mutación de apuesta en el exchange `bets.events`, y el binding `bet.#` la deposita en
la cola `progression.recalc`, que este servicio consume desde su lifespan. El endpoint
`POST /internal/recalculate/{user_id}` queda como disparo manual/de emergencia.

La topología (exchange, cola, binding) la declara la infraestructura en
`rabbitmq/definitions.json`: el servicio la busca con `get_queue`, nunca la declara.

Política de confirmación, en `infrastructure/events/rabbitmq_consumer.py`:

| Situación | Qué hace | Por qué |
| --- | --- | --- |
| Mensaje ilegible o `event_type` desconocido | `ack` (se descarta) | Reintentarlo nunca funcionaría y, sin dead-letter queue, dejarlo pendiente bloquearía la cola |
| bets-service no responde (`BetSourceUnavailableError`) | `nack` con requeue + pausa | Fallo transitorio. Descartarlo dejaría la proyección obsoleta para siempre; la pausa evita que el requeue se vuelva un bucle cerrado |
| Cualquier otro error | `nack` sin requeue | Queda en Sentry y en el log; lo repara el siguiente evento del usuario o el backfill |

Con `RABBITMQ_URL` vacío el servicio arranca **sin** consumer: útil para desarrollo local
sin broker, pero entonces el recálculo vuelve a ser manual.

| Variable | Por defecto | Para qué |
| --- | --- | --- |
| `RABBITMQ_URL` | *(vacío)* | Sin valor, no se levanta el consumer |
| `PROGRESSION_RECALC_QUEUE` | `progression.recalc` | Cola que se consume |
| `RABBITMQ_PREFETCH_COUNT` | `1` | Mensajes en vuelo por consumer |
| `RABBITMQ_RETRY_COOLDOWN_SECONDS` | `5.0` | Pausa tras devolver un mensaje a la cola |

## De dónde salen las apuestas

Este servicio **no almacena apuestas**: son de bets-service, que es quien las escribe. Para
recalcular, se leen por su API interna con el secreto de servicio compartido:

| Llamada | Para qué |
| --- | --- |
| `GET /internal/bets?user_id=&page=&page_size=` | Historial completo de un usuario (se pagina hasta `total`) |
| `GET /internal/bets/user-ids` | Usuarios con al menos una apuesta, para el recálculo masivo |

El evento de RabbitMQ solo **avisa** de qué usuario cambió; el historial se relee aquí. Por
eso reprocesar un evento repetido o antiguo da el mismo resultado, y por eso el backfill
puede publicar eventos con un `bet_id` centinela.

**Fail-closed**, al contrario que el resto de dependencias del sistema: si bets-service no
responde, el recálculo devuelve `503` y **no** persiste nada. Tratar el fallo como "este
usuario no tiene apuestas" sobrescribiría sus estadísticas reales con ceros, y esta
proyección es la única copia.

> **Gap conocido**: el perfil del usuario (`username`, fecha de alta) se sigue leyendo de una
> colección `users` local que nadie escribe, así que hoy degrada en silencio a `username=""`
> y `account_age_days=0` — lo que sesga a la baja el `rank_score`. Necesita el mismo
> tratamiento contra users-service; queda fuera de este cambio.

## Puesta en marcha

```bash
cp .env.example .env      # INTERNAL_API_KEY es obligatorio; BETS_SERVICE_URL apunta a bets-service
poetry install
poetry run uvicorn progression_service.main:app --reload --port 8003
```

## Tests

```bash
poetry run pytest    # no requieren Mongo ni bets-service: el cliente HTTP se simula
```
