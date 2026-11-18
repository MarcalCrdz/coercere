"""Simula muitas lutas com estratégias fixas para checar balanceamento.

Uso:  python -m tools.simulate [N]
As estratégias "ingênuas" NÃO leem o estado do inimigo; as "atentas" imitam um
jogador que reparou no que a narração mostra (sigilos vermelhos, braços erguidos).
"""
import os
import sys

from engine.loader import load_content
from engine.model import Battle

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------- encontro 1
def spam_fire(b):
    return "fire"


def spam_dodge(b):
    return "dodge"


def spam_strike(b):
    return "strike"


def blood_then_fire(b):
    return "offer_blood" if b.turn % 2 == 0 else "fire"


def attentive(b):
    if b.enemy.has_state("blood_on_sigil", b.turn + 1):
        return "dodge"
    return "fire"


def attentive_blood(b):
    if b.enemy.has_state("blood_on_sigil", b.turn + 1):
        return "dodge"
    if b.player.has_state("blood_on_hand", b.turn):
        return "fire"
    if b.player.hp > 12 and b.player.vigor >= 2:
        return "offer_blood"
    return "fire" if b.player.vigor >= 2 else "strike"


# ---------------------------------------------------------------- encontro 2
def attentive_no_arm(b):
    """Sem o braço: esquiva no aviso; senão alterna sangue na mão e fogo."""
    if b.enemy.has_state("winding", b.turn + 1):
        return "dodge"
    if b.player.has_state("blood_on_hand", b.turn):
        return "fire"
    if b.player.hp > 8 and b.player.vigor >= 2:
        return "offer_blood"
    return "fire" if b.player.vigor >= 2 else "strike"


def arm_blind(b):
    """Com o braço, mas sem ler nada: alterna sangue nos sigilos e chama."""
    return "sigil_flame" if b.player.has_state("blood_on_sigil", b.turn) else "smear_sigils"


def arm_attentive(b):
    """Com o braço e lendo o aviso: esquiva quando os braços sobem."""
    if b.enemy.has_state("winding", b.turn + 1):
        return "dodge"
    return "sigil_flame" if b.player.has_state("blood_on_sigil", b.turn) else "smear_sigils"


SCENARIOS = [
    # (rótulo, encontro, itens, estratégia)
    ("1 | só fogo", "hooded_man", [], spam_fire),
    ("1 | só esquiva", "hooded_man", [], spam_dodge),
    ("1 | só golpe", "hooded_man", [], spam_strike),
    ("1 | sangue+fogo às cegas", "hooded_man", [], blood_then_fire),
    ("1 | atento (esquiva no sinal)", "hooded_man", [], attentive),
    ("1 | atento + sangue próprio", "hooded_man", [], attentive_blood),
    ("2 | só fogo, sem braço", "bloated_one", [], spam_fire),
    ("2 | atento, sem braço", "bloated_one", [], attentive_no_arm),
    ("2 | braço às cegas", "bloated_one", ["metal_arm"], arm_blind),
    ("2 | braço + atento", "bloated_one", ["metal_arm"], arm_attentive),
]


def run(encounter, items, strategy, n):
    content = load_content(BASE, encounter)
    wins, turns = 0, 0
    for seed in range(1, n + 1):
        b = Battle(content, seed, items)
        while not b.over and b.turn < 80:
            b.step(strategy(b))
        wins += 1 if b.result == "victory" else 0
        turns += b.turn
    return wins / float(n), turns / float(n)


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    print("%-34s %8s %8s" % ("cenário", "vitórias", "turnos"))
    for label, enc, items, strat in SCENARIOS:
        w, t = run(enc, items, strat, n)
        print("%-34s %7.0f%% %8.1f" % (label, w * 100, t))