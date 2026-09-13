# RIO.py


"""
RIO

Autor: feito por BitOS (apenas um desenvolvedor)
"""

import pygame
import random
import math
import sys
import os
import json

# ============================================================
#  INICIALIZAÇÃO SEGURA DE ÁUDIO
#  (se não houver arquivos de som/dispositivo de áudio, o jogo
#   continua rodando normalmente sem travar)
# ============================================================
AUDIO_OK = True
try:
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.init()
    pygame.mixer.init()
except Exception:
    AUDIO_OK = False
    try:
        pygame.init()
    except Exception:
        pass

pygame.font.init()

# ============================================================
#  VIBRAÇÃO (Android) - à prova de falhas
#  Em Android (via python-for-android/plyer) tenta vibrar o
#  aparelho. Em qualquer outro ambiente, não faz nada.
# ============================================================
def vibrate(duration_ms=40):
    try:
        from plyer import vibrator
        vibrator.vibrate(duration_ms / 1000.0)
        return
    except Exception:
        pass
    try:
        from jnius import autoclass
        Context = autoclass("android.content.Context")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        vib = PythonActivity.mActivity.getSystemService(Context.VIBRATOR_SERVICE)
        vib.vibrate(duration_ms)
    except Exception:
        pass


# ============================================================
#  CONFIGURAÇÕES GERAIS  (MODO PAISAGEM)
# ============================================================
LOGICAL_WIDTH = 960
LOGICAL_HEIGHT = 540
FPS = 60

SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "save_rio.json")

# ---- Paleta Neon ----
COLOR_BG = (10, 8, 14)
COLOR_FLOOR = (18, 14, 22)
NEON_PINK = (255, 20, 147)      # Rosa Choque
NEON_BLUE = (0, 200, 255)       # Azul Piscina
NEON_YELLOW = (255, 230, 0)     # Amarelo
NEON_LIME = (150, 255, 0)       # Verde Limão
NEON_ORANGE = (255, 140, 0)
NEON_RED = (255, 30, 60)
BLOOD_RED = (130, 0, 20)
WHITE = (240, 240, 240)
BLACK = (0, 0, 0)
GREY = (60, 55, 65)
DARK_GREY = (35, 32, 40)


# ============================================================
#  SISTEMA DE ÁUDIO (à prova de falhas)
# ============================================================
class AudioManager:
    """Carrega e toca sons/música. Se algo faltar, ignora silenciosamente."""

    def __init__(self):
        self.sounds = {}
        self.music_loaded = False
        if not AUDIO_OK:
            return
        sound_files = {
            "shot": "assets/sfx_shot.wav",
            "shotgun": "assets/sfx_shotgun.wav",
            "smg": "assets/sfx_smg.wav",
            "death": "assets/sfx_death.wav",
            "reload": "assets/sfx_reload.wav",
            "pickup": "assets/sfx_pickup.wav",
            "boss_hit": "assets/sfx_boss_hit.wav",
            "player_hurt": "assets/sfx_player_hurt.wav",
            "explosion": "assets/sfx_explosion.wav",
            "shield": "assets/sfx_shield.wav",
            "no_ammo": "assets/sfx_no_ammo.wav",
            "pause": "assets/sfx_pause.wav",
        }
        base = os.path.dirname(os.path.abspath(__file__))
        for key, rel_path in sound_files.items():
            full_path = os.path.join(base, rel_path)
            try:
                self.sounds[key] = pygame.mixer.Sound(full_path)
            except Exception:
                self.sounds[key] = None

        try:
            music_path = os.path.join(base, "assets/music_synthwave.ogg")
            pygame.mixer.music.load(music_path)
            self.music_loaded = True
        except Exception:
            self.music_loaded = False

    def play(self, key, volume=1.0):
        if not AUDIO_OK:
            return
        snd = self.sounds.get(key)
        if snd is not None:
            try:
                snd.set_volume(volume)
                snd.play()
            except Exception:
                pass

    def play_music(self, loops=-1, volume=0.5):
        if not AUDIO_OK or not self.music_loaded:
            return
        try:
            pygame.mixer.music.set_volume(volume)
            pygame.mixer.music.play(loops)
        except Exception:
            pass


# ============================================================
#  GERENCIADOR DE PROGRESSO (SAVE/LOAD)
# ============================================================
class SaveManager:
    @staticmethod
    def load():
        try:
            with open(SAVE_FILE, "r") as f:
                data = json.load(f)
                return {
                    "current_level": int(data.get("current_level", 1)),
                    "high_score": int(data.get("high_score", 0)),
                }
        except Exception:
            return {"current_level": 1, "high_score": 0}

    @staticmethod
    def save(level, high_score):
        try:
            with open(SAVE_FILE, "w") as f:
                json.dump({"current_level": level, "high_score": high_score}, f)
        except Exception:
            pass


# ============================================================
#  UTILITÁRIOS
# ============================================================
def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def vec_from_angle(angle_rad):
    return pygame.math.Vector2(math.cos(angle_rad), math.sin(angle_rad))


def rects_overlap_circle(rect, center, radius):
    """Colisão simples círculo x retângulo."""
    closest_x = clamp(center.x, rect.left, rect.right)
    closest_y = clamp(center.y, rect.top, rect.bottom)
    dx = center.x - closest_x
    dy = center.y - closest_y
    return (dx * dx + dy * dy) < (radius * radius)


