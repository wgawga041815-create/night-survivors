"""Night Survivors rules.

This module contains the whole game simulation and no pygame code, so it can be
tested with plain unittest.  main.py only draws the world and sends input.
"""
from __future__ import annotations

import math
import random


def _clamp(value, low, high):
    return low if value < low else high if value > high else value


def _length(x, y):
    return math.hypot(x, y)


class Hero:
    __slots__ = (
        "x", "y", "hp", "max_hp", "speed", "base_speed", "level", "xp",
        "xp_next", "magnet", "base_magnet", "hit_radius",
    )

    def __init__(self, x, y, hp, speed, magnet, hit_radius, xp_next):
        self.x = float(x)
        self.y = float(y)
        self.hp = float(hp)
        self.max_hp = float(hp)
        self.base_speed = float(speed)
        self.speed = float(speed)
        self.base_magnet = float(magnet)
        self.magnet = float(magnet)
        self.hit_radius = float(hit_radius)
        self.level = 1
        self.xp = 0
        self.xp_next = int(xp_next)


class Enemy:
    __slots__ = (
        "kind", "x", "y", "hp", "max_hp", "speed", "damage", "xp",
        "radius", "boss", "blade_cd", "dead", "hit_flash",
    )

    def __init__(self, kind, x, y, data):
        self.kind = kind
        self.x = float(x)
        self.y = float(y)
        self.hp = float(data["hp"])
        self.max_hp = float(data["hp"])
        self.speed = float(data["speed"])
        self.damage = float(data["damage"])
        self.xp = int(data.get("xp", 0))
        self.radius = float(data.get("radius", 13.0))
        self.boss = bool(data.get("boss", False))
        self.blade_cd = 0.0
        self.dead = False
        self.hit_flash = 0.0


class Projectile:
    __slots__ = ("x", "y", "vx", "vy", "damage", "life", "radius", "dead")

    def __init__(self, x, y, vx, vy, damage, life, radius):
        self.x = float(x)
        self.y = float(y)
        self.vx = float(vx)
        self.vy = float(vy)
        self.damage = float(damage)
        self.life = float(life)
        self.radius = float(radius)
        self.dead = False


class Gem:
    __slots__ = ("x", "y", "xp", "phase", "dead")

    def __init__(self, x, y, xp, phase):
        self.x = float(x)
        self.y = float(y)
        self.xp = int(xp)
        self.phase = float(phase)
        self.dead = False


class Floater:
    __slots__ = ("x", "y", "text", "life", "max_life", "color")

    def __init__(self, x, y, text, color):
        self.x = float(x)
        self.y = float(y)
        self.text = str(text)
        self.life = 0.65
        self.max_life = 0.65
        self.color = color


class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "size", "color")

    def __init__(self, x, y, vx, vy, life, size, color):
        self.x = float(x)
        self.y = float(y)
        self.vx = float(vx)
        self.vy = float(vy)
        self.life = float(life)
        self.max_life = float(life)
        self.size = float(size)
        self.color = color


class Flash:
    __slots__ = ("x", "y", "radius", "life", "max_life")

    def __init__(self, x, y, radius):
        self.x = float(x)
        self.y = float(y)
        self.radius = float(radius)
        self.life = 0.18
        self.max_life = 0.18


