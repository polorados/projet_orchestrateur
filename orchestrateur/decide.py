"""decider.py : transforme des mesures en actions (changement de local-pref).

Entrée  : liste de Measurement (produite par measure.py, au format JSON)
Sortie  : liste d'Action (consommée par configure.py)
"""
from dataclasses import dataclass, asdict
from typing import Optional
import json


@dataclass
class Measurement:
    site: str
    link: str
    latency_ms: Optional[float]   # None si tous les pings sont perdus
    loss_pct: float
    bgp_state: str                # "Established", "Active", ...


@dataclass
class Action:
    site: str
    link: str
    set_local_pref: int
    reason: str


class Decider:
    def __init__(self,
                 base_pref=None,          # local-pref "normale" de chaque lien
                 penalty=100,             # retirée à un lien dégradé
                 max_latency_ms=100,
                 max_loss_pct=5,
                 bad_needed=3,            # mesures mauvaises avant de basculer
                 good_needed=5):          # mesures bonnes avant de revenir
        # wan1 = lien principal, wan2 = secours.
        # Avec une pénalité de 100, l'ordre reste cohérent même si les 2 liens
        # sont dégradés : wan1 (200-100=100) reste préféré à wan2 (150-100=50).
        self.base_pref = base_pref or {"wan1": 200, "wan2": 150}
        self.penalty = penalty
        self.max_latency_ms = max_latency_ms
        self.max_loss_pct = max_loss_pct
        self.bad_needed = bad_needed
        self.good_needed = good_needed

        # État conservé entre deux itérations, clé = (site, link)
        self.bad_streak = {}    # nb de mauvaises mesures consécutives
        self.good_streak = {}   # nb de bonnes mesures consécutives
        self.degraded = {}      # le lien est-il actuellement considéré dégradé ?
        self.applied = {}       # dernière local-pref réellement envoyée

    # -- évaluation d'une mesure ------------------------------------------
    def _problem(self, m: Measurement) -> Optional[str]:
        """Retourne la raison du problème, ou None si la mesure est bonne."""
        if m.bgp_state != "Established":
            return f"session BGP {m.bgp_state}"
        if m.latency_ms is None or m.loss_pct >= 100:
            return "lien injoignable (ping)"
        if m.loss_pct > self.max_loss_pct:
            return f"perte {m.loss_pct}% > {self.max_loss_pct}%"
        if m.latency_ms > self.max_latency_ms:
            return f"latence {m.latency_ms}ms > {self.max_latency_ms}ms"
        return None

    # -- décision ---------------------------------------------------------
    def decide(self, measurements: list) -> list:
        actions = []
        for m in measurements:
            key = (m.site, m.link)
            problem = self._problem(m)

            # 1. Mise à jour des compteurs (hystérésis)
            if problem:
                self.bad_streak[key] = self.bad_streak.get(key, 0) + 1
                self.good_streak[key] = 0
            else:
                self.good_streak[key] = self.good_streak.get(key, 0) + 1
                self.bad_streak[key] = 0

            # 2. Changement d'état seulement après plusieurs mesures concordantes
            was_degraded = self.degraded.get(key, False)
            if not was_degraded and self.bad_streak[key] >= self.bad_needed:
                self.degraded[key] = True
                reason = problem
            elif was_degraded and self.good_streak[key] >= self.good_needed:
                self.degraded[key] = False
                reason = f"lien stable depuis {self.good_needed} mesures"
            else:
                reason = "état maintenu"

            # 3. Valeur de local-pref souhaitée
            base = self.base_pref.get(m.link, 100)
            desired = base - self.penalty if self.degraded.get(key) else base

            # 4. On n'émet une action que si la valeur change
            if self.applied.get(key) != desired:
                if key not in self.applied:
                    reason = "configuration initiale"
                actions.append(Action(m.site, m.link, desired, reason))
                self.applied[key] = desired

        return actions


# -- Test rapide sans lancer la topologie ------------------------------------
if __name__ == "__main__":
    d = Decider()

    def cycle(lat_wan1):
        return [
            Measurement("paris", "wan1", lat_wan1, 0, "Established"),
            Measurement("paris", "wan2", 20.0, 0, "Established"),
        ]

    scenario = [10, 10, 200, 200, 200, 200, 10, 10, 10, 10, 10, 10]
    for i, lat in enumerate(scenario):
        acts = d.decide(cycle(lat))
        print(i, lat, json.dumps([asdict(a) for a in acts]))