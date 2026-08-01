import math
import random
import time
import tkinter as tk


WIDTH, HEIGHT = 1000, 650
PLAYER_SPEED = 270
BULLET_SPEED = 620


def clamp(value, low, high):
    return max(low, min(high, value))


def distance(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)


class MiniBrawl:
    def __init__(self, root):
        self.root = root
        self.root.title("Mini Brawl — Python Edition")
        self.root.resizable(False, False)
        self.canvas = tk.Canvas(root, width=WIDTH, height=HEIGHT, bg="#62c96b", highlightthickness=0)
        self.canvas.pack()

        self.keys = set()
        self.mouse_x = WIDTH // 2
        self.mouse_y = HEIGHT // 2
        self.mouse_down = False
        self.running = True
        self.last_time = time.perf_counter()
        self.last_shot = 0.0

        root.bind("<KeyPress>", self.key_down)
        root.bind("<KeyRelease>", self.key_up)
        root.bind("<Motion>", self.mouse_move)
        root.bind("<ButtonPress-1>", self.mouse_press)
        root.bind("<ButtonRelease-1>", self.mouse_release)
        root.focus_force()

        self.reset()
        self.loop()

    def reset(self):
        self.running = True
        self.score = 0
        self.wave = 1
        self.bullets = []
        self.enemy_bullets = []
        self.pickups = []
        self.player = {
            "x": WIDTH / 2,
            "y": HEIGHT / 2,
            "r": 22,
            "hp": 100,
            "max_hp": 100,
            "ammo": 3.0,
            "hit_flash": 0.0,
        }
        self.walls = [
            (150, 120, 300, 155),
            (700, 120, 850, 155),
            (80, 300, 230, 340),
            (770, 300, 920, 340),
            (170, 500, 320, 535),
            (680, 500, 830, 535),
            (445, 210, 555, 250),
            (445, 400, 555, 440),
        ]
        self.enemies = []
        self.spawn_wave()

    def spawn_wave(self):
        count = min(3 + self.wave, 10)
        for _ in range(count):
            for _attempt in range(100):
                x = random.choice([random.randint(35, 150), random.randint(850, 965)])
                y = random.randint(50, HEIGHT - 50)
                if distance(x, y, self.player["x"], self.player["y"]) > 320 and not self.circle_hits_wall(x, y, 20):
                    break
            self.enemies.append({
                "x": x,
                "y": y,
                "r": 20,
                "hp": 45 + self.wave * 6,
                "max_hp": 45 + self.wave * 6,
                "speed": random.randint(75, 105) + self.wave * 3,
                "shoot_cd": random.uniform(0.4, 1.5),
                "strafe": random.choice([-1, 1]),
                "hit_flash": 0.0,
            })

    def key_down(self, event):
        key = event.keysym.lower()
        self.keys.add(key)
        if key == "r" and not self.running:
            self.reset()

    def key_up(self, event):
        self.keys.discard(event.keysym.lower())

    def mouse_move(self, event):
        self.mouse_x, self.mouse_y = event.x, event.y

    def mouse_press(self, _event):
        self.mouse_down = True

    def mouse_release(self, _event):
        self.mouse_down = False

    def circle_hits_wall(self, x, y, radius):
        for left, top, right, bottom in self.walls:
            nearest_x = clamp(x, left, right)
            nearest_y = clamp(y, top, bottom)
            if distance(x, y, nearest_x, nearest_y) < radius:
                return True
        return False

    def move_circle(self, obj, dx, dy):
        new_x = clamp(obj["x"] + dx, obj["r"], WIDTH - obj["r"])
        if not self.circle_hits_wall(new_x, obj["y"], obj["r"]):
            obj["x"] = new_x
        new_y = clamp(obj["y"] + dy, obj["r"] + 35, HEIGHT - obj["r"])
        if not self.circle_hits_wall(obj["x"], new_y, obj["r"]):
            obj["y"] = new_y

    def shoot(self):
        now = time.perf_counter()
        if self.player["ammo"] < 1 or now - self.last_shot < 0.16:
            return
        dx = self.mouse_x - self.player["x"]
        dy = self.mouse_y - self.player["y"]
        length = math.hypot(dx, dy) or 1
        dx, dy = dx / length, dy / length
        self.bullets.append({
            "x": self.player["x"] + dx * 27,
            "y": self.player["y"] + dy * 27,
            "vx": dx * BULLET_SPEED,
            "vy": dy * BULLET_SPEED,
            "life": 0.9,
            "r": 6,
        })
        self.player["ammo"] -= 1
        self.last_shot = now

    def enemy_shoot(self, enemy):
        dx = self.player["x"] - enemy["x"]
        dy = self.player["y"] - enemy["y"]
        length = math.hypot(dx, dy) or 1
        dx, dy = dx / length, dy / length
        self.enemy_bullets.append({
            "x": enemy["x"] + dx * 24,
            "y": enemy["y"] + dy * 24,
            "vx": dx * (280 + self.wave * 8),
            "vy": dy * (280 + self.wave * 8),
            "life": 2.4,
            "r": 6,
        })

    def update(self, dt):
        if not self.running:
            return

        p = self.player
        mx = (1 if "d" in self.keys or "right" in self.keys else 0) - (1 if "a" in self.keys or "left" in self.keys else 0)
        my = (1 if "s" in self.keys or "down" in self.keys else 0) - (1 if "w" in self.keys or "up" in self.keys else 0)
        if mx or my:
            length = math.hypot(mx, my)
            self.move_circle(p, mx / length * PLAYER_SPEED * dt, my / length * PLAYER_SPEED * dt)

        p["ammo"] = min(3.0, p["ammo"] + dt * 0.8)
        p["hit_flash"] = max(0, p["hit_flash"] - dt)
        if self.mouse_down or "space" in self.keys:
            self.shoot()

        for bullet in self.bullets[:]:
            bullet["x"] += bullet["vx"] * dt
            bullet["y"] += bullet["vy"] * dt
            bullet["life"] -= dt
            remove = bullet["life"] <= 0 or self.circle_hits_wall(bullet["x"], bullet["y"], bullet["r"])
            if not remove:
                for enemy in self.enemies[:]:
                    if distance(bullet["x"], bullet["y"], enemy["x"], enemy["y"]) < bullet["r"] + enemy["r"]:
                        enemy["hp"] -= 25
                        enemy["hit_flash"] = 0.09
                        remove = True
                        if enemy["hp"] <= 0:
                            self.enemies.remove(enemy)
                            self.score += 100
                            if random.random() < 0.28:
                                self.pickups.append({"x": enemy["x"], "y": enemy["y"], "life": 10})
                        break
            if remove and bullet in self.bullets:
                self.bullets.remove(bullet)

        for enemy in self.enemies:
            enemy["hit_flash"] = max(0, enemy["hit_flash"] - dt)
            dx = p["x"] - enemy["x"]
            dy = p["y"] - enemy["y"]
            dist = math.hypot(dx, dy) or 1
            nx, ny = dx / dist, dy / dist
            if dist > 240:
                move_x, move_y = nx, ny
            else:
                move_x = -ny * enemy["strafe"] * 0.75 - nx * 0.18
                move_y = nx * enemy["strafe"] * 0.75 - ny * 0.18
            self.move_circle(enemy, move_x * enemy["speed"] * dt, move_y * enemy["speed"] * dt)
            enemy["shoot_cd"] -= dt
            if enemy["shoot_cd"] <= 0 and dist < 520:
                self.enemy_shoot(enemy)
                enemy["shoot_cd"] = random.uniform(1.0, 1.65) * max(0.55, 1 - self.wave * 0.025)

        for bullet in self.enemy_bullets[:]:
            bullet["x"] += bullet["vx"] * dt
            bullet["y"] += bullet["vy"] * dt
            bullet["life"] -= dt
            remove = bullet["life"] <= 0 or self.circle_hits_wall(bullet["x"], bullet["y"], bullet["r"])
            if not remove and distance(bullet["x"], bullet["y"], p["x"], p["y"]) < bullet["r"] + p["r"]:
                p["hp"] -= 12 + self.wave
                p["hit_flash"] = 0.12
                remove = True
                if p["hp"] <= 0:
                    p["hp"] = 0
                    self.running = False
            if remove and bullet in self.enemy_bullets:
                self.enemy_bullets.remove(bullet)

        for pickup in self.pickups[:]:
            pickup["life"] -= dt
            if distance(pickup["x"], pickup["y"], p["x"], p["y"]) < 35:
                p["hp"] = min(p["max_hp"], p["hp"] + 25)
                self.pickups.remove(pickup)
            elif pickup["life"] <= 0:
                self.pickups.remove(pickup)

        if not self.enemies and self.running:
            self.wave += 1
            p["hp"] = min(p["max_hp"], p["hp"] + 20)
            self.spawn_wave()

    def draw_bar(self, x, y, width, value, maximum, color):
        ratio = clamp(value / maximum, 0, 1)
        self.canvas.create_rectangle(x - width / 2, y, x + width / 2, y + 7, fill="#352f3c", outline="")
        self.canvas.create_rectangle(x - width / 2 + 1, y + 1, x - width / 2 + (width - 2) * ratio, y + 6, fill=color, outline="")

    def draw(self):
        c = self.canvas
        c.delete("all")
        c.create_rectangle(0, 0, WIDTH, HEIGHT, fill="#62c96b", outline="")
        for x in range(25, WIDTH, 50):
            for y in range(55, HEIGHT, 50):
                c.create_oval(x, y, x + 5, y + 5, fill="#55b95e", outline="")

        for left, top, right, bottom in self.walls:
            c.create_rectangle(left + 5, top + 6, right + 5, bottom + 6, fill="#3d7b42", outline="")
            c.create_rectangle(left, top, right, bottom, fill="#c58a52", outline="#7d4f2b", width=3)
            for x in range(left + 14, right, 30):
                c.create_line(x, top + 3, x, bottom - 3, fill="#a66f3f", width=2)

        for pickup in self.pickups:
            x, y = pickup["x"], pickup["y"]
            c.create_oval(x - 13, y - 13, x + 13, y + 13, fill="#54e675", outline="#116c2c", width=3)
            c.create_rectangle(x - 3, y - 9, x + 3, y + 9, fill="white", outline="")
            c.create_rectangle(x - 9, y - 3, x + 9, y + 3, fill="white", outline="")

        for bullet in self.bullets:
            x, y, r = bullet["x"], bullet["y"], bullet["r"]
            c.create_oval(x - r, y - r, x + r, y + r, fill="#ffeb3b", outline="#e57c00", width=2)
        for bullet in self.enemy_bullets:
            x, y, r = bullet["x"], bullet["y"], bullet["r"]
            c.create_oval(x - r, y - r, x + r, y + r, fill="#ff5b55", outline="#9d1515", width=2)

        for enemy in self.enemies:
            x, y, r = enemy["x"], enemy["y"], enemy["r"]
            color = "white" if enemy["hit_flash"] > 0 else "#e84d63"
            c.create_oval(x - r, y - r, x + r, y + r, fill=color, outline="#802034", width=3)
            c.create_oval(x - 9, y - 7, x - 3, y - 1, fill="#24202b", outline="")
            c.create_oval(x + 3, y - 7, x + 9, y - 1, fill="#24202b", outline="")
            self.draw_bar(x, y - 31, 44, enemy["hp"], enemy["max_hp"], "#ff425b")

        p = self.player
        angle = math.atan2(self.mouse_y - p["y"], self.mouse_x - p["x"])
        gun_x = p["x"] + math.cos(angle) * 29
        gun_y = p["y"] + math.sin(angle) * 29
        c.create_line(p["x"], p["y"], gun_x, gun_y, fill="#303b57", width=12)
        player_color = "white" if p["hit_flash"] > 0 else "#3e83ef"
        c.create_oval(p["x"] - p["r"], p["y"] - p["r"], p["x"] + p["r"], p["y"] + p["r"], fill=player_color, outline="#164d9e", width=4)
        c.create_oval(p["x"] - 10, p["y"] - 8, p["x"] - 3, p["y"] - 1, fill="white", outline="")
        c.create_oval(p["x"] + 3, p["y"] - 8, p["x"] + 10, p["y"] - 1, fill="white", outline="")
        self.draw_bar(p["x"], p["y"] - 37, 58, p["hp"], p["max_hp"], "#42e56f")

        c.create_rectangle(0, 0, WIDTH, 40, fill="#24202b", outline="")
        c.create_text(18, 20, anchor="w", text=f"SCORE  {self.score}", fill="white", font=("Arial", 16, "bold"))
        c.create_text(WIDTH / 2, 20, text=f"WAVE  {self.wave}", fill="#ffd64a", font=("Arial", 16, "bold"))
        c.create_text(WIDTH - 18, 20, anchor="e", text=f"ENEMIES  {len(self.enemies)}", fill="white", font=("Arial", 16, "bold"))

        for index in range(3):
            x = WIDTH / 2 - 34 + index * 34
            loaded = p["ammo"] >= index + 1
            c.create_rectangle(x - 12, HEIGHT - 28, x + 12, HEIGHT - 10, fill="#ffd83d" if loaded else "#657080", outline="#272d38", width=2)

        c.create_oval(self.mouse_x - 10, self.mouse_y - 10, self.mouse_x + 10, self.mouse_y + 10, outline="white", width=2)
        c.create_line(self.mouse_x - 15, self.mouse_y, self.mouse_x + 15, self.mouse_y, fill="white")
        c.create_line(self.mouse_x, self.mouse_y - 15, self.mouse_x, self.mouse_y + 15, fill="white")

        if not self.running:
            c.create_rectangle(220, 190, 780, 460, fill="#201c2a", outline="#f14f64", width=5)
            c.create_text(WIDTH / 2, 260, text="GAME OVER", fill="#ff5368", font=("Arial", 42, "bold"))
            c.create_text(WIDTH / 2, 330, text=f"Score: {self.score}    Wave: {self.wave}", fill="white", font=("Arial", 22, "bold"))
            c.create_text(WIDTH / 2, 400, text="Press R to play again", fill="#ffd64a", font=("Arial", 18, "bold"))

    def loop(self):
        now = time.perf_counter()
        dt = min(now - self.last_time, 0.033)
        self.last_time = now
        self.update(dt)
        self.draw()
        self.root.after(16, self.loop)


if __name__ == "__main__":
    window = tk.Tk()
    MiniBrawl(window)
    window.mainloop()
