"""Simula muitas lutas com estratégias fixas para checar balanceamento.

Uso:  python -m tools.simulate [N]
As estratégias "ingênuas" NÃO leem o estado do inimigo; a "atenta" imita um
jogador que reparou nos sigilos vermelhos (o que a ação 'observar' revelaria).
"""
import os
import sys

from engine.loader import load_content
from engine.model import Battle

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def spam_fire(b):
    return "fire"


def spam_dodge(b):
    return "dodge"


def spam_strike(b):
    return "strike"


def blood_then_fire(b):
    # corta a mão, solta o fogo; repete
    return "offer_blood" if b.turn % 2 == 0 else "fire"


def attentive(b):
    # reage ao sinal visível: sigilos vermelhos => esquiva; senão ataca com fogo
    if b.enemy.has_state("blood_offered", b.turn + 1):
        return "dodge"
    return "fire"


def attentive_blood(b):
    if b.enemy.has_state("blood_offered", b.turn + 1):
        return "dodge"
    if b.player.has_state("blood_offered", b.turn):
        return "fire"
    if b.player.hp > 12 and b.player.vigor >= 2:
        return "offer_blood"
    return "fire" if b.player.vigor >= 2 else "strike"


STRATEGIES = [
    ("só fogo", spam_fire),
    ("só esquiva", spam_dodge),
    ("só golpe", spam_strike),
    ("sangue+fogo às cegas", blood_then_fire),
    ("atento (esquiva no sinal)", attentive),
    ("atento + sangue próprio", attentive_blood),
]


def run(strategy, n):
    content = load_content(BASE)
    wins, turns = 0, 0
    for seed in range(1, n + 1):
        b = Battle(content, seed)
        while not b.over and b.turn < 60:
            b.step(strategy(b))
        wins += 1 if b.result == "victory" else 0
        turns += b.turn
    return wins / float(n), turns / float(n)


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    print("%-30s %8s %8s" % ("estratégia", "vitórias", "turnos"))
    for name, strat in STRATEGIES:
        w, t = run(strat, n)
        print("%-30s %7.0f%% %8.1f" % (name, w * 100, t))
