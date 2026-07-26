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

## De dónde salen las apuestas

Este servicio **no almacena apuestas**: son de bets-service, que es quien las escribe. Para
recalcular, se leen por su API interna con el secreto de servicio compartido:

| Llamada | Para qué |
| --- | --- |
| `GET /internal/bets?user_id=&page=&page_size=` | Historial completo de un usuario (se pagina hasta `total`) |
| `GET /internal/bets/user-ids` | Usuarios con al menos una apuesta, para el recálculo masivo |

El evento `bet.created` de RabbitMQ solo **avisa** de qué usuario cambió; el historial se
relee aquí. Por eso reprocesar un evento repetido o antiguo da el mismo resultado.

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
