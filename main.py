#!/usr/bin/env python3
"""SIGILOS V0.2 — corredores, sem HUD, sem tutorial.

Uso:
  python main.py                       jogar a campanha
  python main.py --debug               mostra o estado real (para quem desenvolve)
  python main.py --seed 123            repete exatamente as mesmas lutas
  python main.py --encounter bloated_one --with metal_arm
                                       testa um encontro isolado, já com itens
  python main.py --validate            valida todo o conteúdo em content/
  python main.py --reset-diary         apaga o diário
"""
import argparse
import datetime
import json
import os
import sys
import textwrap

from engine.diary import Diary
from engine.loader import ContentError, load_campaign, load_content
from engine.model import Battle
from engine.narrator import Narrator

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAVES = os.path.join(BASE_DIR, "saves")
WIDTH = 78


def say(text=""):
    if not text:
        print()
    else:
        print(textwrap.fill(text, WIDTH))


def ask(prompt="> "):
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        print()
        raise SystemExit(0)


def resolve_choice(raw, player_actions, menu):
    """Converte o que foi digitado em um id de ação (ou None)."""
    raw = raw.strip().lower()
    if not raw:
        return None
    if raw.isdigit():
        idx = int(raw)
        return player_actions[idx - 1] if 1 <= idx <= len(player_actions) else None
    for aid in player_actions:
        if raw in [a.lower() for a in menu[aid]["aliases"]]:
            return aid
    if len(raw) >= 3:
        for aid in player_actions:
            if any(a.lower().startswith(raw) for a in menu[aid]["aliases"]):
                return aid
    return None


def show_inventory(content, inventory):
    ui = content["narration"]["ui"]
    print()
    say(ui["inventory_header"])
    if not inventory:
        say(ui["inventory_empty"])
    for item_id in inventory:
        item = content["items"][item_id]
        say("· %s: %s" % (item["name"].capitalize(), item["description"]))


def read_choice(battle, narrator, diary, content, inventory):
    actions = battle.player.actions
    menu = content["narration"]["menu"]
    while True:
        print()
        for line in narrator.menu(actions):
            print(line)
        print("  (d) diário   (i) itens   (s) sair")
        raw = ask()
        word = raw.strip().lower()
        if word in ("s", "sair", "q"):
            raise SystemExit(0)
        if word in ("d", "diario", "diário"):
            print()
            say("— Diário —")
            for line in diary.lines():
                say(line)
            continue
        if word in ("i", "itens", "item"):
            show_inventory(content, inventory)
            continue
        choice = resolve_choice(raw, actions, menu)
        if choice:
            return choice
        say("Você hesita.")


def loot_menu(content, inventory, diary, narrator):
    """Menu de itens para saquear depois de uma vitória."""
    loot = list(content["encounter"].get("loot", []))
    ui = content["narration"]["ui"]
    while loot:
        print()
        say(ui["loot_header"])
        for i, entry in enumerate(loot, 1):
            print("  %d. %s" % (i, entry["label"]))
        print("  (c) %s   (i) itens" % ui["loot_leave"])
        word = ask().strip().lower()
        if word in ("c", "continuar", "seguir", "s"):
            break
        if word in ("i", "itens", "item"):
            show_inventory(content, inventory)
            continue
        if word.isdigit() and 1 <= int(word) <= len(loot):
            entry = loot.pop(int(word) - 1)
            inventory.append(entry["item"])
            events = [{"kind": "loot", "item": entry["item"], "turn": 0}]
            print()
            for line in narrator.render(events):
                say(line)
            diary.record(events)
        else:
            say("Você hesita.")


def log_run(battle, encounter_id, inventory_at_start):
    try:
        os.makedirs(SAVES, exist_ok=True)
        entry = {
            "time": datetime.datetime.now().isoformat(timespec="seconds"),
            "seed": battle.seed,
            "encounter": encounter_id,
            "inventory": inventory_at_start,
            "result": battle.result,
            "turns": battle.turn,
            "player_actions": [h[0] for h in battle.history],
            "enemy_actions": [h[1] for h in battle.history],
        }
        with open(os.path.join(SAVES, "runs.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def fight(content, diary, seed, debug, inventory):
    """Uma luta. Retorna a Battle terminada."""
    battle = Battle(content, seed, inventory)
    narrator = Narrator(content["narration"])
    start_inventory = list(inventory)

    print("\n" + "=" * WIDTH)
    for line in content["encounter"]["intro"]:
        say(line)
    diary.record([{"kind": "start", "turn": 0}])

    while not battle.over:
        choice = read_choice(battle, narrator, diary, content, inventory)
        events = battle.step(choice)
        print()
        for line in narrator.render(events, battle):
            say(line)
        diary.record(events)
        if debug:
            print(battle.debug_snapshot())
            for ev in events:
                print("[debug]   evento:", json.dumps(ev, ensure_ascii=False))

    log_run(battle, content["encounter"]["id"], start_inventory)
    return battle


def run_character(campaign, diary, seed, debug, inventory):
    """Um personagem: percorre a campanha até morrer ou terminar."""
    for index, enc_id in enumerate(campaign):
        content = load_content(BASE_DIR, enc_id)
        if index > 0:
            print()
            for line in content["narration"].get("between", []):
                say(line)
        fight_seed = None if seed is None else seed + index
        battle = fight(content, diary, fight_seed, debug, inventory)
        print()
        if battle.result != "victory":
            say("Você morreu. O corpo fica; o que você aprendeu, não.")
            say("(semente %s)" % battle.seed)
            return
        say("Você venceu.")
        loot_menu(content, inventory, diary, Narrator(content["narration"]))
    print()
    for line in content["narration"].get("finale", []):
        say(line)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="SIGILOS V0.2")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--reset-diary", action="store_true")
    parser.add_argument("--encounter", default=None, help="roda só este encontro")
    parser.add_argument("--with", dest="with_items", nargs="*", default=[],
                        help="itens iniciais (para testar)")
    args = parser.parse_args()

    try:
        campaign = [args.encounter] if args.encounter else load_campaign(BASE_DIR)
        contents = [load_content(BASE_DIR, e) for e in campaign]  # valida tudo de uma vez
    except ContentError as e:
        print(e)
        raise SystemExit(1)

    if args.validate:
        print("Conteúdo válido (%d encontros)." % len(contents))
        return

    diary = Diary(os.path.join(SAVES, "diary.json"), contents[0]["diary_rules"])
    if args.reset_diary:
        diary.reset()
        print("Diário apagado.")
        return

    seed = args.seed
    while True:
        run_character(campaign, diary, seed, args.debug, list(args.with_items))
        seed = None  # a partir do segundo personagem, seeds aleatórias
        print()
        if ask("Enter para recomeçar com outro corpo, ou 's' para sair: ").strip().lower() in ("s", "sair", "q"):
            break


if __name__ == "__main__":
    main()