class World:
    """The complete game state.  Feed it fixed steps of 1/60 s."""

    def __init__(self, config, seed=None):
        self.cfg = config
        self.rng = random.Random(seed)
        self.state = "title"
        self.reset()
        self.state = "title"

    # ------------------------------------------------------------------ setup
    def reset(self):
        hero_cfg = self.cfg["hero"]
        prog = self.cfg["progression"]
        self.hero = Hero(
            0.0, 0.0, hero_cfg["hp"], hero_cfg["speed"],
            hero_cfg["magnet"], hero_cfg["hit_radius"], prog["first_level"],
        )
        self.weapons = {hero_cfg.get("start_weapon", "spark"): 1}
        self.items = {}
        self.enemies = []
        self.projectiles = []
        self.gems = []
        self.floaters = []
        self.particles = []
        self.flashes = []
        self.time = 0.0
        self.state = "playing"
        self.paused = False
        self.kills = 0
        self.spawn_timer = float(self.cfg["spawn"]["interval"])
        self.spark_timer = 0.0
        self.ring_timer = 0.0
        self.ring_pulse = 0.0
        self.hurt_cd = 0.0
        self.hurt_flash = 0.0
        self.shake = 0.0
        self.boss_spawned = False
        self.pending_levelups = 0
        self.cards = []
        self.pointer_x = 0.0
        self.pointer_y = 0.0
        self.pointer_active = False
        self.events = []
        self._spawn_initial()

    def start(self):
        self.reset()
        self.state = "playing"

    def restart(self):
        self.start()

    # ------------------------------------------------------------------ input
    def set_pointer(self, x, y, active=True):
        self.pointer_x = float(x)
        self.pointer_y = float(y)
        self.pointer_active = bool(active)

    def pause_toggle(self):
        if self.state == "playing":
            self.paused = not self.paused

    # ------------------------------------------------------------------ update
    def update(self, dt):
        if self.state != "playing" or self.paused:
            return

        self.time += dt
        if self.time >= self.cfg["duration"]:
            self.time = self.cfg["duration"]
            self.state = "victory"
            self.events.append("victory")
            return

        self.hurt_cd = max(0.0, self.hurt_cd - dt)
        self.hurt_flash = max(0.0, self.hurt_flash - dt * 2.5)
        self.shake = max(0.0, self.shake - dt * 22.0)
        self.ring_pulse = max(0.0, self.ring_pulse - dt)

        self._move_hero(dt)
        self._spawn_update(dt)
        self._enemies_update(dt)
        if self.state != "playing":
            return
        self._weapons_update(dt)
        self._projectiles_update(dt)
        self._gems_update(dt)
        self._fx_update(dt)
        self._cleanup()

    def _move_hero(self, dt):
        if not self.pointer_active:
            return
        dx = self.pointer_x - self.hero.x
        dy = self.pointer_y - self.hero.y
        dist = _length(dx, dy)
        if dist <= 12.0:
            return
        step = min(self.hero.speed * dt, dist)
        self.hero.x += dx / dist * step
        self.hero.y += dy / dist * step

    # ---------------------------------------------------------------- spawning
    def _spawn_initial(self):
        row = self.cfg["spawn"]["table"][0]
        for _ in range(int(row["minimum"])):
            self._spawn_at(row["types"][self.rng.randrange(len(row["types"]))], 380.0)

    def _spawn_update(self, dt):
        spawn_cfg = self.cfg["spawn"]
        if not self.boss_spawned and self.time >= 90.0:
            self.boss_spawned = True
            self._spawn_at("demon", spawn_cfg["radius"])
            self.events.append("boss")

        self.spawn_timer -= dt
        if self.spawn_timer > 0.0:
            return
        self.spawn_timer += float(spawn_cfg["interval"])

        row = self._spawn_row()
        normal = sum(1 for e in self.enemies if not e.boss and not e.dead)
        missing = int(row["minimum"]) - normal
        if missing <= 0:
            return
        room = int(spawn_cfg["max_alive"]) - len(self.enemies)
        count = min(int(spawn_cfg["max_per_tick"]), missing, room)
        for _ in range(max(0, count)):
            kind = row["types"][self.rng.randrange(len(row["types"]))]
            self._spawn_at(kind, float(spawn_cfg["radius"]))

    def _spawn_row(self):
        row = self.cfg["spawn"]["table"][0]
        for candidate in self.cfg["spawn"]["table"]:
            if self.time >= float(candidate["from"]):
                row = candidate
            else:
                break
        return row

    def _spawn_at(self, kind, radius):
        angle = self.rng.random() * math.tau
        x = self.hero.x + math.cos(angle) * radius
        y = self.hero.y + math.sin(angle) * radius
        self.spawn_enemy(kind, x, y)

    def spawn_enemy(self, kind, x, y):
        data = self.cfg["enemies"][kind]
        enemy = Enemy(kind, x, y, data)
        self.enemies.append(enemy)
        return enemy

    # ---------------------------------------------------------------- enemies
    def _enemies_update(self, dt):
        boss_reposition = float(self.cfg["spawn"]["boss_reposition"])
        remove_distance = float(self.cfg["spawn"]["remove_distance"])
        hit_enemy = None
        hit_damage = -1.0

        for enemy in self.enemies:
            if enemy.dead:
                continue
            enemy.blade_cd = max(0.0, enemy.blade_cd - dt)
            enemy.hit_flash = max(0.0, enemy.hit_flash - dt)

            dx = self.hero.x - enemy.x
            dy = self.hero.y - enemy.y
            dist = _length(dx, dy)
            if dist > 0.001:
                enemy.x += dx / dist * enemy.speed * dt
                enemy.y += dy / dist * enemy.speed * dt

            # Recompute after moving.
            dx = self.hero.x - enemy.x
            dy = self.hero.y - enemy.y
            dist = _length(dx, dy)

            if enemy.boss:
                if dist > boss_reposition:
                    angle = math.atan2(dy, dx) if dist > 0.001 else self.rng.random() * math.tau
                    enemy.x = self.hero.x + math.cos(angle) * boss_reposition
                    enemy.y = self.hero.y + math.sin(angle) * boss_reposition
            elif dist > remove_distance:
                enemy.dead = True
                continue

            if dist < enemy.radius + self.hero.hit_radius and enemy.damage > hit_damage:
                hit_enemy = enemy
                hit_damage = enemy.damage

        if hit_enemy is not None and self.hurt_cd <= 0.0:
            self.hurt_cd = float(self.cfg["combat"]["contact_cooldown"])
            self.hero.hp -= hit_enemy.damage
            self.hurt_flash = 0.75
            self.shake = 6.0
            self.events.append("hurt")
            self._add_floater(
                self.hero.x, self.hero.y - 18, "-" + str(int(hit_enemy.damage)), (255, 110, 130)
            )
            if self.hero.hp <= 0.0:
                self.hero.hp = 0.0
                self.state = "gameover"
                self.events.append("gameover")

    # ---------------------------------------------------------------- weapons
    def _weapons_update(self, dt):
        self.spark_timer -= dt
        self.ring_timer -= dt

        if "spark" in self.weapons:
            stats = self._weapon_stats("spark")
            if self.spark_timer <= 0.0:
                target = self._nearest_enemy()
                if target is not None:
                    base = math.atan2(target.y - self.hero.y, target.x - self.hero.x)
                    count = int(stats["sparks"])
                    for i in range(count):
                        offset = (i - (count - 1) / 2.0) * 0.09
                        angle = base + offset
                        speed = float(self.cfg["weapons"]["spark"]["projectile_speed"])
                        self.projectiles.append(
                            Projectile(
                                self.hero.x, self.hero.y,
                                math.cos(angle) * speed, math.sin(angle) * speed,
                                float(stats["damage"]),
                                float(self.cfg["combat"]["projectile_life"]),
                                7.0,
                            )
                        )
                    self.spark_timer = float(stats["cooldown"])
                    self.events.append("shoot")

        if "blades" in self.weapons:
            stats = self._weapon_stats("blades")
            blades = int(stats["blades"])
            radius = float(self.cfg["weapons"]["blades"]["radius"])
            turn = float(self.cfg["weapons"]["blades"]["turn_seconds"])
            base_angle = self.time * math.tau / turn
            for i in range(blades):
                angle = base_angle + i * math.tau / blades
                bx = self.hero.x + math.cos(angle) * radius
                by = self.hero.y + math.sin(angle) * radius
                for enemy in self.enemies:
                    if enemy.dead or enemy.blade_cd > 0.0:
                        continue
                    if _length(enemy.x - bx, enemy.y - by) < enemy.radius + 9.0:
                        enemy.blade_cd = float(
                            self.cfg["weapons"]["blades"]["blade_hit_cooldown"]
                        )
                        self._damage_enemy(enemy, float(stats["damage"]), (255, 220, 150))

        if "ring" in self.weapons and self.ring_timer <= 0.0:
            stats = self._weapon_stats("ring")
            radius = float(stats["radius"])
            self.ring_pulse = 0.28
            self.ring_timer = float(stats["cooldown"])
            for enemy in list(self.enemies):
                if not enemy.dead and _length(enemy.x - self.hero.x, enemy.y - self.hero.y) < radius:
                    self._damage_enemy(enemy, float(stats["damage"]), (255, 150, 220))

    def _weapon_stats(self, key):
        level = self.weapons[key]
        return self.cfg["weapons"][key]["levels"][level - 1]

    def _nearest_enemy(self):
        best = None
        best_dist = float("inf")
        for enemy in self.enemies:
            if enemy.dead:
                continue
            d = _length(enemy.x - self.hero.x, enemy.y - self.hero.y)
            if d < best_dist:
                best = enemy
                best_dist = d
        return best

    # ------------------------------------------------------------ projectiles
    def _projectiles_update(self, dt):
        for proj in self.projectiles:
            if proj.dead:
                continue
            proj.x += proj.vx * dt
            proj.y += proj.vy * dt
            proj.life -= dt
            if proj.life <= 0.0:
                proj.dead = True
                continue
            for enemy in self.enemies:
                if enemy.dead:
                    continue
                if _length(enemy.x - proj.x, enemy.y - proj.y) < enemy.radius + proj.radius:
                    self._damage_enemy(enemy, proj.damage, (255, 240, 150))
                    proj.dead = True
                    break

    # ------------------------------------------------------------------ damage
    def _damage_enemy(self, enemy, amount, color):
        if enemy.dead or amount <= 0:
            return
        enemy.hp -= amount
        enemy.hit_flash = 0.1
        self._add_floater(
            enemy.x + self.rng.uniform(-4, 4),
            enemy.y - enemy.radius - 4,
            str(int(round(amount))), color,
        )
        self.events.append("hit")
        if enemy.hp <= 0.0:
            enemy.dead = True
            self.kills += 1
            self.flashes.append(Flash(enemy.x, enemy.y, enemy.radius * 1.6))
            for _ in range(7):
                angle = self.rng.random() * math.tau
                speed = self.rng.uniform(30.0, 120.0)
                self.particles.append(
                    Particle(
                        enemy.x, enemy.y, math.cos(angle) * speed, math.sin(angle) * speed,
                        self.rng.uniform(0.22, 0.5), self.rng.uniform(1.5, 3.5),
                        (255, 190, 120) if enemy.boss else (255, 150, 200),
                    )
                )
            if enemy.xp > 0:
                self.gems.append(Gem(enemy.x, enemy.y, enemy.xp, self.rng.random() * math.tau))

    # -------------------------------------------------------------------- gems
    def _gems_update(self, dt):
        speed = float(self.cfg["combat"]["gem_speed"])
        pickup = float(self.cfg["hero"]["pickup_radius"])
        for gem in self.gems:
            if gem.dead:
                continue
            dx = self.hero.x - gem.x
            dy = self.hero.y - gem.y
            dist = _length(dx, dy)
            if dist < self.hero.magnet and dist > 0.001:
                step = min(speed * dt, dist)
                gem.x += dx / dist * step
                gem.y += dy / dist * step
                dist = max(0.0, dist - step)
            if dist < pickup:
                gem.dead = True
                self.events.append("gem")
                self.gain_xp(gem.xp)
                if self.state != "playing":
                    break

    def gain_xp(self, amount):
        if amount <= 0:
            return
        self.hero.xp += int(amount)
        leveled = False
        while self.hero.xp >= self.hero.xp_next:
            self.hero.xp -= self.hero.xp_next
            self.hero.level += 1
            self.hero.xp_next += int(self.cfg["progression"]["increment"])
            self.pending_levelups += 1
            leveled = True
        if leveled:
            self.events.append("levelup")
            if self.state == "playing":
                self._begin_levelup()

    # --------------------------------------------------------------- level up
    def _begin_levelup(self):
        self.state = "levelup"
        self.paused = False
        self.cards = self._make_cards()

    def _make_cards(self):
        candidates = []
        weapon_count = len(self.weapons)

        for key, weapon in self.cfg["weapons"].items():
            level = self.weapons.get(key, 0)
            if level == 0 and weapon_count < 3:
                candidates.append({
                    "kind": "weapon_new", "key": key, "name": weapon["name"],
                    "level": 1, "desc": weapon["desc"],
                })
            elif 0 < level < int(weapon["max_level"]):
                candidates.append({
                    "kind": "weapon_up", "key": key, "name": weapon["name"],
                    "level": level + 1,
                    "desc": "Level " + str(level + 1) + ". " + weapon["desc"],
                })

        for key, item in self.cfg["items"].items():
            level = self.items.get(key, 0)
            if level < int(item["max_level"]):
                candidates.append({
                    "kind": "item", "key": key, "name": item["name"],
                    "level": level + 1,
                    "desc": "Level " + str(level + 1) + ". " + item["desc"],
                })

        if not candidates:
            heal = float(self.cfg["progression"]["heal_amount"])
            cards = [{
                "kind": "heal", "key": "heal", "name": "Heal " + str(int(heal)) + " HP",
                "level": 0, "desc": "Recover " + str(int(heal)) + " HP.",
            }]
            while len(cards) < 3:
                cards.append(dict(cards[0], name="Heal " + str(int(heal)) + " HP"))
            return cards

        self.rng.shuffle(candidates)
        cards = candidates[:3]
        if len(cards) < 3:
            heal = float(self.cfg["progression"]["heal_amount"])
            while len(cards) < 3:
                cards.append({
                    "kind": "heal", "key": "heal",
                    "name": "Heal " + str(int(heal)) + " HP",
                    "level": 0, "desc": "Recover " + str(int(heal)) + " HP.",
                })
        return cards

    def choose_card(self, index):
        if self.state != "levelup":
            return False
        if index < 0 or index >= len(self.cards):
            return False
        card = self.cards[index]
        self._apply_card(card)
        self.pending_levelups = max(0, self.pending_levelups - 1)
        if self.pending_levelups > 0:
            self.cards = self._make_cards()
        else:
            self.cards = []
            self.state = "playing"
        return True

    def _apply_card(self, card):
        kind = card["kind"]
        key = card["key"]
        if kind == "weapon_new":
            self.weapons[key] = 1
        elif kind == "weapon_up":
            self.weapons[key] = min(
                int(self.cfg["weapons"][key]["max_level"]), self.weapons[key] + 1
            )
        elif kind == "item":
            self.items[key] = min(
                int(self.cfg["items"][key]["max_level"]), self.items.get(key, 0) + 1
            )
            if key == "heart":
                level = self.items[key]
                self.hero.max_hp = float(self.cfg["hero"]["hp"]) + 20.0 * level
                self.hero.hp = min(self.hero.max_hp, self.hero.hp + 20.0)
            self._recompute_stats()
        elif kind == "heal":
            self.hero.hp = min(
                self.hero.max_hp,
                self.hero.hp + float(self.cfg["progression"]["heal_amount"]),
            )

    def _recompute_stats(self):
        self.hero.speed = self.hero.base_speed * (
            1.0 + float(self.cfg["items"]["boots"]["speed_pct"]) * self.items.get("boots", 0)
        )
        self.hero.magnet = self.hero.base_magnet + float(
            self.cfg["items"]["magnet"]["radius"]
        ) * self.items.get("magnet", 0)

    # --------------------------------------------------------------------- fx
    def _add_floater(self, x, y, text, color):
        if len(self.floaters) >= int(self.cfg["combat"]["max_floaters"]):
            self.floaters.pop(0)
        self.floaters.append(Floater(x, y, text, color))

    def _fx_update(self, dt):
        for floater in self.floaters:
            floater.y -= 28.0 * dt
            floater.life -= dt
        self.floaters = [f for f in self.floaters if f.life > 0]

        for particle in self.particles:
            particle.x += particle.vx * dt
            particle.y += particle.vy * dt
            particle.vx *= 0.92
            particle.vy *= 0.92
            particle.life -= dt
        self.particles = [p for p in self.particles if p.life > 0]
        for flash in self.flashes:
            flash.life -= dt
        self.flashes = [f for f in self.flashes if f.life > 0]

    def _cleanup(self):
        self.enemies = [e for e in self.enemies if not e.dead]
        self.projectiles = [p for p in self.projectiles if not p.dead]
        self.gems = [g for g in self.gems if not g.dead]
        max_particles = int(self.cfg["combat"]["max_particles"])
        if len(self.particles) > max_particles:
            self.particles = self.particles[-max_particles:]

    # ------------------------------------------------------------------ query
    def pop_events(self):
        events = self.events
        self.events = []
        return events

    @property
    def boss(self):
        for enemy in self.enemies:
            if enemy.boss and not enemy.dead:
                return enemy
        return None

    def normal_count(self):
        return sum(1 for e in self.enemies if not e.boss and not e.dead)

    def time_text(self):
        shown = int(min(self.time, self.cfg["duration"]))
        return str(shown // 60) + ":" + str(shown % 60).zfill(2)

    def time_left_text(self):
        total = int(self.cfg["duration"])
        left = max(0, total - int(self.time))
        return str(left // 60) + ":" + str(left % 60).zfill(2)
