"""SQLAlchemy adapter persisting scenario runs (audit of what the merchant was shown)."""

from sqlalchemy.orm import Session

from app.contexts.simulation.domain.scenario_lab import LabAssumptions, LabProjection
from app.contexts.simulation.domain.scenario_run import ScenarioRun
from app.db.models import ScenarioRunRow
from app.shared.domain.date_range import DateRange


class SqlScenarioRunRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def save(self, run: ScenarioRun) -> None:
        a = run.assumptions
        self._s.add(ScenarioRunRow(
            merchant_id=run.merchant_id,
            created_by=run.created_by,
            baseline_start=run.baseline_period.start,
            baseline_end=run.baseline_period.end,
            # Decimals stored as strings so the assumptions JSON round-trips exactly.
            assumptions={
                "volume_growth": str(a.volume_growth),
                "acceptance_change": str(a.acceptance_change),
                "ticket_change": str(a.ticket_change),
            },
            projected_count=run.projection.projected_count,
            projected_collection_centimes=run.projection.projected_collection.centimes,
        ))
        self._s.flush()

    def save_lab(self, merchant_id: str, created_by: int, period: DateRange, name: str,
                 assumptions: LabAssumptions, projection: LabProjection) -> None:
        a = assumptions
        self._s.add(ScenarioRunRow(
            merchant_id=merchant_id, created_by=created_by,
            baseline_start=period.start, baseline_end=period.end,
            assumptions={
                "kind": "scenario_lab", "name": name,
                "volume_growth": str(a.volume_growth), "acceptance_change": str(a.acceptance_change),
                "ticket_change": str(a.ticket_change),
                "shifts": [{"from": s.from_channel.value, "to": s.to_channel.value, "share": str(s.share)}
                           for s in a.shifts],
            },
            projected_count=projection.transactions,
            projected_collection_centimes=projection.collection.centimes,
        ))
        self._s.flush()

