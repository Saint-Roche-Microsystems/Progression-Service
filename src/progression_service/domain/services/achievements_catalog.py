"""Catálogo de logros (configuración + condiciones de desbloqueo documentadas).

Fuente única de verdad de los logros. **Para añadir un logro nuevo basta con
registrar otro `AchievementDefinition` en `CATALOG`**: el evaluador
(`achievement_evaluator`) recorre esta lista sin necesitar cambios.

Cada condición es un predicado ``(stats, now) -> bool`` sobre las estadísticas ya
calculadas del usuario, por lo que no se duplica ninguna lógica de cálculo.
"""

from datetime import datetime, timedelta

from progression_service.domain.entities.achievement import (
    AchievementCategory,
    AchievementDefinition,
)
from progression_service.domain.entities.statistics import UserStatistics

# --- Parámetros ajustables -------------------------------------------------

#: Mínimo de apuestas decididas exigido a los logros de precisión (evita sesgos).
PRECISION_MIN_DECIDED = {60: 10, 70: 15, 80: 20}
#: Ganancia acumulada (beneficio neto) del logro de rentabilidad alta.
ACCUMULATED_PROFIT_TARGET = 500.0
#: Ventana (días) para considerar "actividad mensual" vigente.
MONTHLY_ACTIVITY_DAYS = 30


def _decided(stats: UserStatistics) -> int:
    return stats.won + stats.lost


def _win_rate_ok(threshold: int):
    """Win rate >= umbral con un mínimo de apuestas decididas."""

    min_decided = PRECISION_MIN_DECIDED[threshold]

    def condition(stats: UserStatistics, now: datetime) -> bool:
        return _decided(stats) >= min_decided and stats.win_rate >= threshold

    return condition


def _monthly_active(stats: UserStatistics, now: datetime) -> bool:
    if stats.last_activity_at is None:
        return False
    return now - stats.last_activity_at <= timedelta(days=MONTHLY_ACTIVITY_DAYS)


def _def(
    id_: str,
    name: str,
    description: str,
    category: AchievementCategory,
    icon: str,
    condition,
) -> AchievementDefinition:
    return AchievementDefinition(id_, name, description, category, icon, condition)


C = AchievementCategory

#: Catálogo completo de logros.
CATALOG: tuple[AchievementDefinition, ...] = (
    # --- Rachas: best_streak = mayor racha de victorias consecutivas ---
    _def(
        "streak_3",
        "En racha",
        "Gana 3 apuestas consecutivas.",
        C.STREAKS,
        "🔥",
        lambda s, n: s.best_streak >= 3,
    ),
    _def(
        "streak_5",
        "Imparable",
        "Gana 5 apuestas consecutivas.",
        C.STREAKS,
        "🔥",
        lambda s, n: s.best_streak >= 5,
    ),
    _def(
        "streak_10",
        "Racha legendaria",
        "Gana 10 apuestas consecutivas.",
        C.STREAKS,
        "⚡",
        lambda s, n: s.best_streak >= 10,
    ),
    _def(
        "streak_20",
        "Invencible",
        "Gana 20 apuestas consecutivas.",
        C.STREAKS,
        "🌟",
        lambda s, n: s.best_streak >= 20,
    ),
    # --- Experiencia: total de apuestas registradas ---
    _def(
        "exp_first",
        "Primera apuesta",
        "Registra tu primera apuesta.",
        C.EXPERIENCE,
        "🎫",
        lambda s, n: s.total_bets >= 1,
    ),
    _def(
        "exp_10",
        "Aprendiz",
        "Registra 10 apuestas.",
        C.EXPERIENCE,
        "📒",
        lambda s, n: s.total_bets >= 10,
    ),
    _def(
        "exp_50",
        "Habitual",
        "Registra 50 apuestas.",
        C.EXPERIENCE,
        "📚",
        lambda s, n: s.total_bets >= 50,
    ),
    _def(
        "exp_100",
        "Veterano",
        "Registra 100 apuestas.",
        C.EXPERIENCE,
        "🎖️",
        lambda s, n: s.total_bets >= 100,
    ),
    _def(
        "exp_500",
        "Centurión",
        "Registra 500 apuestas.",
        C.EXPERIENCE,
        "🏛️",
        lambda s, n: s.total_bets >= 500,
    ),
    # --- Rentabilidad ---
    _def(
        "profit_first",
        "Primer beneficio",
        "Obtén tu primer beneficio neto.",
        C.PROFITABILITY,
        "💰",
        lambda s, n: s.net_profit > 0,
    ),
    _def(
        "roi_positive",
        "En verde",
        "Alcanza un ROI positivo.",
        C.PROFITABILITY,
        "📗",
        lambda s, n: s.roi > 0,
    ),
    _def(
        "roi_20",
        "Rentable",
        "Alcanza un ROI superior al 20%.",
        C.PROFITABILITY,
        "💎",
        lambda s, n: s.roi > 20,
    ),
    _def(
        "profit_target",
        "Gran ganador",
        f"Acumula un beneficio neto de {ACCUMULATED_PROFIT_TARGET:.0f}.",
        C.PROFITABILITY,
        "🤑",
        lambda s, n: s.net_profit >= ACCUMULATED_PROFIT_TARGET,
    ),
    # --- Precisión (con mínimo de apuestas) ---
    _def("winrate_60", "Certero", "Win Rate superior al 60%.", C.PRECISION, "🎯", _win_rate_ok(60)),
    _def("winrate_70", "Preciso", "Win Rate superior al 70%.", C.PRECISION, "🏹", _win_rate_ok(70)),
    _def(
        "winrate_80",
        "Francotirador",
        "Win Rate superior al 80%.",
        C.PRECISION,
        "🥇",
        _win_rate_ok(80),
    ),
    # --- Actividad ---
    _def(
        "activity_7",
        "Constante",
        "Apuesta 7 días consecutivos.",
        C.ACTIVITY,
        "📅",
        lambda s, n: s.max_consecutive_days >= 7,
    ),
    _def(
        "activity_30",
        "Disciplinado",
        "Apuesta 30 días consecutivos.",
        C.ACTIVITY,
        "🗓️",
        lambda s, n: s.max_consecutive_days >= 30,
    ),
    _def(
        "activity_monthly",
        "Activo",
        "Mantén actividad en el último mes.",
        C.ACTIVITY,
        "🔄",
        _monthly_active,
    ),
    # --- Casas de apuestas ---
    _def(
        "bookmakers_3",
        "Explorador",
        "Apuesta en 3 casas distintas.",
        C.BOOKMAKERS,
        "🏦",
        lambda s, n: s.distinct_bookmakers >= 3,
    ),
    _def(
        "bookmakers_5",
        "Trotamundos",
        "Apuesta en 5 casas distintas.",
        C.BOOKMAKERS,
        "🌐",
        lambda s, n: s.distinct_bookmakers >= 5,
    ),
    # --- Deportes ---
    _def(
        "sports_3",
        "Polivalente",
        "Apuesta en 3 deportes distintos.",
        C.SPORTS,
        "🎽",
        lambda s, n: s.distinct_sports >= 3,
    ),
    _def(
        "sports_5",
        "Todoterreno",
        "Apuesta en 5 deportes distintos.",
        C.SPORTS,
        "🏅",
        lambda s, n: s.distinct_sports >= 5,
    ),
)

#: Índice id -> definición, para búsquedas rápidas.
CATALOG_BY_ID = {a.id: a for a in CATALOG}
