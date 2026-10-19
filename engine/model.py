"""Modelo de batalha por turnos, determinístico (mesma seed + mesmas escolhas = mesma luta).

Cada turno:
  1. o bot decide usando só informação pública (veja bot.py);
  2. os dois pagam custos e declaram ações ao mesmo tempo;
  3. as regras do mundo (rules.json) são aplicadas aos ataques;
  4. o dano é aplicado simultaneamente.
O motor produz EVENTOS estruturados; quem transforma eventos em texto é o narrator.
"""
import random

from . import bot


class Actor:
    def __init__(self, actor_id, name, hp, vigor, regen, actions):
        self.id = actor_id
        self.name = name
        self.max_hp = hp
        self.hp = hp
        self.max_vigor = vigor
        self.vigor = vigor
        self.regen = regen
        self.actions = list(actions)
        self.states = {}          # nome do estado -> último turno em que ainda vale
        self.last_action = None   # última ação (pública) deste ator
        self.uses = {}            # id da ação -> quantas vezes usou

    def has_state(self, name, turn):
        return self.states.get(name, -1) >= turn

    def purge_states(self, turn):
        self.states = {k: v for k, v in self.states.items() if v >= turn}

    @property
    def hp_frac(self):
        return max(self.hp, 0) / float(self.max_hp)

    @property
    def vigor_frac(self):
        return (self.vigor / float(self.max_vigor)) if self.max_vigor else 0.0


class Battle:
    def __init__(self, content, seed=None):
        self.content = content
        self.actions = content["actions"]
        self.rules = content["rules"]
        self.encounter = content["encounter"]
        self.seed = seed if seed is not None else random.randrange(1, 10 ** 9)
        self.rng = random.Random(self.seed)
        p = content["player"]
        e = self.encounter
        self.player = Actor("player", "você", p["hp"], p["vigor"], p.get("regen", 0), p["actions"])
        self.enemy = Actor(e["id"], e["name"], e["hp"], e.get("vigor", 0), e.get("regen", 0), e["actions"])
        self.turn = 0
        self.over = False
        self.result = None  # "victory" ou "defeat"
        self.history = []   # lista de (ação do jogador, ação do inimigo)

    # ------------------------------------------------------------------ turno
    def step(self, player_action):
        if self.over:
            raise RuntimeError("A luta já terminou.")
        if player_action not in self.player.actions:
            raise ValueError("Ação inválida para o jogador: %s" % player_action)

        self.turn += 1
        t = self.turn
        for actor in (self.player, self.enemy):
            actor.purge_states(t)

        # 1) bot decide com informação pública
        enemy_action = bot.decide(self.encounter["behavior"], self.actions,
                                  self.enemy, self.player, t, self.rng)

        # observação lê o estado ANTES do turno acontecer (nada de vazar o futuro)
        observed = self._observe() if self.actions[player_action].get("observe") else []

        plans = [
            {"actor": self.player, "target": self.enemy, "action": self.actions[player_action], "ok": True},
            {"actor": self.enemy, "target": self.player, "action": self.actions[enemy_action], "ok": True},
        ]
        groups = {self.player.id: [], self.enemy.id: []}

        # 2) custos e declaração (simultâneo)
        for plan in plans:
            self._prepare(plan, groups[plan["actor"].id], t)
        groups[self.player.id].extend(observed)

        # 3) regras do mundo e ataques
        pending = []
        for plan in plans:
            if plan["ok"]:
                self._resolve_attack(plan, groups[plan["actor"].id], pending, t)

        # 4) dano simultâneo
        for target, amount in pending:
            target.hp -= amount

        final = []
        if self.player.hp <= 0:
            final.append({"kind": "death", "actor": self.player.id, "turn": t})
        if self.enemy.hp <= 0:
            final.append({"kind": "death", "actor": self.enemy.id, "turn": t})
        if self.player.hp <= 0:
            self.over, self.result = True, "defeat"      # se os dois caem, você perde
        elif self.enemy.hp <= 0:
            self.over, self.result = True, "victory"

        # fim do turno
        for plan in plans:
            actor = plan["actor"]
            actor.last_action = plan["action"]["id"] if plan["ok"] else "failed"
            if actor.hp > 0 and actor.regen:
                actor.vigor = min(actor.max_vigor, actor.vigor + actor.regen)
        self.history.append((player_action, enemy_action))

        return groups[self.player.id] + groups[self.enemy.id] + final

    # --------------------------------------------------------------- internos
    def _prepare(self, plan, group, t):
        actor, action = plan["actor"], plan["action"]
        aid = action["id"]
        if actor.vigor < action["vigor_cost"]:
            plan["ok"] = False
            group.append({"kind": "fail", "actor": actor.id, "action": aid, "reason": "vigor", "turn": t})
            return
        actor.vigor -= action["vigor_cost"]
        actor.hp -= action["hp_cost"]
        actor.uses[aid] = actor.uses.get(aid, 0) + 1
        for st in action.get("sets_states", []):
            actor.states[st["name"]] = t + st["duration"]
        group.append({"kind": "declare", "actor": actor.id, "action": aid, "turn": t})

    def _rule_applies(self, rule, action, actor, t):
        when = rule.get("when", {})
        if "source" in when and action["source"] != when["source"]:
            return False
        if "tag" in when and when["tag"] not in action["tags"]:
            return False
        if "actor_state" in when and not actor.has_state(when["actor_state"], t):
            return False
        return True

    def _resolve_attack(self, plan, group, pending, t):
        action, actor, target = plan["action"], plan["actor"], plan["target"]
        if "damage" not in action:
            return
        hits, dmg = action["hits"], action["damage"]

        applicable = [r for r in self.rules if self._rule_applies(r, action, actor, t)]
        for rule in applicable:
            eff = rule.get("effect", {})
            hits *= eff.get("hits_multiplier", 1)
            dmg *= eff.get("damage_multiplier", 1)
            if rule.get("consume_state"):
                actor.states.pop(rule["consume_state"], None)
            group.append({"kind": "rule", "rule": rule["id"], "actor": actor.id, "turn": t})

        dodging = target.has_state("dodging", t)
        if "projectile" in action["tags"] and dodging:
            group.append({"kind": "dodged", "actor": actor.id, "action": action["id"],
                          "count": hits, "turn": t})
            return
        for i in range(hits):
            group.append({"kind": "hit", "actor": actor.id, "target": target.id,
                          "action": action["id"], "index": i, "of": hits, "amount": dmg,
                          "target_dodging": dodging, "turn": t})
            pending.append((target, dmg))

    def _observe_when(self, when):
        e, t = self.enemy, self.turn
        if "state" in when and not e.has_state(when["state"], t):
            return False
        if "hp_frac_below" in when and not e.hp_frac < when["hp_frac_below"]:
            return False
        return True

    def _observe(self):
        events = []
        for line in self.encounter.get("observe", []):
            if self._observe_when(line.get("when", {})):
                events.append({"kind": "observe_line", "actor": "player", "line_id": line["id"],
                               "text": line["text"], "turn": self.turn})
        return events

    # ------------------------------------------------------------------ debug
    def debug_snapshot(self):
        def fmt(a):
            return "hp=%d/%d vigor=%d/%d estados=%s" % (a.hp, a.max_hp, a.vigor, a.max_vigor, dict(a.states))
        last = self.history[-1] if self.history else (None, None)
        return "[debug] turno %d | jogador %s | %s %s | ações do turno: jogador=%s, inimigo=%s | seed=%s" % (
            self.turn, fmt(self.player), self.enemy.id, fmt(self.enemy), last[0], last[1], self.seed)
