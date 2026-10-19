import os
import unittest

from engine.loader import load_content
from engine.model import Battle

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def new_battle(seed=1):
    return Battle(load_content(BASE), seed)


def kinds(events, kind, **filters):
    return [e for e in events if e["kind"] == kind and all(e.get(k) == v for k, v in filters.items())]


class BattleTests(unittest.TestCase):
    def test_determinismo(self):
        choices = ["fire", "dodge", "fire", "strike", "offer_blood", "fire"]
        runs = []
        for _ in range(2):
            b = new_battle(seed=42)
            out = []
            for c in choices:
                if b.over:
                    break
                out.append(b.step(c))
            runs.append(out)
        self.assertEqual(runs[0], runs[1])

    def test_bot_nao_ve_a_acao_atual_do_jogador(self):
        # mesmo histórico, ações diferentes no turno 3: o inimigo precisa escolher igual
        results = []
        for third in ("fire", "dodge", "strike", "observe"):
            b = new_battle(seed=7)
            b.step("observe")
            b.step("observe")
            b.step(third)
            results.append(b.history[-1][1])
        self.assertEqual(len(set(results)), 1)

    def test_fogo_sem_vigor_falha(self):
        b = new_battle()
        b.player.vigor = 0
        b.player.regen = 0
        events = b.step("fire")
        self.assertTrue(kinds(events, "fail", actor="player", action="fire"))
        self.assertEqual(b.enemy.hp, b.enemy.max_hp)

    def test_esquiva_anula_projetil_mas_nao_corpo_a_corpo(self):
        b = new_battle()
        b.enemy.states.clear()
        # força o inimigo a usar sigil_flame e depois metal_strike via comportamento padrão
        b.encounter["behavior"] = {"rules": [], "default": [{"do": "sigil_flame", "weight": 1}]}
        events = b.step("dodge")
        self.assertTrue(kinds(events, "dodged"))
        self.assertEqual(b.player.hp, b.player.max_hp)

        b2 = new_battle()
        b2.encounter["behavior"] = {"rules": [], "default": [{"do": "metal_strike", "weight": 1}]}
        events = b2.step("dodge")
        self.assertFalse(kinds(events, "dodged"))
        self.assertTrue(kinds(events, "hit", action="metal_strike", target_dodging=True))
        self.assertLess(b2.player.hp, b2.player.max_hp)

    def test_sangue_amplifica_dano_do_fogo_inato(self):
        b = new_battle()
        b.encounter["behavior"] = {"rules": [], "default": [{"do": "offer_blood", "weight": 1}]}
        b.step("offer_blood")
        hp_before = b.enemy.hp
        events = b.step("fire")
        hits = kinds(events, "hit", actor="player")
        mult = [r for r in b.rules if r["id"] == "blood_amplifies_innate"][0]["effect"]["damage_multiplier"]
        expected = b.actions["fire"]["damage"] * mult
        self.assertEqual(hits[0]["amount"], expected)
        self.assertTrue(kinds(events, "rule", rule="blood_amplifies_innate"))
        self.assertLessEqual(b.enemy.hp, hp_before - expected)

    def test_sangue_no_sigilo_triplica_chamas_do_inimigo(self):
        b = new_battle()
        b.enemy.states["blood_offered"] = 1  # estado vale no turno 1
        b.encounter["behavior"] = {"rules": [{"when": {"self_state": "blood_offered"}, "do": "sigil_flame"}],
                                   "default": [{"do": "metal_strike", "weight": 1}]}
        events = b.step("observe")
        self.assertEqual(len(kinds(events, "hit", actor="hooded_man")), 3)
        self.assertNotIn("blood_offered", b.enemy.states)  # consumido

    def test_sangue_expira(self):
        b = new_battle()
        b.encounter["behavior"] = {"rules": [], "default": [{"do": "metal_strike", "weight": 1}]}
        b.step("offer_blood")       # turno 1: estado vale até o turno 2
        b.step("observe")           # turno 2: não ataca com fogo
        b.step("observe")           # turno 3: expirou
        self.assertFalse(b.player.has_state("blood_offered", b.turn))

    def test_observar_nao_vaza_o_futuro(self):
        b = new_battle()
        b.encounter["behavior"] = {"rules": [], "default": [{"do": "offer_blood", "weight": 1}]}
        events = b.step("observe")
        ids = [e["line_id"] for e in kinds(events, "observe_line")]
        self.assertIn("base", ids)
        self.assertNotIn("sigils_red", ids)   # o ritual aconteceu neste turno, depois da observação
        events = b.step("observe")
        ids = [e["line_id"] for e in kinds(events, "observe_line")]
        self.assertIn("sigils_red", ids)

    def test_morte_do_jogador_tem_prioridade(self):
        b = new_battle()
        b.player.hp = 1
        b.enemy.hp = 1
        b.encounter["behavior"] = {"rules": [], "default": [{"do": "metal_strike", "weight": 1}]}
        b.step("fire")
        self.assertTrue(b.over)
        self.assertEqual(b.result, "defeat")


if __name__ == "__main__":
    unittest.main()
