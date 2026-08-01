"""Pocket Brawl — a dependency-free top-down arena game built with Tkinter."""

from __future__ import annotations

import math
import random
import time
import tkinter as tk
from dataclasses import dataclass, field


WIDTH, HEIGHT = 1100, 700
ARENA = (35, 60, WIDTH - 35, HEIGHT - 35)
TICK_MS = 16
PLAYER_COLOR = "#39a9ff"
BOT_COLORS = ["#ff4f70", "#ff9f43", "#a55eea", "#26de81", "#fd79a8", "#45aaf2", "#fed330"]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def distance(a: "Actor", b: "Actor") -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def circle_rect_collision(x: float, y: float, radius: float, wall: "Wall") -> bool:
    px = clamp(x, wall.x, wall.x + wall.w)
    py = clamp(y, wall.y, wall.y + wall.h)
    return (x - px) ** 2 + (y - py) ** 2 < radius**2


@dataclass
class Wall:
    x: float
    y: float
    w: float
    h: float


@dataclass
class Bush:
    x: float
    y: float
    w: float
    h: float

    def contains(self, actor: "Actor") -> bool:
        return self.x < actor.x < self.x + self.w and self.y < actor.y < self.y + self.h


@dataclass
class Projectile:
    x: float
    y: float
    vx: float
    vy: float
    owner: "Actor"
    damage: float
    color: str
    radius: float = 6
    life: float = 1.4
    super_shot: bool = False


@dataclass
class Pickup:
    x: float
    y: float
    kind: str = "cube"
    radius: float = 11
    bob: float = field(default_factory=lambda: random.random() * math.tau)


@dataclass
class Crate:
    x: float
    y: float
    hp: float = 1500
    radius: float = 25
    alive: bool = True


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    color: str
    life: float
    size: float


class Actor:
    def __init__(self, x: float, y: float, name: str, color: str, is_player: bool = False):
        self.x, self.y = x, y
        self.name = name
        self.color = color
        self.is_player = is_player
        self.radius = 24
        self.max_hp = 3600.0
        self.hp = self.max_hp
        self.speed = 190.0 if is_player else random.uniform(125, 165)
        self.reload = random.random() * 0.5
        self.super_charge = 0.0
        self.cubes = 0
        self.alive = True
        self.angle = 0.0
        self.last_hit = 0.0
        self.dash_cd = 0.0
        self.dash_time = 0.0
        self.flash = 0.0
        self.ai_turn = random.uniform(0.2, 1.0)
        self.ai_x, self.ai_y = 0.0, 0.0
        self.target: Actor | None = None

    @property
    def damage(self) -> float:
        return 420 + self.cubes * 42

    def add_cube(self) -> None:
        self.cubes += 1
        self.max_hp += 260
        self.hp = min(self.max_hp, self.hp + 700)


