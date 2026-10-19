"""Carrega e valida o conteúdo (dados) do jogo.

O motor nunca tem conteúdo "escondido" no código: tudo que é magia, inimigo
e texto vive em arquivos JSON dentro de content/.
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


def load_content(base_dir, encounter="hooded_man"):
    cdir = os.path.join(base_dir, "content")
    content = {
        "actions": _load_json(os.path.join(cdir, "actions.json")),
        "rules": _load_json(os.path.join(cdir, "rules.json")),
        "player": _load_json(os.path.join(cdir, "player.json")),
        "narration": _load_json(os.path.join(cdir, "narration.json")),
        "diary_rules": _load_json(os.path.join(cdir, "diary_rules.json")),
        "encounter": _load_json(os.path.join(cdir, "encounters", encounter + ".json")),
    }
    # preenche padrões e o id de cada ação
    for aid, action in content["actions"].items():
        action["id"] = aid
        action.setdefault("tags", [])
        action.setdefault("vigor_cost", 0)
        action.setdefault("hp_cost", 0)
        action.setdefault("source", "body")
        if "damage" in action:
            action.setdefault("hits", 1)
    validate(content)
    return content


def validate(content):
    """Levanta ContentError com uma mensagem clara se algo estiver inconsistente."""
    actions = content["actions"]
    narration = content["narration"]
    enc = content["encounter"]
    player = content["player"]
    problems = []

    known_states = set()
    for aid, action in actions.items():
        for st in action.get("sets_states", []):
            known_states.add(st["name"])

    # ações referenciadas existem
    for owner, ids in (("player", player["actions"]), (enc["id"], enc["actions"])):
        for aid in ids:
            if aid not in actions:
                problems.append("%s usa a ação inexistente '%s'." % (owner, aid))

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
        for key in ("consume_state",):
            if rule.get(key) and rule[key] not in known_states:
                problems.append("Regra '%s' consome o estado '%s', que nenhuma ação cria." % (rule["id"], rule[key]))
        st = rule.get("when", {}).get("actor_state")
        if st and st not in known_states:
            problems.append("Regra '%s' exige o estado '%s', que nenhuma ação cria." % (rule["id"], st))

    # narração: toda ação declarada precisa ter texto para quem a usa
    def has_text(aid, actor_id):
        entry = narration.get("actions", {}).get(aid, {})
        return actor_id in entry or "default" in entry

    for aid in player["actions"]:
        if not has_text(aid, "player"):
            problems.append("Falta narração de '%s' para o jogador (actions.%s.player)." % (aid, aid))
        if aid not in narration.get("menu", {}):
            problems.append("Falta item de menu para '%s' (menu.%s)." % (aid, aid))
    for aid in enc["actions"]:
        if not has_text(aid, enc["id"]):
            problems.append("Falta narração de '%s' para %s (actions.%s.%s)." % (aid, enc["id"], aid, enc["id"]))

    # diário: ids únicos
    ids = [r["id"] for r in content["diary_rules"]]
    for dup in {i for i in ids if ids.count(i) > 1}:
        problems.append("Entrada de diário com id repetido: %s" % dup)

    if problems:
        raise ContentError("Conteúdo inconsistente:\n  - " + "\n  - ".join(problems))
