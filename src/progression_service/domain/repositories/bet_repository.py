"""Puerto de lectura de las apuestas.

Las apuestas **no** son de este servicio: las posee bets-service, que es quien las escribe
y quien las expone por su API interna. Aquí solo se leen para proyectar estadísticas, rangos,
logros y ranking, así que el puerto no tiene ``create``/``update``/``delete``: no habría
implementación honesta para ellos.
"""

from abc import ABC, abstractmethod

from progression_service.domain.entities.bet import Bet


class BetRepository(ABC):
    """Contrato de lectura de las apuestas de un usuario."""

    @abstractmethod
    async def list_all_by_user(self, user_id: str) -> list[Bet]:
        """Todas las apuestas del usuario, sin paginar.

        El recálculo es siempre sobre el historial completo (no aplica deltas), así que
        quien implemente esto es responsable de recorrer las páginas que haga falta.

        Debe señalar los fallos de transporte con
        :class:`~progression_service.core.exceptions.BetSourceUnavailableError`: devolver
        una lista vacía haría que el recálculo persistiera estadísticas en cero.
        """

    @abstractmethod
    async def distinct_user_ids(self) -> list[str]:
        """``user_id`` distintos con al menos una apuesta.

        Se usa para el recálculo masivo y la carga inicial manual (T-029).
        """
