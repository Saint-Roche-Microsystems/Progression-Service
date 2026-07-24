"""Configuración de rangos (datos, no lógica).

Los rangos son fácilmente modificables: basta editar esta lista. Los umbrales se
expresan sobre la puntuación de rango 0..100 (ver ``rank_scorer``).
"""

from progression_service.domain.entities.rank import RankDefinition

#: Rangos ordenados por nivel ascendente. ``min_score`` es el umbral de entrada.
RANKS: tuple[RankDefinition, ...] = (
    RankDefinition(1, "Novato", "🐣", 0.0),
    RankDefinition(2, "Principiante", "🌱", 10.0),
    RankDefinition(3, "Amateur", "🎯", 20.0),
    RankDefinition(4, "Experimentado", "📈", 30.0),
    RankDefinition(5, "Profesional", "💼", 42.0),
    RankDefinition(6, "Experto", "🧠", 55.0),
    RankDefinition(7, "Maestro", "🏆", 68.0),
    RankDefinition(8, "Elite", "👑", 80.0),
    RankDefinition(9, "Leyenda", "🔥", 92.0),
)
