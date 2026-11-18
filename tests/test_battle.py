import os
import unittest

from engine.loader import load_content
from engine.model import Battle

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def new_battle(seed=1, encounter="hooded_man", inventory=()):
    return Battle(load_content(BASE, encounter), seed, inventory)


def only(behavior_action):
    return {"rules": [], "default": [{"do": behavior_action, "weight": 1}]}


def kinds(events, kind, **filters):
    return [e for e in events if e["kind"] == kind and all(e.get(k) == v for k, v in filters.items())]


class HoodedManTests(unittest.TestCase):
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
        b.encounter["behavior"] = only("sigil_flame")
        events = b.step("dodge")
        self.assertTrue(kinds(events, "dodged"))
        self.assertEqual(b.player.hp, b.player.max_hp)

        b2 = new_battle()
        b2.encounter["behavior"] = only("metal_strike")
        events = b2.step("dodge")
        self.assertFalse(kinds(events, "dodged"))
        self.assertTrue(kinds(events, "hit", action="metal_strike", target_dodging=True))
        self.assertLess(b2.player.hp, b2.player.max_hp)

    def test_sangue_na_mao_amplifica_fogo_inato(self):
        b = new_battle()
        b.encounter["behavior"] = only("metal_strike")
        b.step("offer_blood")
        events = b.step("fire")
        mult = [r for r in b.rules if r["id"] == "blood_amplifies_innate"][0]["effect"]["damage_multiplier"]
        self.assertEqual(kinds(events, "hit", actor="player")[0]["amount"], b.actions["fire"]["damage"] * mult)
        self.assertTrue(kinds(events, "rule", rule="blood_amplifies_innate"))

    def test_sangue_no_sigilo_triplica_chamas_do_inimigo(self):
        b = new_battle()
        b.enemy.states["blood_on_sigil"] = 1
        events = b.step("observe")
        self.assertEqual(len(kinds(events, "hit", actor="hooded_man")), 3)
        self.assertNotIn("blood_on_sigil", b.enemy.states)

    def test_sangue_expira(self):
        b = new_battle()
        b.encounter["behavior"] = only("metal_strike")
        b.step("offer_blood")
        b.step("observe")
        b.step("observe")
        self.assertFalse(b.player.has_state("blood_on_hand", b.turn))

    def test_observar_nao_vaza_o_futuro(self):
        b = new_battle()
        b.encounter["behavior"] = only("smear_sigils")
        ids = [e["line_id"] for e in kinds(b.step("observe"), "observe_line")]
        self.assertIn("base", ids)
        self.assertNotIn("sigils_red", ids)
        ids = [e["line_id"] for e in kinds(b.step("observe"), "observe_line")]
        self.assertIn("sigils_red", ids)

    def test_morte_do_jogador_tem_prioridade(self):
        b = new_battle()
        b.player.hp = 1
        b.enemy.hp = 1
        b.encounter["behavior"] = only("metal_strike")
        b.step("fire")
        self.assertTrue(b.over)
        self.assertEqual(b.result, "defeat")


class ItemTests(unittest.TestCase):
    def test_sem_braco_nao_ha_acoes_do_braco(self):
        b = new_battle(encounter="bloated_one")
        self.assertNotIn("smear_sigils", b.player.actions)
        self.assertNotIn("sigil_flame", b.player.actions)

    def test_com_braco_o_jogador_ganha_as_mesmas_acoes_do_encapuzado(self):
        b = new_battle(encounter="bloated_one", inventory=["metal_arm"])
        self.assertIn("smear_sigils", b.player.actions)
        self.assertIn("sigil_flame", b.player.actions)

    def test_sangue_na_mao_nao_ativa_o_braco(self):
        b = new_battle(encounter="bloated_one", inventory=["metal_arm"])
        b.encounter["behavior"] = only("shove")
        b.step("offer_blood")
        events = b.step("sigil_flame")
        self.assertEqual(len(kinds(events, "hit", actor="player")), 1)

    def test_sangue_nos_sigilos_do_braco_dispara_tres_chamas(self):
        b = new_battle(encounter="bloated_one", inventory=["metal_arm"])
        b.encounter["behavior"] = only("shove")
        b.step("smear_sigils")
        events = b.step("sigil_flame")
        self.assertEqual(len(kinds(events, "hit", actor="player")), 3)
        self.assertTrue(kinds(events, "rule", rule="blood_amplifies_sigil", actor="player"))


class BloatedOneTests(unittest.TestCase):
    def test_pele_encharcada_reduz_fogo_inato_mas_nao_o_do_braco(self):
        b = new_battle(encounter="bloated_one", inventory=["metal_arm"])
        b.encounter["behavior"] = only("shove")
        fire = kinds(b.step("fire"), "hit", actor="player")[0]["amount"]
        flame = kinds(b.step("sigil_flame"), "hit", actor="player")[0]["amount"]
        self.assertEqual(fire, b.actions["fire"]["damage"] // 2)
        self.assertEqual(flame, b.actions["sigil_flame"]["damage"])

    def test_golpe_pesado_e_esquivavel_so_depois_do_aviso(self):
        b = new_battle(encounter="bloated_one")
        b.step("observe")
        b.enemy.states["winding"] = 2
        b.encounter["behavior"] = {"rules": [{"when": {"self_state": "winding"}, "do": "crush"}],
                                   "default": [{"do": "shove", "weight": 1}]}
        events = b.step("dodge")
        self.assertTrue(kinds(events, "dodged", action="crush"))


if __name__ == "__main__":
    unittest.main()