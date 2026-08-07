"""The front door: build the team, route questions, return grounded answers.

This is the object you interact with from the CLI, the Streamlit app, or your
own code::

    from factory_knowledge import FactoryKnowledge
    fk = FactoryKnowledge()
    print(fk.ask("What does alarm code E-204 mean on the CNC mill?").text)
"""

from __future__ import annotations

from .agent import Answer, RoleAgent
from .config import Settings, settings
from .roles import RoleConfig, load_roles
from .router import route


class FactoryKnowledge:
    """Owns the roster of specialist assistants and dispatches questions to them."""

    def __init__(self, cfg: Settings | None = None) -> None:
        self.cfg = cfg or settings
        self.roles: list[RoleConfig] = load_roles()
        self.agents: dict[str, RoleAgent] = {
            r.key: RoleAgent(r, self.cfg) for r in self.roles
        }
        self._ready = False

    # -- setup --------------------------------------------------------------
    def warmup(self) -> dict[str, int]:
        """Index every assistant up front. Returns ``{role_key: chunk_count}``.

        Call this once at startup so the first question isn't slow. Optional —
        agents lazily index themselves on first use otherwise.
        """
        counts = {key: agent.index() for key, agent in self.agents.items()}
        self._ready = True
        return counts

    # -- querying -----------------------------------------------------------
    def pick_role(self, question: str) -> RoleConfig:
        """Expose routing on its own so UIs can show *who* will answer."""
        return route(question, self.roles, self.cfg)

    def ask(self, question: str, role_key: str | None = None) -> Answer:
        """Answer a question, auto-routing unless ``role_key`` is given.

        Pass ``role_key`` to force a specific specialist (e.g. when the user
        picked one from a menu).
        """
        if role_key:
            agent = self.agents.get(role_key)
            if agent is None:
                raise KeyError(f"Unknown role: {role_key}. Known: {list(self.agents)}")
        else:
            role = self.pick_role(question)
            agent = self.agents[role.key]
        return agent.answer(question)

    # -- introspection ------------------------------------------------------
    def describe_team(self) -> str:
        """Human-readable roster, handy for help text and onboarding."""
        lines = ["Your factory-floor assistants:"]
        for r in self.roles:
            lines.append(f"  • {r.name} ({r.key}) — {r.description}")
        return "\n".join(lines)
