"""Transforma EVENTOS do motor em texto. O jogador nunca vê números."""


class Narrator:
    def __init__(self, narration):
        self.n = narration
        self._hp_bracket = 0
        self._vigor_bracket = 0

    # -------------------------------------------------------------- utilitários
    @staticmethod
    def _pick(value, turn, index=0):
        if isinstance(value, list):
            return value[(turn + index) % len(value)]
        return value

    def _entry(self, action_id, actor_id):
        entry = self.n.get("actions", {}).get(action_id, {})
        return entry.get(actor_id) or entry.get("default") or {}

    def _severity(self, amount):
        sev = self.n.get("severity", {"light_max": 3, "medium_max": 6})
        if amount <= sev["light_max"]:
            return "light"
        if amount <= sev["medium_max"]:
            return "medium"
        return "heavy"

    @staticmethod
    def _bracket(frac, thresholds):
        return sum(1 for th in thresholds if frac < th["below"])

    # ------------------------------------------------------------------- partes
    def intro(self):
        return list(self.n.get("intro", []))

    def menu(self, action_ids):
        menu = self.n["menu"]
        return ["  %d. %s" % (i, menu[aid]["label"]) for i, aid in enumerate(action_ids, 1)]

    def render(self, events, battle):
        lines = []
        for ev in events:
            kind = ev["kind"]
            t = ev["turn"]
            if kind == "declare":
                entry = self._entry(ev["action"], ev["actor"])
                if entry.get("declare"):
                    lines.append(entry["declare"])
                if entry.get("say"):
                    lines.append(entry["say"])
            elif kind == "observe_line":
                lines.append(ev["text"])
            elif kind == "rule":
                text = self.n.get("rules", {}).get(ev["rule"], {}).get(ev["actor"])
                if text:
                    lines.append(text)
            elif kind == "hit":
                entry = self._entry(ev["action"], ev["actor"])
                if ev["target_dodging"] and entry.get("hit_dodging"):
                    lines.append(self._pick(entry["hit_dodging"], t, ev["index"]))
                else:
                    texts = entry.get("hit", {}).get(self._severity(ev["amount"]))
                    if texts:
                        lines.append(self._pick(texts, t, ev["index"]))
            elif kind == "dodged":
                entry = self._entry(ev["action"], ev["actor"])
                if ev["count"] > 1 and entry.get("dodged_multi"):
                    lines.append(entry["dodged_multi"])
                elif entry.get("dodged"):
                    lines.append(entry["dodged"])
            elif kind == "fail":
                entry = self._entry(ev["action"], ev["actor"])
                if entry.get("fail"):
                    lines.append(entry["fail"])
            elif kind == "death":
                text = self.n.get("death", {}).get(ev["actor"])
                if text:
                    lines.append(self._pick(text, t))

        if battle.player.hp > 0:
            lines.extend(self._body_lines(battle))
        return lines

    def _body_lines(self, battle):
        """Sensações do corpo do jogador; só aparecem quando pioram."""
        out = []
        body = self.n.get("body", {})
        hp_th = body.get("hp", [])
        new_hp = self._bracket(battle.player.hp_frac, hp_th)
        if new_hp > self._hp_bracket:
            out.append(hp_th[new_hp - 1]["text"])
        self._hp_bracket = new_hp

        vg_th = body.get("vigor", [])
        new_vg = self._bracket(battle.player.vigor_frac, vg_th)
        if new_vg > self._vigor_bracket:
            out.append(vg_th[new_vg - 1]["text"])
        self._vigor_bracket = new_vg
        return out
