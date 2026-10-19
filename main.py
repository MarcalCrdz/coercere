#!/usr/bin/env python3
"""SIGILOS V0.1 — um duelo, sem HUD, sem tutorial.

Uso:
  python main.py                 jogar
  python main.py --debug         mostra o estado real (para quem desenvolve)
  python main.py --seed 123      repete exatamente a mesma luta
  python main.py --validate      valida o conteúdo em content/
  python main.py --reset-diary   apaga o diário
"""
import argparse
import datetime
import json
import os
import sys
import textwrap

from engine.diary import Diary
from engine.loader import ContentError, load_content, validate
from engine.model import Battle
from engine.narrator import Narrator

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAVES = os.path.join(BASE_DIR, "saves")
WIDTH = 78


def say(text="", indent=""):
    if not text:
        print()
        return
    print(textwrap.fill(text, WIDTH, initial_indent=indent, subsequent_indent=indent))


def resolve_choice(raw, player_actions, menu):
    """Converte o que foi digitado em um id de ação (ou None)."""
    raw = raw.strip().lower()
    if not raw:
        return None
    if raw.isdigit():
        idx = int(raw)
        return player_actions[idx - 1] if 1 <= idx <= len(player_actions) else None
    for aid in player_actions:
        aliases = [a.lower() for a in menu[aid]["aliases"]]
        if raw in aliases:
            return aid
    if len(raw) >= 3:
        for aid in player_actions:
            if any(a.lower().startswith(raw) for a in menu[aid]["aliases"]):
                return aid
    return None


def read_choice(battle, narrator, diary, menu):
    actions = battle.player.actions
    while True:
        print()
        for line in narrator.menu(actions):
            print(line)
        print("  (d) diário   (s) sair")
        try:
            raw = input("> ")
        except (EOFError, KeyboardInterrupt):
            print()
            raise SystemExit(0)
        word = raw.strip().lower()
        if word in ("s", "sair", "q"):
            raise SystemExit(0)
        if word in ("d", "diario", "diário"):
            print()
            say("— Diário —")
            for line in diary.lines():
                say(line, indent="")
            continue
        choice = resolve_choice(raw, actions, menu)
        if choice:
            return choice
        say("Você hesita.")


def log_run(battle, seed, encounter_id):
    try:
        os.makedirs(SAVES, exist_ok=True)
        entry = {
            "time": datetime.datetime.now().isoformat(timespec="seconds"),
            "seed": seed,
            "encounter": encounter_id,
            "result": battle.result,
            "turns": battle.turn,
            "player_actions": [h[0] for h in battle.history],
            "enemy_actions": [h[1] for h in battle.history],
        }
        with open(os.path.join(SAVES, "runs.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def play_once(content, diary, seed, debug):
    battle = Battle(content, seed)
    narrator = Narrator(content["narration"])
    menu = content["narration"]["menu"]

    print("\n" + "=" * WIDTH)
    for line in narrator.intro():
        say(line)
    diary.record([{"kind": "start", "turn": 0}])

    while not battle.over:
        choice = read_choice(battle, narrator, diary, menu)
        events = battle.step(choice)
        print()
        for line in narrator.render(events, battle):
            say(line)
        diary.record(events)
        if debug:
            print(battle.debug_snapshot())
            for ev in events:
                print("[debug]   evento:", json.dumps(ev, ensure_ascii=False))

    print()
    say("Você venceu." if battle.result == "victory" else "Você morreu.")
    say("(semente %s)" % battle.seed)
    log_run(battle, battle.seed, content["encounter"]["id"])


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="SIGILOS V0.1")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--reset-diary", action="store_true")
    parser.add_argument("--encounter", default="hooded_man")
    args = parser.parse_args()

    try:
        content = load_content(BASE_DIR, args.encounter)
    except ContentError as e:
        print(e)
        raise SystemExit(1)

    if args.validate:
        validate(content)
        print("Conteúdo válido.")
        return

    diary = Diary(os.path.join(SAVES, "diary.json"), content["diary_rules"])
    if args.reset_diary:
        diary.reset()
        print("Diário apagado.")
        return

    seed = args.seed
    while True:
        play_once(content, diary, seed, args.debug)
        seed = None  # a partir da segunda tentativa, seed aleatória
        print()
        try:
            again = input("Enter para recomeçar com outro corpo, ou 's' para sair: ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if again.strip().lower() in ("s", "sair", "q"):
            break


if __name__ == "__main__":
    main()