# ============================================================
#  JOYSTICK VIRTUAL (visível na tela, base + manete)
# ============================================================
class VirtualStick:
    def __init__(self, radius=68, dead_zone=10, base_color=WHITE, knob_color=WHITE):
        self.radius = radius
        self.dead_zone = dead_zone
        self.active = False
        self.finger_id = None
        self.base = pygame.math.Vector2(0, 0)
        self.knob = pygame.math.Vector2(0, 0)
        self.base_color = base_color
        self.knob_color = knob_color

    def start(self, finger_id, pos, anchor=None):
        self.active = True
        self.finger_id = finger_id
        # se um "anchor" (posição fixa) for dado, o joystick nasce ali;
        # senão nasce embaixo do dedo (joystick flutuante)
        origin = pygame.math.Vector2(anchor) if anchor is not None else pygame.math.Vector2(pos)
        self.base = origin
        self.knob = pygame.math.Vector2(pos)
        self._clamp_knob()

    def move(self, pos):
        if not self.active:
            return
        self.knob = pygame.math.Vector2(pos)
        self._clamp_knob()

    def _clamp_knob(self):
        delta = self.knob - self.base
        if delta.length() > self.radius:
            delta.scale_to_length(self.radius)
            self.knob = self.base + delta

    def stop(self):
        self.active = False
        self.finger_id = None

    def get_direction(self):
        """Retorna vetor normalizado da direção, ou None se dentro da zona morta."""
        delta = self.knob - self.base
        if delta.length() < self.dead_zone:
            return None
        return delta.normalize()

    def get_strength(self):
        delta = self.knob - self.base
        return clamp(delta.length() / self.radius, 0.0, 1.0)

    def draw(self, surf):
        if not self.active:
            return
        size = self.radius * 2 + 24
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        center = (size // 2, size // 2)
        pygame.draw.circle(s, (*self.base_color, 45), center, self.radius)
        pygame.draw.circle(s, (*self.base_color, 130), center, self.radius, 3)
        knob_offset = self.knob - self.base
        knob_pos = (center[0] + knob_offset.x, center[1] + knob_offset.y)
        pygame.draw.circle(s, (*self.knob_color, 200), (int(knob_pos[0]), int(knob_pos[1])), 28)
        pygame.draw.circle(s, (255, 255, 255, 230), (int(knob_pos[0]), int(knob_pos[1])), 28, 3)
        surf.blit(s, (self.base.x - size // 2, self.base.y - size // 2))


# ============================================================
#  DEFINIÇÃO DE ARMAS
# ============================================================
WEAPONS = {
    "pistol": {
        "label": "PISTOLA",
        "fire_rate": 260,
        "damage": 1,
        "spread_deg": 2,
        "bullets_per_shot": 1,
        "bullet_speed": 900,
        "ammo": -1,
        "color": NEON_YELLOW,
        "sound": "shot",
    },
    "shotgun": {
        "label": "ESCOPETA",
        "fire_rate": 520,
        "damage": 1,
        "spread_deg": 26,
        "bullets_per_shot": 3,
        "bullet_speed": 820,
        "ammo": 12,
        "color": NEON_PINK,
        "sound": "shotgun",
    },
    "smg": {
        "label": "METRALHADORA",
        "fire_rate": 70,
        "damage": 1,
        "spread_deg": 9,
        "bullets_per_shot": 1,
        "bullet_speed": 950,
        "ammo": 60,
        "color": NEON_BLUE,
        "sound": "smg",
    },
}


# ============================================================
#  PARTÍCULAS (faíscas / impacto / explosão)
# ============================================================
class Particle:
    __slots__ = ("pos", "vel", "life", "max_life", "color", "radius")

    def __init__(self, pos, vel, life, color, radius):
        self.pos = pygame.math.Vector2(pos)
        self.vel = pygame.math.Vector2(vel)
        self.life = life
        self.max_life = life
        self.color = color
        self.radius = radius

    def update(self, dt):
        self.pos += self.vel * dt
        self.vel *= 0.90
        self.life -= dt

    def is_dead(self):
        return self.life <= 0

    def draw(self, surf):
        t = max(0.0, self.life / self.max_life)
        r = max(1, int(self.radius * t))
        pygame.draw.circle(surf, self.color, (int(self.pos.x), int(self.pos.y)), r)


# ============================================================
#  TEXTO FLUTUANTE (pontos de combo, "SEM MUNIÇÃO", etc.)
# ============================================================
class FloatingText:
    def __init__(self, pos, text, color, life=0.8, size=22, rise=40):
        self.pos = pygame.math.Vector2(pos)
        self.text = text
        self.color = color
        self.life = life
        self.max_life = life
        self.size = size
        self.rise = rise

    def update(self, dt):
        self.life -= dt

    def is_dead(self):
        return self.life <= 0

    def draw(self, surf, font_cache):
        t = max(0.0, self.life / self.max_life)
        y_off = (1 - t) * self.rise
        font = font_cache
        label = font.render(self.text, True, self.color)
        label.set_alpha(int(255 * t))
        surf.blit(label, (self.pos.x - label.get_width() / 2, self.pos.y - y_off))


# ============================================================
#  MANCHAS DE SANGUE PERMANENTES
# ============================================================
class BloodStain:
    __slots__ = ("pos", "radius")

    def __init__(self, pos, radius):
        self.pos = pygame.math.Vector2(pos)
        self.radius = radius


# ============================================================
#  OBSTÁCULOS (paredes internas / caixas destrutíveis / barris explosivos)
# ============================================================
class Obstacle:
    def __init__(self, rect, kind="wall"):
        self.rect = rect
        self.kind = kind  # "wall", "crate" ou "barrel"
        if kind == "crate":
            self.hp = 3
        elif kind == "barrel":
            self.hp = 1
        else:
            self.hp = -1
        self.alive = True

    def hit(self):
        if self.kind in ("crate", "barrel"):
            self.hp -= 1
            if self.hp <= 0:
                self.alive = False
                return True
        return False

    def draw(self, surf):
        if self.kind == "wall":
            pygame.draw.rect(surf, DARK_GREY, self.rect)
            pygame.draw.rect(surf, GREY, self.rect, 2)
        elif self.kind == "crate":
            pygame.draw.rect(surf, (90, 60, 30), self.rect)
            pygame.draw.rect(surf, (140, 100, 50), self.rect, 2)
        else:  # barrel
            pygame.draw.ellipse(surf, NEON_ORANGE, self.rect)
            pygame.draw.ellipse(surf, (120, 40, 0), self.rect, 3)


# ============================================================
#  PICKUPS (arma, munição extra, colete/escudo)
# ============================================================
class Pickup:
    def __init__(self, pos, kind, weapon_key=None):
        self.pos = pygame.math.Vector2(pos)
        self.kind = kind  # "weapon", "ammo", "armor"
        self.weapon_key = weapon_key
        self.radius = 14
        self.timer = 0.0

    def update(self, dt):
        self.timer += dt

    def draw(self, surf):
        bob = math.sin(self.timer * 4) * 4
        pos = (int(self.pos.x), int(self.pos.y + bob))
        if self.kind == "weapon":
            color = WEAPONS[self.weapon_key]["color"]
            pygame.draw.circle(surf, color, pos, self.radius, 3)
            pygame.draw.circle(surf, color, pos, 4)
        elif self.kind == "ammo":
            pygame.draw.rect(surf, NEON_YELLOW, (pos[0] - 10, pos[1] - 10, 20, 20), 3)
            pygame.draw.rect(surf, NEON_YELLOW, (pos[0] - 4, pos[1] - 4, 8, 8))
        elif self.kind == "armor":
            pygame.draw.circle(surf, NEON_BLUE, pos, self.radius, 3)
            pygame.draw.polygon(surf, NEON_BLUE, [
                (pos[0], pos[1] - 8), (pos[0] - 7, pos[1] + 6), (pos[0] + 7, pos[1] + 6)
            ])


# ============================================================
#  PROJÉTEIS
# ============================================================
class Bullet:
    __slots__ = ("pos", "vel", "owner", "damage", "radius", "color", "alive")

    def __init__(self, pos, vel, owner, damage, color, radius=4):
        self.pos = pygame.math.Vector2(pos)
        self.vel = pygame.math.Vector2(vel)
        self.owner = owner  # "player", "enemy", "boss"
        self.damage = damage
        self.radius = radius
        self.color = color
        self.alive = True

    def update(self, dt):
        self.pos += self.vel * dt

    def draw(self, surf):
        pygame.draw.circle(surf, self.color, (int(self.pos.x), int(self.pos.y)), self.radius)


# ============================================================
#  ENTIDADE BASE
# ============================================================
class Entity:
    def __init__(self, pos, radius, hp):
        self.pos = pygame.math.Vector2(pos)
        self.radius = radius
        self.hp = hp
        self.max_hp = hp
        self.alive = True
        self.angle = 0.0

    def take_damage(self, amount):
        self.hp -= amount
        if self.hp <= 0:
            self.alive = False


# ============================================================
#  JOGADOR
# ============================================================
class Player(Entity):
    def __init__(self, pos):
        # Estilo "Hotline Miami": o jogador morre em UM único hit (mortes instantâneas),
        # a menos que tenha um colete (escudo) ativo.
        super().__init__(pos, radius=16, hp=1)
        self.speed = 260
        self.weapon_key = "pistol"
        self.ammo = -1
        self.fire_cooldown = 0.0
        self.move_dir = pygame.math.Vector2(0, 0)
        self.shield = 0  # quantidade de hits extras que o colete absorve
        self.shield_flash = 0.0

    def switch_weapon(self, weapon_key):
        self.weapon_key = weapon_key
        self.ammo = WEAPONS[weapon_key]["ammo"]

    def add_ammo(self, amount):
        weapon = WEAPONS[self.weapon_key]
        if weapon["ammo"] != -1:
            self.ammo = min(self.ammo + amount, 999)

    def take_hit(self):
        """Aplica um hit fatal, mas o colete (se houver) absorve primeiro."""
        if self.shield > 0:
            self.shield -= 1
            self.shield_flash = 0.25
            return False  # sobreviveu
        self.take_damage(self.hp)
        return True  # morreu

    def try_shoot(self, dt_ms, bullets, particles, audio, shake_callback, floaters=None):
        if self.fire_cooldown > 0:
            return
        weapon = WEAPONS[self.weapon_key]
        if weapon["ammo"] != -1 and self.ammo <= 0:
            self.switch_weapon("pistol")
            weapon = WEAPONS[self.weapon_key]
            audio.play("no_ammo", 0.5)
            if floaters is not None:
                floaters.append(FloatingText(self.pos + (0, -30), "SEM MUNIÇÃO!", NEON_RED, 0.7, 16))

        self.fire_cooldown = weapon["fire_rate"]
        if weapon["ammo"] != -1:
            self.ammo -= 1

        for _ in range(weapon["bullets_per_shot"]):
            spread = math.radians(random.uniform(-weapon["spread_deg"], weapon["spread_deg"]))
            shot_angle = self.angle + spread
            direction = vec_from_angle(shot_angle)
            bpos = self.pos + direction * (self.radius + 6)
            bvel = direction * weapon["bullet_speed"]
            bullets.append(Bullet(bpos, bvel, "player", weapon["damage"], weapon["color"]))

        muzzle = self.pos + vec_from_angle(self.angle) * (self.radius + 8)
        for _ in range(6):
            spark_angle = self.angle + random.uniform(-0.6, 0.6)
            speed = random.uniform(80, 220)
            vel = vec_from_angle(spark_angle) * speed
            particles.append(Particle(muzzle, vel, random.uniform(0.08, 0.18), NEON_YELLOW, 3))

        audio.play(weapon["sound"], 0.6)
        shake_callback(4)

    def update(self, dt, dt_ms, obstacles):
        if self.fire_cooldown > 0:
            self.fire_cooldown -= dt_ms
        if self.shield_flash > 0:
            self.shield_flash -= dt

        # o ângulo NÃO é definido aqui — é controlado pelo stick de mira em Game
        if self.move_dir.length_squared() > 0.0001:
            move = self.move_dir.normalize() * self.speed * dt
            new_pos = self.pos + move
            new_rect = pygame.Rect(new_pos.x - self.radius, new_pos.y - self.radius,
                                    self.radius * 2, self.radius * 2)
            blocked = False
            for obs in obstacles:
                if obs.alive and obs.rect.colliderect(new_rect):
                    blocked = True
                    break
            if not blocked:
                self.pos = new_pos

    def draw(self, surf):
        color = NEON_LIME
        if self.shield_flash > 0:
            color = WHITE
        elif self.shield > 0:
            color = NEON_BLUE
        pygame.draw.circle(surf, color, (int(self.pos.x), int(self.pos.y)), self.radius)
        pygame.draw.circle(surf, WHITE, (int(self.pos.x), int(self.pos.y)), self.radius, 2)
        tip = self.pos + vec_from_angle(self.angle) * (self.radius + 14)
        pygame.draw.line(surf, WHITE, self.pos, tip, 4)


# ============================================================
#  INIMIGO
# ============================================================
class Enemy(Entity):
    def __init__(self, pos, speed, hp=1):
        super().__init__(pos, radius=15, hp=hp)
        self.speed = speed
        self.flank_offset = random.uniform(-1, 1)
        self.flank_phase = random.uniform(0, math.pi * 2)
        self.fire_cooldown = random.uniform(500, 1500)
        self.can_shoot = random.random() < 0.35

    def steer_away_from_obstacles(self, desired_dir, obstacles):
        probe_dist = self.radius + 40
        probe_point = self.pos + desired_dir * probe_dist
        for obs in obstacles:
            if not obs.alive:
                continue
            if rects_overlap_circle(obs.rect, probe_point, self.radius + 6):
                perp = pygame.math.Vector2(-desired_dir.y, desired_dir.x)
                if random.random() < 0.5:
                    perp = -perp
                desired_dir = (desired_dir * 0.4 + perp * 0.9)
                if desired_dir.length_squared() > 0.0001:
                    desired_dir = desired_dir.normalize()
                break
        return desired_dir

    def update(self, dt, dt_ms, player, obstacles, bullets, particles):
        to_player = player.pos - self.pos
        dist = to_player.length()
        base_dir = to_player.normalize() if dist > 0.001 else pygame.math.Vector2(1, 0)

        self.flank_phase += dt * 2.0
        perp = pygame.math.Vector2(-base_dir.y, base_dir.x) * self.flank_offset
        weave = math.sin(self.flank_phase) * 0.5
        desired_dir = base_dir + perp * weave
        if desired_dir.length_squared() > 0.0001:
            desired_dir = desired_dir.normalize()

        desired_dir = self.steer_away_from_obstacles(desired_dir, obstacles)

        if dist > 46:
            move = desired_dir * self.speed * dt
            new_pos = self.pos + move
            new_rect = pygame.Rect(new_pos.x - self.radius, new_pos.y - self.radius,
                                    self.radius * 2, self.radius * 2)
            blocked = any(o.alive and o.rect.colliderect(new_rect) for o in obstacles)
            if not blocked:
                self.pos = new_pos

        self.angle = math.atan2(to_player.y, to_player.x)

        if self.can_shoot:
            self.fire_cooldown -= dt_ms
            if self.fire_cooldown <= 0 and dist < 480:
                self.fire_cooldown = random.uniform(900, 1700)
                direction = vec_from_angle(self.angle)
                bpos = self.pos + direction * (self.radius + 4)
                bvel = direction * 420
                bullets.append(Bullet(bpos, bvel, "enemy", 1, NEON_RED, 5))

    def draw(self, surf):
        pygame.draw.circle(surf, NEON_PINK, (int(self.pos.x), int(self.pos.y)), self.radius)
        pygame.draw.circle(surf, BLACK, (int(self.pos.x), int(self.pos.y)), self.radius, 2)
        tip = self.pos + vec_from_angle(self.angle) * (self.radius + 10)
        pygame.draw.line(surf, BLACK, self.pos, tip, 3)


# ============================================================
#  CHEFÃO (BOSS)
# ============================================================
class Boss(Entity):
    def __init__(self, pos, level):
        hp = 60 + level * 3
        super().__init__(pos, radius=44, hp=hp)
        self.speed = 90
        self.target = pygame.math.Vector2(pos)
        self.retarget_timer = 0.0
        self.fire_timer = 0.0
        self.fire_interval = 1700
        self.bullets_in_ring = 16

    def pick_new_target(self, bounds):
        self.target = pygame.math.Vector2(
            random.uniform(bounds.left + 80, bounds.right - 80),
            random.uniform(bounds.top + 80, bounds.bottom - 80),
        )

    def update(self, dt, dt_ms, player, bullets, bounds):
        self.retarget_timer -= dt_ms
        if self.retarget_timer <= 0:
            self.pick_new_target(bounds)
            self.retarget_timer = random.uniform(1500, 3000)

        to_target = self.target - self.pos
        if to_target.length() > 5:
            self.pos += to_target.normalize() * self.speed * dt

        to_player = player.pos - self.pos
        self.angle = math.atan2(to_player.y, to_player.x)

        self.fire_timer -= dt_ms
        if self.fire_timer <= 0:
            self.fire_timer = self.fire_interval
            for i in range(self.bullets_in_ring):
                a = (2 * math.pi / self.bullets_in_ring) * i
                direction = vec_from_angle(a)
                bvel = direction * 260
                bullets.append(Bullet(self.pos + direction * self.radius, bvel, "boss", 1, NEON_RED, 6))

    def draw(self, surf):
        pygame.draw.circle(surf, (200, 0, 60), (int(self.pos.x), int(self.pos.y)), self.radius)
        pygame.draw.circle(surf, NEON_YELLOW, (int(self.pos.x), int(self.pos.y)), self.radius, 4)
        tip = self.pos + vec_from_angle(self.angle) * (self.radius + 18)
        pygame.draw.line(surf, NEON_YELLOW, self.pos, tip, 5)

    def draw_healthbar(self, surf, font):
        bar_w = LOGICAL_WIDTH - 300
        bar_h = 18
        x = LOGICAL_WIDTH // 2 - bar_w // 2
        y = 14
        pct = max(0, self.hp / self.max_hp)
        pygame.draw.rect(surf, DARK_GREY, (x, y, bar_w, bar_h))
        pygame.draw.rect(surf, NEON_RED, (x, y, int(bar_w * pct), bar_h))
        pygame.draw.rect(surf, WHITE, (x, y, bar_w, bar_h), 2)
        label = font.render("CHEFÃO", True, WHITE)
        surf.blit(label, (x + bar_w // 2 - label.get_width() // 2, y - 20))


# ============================================================
#  GERADOR PROCEDURAL DE NÍVEIS
# ============================================================
def is_boss_level(level):
    return level % 20 == 0


def generate_level_params(level):
    enemy_count = min(3 + level // 2, 26)
    speed = 70 + min(level * 1.6, 160)
    obstacle_count = min(3 + level // 6, 14)
    crate_chance = clamp(0.45 - level * 0.002, 0.12, 0.45)
    barrel_chance = clamp(0.08 + level * 0.001, 0.08, 0.20)
    return {
        "enemy_count": enemy_count,
        "enemy_speed": speed,
        "obstacle_count": obstacle_count,
        "crate_chance": crate_chance,
        "barrel_chance": barrel_chance,
    }


# ============================================================
#  JOGO PRINCIPAL
# ============================================================
class Game:
    STATE_MENU = "menu"
    STATE_PLAYING = "playing"
    STATE_LEVEL_CLEAR = "level_clear"
    STATE_GAME_OVER = "game_over"
    STATE_PAUSED = "paused"

    def __init__(self):
        try:
            flags = pygame.FULLSCREEN | pygame.SCALED
            self.screen = pygame.display.set_mode((LOGICAL_WIDTH, LOGICAL_HEIGHT), flags)
        except Exception:
            self.screen = pygame.display.set_mode((LOGICAL_WIDTH, LOGICAL_HEIGHT))

        pygame.display.set_caption("RIO")
        self.clock = pygame.time.Clock()
        self.font_big = pygame.font.SysFont("arial", 46, bold=True)
        self.font_med = pygame.font.SysFont("arial", 24, bold=True)
        self.font_small = pygame.font.SysFont("arial", 17)
        self.font_tiny = pygame.font.SysFont("arial", 15)

        self.audio = AudioManager()
        self.audio.play_music()

        # Área de jogo em paisagem: uma faixa de HUD fina no topo, resto é arena.
        self.play_area = pygame.Rect(16, 54, LOGICAL_WIDTH - 32, LOGICAL_HEIGHT - 70)

        save_data = SaveManager.load()
        self.state = Game.STATE_MENU
        self.current_level = save_data["current_level"]
        self.high_score = save_data["high_score"]
        self.state_before_pause = Game.STATE_PLAYING

        self.player = None
        self.enemies = []
        self.boss = None
        self.bullets = []
        self.particles = []
        self.obstacles = []
        self.blood_stains = []
        self.pickups = []
        self.floaters = []

        self.boss_spawned_this_level = False
        self.level_message_timer = 0.0

        self.score = 0
        self.combo = 0
        self.combo_timer = 0.0

        # --- controles twin-stick ---
        self.left_stick = VirtualStick(radius=64, dead_zone=10,
                                        base_color=NEON_LIME, knob_color=NEON_LIME)
        self.right_stick = VirtualStick(radius=64, dead_zone=8,
                                         base_color=NEON_PINK, knob_color=NEON_PINK)
        self.pause_button = pygame.Rect(LOGICAL_WIDTH - 54, 10, 40, 40)

        self.shake_timer = 0.0
        self.shake_strength = 0.0

        self.running = True

    # ------------------------------------------------------
    def trigger_shake(self, strength):
        self.shake_strength = max(self.shake_strength, strength)
        self.shake_timer = 0.12

    def get_shake_offset(self):
        if self.shake_timer > 0:
            return (random.uniform(-1, 1) * self.shake_strength,
                    random.uniform(-1, 1) * self.shake_strength)
        return (0, 0)

    def add_score(self, base_points):
        self.combo += 1
        self.combo_timer = 2.5
        gained = base_points * self.combo
        self.score += gained
        self.floaters.append(FloatingText(
            self.player.pos + (0, -34), f"+{gained} x{self.combo}", NEON_YELLOW, 0.6, 18))
        if self.score > self.high_score:
            self.high_score = self.score

    # ------------------------------------------------------
    def start_level(self, level):
        self.current_level = level
        SaveManager.save(level, self.high_score)

        self.player = Player((LOGICAL_WIDTH // 2, LOGICAL_HEIGHT // 2))
        self.enemies = []
        self.boss = None
        self.bullets = []
        self.particles = []
        self.pickups = []
        self.floaters = []
        self.blood_stains = []
        self.boss_spawned_this_level = False
        self.score = 0
        self.combo = 0
        self.combo_timer = 0.0

        params = generate_level_params(level)
        self.obstacles = self._generate_obstacles(
            params["obstacle_count"], params["crate_chance"], params["barrel_chance"])
        self.enemies = self._spawn_enemies(params["enemy_count"], params["enemy_speed"])

        self.state = Game.STATE_PLAYING

    def _generate_obstacles(self, count, crate_chance, barrel_chance):
        obstacles = []
        attempts = 0
        area = self.play_area
        while len(obstacles) < count and attempts < count * 12:
            attempts += 1
            w = random.randint(40, 90)
            h = random.randint(40, 90)
            x = random.randint(area.left + 20, area.right - 20 - w)
            y = random.randint(area.top + 20, area.bottom - 20 - h)
            rect = pygame.Rect(x, y, w, h)
            center_zone = pygame.Rect(LOGICAL_WIDTH // 2 - 70, LOGICAL_HEIGHT // 2 - 70, 140, 140)
            if rect.colliderect(center_zone):
                continue
            if any(rect.colliderect(o.rect.inflate(20, 20)) for o in obstacles):
                continue
            roll = random.random()
            if roll < barrel_chance:
                kind = "barrel"
            elif roll < barrel_chance + crate_chance:
                kind = "crate"
            else:
                kind = "wall"
            obstacles.append(Obstacle(rect, kind))
        return obstacles

    def _spawn_enemies(self, count, speed):
        enemies = []
        area = self.play_area
        for _ in range(count):
            for _try in range(30):
                x = random.randint(area.left + 30, area.right - 30)
                y = random.randint(area.top + 30, area.bottom - 30)
                pos = pygame.math.Vector2(x, y)
                if pos.distance_to((LOGICAL_WIDTH // 2, LOGICAL_HEIGHT // 2)) > 160:
                    enemies.append(Enemy(pos, speed))
                    break
        return enemies

    def _spawn_boss(self):
        pos = (LOGICAL_WIDTH // 2, self.play_area.top + 90)
        self.boss = Boss(pos, self.current_level)
        self.boss_spawned_this_level = True

    # ------------------------------------------------------
    #  EXPLOSÕES (barris) — dano em área + reação em cadeia
    # ------------------------------------------------------
    def trigger_explosion(self, pos, radius=110, damage=99):
        self.audio.play("explosion", 0.8)
        self.trigger_shake(14)
        for _ in range(26):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(120, 380)
            vel = vec_from_angle(angle) * speed
            color = random.choice([NEON_ORANGE, NEON_YELLOW, NEON_RED])
            self.particles.append(Particle(pos, vel, random.uniform(0.25, 0.5), color, 6))

        pos_v = pygame.math.Vector2(pos)
        for enemy in self.enemies:
            if enemy.alive and pos_v.distance_to(enemy.pos) <= radius:
                enemy.take_damage(damage)
                if not enemy.alive:
                    self.spawn_death_effects(enemy, True, from_explosion=True)

        if self.boss is not None and self.boss.alive and pos_v.distance_to(self.boss.pos) <= radius:
            self.boss.take_damage(damage / 4)
            if not self.boss.alive:
                self.spawn_death_effects(self.boss, False)

        if self.player.alive and pos_v.distance_to(self.player.pos) <= radius:
            died = self.player.take_hit()
            if died:
                self.spawn_death_effects(self.player, False)

        # reação em cadeia: outros barris próximos também explodem
        for obs in self.obstacles:
            if obs.alive and obs.kind == "barrel":
                if pos_v.distance_to(pygame.math.Vector2(obs.rect.center)) <= radius and \
                        pygame.math.Vector2(obs.rect.center) != pos_v:
                    obs.alive = False
                    self.trigger_explosion(obs.rect.center, radius, damage)

    # ------------------------------------------------------
    #  ENTRADA DE TOQUE (dois joysticks + botão de pausa)
    # ------------------------------------------------------
    def handle_touch_down(self, finger_id, x, y):
        if self.pause_button.collidepoint(x, y):
            self.toggle_pause()
            return
        if self.state != Game.STATE_PLAYING:
            return
        if x < LOGICAL_WIDTH / 2:
            if not self.left_stick.active:
                self.left_stick.start(finger_id, (x, y))
        else:
            if not self.right_stick.active:
                self.right_stick.start(finger_id, (x, y))

    def handle_touch_move(self, finger_id, x, y):
        if self.left_stick.active and self.left_stick.finger_id == finger_id:
            self.left_stick.move((x, y))
        elif self.right_stick.active and self.right_stick.finger_id == finger_id:
            self.right_stick.move((x, y))

    def handle_touch_up(self, finger_id):
        if self.left_stick.finger_id == finger_id:
            self.left_stick.stop()
        if self.right_stick.finger_id == finger_id:
            self.right_stick.stop()

    def toggle_pause(self):
        if self.state == Game.STATE_PLAYING:
            self.state_before_pause = self.state
            self.state = Game.STATE_PAUSED
            self.audio.play("pause", 0.5)
        elif self.state == Game.STATE_PAUSED:
            self.state = self.state_before_pause

    def _process_twin_stick(self, dt, dt_ms):
        # --- MOVIMENTO (stick esquerdo) ---
        move_dir = self.left_stick.get_direction()
        self.player.move_dir = move_dir if move_dir else pygame.math.Vector2(0, 0)

        # --- MIRA + TIRO (stick direito) ---
        aim_dir = self.right_stick.get_direction()
        if self.right_stick.active:
            if aim_dir is not None:
                self.player.angle = math.atan2(aim_dir.y, aim_dir.x)
            # mesmo sem arrastar (dedo parado), continua atirando na direção atual
            self.player.try_shoot(dt_ms, self.bullets, self.particles, self.audio,
                                   self.trigger_shake, self.floaters)
        elif move_dir is not None:
            # sem mirar, o personagem olha pra onde anda
            self.player.angle = math.atan2(move_dir.y, move_dir.x)

    # ------------------------------------------------------
    def spawn_death_effects(self, entity, is_enemy=True, from_explosion=False):
        self.blood_stains.append(BloodStain(entity.pos, random.randint(20, 34)))
        for _ in range(3):
            offset = pygame.math.Vector2(random.uniform(-14, 14), random.uniform(-14, 14))
            self.blood_stains.append(BloodStain(entity.pos + offset, random.randint(8, 16)))

        for _ in range(14):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(60, 220)
            vel = vec_from_angle(angle) * speed
            self.particles.append(Particle(entity.pos, vel, random.uniform(0.2, 0.45), NEON_RED, 4))

        self.audio.play("death", 0.7)
        self.trigger_shake(6)
        vibrate(25)

        if is_enemy:
            self.add_score(100)
            drop_roll = random.random()
            if drop_roll < 0.16:
                weapon_key = random.choice(["shotgun", "smg"])
                self.pickups.append(Pickup(entity.pos, "weapon", weapon_key))
            elif drop_roll < 0.28:
                self.pickups.append(Pickup(entity.pos, "ammo"))
            elif drop_roll < 0.33:
                self.pickups.append(Pickup(entity.pos, "armor"))
        else:
            # chefão morto = pontuação alta
            self.add_score(2000)

    # ------------------------------------------------------
    def update_playing(self, dt, dt_ms):
        self._process_twin_stick(dt, dt_ms)
        self.player.update(dt, dt_ms, self.obstacles)

        area = self.play_area
        self.player.pos.x = clamp(self.player.pos.x, area.left + self.player.radius, area.right - self.player.radius)
        self.player.pos.y = clamp(self.player.pos.y, area.top + self.player.radius, area.bottom - self.player.radius)

        for enemy in self.enemies.copy():
            enemy.update(dt, dt_ms, self.player, self.obstacles, self.bullets, self.particles)

        if self.boss is not None:
            self.boss.update(dt, dt_ms, self.player, self.bullets, self.play_area)

        for bullet in self.bullets.copy():
            bullet.update(dt)
            if not self.play_area.inflate(40, 40).collidepoint(bullet.pos):
                bullet.alive = False
                continue

            hit_obstacle = False
            for obs in self.obstacles:
                if obs.alive and obs.rect.collidepoint(bullet.pos):
                    bullet.alive = False
                    hit_obstacle = True
                    if obs.kind == "crate":
                        destroyed = obs.hit()
                        if destroyed and random.random() < 0.35:
                            weapon_key = random.choice(["shotgun", "smg"])
                            self.pickups.append(Pickup(obs.rect.center, "weapon", weapon_key))
                    elif obs.kind == "barrel":
                        obs.alive = False
                        self.trigger_explosion(obs.rect.center)
                    break
            if hit_obstacle:
                continue

            if bullet.owner == "player":
                for enemy in self.enemies:
                    if enemy.alive and bullet.pos.distance_to(enemy.pos) < enemy.radius:
                        enemy.take_damage(bullet.damage)
                        bullet.alive = False
                        if not enemy.alive:
                            self.spawn_death_effects(enemy, True)
                        break
                if bullet.alive and self.boss is not None and self.boss.alive:
                    if bullet.pos.distance_to(self.boss.pos) < self.boss.radius:
                        self.boss.take_damage(bullet.damage)
                        bullet.alive = False
                        self.audio.play("boss_hit", 0.4)
                        if not self.boss.alive:
                            self.spawn_death_effects(self.boss, False)
            elif bullet.owner in ("enemy", "boss"):
                if self.player.alive and bullet.pos.distance_to(self.player.pos) < self.player.radius:
                    bullet.alive = False
                    died = self.player.take_hit()
                    self.audio.play("player_hurt", 0.6)
                    self.trigger_shake(8)
                    vibrate(60)
                    if died:
                        self.spawn_death_effects(self.player, False)

        self.enemies = [e for e in self.enemies if e.alive]
        self.bullets = [b for b in self.bullets if b.alive]

        for p in self.particles.copy():
            p.update(dt)
        self.particles = [p for p in self.particles if not p.is_dead()]

        for ft in self.floaters.copy():
            ft.update(dt)
        self.floaters = [f for f in self.floaters if not f.is_dead()]

        for pk in self.pickups.copy():
            pk.update(dt)
            if self.player.pos.distance_to(pk.pos) < self.player.radius + pk.radius:
                if pk.kind == "weapon":
                    self.player.switch_weapon(pk.weapon_key)
                    self.audio.play("pickup", 0.7)
                elif pk.kind == "ammo":
                    self.player.add_ammo(24)
                    self.audio.play("pickup", 0.7)
                    self.floaters.append(FloatingText(self.player.pos + (0, -30), "+MUNIÇÃO", NEON_YELLOW, 0.6, 16))
                elif pk.kind == "armor":
                    self.player.shield = min(self.player.shield + 1, 2)
                    self.audio.play("shield", 0.7)
                    self.floaters.append(FloatingText(self.player.pos + (0, -30), "+COLETE", NEON_BLUE, 0.6, 16))
                self.pickups.remove(pk)

        # colisão corpo a corpo (instantânea, salvo se houver colete)
        if self.player.alive:
            for enemy in self.enemies:
                if self.player.pos.distance_to(enemy.pos) < (self.player.radius + enemy.radius - 6):
                    died = self.player.take_hit()
                    vibrate(60)
                    if died:
                        self.spawn_death_effects(self.player, False)
                    break

        if self.combo_timer > 0:
            self.combo_timer -= dt
            if self.combo_timer <= 0:
                self.combo = 0

        if self.shake_timer > 0:
            self.shake_timer -= dt
            self.shake_strength *= 0.85

        if not self.player.alive:
            SaveManager.save(self.current_level, self.high_score)
            self.state = Game.STATE_GAME_OVER
            return

        if is_boss_level(self.current_level):
            if len(self.enemies) == 0 and self.boss is None and not self.boss_spawned_this_level:
                self._spawn_boss()
            elif self.boss is not None and not self.boss.alive:
                self.state = Game.STATE_LEVEL_CLEAR
                self.level_message_timer = 1.6
        else:
            if len(self.enemies) == 0:
                self.state = Game.STATE_LEVEL_CLEAR
                self.level_message_timer = 1.2

    # ------------------------------------------------------
    def update_level_clear(self, dt):
        self.level_message_timer -= dt
        if self.level_message_timer <= 0:
            next_level = self.current_level + 1
            if next_level > 100:
                SaveManager.save(1, self.high_score)
                self.state = Game.STATE_MENU
                self.current_level = 1
            else:
                self.start_level(next_level)

    # ------------------------------------------------------
    def draw_floor(self, surf):
        surf.fill(COLOR_BG)
        pygame.draw.rect(surf, COLOR_FLOOR, self.play_area)
        step = 40
        for gx in range(self.play_area.left, self.play_area.right, step):
            pygame.draw.line(surf, DARK_GREY, (gx, self.play_area.top), (gx, self.play_area.bottom), 1)
        for gy in range(self.play_area.top, self.play_area.bottom, step):
            pygame.draw.line(surf, DARK_GREY, (self.play_area.left, gy), (self.play_area.right, gy), 1)

        for stain in self.blood_stains:
            pygame.draw.circle(surf, BLOOD_RED, (int(stain.pos.x), int(stain.pos.y)), stain.radius)

        pygame.draw.rect(surf, NEON_BLUE, self.play_area, 4)

    def draw_hud(self, surf):
        weapon = WEAPONS[self.player.weapon_key]
        ammo_text = "∞" if self.player.ammo == -1 else str(self.player.ammo)
        hud_text = f"{weapon['label']}  |  MUNIÇÃO: {ammo_text}"
        label = self.font_small.render(hud_text, True, WHITE)
        surf.blit(label, (16, 10))

        score_text = self.font_small.render(f"PONTOS: {self.score}", True, NEON_YELLOW)
        surf.blit(score_text, (16, 30))

        level_label = self.font_small.render(f"NÍVEL {self.current_level}/100", True, NEON_LIME)
        surf.blit(level_label, (LOGICAL_WIDTH // 2 - level_label.get_width() // 2, 10))

        if self.combo > 1:
            combo_label = self.font_med.render(f"COMBO x{self.combo}!", True, NEON_ORANGE)
            surf.blit(combo_label, (LOGICAL_WIDTH // 2 - combo_label.get_width() // 2, 30))

        # vida / colete
        color = NEON_PINK if self.player.alive else DARK_GREY
        pygame.draw.circle(surf, color, (LOGICAL_WIDTH - 90, 22), 9)
        if self.player.shield > 0:
            shield_label = self.font_tiny.render(f"COLETE x{self.player.shield}", True, NEON_BLUE)
            surf.blit(shield_label, (LOGICAL_WIDTH - 220, 14))

        # botão de pausa
        pygame.draw.rect(surf, DARK_GREY, self.pause_button, border_radius=6)
        pygame.draw.rect(surf, WHITE, self.pause_button, 2, border_radius=6)
        bar_w, bar_h = 5, 18
        cx, cy = self.pause_button.center
        pygame.draw.rect(surf, WHITE, (cx - 8, cy - bar_h // 2, bar_w, bar_h))
        pygame.draw.rect(surf, WHITE, (cx + 3, cy - bar_h // 2, bar_w, bar_h))

        if self.boss is not None and self.boss.alive:
            self.boss.draw_healthbar(surf, self.font_small)

        for ft in self.floaters:
            ft.draw(surf, self.font_small)

    def draw_playing(self, surf):
        self.draw_floor(surf)
        for obs in self.obstacles:
            if obs.alive:
                obs.draw(surf)
        for pk in self.pickups:
            pk.draw(surf)
        for enemy in self.enemies:
            enemy.draw(surf)
        if self.boss is not None and self.boss.alive:
            self.boss.draw(surf)
        for bullet in self.bullets:
            bullet.draw(surf)
        for p in self.particles:
            p.draw(surf)
        if self.player.alive:
            self.player.draw(surf)
        self.draw_hud(surf)
        # joysticks visíveis por cima de tudo
        self.left_stick.draw(surf)
        self.right_stick.draw(surf)

    def draw_menu(self, surf):
        surf.fill(COLOR_BG)
        title = self.font_big.render("RIO", True, NEON_PINK)
        surf.blit(title, (LOGICAL_WIDTH // 2 - title.get_width() // 2, 160))
        subtitle = self.font_med.render("toque para começar", True, NEON_BLUE)
        surf.blit(subtitle, (LOGICAL_WIDTH // 2 - subtitle.get_width() // 2, 230))
        info = self.font_small.render(f"continuar do nível {self.current_level}  |  recorde: {self.high_score}",
                                       True, WHITE)
        surf.blit(info, (LOGICAL_WIDTH // 2 - info.get_width() // 2, 280))

        hint1 = self.font_tiny.render("stick esquerdo: mover   |   stick direito: mirar e atirar", True, GREY)
        surf.blit(hint1, (LOGICAL_WIDTH // 2 - hint1.get_width() // 2, 340))

    def draw_level_clear(self, surf):
        self.draw_playing(surf)
        overlay = pygame.Surface((LOGICAL_WIDTH, LOGICAL_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        surf.blit(overlay, (0, 0))
        msg = self.font_big.render("FASE LIMPA!", True, NEON_LIME)
        surf.blit(msg, (LOGICAL_WIDTH // 2 - msg.get_width() // 2, LOGICAL_HEIGHT // 2 - 40))
        score_msg = self.font_med.render(f"pontos: {self.score}", True, NEON_YELLOW)
        surf.blit(score_msg, (LOGICAL_WIDTH // 2 - score_msg.get_width() // 2, LOGICAL_HEIGHT // 2 + 10))

    def draw_game_over(self, surf):
        surf.fill(COLOR_BG)
        msg = self.font_big.render("VOCÊ MORREU", True, NEON_RED)
        surf.blit(msg, (LOGICAL_WIDTH // 2 - msg.get_width() // 2, 200))
        score_msg = self.font_med.render(f"pontos: {self.score}   |   recorde: {self.high_score}", True, WHITE)
        surf.blit(score_msg, (LOGICAL_WIDTH // 2 - score_msg.get_width() // 2, 260))
        info = self.font_med.render(f"toque para tentar o nível {self.current_level} de novo", True, WHITE)
        surf.blit(info, (LOGICAL_WIDTH // 2 - info.get_width() // 2, 310))

    def draw_paused(self, surf):
        self.draw_playing(surf)
        overlay = pygame.Surface((LOGICAL_WIDTH, LOGICAL_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        surf.blit(overlay, (0, 0))
        msg = self.font_big.render("PAUSADO", True, WHITE)
        surf.blit(msg, (LOGICAL_WIDTH // 2 - msg.get_width() // 2, LOGICAL_HEIGHT // 2 - 40))
        info = self.font_small.render("toque no botão de pausa para continuar", True, GREY)
        surf.blit(info, (LOGICAL_WIDTH // 2 - info.get_width() // 2, LOGICAL_HEIGHT // 2 + 20))

    # ------------------------------------------------------
    def run(self):
        while self.running:
            dt_ms = self.clock.tick(FPS)
            dt = dt_ms / 1000.0
            self.handle_events()

            if self.state == Game.STATE_PLAYING:
                self.update_playing(dt, dt_ms)
            elif self.state == Game.STATE_LEVEL_CLEAR:
                self.update_level_clear(dt)

            shake_offset = self.get_shake_offset()
            frame = pygame.Surface((LOGICAL_WIDTH, LOGICAL_HEIGHT))

            if self.state == Game.STATE_MENU:
                self.draw_menu(frame)
            elif self.state == Game.STATE_PLAYING:
                self.draw_playing(frame)
            elif self.state == Game.STATE_LEVEL_CLEAR:
                self.draw_level_clear(frame)
            elif self.state == Game.STATE_GAME_OVER:
                self.draw_game_over(frame)
            elif self.state == Game.STATE_PAUSED:
                self.draw_paused(frame)

            self.screen.fill(BLACK)
            self.screen.blit(frame, shake_offset)
            pygame.display.flip()

        pygame.quit()
        sys.exit()

    # ------------------------------------------------------
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if self.state in (Game.STATE_PLAYING, Game.STATE_PAUSED):
                    self.toggle_pause()
                else:
                    self.running = False

            # ---- eventos de toque nativo (Android) ----
            elif event.type == pygame.FINGERDOWN:
                x = event.x * LOGICAL_WIDTH
                y = event.y * LOGICAL_HEIGHT
                self._on_press(event.finger_id, x, y)
            elif event.type == pygame.FINGERMOTION:
                x = event.x * LOGICAL_WIDTH
                y = event.y * LOGICAL_HEIGHT
                self.handle_touch_move(event.finger_id, x, y)
            elif event.type == pygame.FINGERUP:
                self.handle_touch_up(event.finger_id)

            # ---- fallback de mouse (testes em desktop) ----
            elif event.type == pygame.MOUSEBUTTONDOWN:
                x, y = event.pos
                self._on_press(-1, x, y)
            elif event.type == pygame.MOUSEMOTION:
                if pygame.mouse.get_pressed()[0]:
                    x, y = event.pos
                    self.handle_touch_move(-1, x, y)
            elif event.type == pygame.MOUSEBUTTONUP:
                self.handle_touch_up(-1)

    def _on_press(self, finger_id, x, y):
        if self.state == Game.STATE_MENU:
            self.start_level(self.current_level)
        elif self.state == Game.STATE_GAME_OVER:
            self.start_level(self.current_level)
        elif self.state == Game.STATE_PAUSED:
            if self.pause_button.collidepoint(x, y):
                self.toggle_pause()
        elif self.state == Game.STATE_PLAYING:
            self.handle_touch_down(finger_id, x, y)


# ============================================================
#  PONTO DE ENTRADA
# ============================================================
def main():
    game = Game()
    game.run()


if __name__ == "__main__":
    main()