class PocketBrawl:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Pocket Brawl")
        self.root.resizable(False, False)
        self.canvas = tk.Canvas(root, width=WIDTH, height=HEIGHT, bg="#151b2f", highlightthickness=0)
        self.canvas.pack()
        self.keys: set[str] = set()
        self.mouse_x, self.mouse_y = WIDTH / 2, HEIGHT / 2
        self.mouse_down = False
        self.state = "menu"
        self.paused = False
        self.last_time = time.perf_counter()
        self.shake = 0.0
        self.storm_radius = 690.0
        self.storm_damage_clock = 0.0
        self.match_time = 0.0
        self.actors: list[Actor] = []
        self.projectiles: list[Projectile] = []
        self.pickups: list[Pickup] = []
        self.crates: list[Crate] = []
        self.particles: list[Particle] = []
        self.walls: list[Wall] = []
        self.bushes: list[Bush] = []
        self.player: Actor | None = None
        self.root.bind("<KeyPress>", self.on_key_down)
        self.root.bind("<KeyRelease>", self.on_key_up)
        self.canvas.bind("<Motion>", self.on_mouse_move)
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<Button-1>", self.on_click)
        self.root.after(TICK_MS, self.loop)

    def on_key_down(self, event: tk.Event) -> None:
        key = event.keysym.lower()
        self.keys.add(key)
        if key == "escape" and self.state == "playing":
            self.paused = not self.paused
        elif key == "space" and self.state == "playing" and not self.paused:
            self.use_super()
        elif key in ("shift_l", "shift_r") and self.state == "playing" and not self.paused:
            self.use_dash()
        elif key == "r" and self.state in ("won", "lost"):
            self.start_game()

    def on_key_up(self, event: tk.Event) -> None:
        self.keys.discard(event.keysym.lower())

    def on_mouse_move(self, event: tk.Event) -> None:
        self.mouse_x, self.mouse_y = event.x, event.y

    def on_mouse_down(self, _event: tk.Event) -> None:
        self.mouse_down = True

    def on_mouse_up(self, _event: tk.Event) -> None:
        self.mouse_down = False

    def on_click(self, event: tk.Event) -> None:
        self.mouse_down = True
        if self.state == "menu" and 415 <= event.x <= 685 and 470 <= event.y <= 535:
            self.start_game()
        elif self.state in ("won", "lost") and 425 <= event.x <= 675 and 475 <= event.y <= 535:
            self.start_game()

    def start_game(self) -> None:
        self.state, self.paused = "playing", False
        self.match_time, self.storm_radius = 0.0, 690.0
        self.projectiles, self.pickups, self.particles = [], [], []
        self.walls = [
            Wall(250, 175, 125, 50), Wall(725, 175, 125, 50),
            Wall(250, 475, 125, 50), Wall(725, 475, 125, 50),
            Wall(500, 270, 100, 45), Wall(500, 385, 100, 45),
            Wall(95, 315, 105, 55), Wall(900, 315, 105, 55),
        ]
        self.bushes = [
            Bush(85, 105, 145, 80), Bush(870, 105, 145, 80),
            Bush(85, 515, 145, 80), Bush(870, 515, 145, 80),
            Bush(415, 105, 270, 45), Bush(415, 550, 270, 45),
        ]
        spawns = [(105, 100), (995, 100), (105, 600), (995, 600), (550, 105), (550, 595), (150, 350), (950, 350)]
        random.shuffle(spawns)
        px, py = spawns.pop()
        self.player = Actor(px, py, "ТИ", PLAYER_COLOR, True)
        bot_names = ["Rex", "Nova", "Spike", "Mika", "Volt", "Byte", "Fang"]
        self.actors = [self.player]
        for index, (x, y) in enumerate(spawns):
            self.actors.append(Actor(x, y, bot_names[index], BOT_COLORS[index]))
        crate_spawns = [(340, 350), (760, 350), (550, 210), (550, 490), (150, 245), (950, 455), (425, 350), (675, 350)]
        self.crates = [Crate(x, y) for x, y in crate_spawns]

    def loop(self) -> None:
        now = time.perf_counter()
        dt = min(now - self.last_time, 0.035)
        self.last_time = now
        if self.state == "playing" and not self.paused:
            self.update(dt)
        self.draw()
        self.root.after(TICK_MS, self.loop)

    def update(self, dt: float) -> None:
        self.match_time += dt
        self.shake = max(0.0, self.shake - dt * 22)
        self.storm_radius = max(150.0, 690.0 - max(0.0, self.match_time - 12) * 6.0)
        for actor in self.actors:
            if not actor.alive:
                continue
            actor.reload = max(0.0, actor.reload - dt)
            actor.dash_cd = max(0.0, actor.dash_cd - dt)
            actor.dash_time = max(0.0, actor.dash_time - dt)
            actor.flash = max(0.0, actor.flash - dt)
            if time.monotonic() - actor.last_hit > 3.2 and actor.hp < actor.max_hp:
                actor.hp = min(actor.max_hp, actor.hp + 390 * dt)
        self.update_player(dt)
        self.update_bots(dt)
        self.update_projectiles(dt)
        self.update_pickups(dt)
        self.update_particles(dt)
        self.update_storm(dt)
        alive = [a for a in self.actors if a.alive]
        if self.player and not self.player.alive:
            self.state = "lost"
        elif self.player and self.player.alive and len(alive) == 1:
            self.state = "won"

    def update_player(self, dt: float) -> None:
        p = self.player
        if not p or not p.alive:
            return
        dx = float("d" in self.keys or "right" in self.keys) - float("a" in self.keys or "left" in self.keys)
        dy = float("s" in self.keys or "down" in self.keys) - float("w" in self.keys or "up" in self.keys)
        length = math.hypot(dx, dy) or 1.0
        boost = 2.65 if p.dash_time > 0 else 1.0
        self.move_actor(p, dx / length * p.speed * boost * dt, dy / length * p.speed * boost * dt)
        p.angle = math.atan2(self.mouse_y - p.y, self.mouse_x - p.x)
        if self.mouse_down:
            self.shoot(p, p.angle)

    def update_bots(self, dt: float) -> None:
        living = [a for a in self.actors if a.alive]
        for bot in self.actors:
            if bot.is_player or not bot.alive:
                continue
            enemies = [a for a in living if a is not bot]
            if not enemies:
                continue
            target = min(enemies, key=lambda other: distance(bot, other))
            bot.target = target
            dist = distance(bot, target)
            bot.angle = math.atan2(target.y - bot.y, target.x - bot.x)
            bot.ai_turn -= dt
            if bot.ai_turn <= 0:
                bot.ai_turn = random.uniform(0.45, 1.1)
                side = random.choice((-1, 1))
                if dist > 310:
                    bot.ai_x, bot.ai_y = math.cos(bot.angle), math.sin(bot.angle)
                elif dist < 145:
                    bot.ai_x, bot.ai_y = -math.cos(bot.angle), -math.sin(bot.angle)
                else:
                    bot.ai_x, bot.ai_y = -math.sin(bot.angle) * side, math.cos(bot.angle) * side
            nearest_cube = min(self.pickups, key=lambda p: math.hypot(bot.x - p.x, bot.y - p.y), default=None)
            if nearest_cube and math.hypot(bot.x - nearest_cube.x, bot.y - nearest_cube.y) < 190:
                angle = math.atan2(nearest_cube.y - bot.y, nearest_cube.x - bot.x)
                bot.ai_x, bot.ai_y = math.cos(angle), math.sin(angle)
            self.move_actor(bot, bot.ai_x * bot.speed * dt, bot.ai_y * bot.speed * dt)
            if dist < 500 and self.clear_shot(bot, target):
                error = random.uniform(-0.09, 0.09)
                self.shoot(bot, bot.angle + error)
            if bot.super_charge >= 100 and dist < 180:
                self.bot_super(bot)

    def move_actor(self, actor: Actor, dx: float, dy: float) -> None:
        nx = clamp(actor.x + dx, ARENA[0] + actor.radius, ARENA[2] - actor.radius)
        if not any(circle_rect_collision(nx, actor.y, actor.radius, wall) for wall in self.walls):
            actor.x = nx
        ny = clamp(actor.y + dy, ARENA[1] + actor.radius, ARENA[3] - actor.radius)
        if not any(circle_rect_collision(actor.x, ny, actor.radius, wall) for wall in self.walls):
            actor.y = ny

    def clear_shot(self, actor: Actor, target: Actor) -> bool:
        steps = max(1, int(distance(actor, target) / 25))
        for i in range(1, steps):
            ratio = i / steps
            x = actor.x + (target.x - actor.x) * ratio
            y = actor.y + (target.y - actor.y) * ratio
            if any(w.x <= x <= w.x + w.w and w.y <= y <= w.y + w.h for w in self.walls):
                return False
        return True

    def shoot(self, actor: Actor, angle: float) -> None:
        if actor.reload > 0 or not actor.alive:
            return
        actor.reload = 0.48 if actor.is_player else random.uniform(0.62, 0.9)
        speed = 570
        self.projectiles.append(Projectile(
            actor.x + math.cos(angle) * 31, actor.y + math.sin(angle) * 31,
            math.cos(angle) * speed, math.sin(angle) * speed, actor, actor.damage,
            "#a8e6ff" if actor.is_player else "#ffd2d9",
        ))
        for _ in range(4):
            spread = angle + random.uniform(-0.6, 0.6)
            self.particles.append(Particle(actor.x, actor.y, math.cos(spread) * 80, math.sin(spread) * 80, "#ffffff", 0.18, 4))

    def use_dash(self) -> None:
        p = self.player
        if p and p.alive and p.dash_cd <= 0:
            p.dash_cd, p.dash_time = 4.0, 0.22

    def use_super(self) -> None:
        p = self.player
        if not p or not p.alive or p.super_charge < 100:
            return
        p.super_charge = 0
        self.shake = 8
        for index in range(16):
            angle = math.tau * index / 16
            self.projectiles.append(Projectile(
                p.x + math.cos(angle) * 30, p.y + math.sin(angle) * 30,
                math.cos(angle) * 680, math.sin(angle) * 680, p, p.damage * 0.72,
                "#ffe66d", 9, 0.85, True,
            ))

    def bot_super(self, bot: Actor) -> None:
        bot.super_charge = 0
        for offset in (-0.20, 0, 0.20):
            angle = bot.angle + offset
            self.projectiles.append(Projectile(bot.x, bot.y, math.cos(angle) * 610, math.sin(angle) * 610, bot, bot.damage * 1.25, "#ffdc73", 9, 0.9, True))

    def update_projectiles(self, dt: float) -> None:
        for shot in list(self.projectiles):
            shot.x += shot.vx * dt
            shot.y += shot.vy * dt
            shot.life -= dt
            remove = shot.life <= 0 or not (ARENA[0] < shot.x < ARENA[2] and ARENA[1] < shot.y < ARENA[3])
            if not remove and any(circle_rect_collision(shot.x, shot.y, shot.radius, wall) for wall in self.walls):
                remove = True
            if not remove:
                for crate in self.crates:
                    if crate.alive and math.hypot(shot.x - crate.x, shot.y - crate.y) < shot.radius + crate.radius:
                        crate.hp -= shot.damage
                        remove = True
                        self.hit_effect(shot.x, shot.y, "#ffcc73", 7)
                        if crate.hp <= 0:
                            crate.alive = False
                            self.pickups.append(Pickup(crate.x, crate.y))
                            self.hit_effect(crate.x, crate.y, "#ffd166", 22)
                        break
            if not remove:
                for actor in self.actors:
                    if actor.alive and actor is not shot.owner and math.hypot(shot.x - actor.x, shot.y - actor.y) < shot.radius + actor.radius:
                        self.damage_actor(actor, shot.damage, shot.owner)
                        shot.owner.super_charge = min(100, shot.owner.super_charge + (22 if shot.super_shot else 15))
                        remove = True
                        break
            if remove and shot in self.projectiles:
                self.projectiles.remove(shot)

    def damage_actor(self, actor: Actor, amount: float, source: Actor | None = None) -> None:
        actor.hp -= amount
        actor.last_hit = time.monotonic()
        actor.flash = 0.12
        self.hit_effect(actor.x, actor.y, "#ffffff", 9)
        if actor.is_player:
            self.shake = 4
        if actor.hp <= 0 and actor.alive:
            actor.alive = False
            self.hit_effect(actor.x, actor.y, actor.color, 35)
            for index in range(max(1, actor.cubes // 2 + 1)):
                angle = math.tau * index / max(1, actor.cubes // 2 + 1)
                self.pickups.append(Pickup(actor.x + math.cos(angle) * 28, actor.y + math.sin(angle) * 28))
            if source:
                source.super_charge = min(100, source.super_charge + 25)

    def update_pickups(self, dt: float) -> None:
        for pickup in list(self.pickups):
            pickup.bob += dt * 4
            for actor in self.actors:
                if actor.alive and math.hypot(actor.x - pickup.x, actor.y - pickup.y) < actor.radius + pickup.radius + 4:
                    actor.add_cube()
                    self.pickups.remove(pickup)
                    self.hit_effect(pickup.x, pickup.y, "#77ff66", 14)
                    break

    def update_storm(self, dt: float) -> None:
        self.storm_damage_clock += dt
        if self.storm_damage_clock < 0.45:
            return
        self.storm_damage_clock = 0
        for actor in self.actors:
            if actor.alive and math.hypot(actor.x - WIDTH / 2, actor.y - HEIGHT / 2) > self.storm_radius:
                self.damage_actor(actor, 210 + self.match_time * 2)

    def hit_effect(self, x: float, y: float, color: str, count: int) -> None:
        for _ in range(count):
            angle = random.random() * math.tau
            speed = random.uniform(35, 190)
            self.particles.append(Particle(x, y, math.cos(angle) * speed, math.sin(angle) * speed, color, random.uniform(0.25, 0.65), random.uniform(2, 6)))

    def update_particles(self, dt: float) -> None:
        for particle in list(self.particles):
            particle.x += particle.vx * dt
            particle.y += particle.vy * dt
            particle.vx *= 0.96
            particle.vy *= 0.96
            particle.life -= dt
            if particle.life <= 0:
                self.particles.remove(particle)

    def draw(self) -> None:
        self.canvas.delete("all")
        if self.state == "menu":
            self.draw_menu()
            return
        ox = random.uniform(-self.shake, self.shake) if self.shake else 0
        oy = random.uniform(-self.shake, self.shake) if self.shake else 0
        self.draw_arena(ox, oy)
        self.draw_entities(ox, oy)
        self.draw_hud()
        if self.paused:
            self.overlay("ПАУЗА", "Натисни Esc, щоб продовжити", "#ffffff")
        elif self.state == "won":
            self.draw_result(True)
        elif self.state == "lost":
            self.draw_result(False)

    def draw_menu(self) -> None:
        self.canvas.create_rectangle(0, 0, WIDTH, HEIGHT, fill="#151b2f", outline="")
        for _ in range(25):
            x, y = random.randint(0, WIDTH), random.randint(0, HEIGHT)
            self.canvas.create_oval(x - 2, y - 2, x + 2, y + 2, fill="#323b62", outline="")
        self.canvas.create_text(WIDTH / 2 + 5, 180 + 7, text="POCKET BRAWL", font=("Arial Black", 54), fill="#080b16")
        self.canvas.create_text(WIDTH / 2, 180, text="POCKET BRAWL", font=("Arial Black", 54), fill="#ffd83d")
        self.canvas.create_text(WIDTH / 2, 255, text="АРЕНА НА ОДНОГО ПЕРЕМОЖЦЯ", font=("Arial", 18, "bold"), fill="#a8b2d8")
        self.canvas.create_oval(465, 310, 635, 440, fill="#35a7ff", outline="#8bd5ff", width=6)
        self.canvas.create_oval(505, 345, 545, 385, fill="#ffffff", outline="")
        self.canvas.create_oval(555, 345, 595, 385, fill="#ffffff", outline="")
        self.canvas.create_oval(521, 360, 537, 378, fill="#1c2745", outline="")
        self.canvas.create_oval(571, 360, 587, 378, fill="#1c2745", outline="")
        self.canvas.create_rectangle(415, 470, 685, 535, fill="#ff4f70", outline="#ff9bad", width=4)
        self.canvas.create_text(WIDTH / 2, 502, text="ГРАТИ", font=("Arial Black", 25), fill="white")
        self.canvas.create_text(WIDTH / 2, 585, text="WASD — рух  •  миша — приціл і постріл  •  Space — супер", font=("Arial", 15), fill="#dbe2ff")

    def draw_arena(self, ox: float, oy: float) -> None:
        self.canvas.create_rectangle(0, 0, WIDTH, HEIGHT, fill="#211b3d", outline="")
        self.canvas.create_rectangle(ARENA[0] + ox, ARENA[1] + oy, ARENA[2] + ox, ARENA[3] + oy, fill="#387c50", outline="#74bd67", width=5)
        for x in range(55, WIDTH - 50, 50):
            for y in range(80, HEIGHT - 45, 50):
                color = "#3d8556" if (x // 50 + y // 50) % 2 else "#377b4e"
                self.canvas.create_rectangle(x + ox, y + oy, x + 50 + ox, y + 50 + oy, fill=color, outline="")
        for bush in self.bushes:
            self.canvas.create_rectangle(bush.x + ox, bush.y + oy, bush.x + bush.w + ox, bush.y + bush.h + oy, fill="#1d663e", outline="#2b8b4e", width=3)
            for x in range(int(bush.x + 12), int(bush.x + bush.w), 24):
                self.canvas.create_oval(x - 10 + ox, bush.y + 8 + oy, x + 14 + ox, bush.y + 35 + oy, fill="#2f9a55", outline="")
        for wall in self.walls:
            self.canvas.create_rectangle(wall.x + 5 + ox, wall.y + 7 + oy, wall.x + wall.w + 5 + ox, wall.y + wall.h + 7 + oy, fill="#235235", outline="")
            self.canvas.create_rectangle(wall.x + ox, wall.y + oy, wall.x + wall.w + ox, wall.y + wall.h + oy, fill="#b8834f", outline="#e5b36d", width=3)
            for x in range(int(wall.x + 12), int(wall.x + wall.w), 28):
                self.canvas.create_line(x + ox, wall.y + oy, x + ox, wall.y + wall.h + oy, fill="#8a5e39", width=2)
        storm = self.storm_radius
        self.canvas.create_oval(WIDTH / 2 - storm + ox, HEIGHT / 2 - storm + oy, WIDTH / 2 + storm + ox, HEIGHT / 2 + storm + oy, outline="#b05cff", width=8)

    def draw_entities(self, ox: float, oy: float) -> None:
        for crate in self.crates:
            if not crate.alive:
                continue
            x, y, r = crate.x + ox, crate.y + oy, crate.radius
            self.canvas.create_rectangle(x - r, y - r, x + r, y + r, fill="#c17b3f", outline="#f5c36d", width=4)
            self.canvas.create_line(x - r, y - r, x + r, y + r, fill="#7e492a", width=5)
            self.canvas.create_line(x + r, y - r, x - r, y + r, fill="#7e492a", width=5)
            if crate.hp < 1500:
                self.bar(x - 25, y - 36, 50, 6, crate.hp / 1500, "#62e66b")
        for pickup in self.pickups:
            y = pickup.y + math.sin(pickup.bob) * 4 + oy
            x = pickup.x + ox
            self.canvas.create_polygon(x, y - 13, x + 12, y - 5, x + 8, y + 12, x - 8, y + 12, x - 12, y - 5, fill="#78ff64", outline="#d8ff8a", width=2)
        for shot in self.projectiles:
            x, y = shot.x + ox, shot.y + oy
            self.canvas.create_line(x - shot.vx * 0.025, y - shot.vy * 0.025, x, y, fill=shot.color, width=shot.radius, capstyle=tk.ROUND)
            self.canvas.create_oval(x - shot.radius, y - shot.radius, x + shot.radius, y + shot.radius, fill="#ffffff", outline=shot.color, width=2)
        for actor in self.actors:
            if not actor.alive:
                continue
            hidden = any(bush.contains(actor) for bush in self.bushes) and self.player is not actor
            if hidden and self.player and distance(actor, self.player) > 115:
                continue
            self.draw_actor(actor, ox, oy)
        for particle in self.particles:
            s = particle.size
            self.canvas.create_oval(particle.x - s + ox, particle.y - s + oy, particle.x + s + ox, particle.y + s + oy, fill=particle.color, outline="")

    def draw_actor(self, actor: Actor, ox: float, oy: float) -> None:
        x, y, r = actor.x + ox, actor.y + oy, actor.radius
        color = "#ffffff" if actor.flash > 0 else actor.color
        self.canvas.create_oval(x - r + 4, y - r + 8, x + r + 4, y + r + 8, fill="#173329", outline="")
        if actor.super_charge >= 100:
            self.canvas.create_oval(x - r - 7, y - r - 7, x + r + 7, y + r + 7, outline="#ffe66d", width=5)
        self.canvas.create_oval(x - r, y - r, x + r, y + r, fill=color, outline="#ffffff", width=2)
        gun_x = x + math.cos(actor.angle) * 34
        gun_y = y + math.sin(actor.angle) * 34
        self.canvas.create_line(x, y, gun_x, gun_y, fill="#263247", width=11, capstyle=tk.ROUND)
        eye_dx, eye_dy = math.cos(actor.angle) * 5, math.sin(actor.angle) * 5
        self.canvas.create_oval(x - 11 + eye_dx, y - 9 + eye_dy, x - 3 + eye_dx, y + 1 + eye_dy, fill="white", outline="")
        self.canvas.create_oval(x + 3 + eye_dx, y - 9 + eye_dy, x + 11 + eye_dx, y + 1 + eye_dy, fill="white", outline="")
        self.bar(x - 27, y - 42, 54, 7, actor.hp / actor.max_hp, "#47ef70" if actor.is_player else "#ff5b6e")
        self.canvas.create_text(x, y - 53, text=f"{actor.name}  ⚡{actor.cubes}", font=("Arial", 9, "bold"), fill="white")

    def bar(self, x: float, y: float, w: float, h: float, ratio: float, color: str) -> None:
        self.canvas.create_rectangle(x, y, x + w, y + h, fill="#20263b", outline="#0c1020")
        self.canvas.create_rectangle(x + 1, y + 1, x + 1 + (w - 2) * clamp(ratio, 0, 1), y + h - 1, fill=color, outline="")

    def draw_hud(self) -> None:
        p = self.player
        if not p:
            return
        alive = sum(1 for actor in self.actors if actor.alive)
        self.canvas.create_rectangle(15, 12, 255, 54, fill="#1b2138", outline="#56638d", width=2)
        self.canvas.create_text(32, 33, text=f"БІЙЦІ: {alive}", anchor="w", font=("Arial Black", 16), fill="white")
        self.canvas.create_text(WIDTH - 25, 31, text=f"{int(self.match_time // 60):02d}:{int(self.match_time % 60):02d}", anchor="e", font=("Arial Black", 16), fill="#ffffff")
        self.canvas.create_rectangle(20, HEIGHT - 26, 320, HEIGHT - 10, fill="#20263b", outline="#090c16")
        self.canvas.create_rectangle(22, HEIGHT - 24, 22 + 296 * max(0, p.hp / p.max_hp), HEIGHT - 12, fill="#42e86a", outline="")
        self.canvas.create_text(170, HEIGHT - 38, text=f"HP {max(0, int(p.hp))} / {int(p.max_hp)}", font=("Arial", 11, "bold"), fill="white")
        cx, cy = WIDTH - 73, HEIGHT - 73
        extent = 359.9 * p.super_charge / 100
        self.canvas.create_oval(cx - 38, cy - 38, cx + 38, cy + 38, fill="#2a3048", outline="#626d91", width=3)
        self.canvas.create_arc(cx - 43, cy - 43, cx + 43, cy + 43, start=90, extent=-extent, style=tk.ARC, outline="#ffe44f", width=8)
        self.canvas.create_text(cx, cy, text="SUPER\nSPACE", font=("Arial Black", 9), fill="#ffe66d" if p.super_charge >= 100 else "#8c94ac")
        dash_text = "READY" if p.dash_cd <= 0 else f"{p.dash_cd:.1f}s"
        self.canvas.create_text(WIDTH - 175, HEIGHT - 32, text=f"SHIFT DASH: {dash_text}", font=("Arial", 10, "bold"), fill="#bfe9ff")

    def overlay(self, title: str, subtitle: str, color: str) -> None:
        self.canvas.create_rectangle(0, 0, WIDTH, HEIGHT, fill="#101528", stipple="gray50", outline="")
        self.canvas.create_text(WIDTH / 2, HEIGHT / 2 - 35, text=title, font=("Arial Black", 45), fill=color)
        self.canvas.create_text(WIDTH / 2, HEIGHT / 2 + 35, text=subtitle, font=("Arial", 17, "bold"), fill="white")

    def draw_result(self, won: bool) -> None:
        self.canvas.create_rectangle(0, 0, WIDTH, HEIGHT, fill="#101528", stipple="gray50", outline="")
        title = "ПЕРЕМОГА!" if won else "ПОРАЗКА"
        color = "#ffe44f" if won else "#ff5b70"
        self.canvas.create_text(WIDTH / 2, 305, text=title, font=("Arial Black", 52), fill=color)
        place = sum(1 for actor in self.actors if actor.alive) + 1 if not won else 1
        self.canvas.create_text(WIDTH / 2, 380, text=f"Місце: #{place}  •  Куби: {self.player.cubes if self.player else 0}", font=("Arial", 18, "bold"), fill="white")
        self.canvas.create_rectangle(425, 475, 675, 535, fill="#35a7ff", outline="#98ddff", width=4)
        self.canvas.create_text(WIDTH / 2, 505, text="ЩЕ РАЗ (R)", font=("Arial Black", 20), fill="white")


def main() -> None:
    root = tk.Tk()
    PocketBrawl(root)
    root.mainloop()


if __name__ == "__main__":
    main()
