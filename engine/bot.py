"""Decisão do bot.

REGRA DE HONESTIDADE: o bot só enxerga o que é público (a última ação do
jogador, o estado do próprio corpo, a vida de cada um). Ele NUNCA vê a ação
que o jogador escolheu neste turno e usa exatamente as mesmas regras.
"""


def condition_met(when, me, opp, turn):
    if "self_state" in when and not me.has_state(when["self_state"], turn):
        return False
    if "opponent_last" in when and opp.last_action != when["opponent_last"]:
        return False
    for aid, n in when.get("self_uses_below", {}).items():
        if me.uses.get(aid, 0) >= n:
            return False
    if "self_hp_frac_below" in when and not me.hp_frac < when["self_hp_frac_below"]:
        return False
    if "opponent_hp_frac_below" in when and not opp.hp_frac < when["opponent_hp_frac_below"]:
        return False
    return True


def affordable(action, actor):
    return actor.vigor >= action.get("vigor_cost", 0)


def decide(behavior, actions, me, opp, turn, rng):
    """Retorna o id da ação escolhida pelo bot neste turno."""
    for rule in behavior.get("rules", []):
        if not (condition_met(rule.get("when", {}), me, opp, turn) and affordable(actions[rule["do"]], me)):
            continue
        # "chance" (0 a 1) torna a reação provável, não garantida; só sorteia se as condições já batem
        if "chance" in rule and rng.random() >= rule["chance"]:
            continue
        return rule["do"]
    options = [o for o in behavior["default"] if affordable(actions[o["do"]], me)]
    if not options:
        options = behavior["default"]
    chosen = rng.choices([o["do"] for o in options], weights=[o.get("weight", 1) for o in options])[0]
    return chosen
