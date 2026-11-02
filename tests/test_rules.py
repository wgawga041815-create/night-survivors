import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import rules  # noqa: E402

STEP = 1.0 / 60.0
CONFIG = json.loads((ROOT / "data" / "game.json").read_text(encoding="utf-8"))


class WorldTests(unittest.TestCase):
    def make_world(self):
        world = rules.World(CONFIG, seed=1)
        world.start()
        return world

    def test_initial_state(self):
        world = self.make_world()
        self.assertEqual(world.state, "playing")
        self.assertEqual(world.hero.hp, 100)
        self.assertEqual(world.hero.level, 1)
        self.assertEqual(world.weapons, {"spark": 1})
        self.assertEqual(world.normal_count(), 12)
        self.assertEqual(world.time, 0.0)

    def test_spawn_table_reaches_minimum(self):
        world = self.make_world()
        world.enemies.clear()
        world.time = 30.0
        world.spawn_timer = 0.0
        for _ in range(300):
            world.update(STEP)
        self.assertGreaterEqual(world.normal_count(), 28)
        self.assertLessEqual(len(world.enemies), 120)

    def test_contact_damage_has_cooldown(self):
        world = self.make_world()
        world.enemies.clear()
        world.weapons = {}
        world.spawn_enemy("slime", world.hero.x, world.hero.y)
        world.hurt_cd = 0.0
        world.update(STEP)
        self.assertEqual(world.hero.hp, 92)
        world.update(STEP)
        self.assertEqual(world.hero.hp, 92)
        world.hurt_cd = 0.0
        world.update(STEP)
        self.assertEqual(world.hero.hp, 84)

    def test_spark_wand_fires_and_hits(self):
        world = self.make_world()
        world.enemies.clear()
        enemy = world.spawn_enemy("slime", world.hero.x + 100, world.hero.y)
        world.spark_timer = 0.0
        world.update(STEP)
        self.assertGreaterEqual(len(world.projectiles), 1)
        for _ in range(40):
            world.update(STEP)
            if enemy.hp < 30:
                break
        self.assertLess(enemy.hp, 30)

    def test_xp_level_up_and_choose_card(self):
        world = self.make_world()
        world.gain_xp(5)
        self.assertEqual(world.hero.level, 2)
        self.assertEqual(world.state, "levelup")
        self.assertEqual(len(world.cards), 3)
        self.assertTrue(world.choose_card(0))
        self.assertEqual(world.state, "playing")

    def test_cards_never_offer_level_six(self):
        world = self.make_world()
        world.weapons = {"spark": 5, "blades": 5, "ring": 5}
        world.items = {"boots": 5, "heart": 5, "magnet": 5}
        cards = world._make_cards()
        self.assertEqual(len(cards), 3)
        self.assertTrue(all(card["kind"] == "heal" for card in cards))

    def test_gem_is_collected(self):
        world = self.make_world()
        world.enemies.clear()
        world.hero.x = 0
        world.hero.y = 0
        world.gems.append(rules.Gem(0, 0, 2, 0))
        world.update(STEP)
        self.assertEqual(world.hero.xp, 2)
        self.assertEqual(world.gems, [])

    def test_victory_at_two_minutes(self):
        world = self.make_world()
        world.time = 119.99
        world.update(0.02)
        self.assertEqual(world.state, "victory")
        self.assertEqual(world.time, 120.0)

    def test_game_over_at_zero_hp(self):
        world = self.make_world()
        world.enemies.clear()
        world.hero.hp = 1
        world.spawn_enemy("demon", world.hero.x, world.hero.y)
        world.hurt_cd = 0.0
        world.update(STEP)
        self.assertEqual(world.state, "gameover")
        self.assertEqual(world.hero.hp, 0)

    def test_boss_spawns_at_ninety_seconds(self):
        world = self.make_world()
        world.time = 90.0
        world.spawn_timer = 0.0
        world.update(STEP)
        self.assertIsNotNone(world.boss)
        self.assertTrue(world.boss.boss)

    def test_pause_stops_time(self):
        world = self.make_world()
        world.pause_toggle()
        before = world.time
        world.update(STEP)
        self.assertEqual(world.time, before)
        world.pause_toggle()
        world.update(STEP)
        self.assertGreater(world.time, before)

    def test_config_numbers_match_design(self):
        self.assertEqual(CONFIG["weapons"]["spark"]["levels"][0]["damage"], 10)
        self.assertEqual(CONFIG["enemies"]["demon"]["hp"], 800)
        self.assertEqual(CONFIG["spawn"]["table"][0]["minimum"], 12)
        self.assertEqual(CONFIG["progression"]["first_level"], 5)


if __name__ == "__main__":
    unittest.main()
