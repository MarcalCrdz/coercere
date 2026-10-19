"""Diário do jogador.

Guarda apenas OBSERVAÇÕES (fatos que o personagem viu), nunca conclusões.
Persiste entre mortes: o personagem morre, o conhecimento do jogador fica.
As entradas são definidas em content/diary_rules.json.
"""
import json
import os


def _matches(match, event):
    return all(event.get(k) == v for k, v in match.items())


class Diary:
    def __init__(self, path, rules):
        self.path = path
        self.rules = rules
        self.entries = []   # [{"id":..., "text":...}] na ordem de descoberta
        self._load()

    def _load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                self.entries = json.load(f)
        except (OSError, ValueError):
            self.entries = []

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.entries, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def _has(self, entry_id):
        return any(e["id"] == entry_id for e in self.entries)

    def record(self, events):
        changed = False
        for ev in events:
            for rule in self.rules:
                if not self._has(rule["id"]) and _matches(rule["match"], ev):
                    self.entries.append({"id": rule["id"], "text": rule["text"]})
                    changed = True
        if changed:
            self._save()

    def lines(self):
        if not self.entries:
            return ["As páginas estão em branco."]
        return ["· " + e["text"] for e in self.entries]

    def reset(self):
        self.entries = []
        self._save()
