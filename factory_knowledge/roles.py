"""Specialist definitions: the heart of the kit's extensibility.

A *role* is one specialist assistant on the factory floor (Maintenance, Safety,
Quality, ...). Each role is pure configuration:

    - which folder of documents it answers from,
    - how it should behave (its system prompt / guardrails),
    - keywords that hint when a question belongs to it.

Roles live in ``roles.yaml`` at the project root. To add a new specialist
(e.g. "Electrical" or "Robotics"):
    1. create ``data/<your_role>/`` and drop manuals / SOPs / logs in it,
    2. add a matching entry to ``roles.yaml``.
No Python changes required — that is the whole point.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .config import DATA_DIR, ROLES_FILE


@dataclass
class RoleConfig:
    """Everything needed to construct one specialist assistant."""

    key: str  # short id, e.g. "maintenance"
    name: str  # display name, e.g. "Maintenance & Troubleshooting Assistant"
    description: str  # one-liner shown in menus and used by the router
    system_prompt: str  # persona / instructions / guardrails for the LLM
    keywords: list[str] = field(default_factory=list)  # routing hints
    data_subdir: str = ""  # folder under data/, defaults to ``key``

    @property
    def data_dir(self) -> Path:
        return DATA_DIR / (self.data_subdir or self.key)


# Shared guardrail appended to every specialist so behaviour is consistent and
# "hallucination-free": answer only from the official docs, cite, or abstain.
_GROUNDING_RULES = (
    " Answer ONLY using the provided official documentation. Cite the source for "
    "each fact using its [number]. If the documentation does not contain the "
    "answer, say clearly that it is not in the official documentation and tell the "
    "technician who to escalate to — never guess part numbers, torque values, "
    "settings, or procedures."
)

# Built-in defaults so the kit boots even before ``roles.yaml`` is read or if
# PyYAML is unavailable. ``roles.yaml`` (when present) takes precedence.
_DEFAULT_ROLES = [
    RoleConfig(
        key="maintenance",
        name="Maintenance & Troubleshooting Assistant",
        description=(
            "Equipment manuals, error/alarm codes, repair and troubleshooting "
            "procedures, maintenance logs, and preventive maintenance."
        ),
        system_prompt=(
            "You are the Maintenance & Troubleshooting Assistant for the factory "
            "floor. Give technicians precise, step-by-step troubleshooting and "
            "repair guidance from the equipment manuals, error-code references, "
            "and maintenance logs. If a step involves moving parts or stored "
            "energy, remind the technician to follow lockout/tagout first."
            + _GROUNDING_RULES
        ),
        keywords=[
            "maintenance", "repair", "troubleshoot", "troubleshooting", "error",
            "code", "fault", "alarm", "motor", "bearing", "conveyor", "cnc",
            "spindle", "hydraulic", "pump", "breakdown", "vibration", "noise",
            "lubrication", "grease", "downtime", "manual", "log", "replace",
            "overheat", "belt", "coolant", "e204", "e110",
        ],
    ),
    RoleConfig(
        key="safety",
        name="Safety & Compliance Officer",
        description=(
            "Safety SOPs, lockout/tagout, PPE, chemical/hazard handling, and "
            "emergency and incident procedures."
        ),
        system_prompt=(
            "You are the Safety & Compliance Officer. Be exact and conservative: "
            "quote required PPE, lockout/tagout steps, exposure limits, and "
            "emergency actions precisely. When in doubt, prioritize human safety "
            "over production and tell the worker to stop and contact the safety "
            "officer." + _GROUNDING_RULES
        ),
        keywords=[
            "safety", "hazard", "ppe", "lockout", "tagout", "loto", "chemical",
            "msds", "sds", "spill", "fire", "emergency", "evacuation", "injury",
            "incident", "osha", "guard", "ventilation", "confined", "fall",
            "ergonomic", "goggles", "respirator", "first", "aid",
        ],
    ),
    RoleConfig(
        key="quality",
        name="Quality & Operations Assistant",
        description=(
            "Quality control SOPs, inspection criteria, tolerances, calibration, "
            "machine setup and changeover, and nonconformance handling."
        ),
        system_prompt=(
            "You are the Quality & Operations Assistant. Be precise about "
            "tolerances, sample sizes, and acceptance criteria, and quote them "
            "exactly from the specifications and SOPs. If a specification is not "
            "in the documentation, tell the operator to check with the quality "
            "engineer rather than assuming a value." + _GROUNDING_RULES
        ),
        keywords=[
            "quality", "inspection", "inspect", "tolerance", "spec",
            "specification", "calibration", "calibrate", "gauge", "measure",
            "defect", "nonconformance", "ncr", "changeover", "setup", "sampling",
            "control", "chart", "scrap", "rework", "sop", "process", "aql",
        ],
    ),
]


def load_roles() -> list[RoleConfig]:
    """Load roles from ``roles.yaml`` if possible, else the built-in defaults."""
    if not ROLES_FILE.exists():
        return _DEFAULT_ROLES

    try:
        import yaml  # PyYAML
    except ImportError:
        return _DEFAULT_ROLES

    raw = yaml.safe_load(ROLES_FILE.read_text(encoding="utf-8")) or {}
    entries = raw.get("roles", [])
    if not entries:
        return _DEFAULT_ROLES

    roles: list[RoleConfig] = []
    for e in entries:
        roles.append(
            RoleConfig(
                key=e["key"],
                name=e.get("name", e["key"].title()),
                description=e.get("description", ""),
                system_prompt=e.get("system_prompt", ""),
                keywords=[k.lower() for k in e.get("keywords", [])],
                data_subdir=e.get("data_subdir", ""),
            )
        )
    return roles
