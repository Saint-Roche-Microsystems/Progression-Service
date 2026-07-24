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

El arranque **no** ejecuta ningún recálculo masivo (ver T-029): sólo abre la conexión y
asegura los índices. La carga inicial se hace vía el flujo de eventos / script manual.

## Puesta en marcha

```bash
cp .env.example .env
poetry install
poetry run uvicorn progression_service.main:app --reload --port 8002
```

## Tests

```bash
poetry run pytest    # usa mongomock-style vía una Mongo real de test
```
