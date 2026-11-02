"""Night Survivors — pygame-ce front end.

Run locally:      python main.py
Build for web:    python -m pygbag --build .
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import random
import sys
from pathlib import Path

import pygame

import rules

ROOT = Path(__file__).resolve().parent
CONFIG = json.loads((ROOT / "data" / "game.json").read_text(encoding="utf-8"))

WIDTH = int(CONFIG["screen"]["width"])
HEIGHT = int(CONFIG["screen"]["height"])
FPS = int(CONFIG["screen"]["fps"])
STEP = float(CONFIG["screen"]["step"])
DURATION = float(CONFIG["duration"])

BG = (10, 8, 18)
PANEL = (23, 17, 30)
PANEL_LIGHT = (34, 24, 44)
TEXT = (248, 240, 246)
MUTED = (173, 156, 173)
GOLD = (255, 210, 63)
PINK = (255, 159, 186)
BLUE = (105, 190, 255)
GREEN = (110, 231, 183)
RED = (255, 92, 116)
WHITE = (255, 255, 255)

SOUND_VOLUME = {
    "hit": 0.20,
    "shoot": 0.10,
    "gem": 0.20,
    "levelup": 0.36,
    "hurt": 0.38,
    "victory": 0.42,
    "gameover": 0.42,
}


def clamp(value, low, high):
    return low if value < low else high if value > high else value


def format_time(seconds):
    seconds = max(0, int(seconds))
    return str(seconds // 60) + ":" + str(seconds % 60).zfill(2)


class App:
    def __init__(self, smoke_frames=0):
        pygame.mixer.pre_init(22050, -16, 1, 512)
        pygame.init()
        pygame.display.set_caption("Night Survivors")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.world = rules.World(CONFIG)
        self.accumulator = 0.0
        self.running = True
        self.smoke_frames = int(smoke_frames)
        self.frame = 0
        self.camera_x = self.world.hero.x - WIDTH / 2
        self.camera_y = self.world.hero.y - HEIGHT / 2
        self.card_rects = []
        self.pointer_screen = (WIDTH // 2, HEIGHT // 2)
        self.last_hit_sound = -999
        self.last_gem_sound = -999
        self.last_shoot_sound = -999
        self.muted = False
        self.assets = self._load_assets()
        self.sounds = self._load_sounds()
        self.fonts = {}
        self.floor_bg = self._make_floor_bg()
        self.vignette = self._make_vignette()

    # ------------------------------------------------------------------ setup
    def _font(self, size, bold=False):
        key = (int(size), bool(bold))
        if key not in self.fonts:
            name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
            path = ROOT / "assets" / "fonts" / name
            try:
                self.fonts[key] = pygame.font.Font(str(path), int(size))
            except Exception:
                self.fonts[key] = pygame.font.Font(None, int(size))
        return self.fonts[key]

    def _load_image(self, name, size=None):
        path = ROOT / "assets" / name
        try:
            image = pygame.image.load(str(path)).convert_alpha()
        except Exception:
            image = pygame.Surface((48, 48), pygame.SRCALPHA)
            image.fill((255, 0, 255, 90))
        if size is not None:
            image = pygame.transform.scale(image, size)
        return image

    def _load_assets(self):
        small_shadow = pygame.Surface((34, 14), pygame.SRCALPHA)
        pygame.draw.ellipse(small_shadow, (0, 0, 0, 95), (0, 0, 34, 14))
        big_shadow = pygame.Surface((62, 18), pygame.SRCALPHA)
        pygame.draw.ellipse(big_shadow, (0, 0, 0, 105), (0, 0, 62, 18))
        assets = {
            "hero": self._load_image("hero.png"),
            "bat": self._load_image("bat.png"),
            "slime": self._load_image("slime.png"),
            "ghost": self._load_image("ghost.png"),
            "demon": self._load_image("demon.png", (96, 96)),
            "floor": self._load_image("floor.png"),
            "sword": self._load_image("sword.png", (34, 34)),
            "gem_blue": self._load_image("gem_blue.png", (26, 26)),
            "gem_pink": self._load_image("gem_pink.png", (26, 26)),
            "shadow_small": small_shadow,
            "shadow_big": big_shadow,
        }
        return assets

    def _load_sounds(self):
        sounds = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.set_num_channels(24)
        except Exception:
            return sounds
        for name, volume in SOUND_VOLUME.items():
            path = ROOT / "sounds" / (name + ".ogg")
            if not path.exists():
                path = ROOT / "sounds" / (name + ".wav")
            if not path.exists():
                continue
            try:
                sound = pygame.mixer.Sound(str(path))
                sound.set_volume(volume)
                sounds[name] = sound
            except Exception:
                pass
        return sounds

    def _make_floor_bg(self):
        tile = self.assets["floor"].get_width()
        surface = pygame.Surface((WIDTH + tile * 2, HEIGHT + tile * 2)).convert()
        for y in range(0, surface.get_height(), tile):
            for x in range(0, surface.get_width(), tile):
                surface.blit(self.assets["floor"], (x, y))
        tint = pygame.Surface((surface.get_width(), surface.get_height()), pygame.SRCALPHA)
        tint.fill((142, 112, 182))
        surface.blit(tint, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        dark = pygame.Surface((surface.get_width(), surface.get_height()), pygame.SRCALPHA)
        dark.fill((12, 8, 26, 118))
        surface.blit(dark, (0, 0))
        return surface

    def _make_vignette(self):
        surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for i in range(18):
            alpha = int(4 + i * 2.2)
            pygame.draw.rect(
                surface, (4, 3, 10, alpha),
                (i, i, WIDTH - i * 2, HEIGHT - i * 2), border_radius=18,
            )
        return surface

    # ------------------------------------------------------------------ input
    def _play(self, name):
        if self.muted:
            return
        sound = self.sounds.get(name)
        if sound is not None:
            sound.play()

    def _update_camera(self):
        self.camera_x = self.world.hero.x - WIDTH / 2
        self.camera_y = self.world.hero.y - HEIGHT / 2

    def _set_pointer(self, pos, active):
        if self.world.state == "playing" and not self.world.paused:
            self.pointer_screen = pos
            self.world.set_pointer(
                self.camera_x + pos[0], self.camera_y + pos[1], active
            )

    def _click(self, pos):
        state = self.world.state
        if state == "title":
            self.world.start()
            self._update_camera()
            self._set_pointer(pos, True)
        elif state == "levelup":
            for rect, index in self.card_rects:
                if rect.collidepoint(pos):
                    self.world.choose_card(index)
                    break
        elif state in ("victory", "gameover"):
            self.world.start()
            self._update_camera()
            self._set_pointer(pos, True)
        elif state == "playing":
            self._set_pointer(pos, True)

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_p:
                self.world.pause_toggle()
            elif event.key == pygame.K_m:
                self.muted = not self.muted
                if self.muted:
                    try:
                        pygame.mixer.stop()
                    except Exception:
                        pass
            elif event.key == pygame.K_r and self.world.state in ("victory", "gameover"):
                self.world.start()
                self._update_camera()
        elif event.type == pygame.MOUSEMOTION:
            self._set_pointer(event.pos, True)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._click(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            # Some browsers turn touch into mouse events; stop when the finger lifts.
            if getattr(event, "touch", False):
                self._set_pointer(event.pos, False)
        elif event.type == pygame.FINGERDOWN:
            pos = (int(event.x * WIDTH), int(event.y * HEIGHT))
            self._click(pos)
        elif event.type == pygame.FINGERMOTION:
            pos = (int(event.x * WIDTH), int(event.y * HEIGHT))
            self._set_pointer(pos, True)
        elif event.type == pygame.FINGERUP:
            pos = (int(event.x * WIDTH), int(event.y * HEIGHT))
            self._set_pointer(pos, False)

    # ----------------------------------------------------------------- update
    def update(self):
        self.world.update(STEP)
        self._update_camera()
        now = pygame.time.get_ticks()
        for event in self.world.pop_events():
            if event == "hit":
                if now - self.last_hit_sound > 45:
                    self._play("hit")
                    self.last_hit_sound = now
            elif event == "gem":
                if now - self.last_gem_sound > 45:
                    self._play("gem")
                    self.last_gem_sound = now
            elif event == "shoot":
                if now - self.last_shoot_sound > 80:
                    self._play("shoot")
                    self.last_shoot_sound = now
            elif event in ("levelup", "hurt", "victory", "gameover"):
                self._play(event)

    # ------------------------------------------------------------------- draw
    def draw(self):
        self.screen.fill(BG)
        shake_x = 0
        shake_y = 0
        if self.world.shake > 0:
            shake_x = int(random.uniform(-self.world.shake, self.world.shake))
            shake_y = int(random.uniform(-self.world.shake, self.world.shake))
        cam_x = self.camera_x + shake_x
        cam_y = self.camera_y + shake_y

        self._draw_floor(cam_x, cam_y)
        self._draw_gems(cam_x, cam_y)
        self._draw_ring(cam_x, cam_y)
        self._draw_enemies(cam_x, cam_y)
        self._draw_projectiles(cam_x, cam_y)
        self._draw_hero(cam_x, cam_y)
        self._draw_blades(cam_x, cam_y)
        self._draw_fx(cam_x, cam_y)

        if self.world.hurt_flash > 0:
            flash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            flash.fill((255, 45, 75, int(70 * self.world.hurt_flash)))
            self.screen.blit(flash, (0, 0))

        self.screen.blit(self.vignette, (0, 0))

        if self.world.state == "playing":
            self._draw_hud()

        if self.world.state == "title":
            self._draw_title()
        elif self.world.state == "levelup":
            self._draw_cards()
        elif self.world.paused and self.world.state == "playing":
            self._draw_pause()
        elif self.world.state in ("victory", "gameover"):
            self._draw_end()

    def _draw_floor(self, cam_x, cam_y):
        tile = self.assets["floor"].get_width()
        ox = -int(cam_x % tile)
        oy = -int(cam_y % tile)
        self.screen.blit(self.floor_bg, (ox, oy))

    def _draw_gems(self, cam_x, cam_y):
        for gem in self.world.gems:
            if gem.dead:
                continue
            sx = int(gem.x - cam_x)
            sy = int(gem.y - cam_y + math.sin(self.world.time * 6 + gem.phase) * 3)
            if -40 < sx < WIDTH + 40 and -40 < sy < HEIGHT + 40:
                image = self.assets["gem_blue"] if gem.xp == 1 else self.assets["gem_pink"]
                pygame.draw.circle(self.screen, (54, 34, 58), (sx, sy), 15)
                self.screen.blit(image, (sx - 13, sy - 13))

    def _draw_enemies(self, cam_x, cam_y):
        for enemy in self.world.enemies:
            if enemy.dead:
                continue
            sx = int(enemy.x - cam_x)
            sy = int(enemy.y - cam_y)
            margin = 110
            if sx < -margin or sx > WIDTH + margin or sy < -margin or sy > HEIGHT + margin:
                continue
            boss = enemy.boss
            size = 96 if boss else 48
            shadow_w = 62 if boss else 34
            shadow = self.assets["shadow_big"] if boss else self.assets["shadow_small"]
            self.screen.blit(shadow, (sx - shadow_w // 2, sy + size // 2 - 8))
            image = self.assets["demon"] if boss else self.assets.get(enemy.kind)
            if image is None:
                image = self.assets["bat"]
            ring = {
                "bat": (150, 105, 95),
                "slime": (90, 135, 105),
                "ghost": (105, 110, 155),
                "demon": (210, 75, 95),
            }.get(enemy.kind, (120, 100, 130))
            pygame.draw.circle(self.screen, ring, (sx, sy), enemy.radius + 5, 1)
            if enemy.hit_flash > 0:
                pygame.draw.circle(self.screen, (255, 255, 255), (sx, sy), enemy.radius + 4, 2)
            self.screen.blit(image, (sx - size // 2, sy - size // 2))
            if not boss and enemy.hp < enemy.max_hp:
                bar_w = 30
                frac = clamp(enemy.hp / enemy.max_hp, 0, 1)
                pygame.draw.rect(self.screen, (36, 25, 40), (sx - bar_w // 2, sy - 31, bar_w, 4), border_radius=2)
                pygame.draw.rect(self.screen, RED, (sx - bar_w // 2, sy - 31, int(bar_w * frac), 4), border_radius=2)

    def _draw_projectiles(self, cam_x, cam_y):
        for proj in self.world.projectiles:
            if proj.dead:
                continue
            sx = int(proj.x - cam_x)
            sy = int(proj.y - cam_y)
            if -20 < sx < WIDTH + 20 and -20 < sy < HEIGHT + 20:
                tail = (int(sx - proj.vx * 0.018), int(sy - proj.vy * 0.018))
                pygame.draw.line(self.screen, (255, 170, 90), tail, (sx, sy), 2)
                pygame.draw.circle(self.screen, (255, 245, 190), (sx, sy), 4)
                pygame.draw.circle(self.screen, (255, 255, 255), (sx, sy), 1)

    def _draw_hero(self, cam_x, cam_y):
        hero = self.world.hero
        sx = int(hero.x - cam_x)
        sy = int(hero.y - cam_y)
        self.screen.blit(self.assets["shadow_small"], (sx - 17, sy + 16))
        image = self.assets["hero"]
        if self.world.hurt_cd > 0 and int(self.world.time * 24) % 2 == 0:
            image = image.copy()
            image.set_alpha(105)
        self.screen.blit(image, (sx - 24, sy - 24))

    def _draw_blades(self, cam_x, cam_y):
        if "blades" not in self.world.weapons:
            return
        level = self.world.weapons["blades"]
        stats = CONFIG["weapons"]["blades"]["levels"][level - 1]
        radius = float(CONFIG["weapons"]["blades"]["radius"])
        turn = float(CONFIG["weapons"]["blades"]["turn_seconds"])
        base = self.world.time * math.tau / turn
        for i in range(int(stats["blades"])):
            angle = base + i * math.tau / int(stats["blades"])
            sx = int(self.world.hero.x + math.cos(angle) * radius - cam_x)
            sy = int(self.world.hero.y + math.sin(angle) * radius - cam_y)
            blade = pygame.transform.rotate(self.assets["sword"], -math.degrees(angle) - 90)
            rect = blade.get_rect(center=(sx, sy))
            pygame.draw.circle(self.screen, (70, 48, 72), (sx, sy), 19, 1)
            self.screen.blit(blade, rect)

    def _draw_ring(self, cam_x, cam_y):
        if "ring" not in self.world.weapons or self.world.ring_pulse <= 0:
            return
        level = self.world.weapons["ring"]
        stats = CONFIG["weapons"]["ring"]["levels"][level - 1]
        radius = int(stats["radius"])
        alpha = int(130 * (self.world.ring_pulse / 0.28))
        surface = pygame.Surface((radius * 2 + 6, radius * 2 + 6), pygame.SRCALPHA)
        pygame.draw.circle(
            surface, (255, 145, 215, alpha),
            (radius + 3, radius + 3), radius, 2,
        )
        self.screen.blit(
            surface,
            (int(self.world.hero.x - cam_x) - radius - 3, int(self.world.hero.y - cam_y) - radius - 3),
        )

    def _draw_fx(self, cam_x, cam_y):
        for flash in self.world.flashes:
            alpha = int(180 * (flash.life / flash.max_life))
            radius = int(flash.radius * (1.3 - 0.3 * flash.life / flash.max_life))
            surface = pygame.Surface((radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(surface, (255, 190, 120, alpha), (radius + 2, radius + 2), radius, 2)
            self.screen.blit(surface, (int(flash.x - cam_x) - radius - 2, int(flash.y - cam_y) - radius - 2))
        for particle in self.world.particles:
            x = int(particle.x - cam_x)
            y = int(particle.y - cam_y)
            if 0 <= x < WIDTH and 0 <= y < HEIGHT:
                pygame.draw.circle(self.screen, particle.color, (x, y), max(1, int(particle.size)))
        for floater in self.world.floaters:
            alpha = int(255 * clamp(floater.life / floater.max_life, 0, 1))
            image = self._font(13).render(floater.text, True, floater.color)
            image = image.copy()
            image.set_alpha(alpha)
            rect = image.get_rect(center=(int(floater.x - cam_x), int(floater.y - cam_y)))
            self.screen.blit(image, rect)

    # -------------------------------------------------------------------- hud
    def _draw_hud(self):
        hero = self.world.hero
        # HP / XP panel
        panel = pygame.Surface((184, 58), pygame.SRCALPHA)
        pygame.draw.rect(panel, (11, 8, 17, 205), (0, 0, 184, 58), border_radius=12)
        pygame.draw.rect(panel, (255, 255, 255, 18), (0, 0, 184, 58), 1, border_radius=12)
        self.screen.blit(panel, (12, 10))
        self._text("Lv " + str(hero.level), 14, GOLD, (22, 17), bold=True)
        self._bar(22, 36, 164, 10, hero.hp / max(1, hero.max_hp), RED, (43, 24, 34))
        self._bar(22, 51, 164, 5, hero.xp / max(1, hero.xp_next), BLUE, (26, 30, 46))

        # Timer / kills
        self._text(
            format_time(self.world.time) + " / " + format_time(DURATION),
            17, TEXT, (WIDTH - 12, 16), anchor="topright", bold=True,
        )
        self._text("Kills " + str(self.world.kills), 11, MUTED, (WIDTH - 12, 38), anchor="topright")

        # Boss bar
        boss = self.world.boss
        if boss is not None:
            label = self._font(10, True).render("DEMON", True, PINK)
            self.screen.blit(label, (WIDTH // 2 - label.get_width() // 2, 66))
            self._bar(WIDTH // 2 - 110, 80, 220, 7, boss.hp / boss.max_hp, PINK, (46, 24, 40))
            self._text("BOSS", 9, MUTED, (WIDTH // 2 + 110, 77), anchor="topright")

        # Bottom build
        pieces = []
        for key, level in self.world.weapons.items():
            short = CONFIG["weapons"][key].get("short", CONFIG["weapons"][key]["name"].split()[0])
            pieces.append(short + " " + str(level))
        for key, level in self.world.items.items():
            short = CONFIG["items"][key].get("short", CONFIG["items"][key]["name"].split()[0])
            pieces.append(short + " " + str(level))
        line = "   ".join(pieces) if pieces else "No upgrades"
        bar = pygame.Surface((WIDTH, 34), pygame.SRCALPHA)
        bar.fill((8, 6, 14, 190))
        self.screen.blit(bar, (0, HEIGHT - 34))
        self._text(line, 11, MUTED, (12, HEIGHT - 25))
        self._text("P pause  ·  M mute", 9, (105, 90, 110), (WIDTH - 12, HEIGHT - 23), anchor="topright")

    def _bar(self, x, y, width, height, fraction, color, back):
        fraction = clamp(fraction, 0, 1)
        pygame.draw.rect(self.screen, back, (x, y, width, height), border_radius=height // 2)
        if fraction > 0:
            pygame.draw.rect(
                self.screen, color,
                (x, y, max(2, int(width * fraction)), height),
                border_radius=height // 2,
            )

    # ----------------------------------------------------------------- overlays
    def _draw_title(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((7, 5, 13, 208))
        self.screen.blit(overlay, (0, 0))

        # Stars and a pale moon behind the title.
        rng = random.Random(21)
        for _ in range(34):
            x = rng.randrange(10, WIDTH - 10)
            y = rng.randrange(40, 520)
            radius = rng.choice((1, 1, 1, 2))
            shade = rng.randrange(120, 190)
            pygame.draw.circle(self.screen, (shade, shade - 18, shade + 8), (x, y), radius)
        for radius, color in ((150, (27, 18, 35)), (136, (32, 21, 40)), (125, (38, 25, 46))):
            pygame.draw.circle(self.screen, color, (WIDTH // 2, 224), radius)
        pygame.draw.circle(self.screen, (66, 43, 65), (WIDTH // 2, 224), 125, 1)

        self._text("NIGHT", 48, GOLD, (WIDTH // 2, 158), anchor="center", bold=True)
        self._text("SURVIVORS", 42, PINK, (WIDTH // 2, 208), anchor="center", bold=True)
        self._text("A 2-MINUTE SURVIVOR GAME", 10, (210, 180, 200), (WIDTH // 2, 264), anchor="center")

        pulse = 170 + int(70 * (0.5 + 0.5 * math.sin(pygame.time.get_ticks() / 420)))
        self._text("Tap or click to start", 17, WHITE, (WIDTH // 2, 336), anchor="center", alpha=pulse, bold=True)
        self._text("Move: mouse or finger    ·    P: pause", 11, MUTED, (WIDTH // 2, 380), anchor="center")

        t = pygame.time.get_ticks() / 1000.0
        hero = pygame.transform.scale(self.assets["hero"], (96, 96))
        hx, hy = WIDTH // 2, 548
        self.screen.blit(self.assets["shadow_big"], (hx - 31, hy + 34))
        self.screen.blit(hero, (hx - 48, hy - 48))
        for i, (bx, by) in enumerate(((54, 470), (332, 506), (286, 626))):
            yy = int(by + math.sin(t * 1.7 + i * 1.4) * 5)
            self.screen.blit(self.assets["bat"], (bx - 24, yy - 24))

        self._text("Art: Kenney.nl (CC0)   ·   Code: AI-assisted", 9, (126, 108, 128), (WIDTH // 2, 654), anchor="center")

    def _draw_cards(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((7, 5, 13, 222))
        self.screen.blit(overlay, (0, 0))
        self._text("LEVEL UP", 30, GOLD, (WIDTH // 2, 62), anchor="center", bold=True)
        self._text("Choose one", 12, MUTED, (WIDTH // 2, 92), anchor="center")

        self.card_rects = []
        mouse = pygame.mouse.get_pos()
        y = 120
        for index, card in enumerate(self.world.cards):
            rect = pygame.Rect(24, y, WIDTH - 48, 92)
            self.card_rects.append((rect, index))
            hover = rect.collidepoint(mouse)
            border = {
                "weapon_new": GOLD,
                "weapon_up": PINK,
                "item": BLUE,
                "heal": GREEN,
            }.get(card["kind"], PINK)
            bg = (39, 27, 48) if hover else (27, 19, 34)
            pygame.draw.rect(self.screen, bg, rect, border_radius=14)
            pygame.draw.rect(self.screen, border, rect, 2, border_radius=14)
            pygame.draw.rect(self.screen, border, (rect.x, rect.y + 14, 4, rect.height - 28), border_radius=2)
            self._text(card["name"], 18, TEXT, (rect.x + 18, rect.y + 14), bold=True)
            tag = "NEW" if card["kind"] == "weapon_new" else ("Lv " + str(card["level"]) if card["level"] else "HEAL")
            self._text(tag, 10, border, (rect.right - 16, rect.y + 18), anchor="topright", bold=True)
            self._text(card["desc"], 12, MUTED, (rect.x + 18, rect.y + 44))
            y += 104
        self._text("Tap a card", 10, (120, 102, 120), (WIDTH // 2, HEIGHT - 30), anchor="center")

    def _draw_pause(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((7, 5, 13, 180))
        self.screen.blit(overlay, (0, 0))
        self._text("PAUSED", 38, TEXT, (WIDTH // 2, HEIGHT // 2 - 24), anchor="center", bold=True)
        self._text("Press P to resume", 13, MUTED, (WIDTH // 2, HEIGHT // 2 + 28), anchor="center")

    def _draw_end(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((7, 5, 13, 214))
        self.screen.blit(overlay, (0, 0))
        victory = self.world.state == "victory"
        self._text("VICTORY" if victory else "GAME OVER", 38, GREEN if victory else RED, (WIDTH // 2, 190), anchor="center", bold=True)
        self._text(
            "You survived 2:00" if victory else "The night got you",
            13, MUTED, (WIDTH // 2, 238), anchor="center",
        )
        self._text("Time  " + format_time(self.world.time) + " / 2:00", 14, TEXT, (WIDTH // 2, 292), anchor="center")
        self._text("Kills  " + str(self.world.kills), 14, TEXT, (WIDTH // 2, 320), anchor="center")
        self._text("Level  " + str(self.world.hero.level), 14, TEXT, (WIDTH // 2, 348), anchor="center")
        self._text("Tap or click to play again", 16, WHITE, (WIDTH // 2, 430), anchor="center", bold=True)
        self._text("Same night. New run.", 10, (125, 105, 125), (WIDTH // 2, 470), anchor="center")

    # ------------------------------------------------------------------- text
    def _text(self, text, size, color, pos, anchor="topleft", alpha=255, bold=False):
        image = self._font(size, bold).render(str(text), True, color)
        if alpha < 255:
            image = image.copy()
            image.set_alpha(alpha)
        rect = image.get_rect()
        setattr(rect, anchor, pos)
        self.screen.blit(image, rect)

    # -------------------------------------------------------------------- run
    async def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            dt = min(dt, 0.25)
            self.frame += 1

            if self.smoke_frames:
                self._post_smoke_events()

            for event in pygame.event.get():
                self.handle_event(event)

            self.accumulator += dt
            steps = 0
            while self.accumulator >= STEP and steps < 5:
                self.update()
                self.accumulator -= STEP
                steps += 1

            self.draw()
            pygame.display.flip()
            await asyncio.sleep(0)

            if self.smoke_frames and self.frame >= self.smoke_frames:
                self._finish_smoke()
                break

        pygame.quit()

    def _post_smoke_events(self):
        if self.frame == 3:
            pygame.event.post(pygame.event.Event(pygame.MOUSEMOTION, pos=(210, 320)))
            pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(210, 320)))
        elif self.frame == 12:
            pygame.event.post(pygame.event.Event(pygame.MOUSEMOTION, pos=(260, 360)))
        elif self.frame == 30:
            pygame.event.post(pygame.event.Event(pygame.FINGERDOWN, x=0.35, y=0.65, finger_id=1, touch_id=1))
            pygame.event.post(pygame.event.Event(pygame.FINGERMOTION, x=0.55, y=0.55, finger_id=1, touch_id=1, dx=0.2, dy=-0.1))
        elif self.frame == 45:
            pygame.event.post(pygame.event.Event(pygame.FINGERUP, x=0.55, y=0.55, finger_id=1, touch_id=1))
        elif self.frame == 55:
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_p))
        elif self.frame == 65:
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_p))
        elif self.frame == 75:
            self.world.gain_xp(5)

    def _finish_smoke(self):
        path = ROOT / "smoke.png"
        try:
            pygame.image.save(self.screen, str(path))
        except Exception as exc:
            print("screenshot failed:", exc)
        print(
            "SMOKE state=%s time=%.2f hp=%.0f enemies=%d kills=%d level=%d weapons=%s items=%s cards=%d screenshot=%s"
            % (
                self.world.state, self.world.time, self.world.hero.hp,
                len(self.world.enemies), self.world.kills, self.world.hero.level,
                self.world.weapons, self.world.items, len(self.world.cards), path,
            )
        )


async def main():
    smoke = int(os.environ.get("NIGHT_SURVIVORS_SMOKE", "0") or "0")
    app = App(smoke_frames=smoke)
    await app.run()


if __name__ == "__main__":
    asyncio.run(main())
