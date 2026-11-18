"""Carrega e valida o conteúdo (dados) do jogo.

O motor nunca tem conteúdo "escondido" no código: tudo que é magia, inimigo,
item e texto vive em arquivos JSON dentro de content/.
"""
import json
import os


class ContentError(Exception):
    """Erro de conteúdo: mensagem pensada para quem está criando conteúdo novo."""


def _load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise ContentError("Arquivo não encontrado: %s" % path)
    except json.JSONDecodeError as e:
        raise ContentError("JSON inválido em %s: %s" % (path, e))


def load_campaign(base_dir):
    """Lista ordenada de ids de encontros (content/campaign.json)."""
    return _load_json(os.path.join(base_dir, "content", "campaign.json"))["encounters"]


def load_content(base_dir, encounter):
    cdir = os.path.join(base_dir, "content")
    content = {
        "actions": _load_json(os.path.join(cdir, "actions.json")),
        "rules": _load_json(os.path.join(cdir, "rules.json")),
        "items": _load_json(os.path.join(cdir, "items.json")),
        "player": _load_json(os.path.join(cdir, "player.json")),
        "narration": _load_json(os.path.join(cdir, "narration.json")),
        "diary_rules": _load_json(os.path.join(cdir, "diary_rules.json")),
        "encounter": _load_json(os.path.join(cdir, "encounters", encounter + ".json")),
    }
    for aid, action in content["actions"].items():
        action["id"] = aid
        action.setdefault("tags", [])
        action.setdefault("vigor_cost", 0)
        action.setdefault("hp_cost", 0)
        action.setdefault("source", "body")
        if "damage" in action:
            action.setdefault("hits", 1)
        # por padrão, só projéteis podem ser evitados com a esquiva
        action.setdefault("dodgeable", "projectile" in action["tags"])
    enc = content["encounter"]
    enc.setdefault("tags", [])
    enc.setdefault("intro", [])
    enc.setdefault("loot", [])
    validate(content)
    return content


def validate(content):
    """Levanta ContentError com uma mensagem clara se algo estiver inconsistente."""
    actions = content["actions"]
    items = content["items"]
    narration = content["narration"]
    enc = content["encounter"]
    player = content["player"]
    problems = []

    known_states = set()
    for action in actions.values():
        for st in action.get("sets_states", []):
            known_states.add(st["name"])

    # ações do jogador, inclusive as concedidas por itens
    player_actions = list(player["actions"])
    for iid, item in items.items():
        for aid in item.get("grants_actions", []):
            if aid not in actions:
                problems.append("O item '%s' concede a ação inexistente '%s'." % (iid, aid))
            elif aid not in player_actions:
                player_actions.append(aid)

    for owner, ids in (("player", player["actions"]), (enc["id"], enc["actions"])):
        for aid in ids:
            if aid not in actions:
                problems.append("%s usa a ação inexistente '%s'." % (owner, aid))

    # loot do encontro
    for entry in enc["loot"]:
        if entry["item"] not in items:
            problems.append("O loot de %s referencia o item inexistente '%s'." % (enc["id"], entry["item"]))
        if entry["item"] not in narration.get("loot", {}):
            problems.append("Falta texto de saque para o item '%s' (loot.%s)." % (entry["item"], entry["item"]))
    for iid, item in items.items():
        if "description" not in item:
            problems.append("O item '%s' precisa de 'description'." % iid)

    # comportamento do inimigo
    beh = enc.get("behavior", {})
    for rule in beh.get("rules", []):
        if rule["do"] not in enc["actions"]:
            problems.append("Comportamento usa '%s', que não está nas ações do inimigo." % rule["do"])
        st = rule.get("when", {}).get("self_state")
        if st and st not in known_states:
            problems.append("Comportamento espera o estado '%s', que nenhuma ação cria." % st)
    for opt in beh.get("default", []):
        if opt["do"] not in enc["actions"]:
            problems.append("Ação padrão '%s' não está nas ações do inimigo." % opt["do"])
    if not beh.get("default"):
        problems.append("O inimigo precisa de ao menos uma ação padrão (behavior.default).")

    # regras do mundo
    seen_rule_ids = set()
    for rule in content["rules"]:
        if rule["id"] in seen_rule_ids:
            problems.append("Regra duplicada: %s" % rule["id"])
        seen_rule_ids.add(rule["id"])
        if rule.get("consume_state") and rule["consume_state"] not in known_states:
            problems.append("Regra '%s' consome o estado '%s', que nenhuma ação cria." % (rule["id"], rule["consume_state"]))
        st = rule.get("when", {}).get("actor_state")
        if st and st not in known_states:
            problems.append("Regra '%s' exige o estado '%s', que nenhuma ação cria." % (rule["id"], st))

    # narração: toda ação precisa ter texto para quem a usa
    def has_text(aid, actor_id):
        entry = narration.get("actions", {}).get(aid, {})
        return actor_id in entry or "default" in entry

    for aid in player_actions:
        if not has_text(aid, "player"):
            problems.append("Falta narração de '%s' para o jogador (actions.%s.player)." % (aid, aid))
        if aid not in narration.get("menu", {}):
            problems.append("Falta item de menu para '%s' (menu.%s)." % (aid, aid))
    for aid in enc["actions"]:
        if not has_text(aid, enc["id"]):
            problems.append("Falta narração de '%s' para %s (actions.%s.%s)." % (aid, enc["id"], aid, enc["id"]))
    if enc["id"] not in narration.get("death", {}):
        problems.append("Falta texto de morte para %s (death.%s)." % (enc["id"], enc["id"]))

    ids = [r["id"] for r in content["diary_rules"]]
    for dup in {i for i in ids if ids.count(i) > 1}:
        problems.append("Entrada de diário com id repetido: %s" % dup)

    if problems:
        raise ContentError("Conteúdo inconsistente:\n  - " + "\n  - ".join(problems))