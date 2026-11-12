#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================
 sim.py — проверка robot.py на компьютере (без робота)
================================================================

Берёт ту же логику ведения по линии, что и robot.py (класс
LineFollower), и прогоняет её по трассе полигона 1: старт — прямо
50 см — линия — объект впереди.

Запуск:
    python3 tools/sim.py              # обычный прогон
    python3 tools/sim.py --animate    # и анимация polygon1.gif
================================================================
"""

import argparse
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
sys.path.insert(0, ROOT)

from robot import Settings, LineFollower           # noqa: E402

# ------------------------------------------------------------
#  ГЕОМЕТРИЯ (мм). Поле 1565x1500, линия 30 мм.
# ------------------------------------------------------------
FIELD_W, FIELD_H = 1565.0, 1500.0
LINE_W = 30.0

# трасса: ('L', x, y) — прямая к точке; ('ARC', cx, cy, r, a0, sweep)
PATH = [
    ('L', 150.0, 1320.0),
    ('L', 150.0, 260.0),
    ('ARC', 280.0, 260.0, 130.0, 180.0, 90.0),
    ('L', 470.0, 130.0),
    ('ARC', 470.0, 260.0, 130.0, 270.0, 90.0),
    ('L', 600.0, 1260.0),
    ('ARC', 825.0, 1260.0, 225.0, 180.0, -180.0),
    ('L', 1050.0, 260.0),
    ('ARC', 1180.0, 260.0, 130.0, 180.0, 90.0),
    ('L', 1430.0, 130.0),
]

# объект-помеха: цилиндр Ø160, стоит на линии в зоне объезда
OBJECT_X, OBJECT_Y = 600.0, 800.0
OBJECT_R = 80.0

# датчики: спереди и по бокам от оси
SENSOR_FWD = 60.0
SENSOR_HALF = 16.0   # каждый датчик — на краю линии (линия 30 мм)
SONAR_RANGE = 1200.0


class Track(object):
    """Ломаная с дугами: ближайшая точка, расстояние, проекция."""

    def __init__(self, path):
        self.parts = []            # ('L', x0, y0, x1, y1) / ('A', cx, cy, r, a0, a1)
        x, y = path[0][1], path[0][2]
        self.length = 0.0
        for seg in path[1:]:
            if seg[0] == 'L':
                self.parts.append(('L', x, y, seg[1], seg[2]))
                self.length += math.hypot(seg[1] - x, seg[2] - y)
                x, y = seg[1], seg[2]
            else:
                _, cx, cy, r, a0, sweep = seg
                self.parts.append(('A', cx, cy, r, a0, a0 + sweep))
                self.length += abs(math.radians(sweep)) * r
                a1 = math.radians(a0 + sweep)
                x, y = cx + r * math.cos(a1), cy + r * math.sin(a1)

    def _closest(self, px, py):
        best = (1e9, 0.0, 0.0, 0.0)
        for p in self.parts:
            if p[0] == 'L':
                _, x0, y0, x1, y1 = p
                dx, dy = x1 - x0, y1 - y0
                l2 = dx * dx + dy * dy
                t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / l2))
                cx, cy = x0 + t * dx, y0 + t * dy
            else:
                _, cx, cy, r, a0, a1 = p
                a = math.atan2(py - cy, px - cx)
                lo, hi = min(a0, a1), max(a0, a1)
                while a < lo:
                    a += 2 * math.pi
                while a > hi:
                    a -= 2 * math.pi
                a = max(lo, min(hi, a))
                cx, cy = cx + r * math.cos(a), cy + r * math.sin(a)
            d = math.hypot(px - cx, py - cy)
            if d < best[0]:
                best = (d, cx, cy, 0.0)
        return best

    def dist(self, px, py):
        return self._closest(px, py)[0]

    def span(self, px, py):
        """Насколько точка поперёк линии (знак: + справа от хода вниз)."""
        d, cx, cy, _ = self._closest(px, py)
        return math.copysign(min(d, 200.0), px - cx)


def make_track():
    return Track(PATH)


def reflection_at(track, px, py, rnd):
    """Показание датчика света: 0 на линии, 100 на белом."""
    d = track.dist(px, py)
    edge = LINE_W / 2.0
    if d <= edge * 0.7:
        return 0.0 + rnd.gauss(0, 1.5)
    if d >= edge * 1.3:
        return 88.0 + rnd.gauss(0, 2.0)
    k = (d - edge * 0.7) / (edge * 0.6)
    return 0.0 + 88.0 * k + rnd.gauss(0, 1.5)


def sonar_front(px, py, heading):
    """Расстояние до объекта по курсу (как EV3-ультразвук, ±25°)."""
    dx, dy = OBJECT_X - px, OBJECT_Y - py
    dist = math.hypot(dx, dy)
    if dist > SONAR_RANGE:
        return SONAR_RANGE
    ang = math.atan2(dy, dx) - heading
    ang = (ang + math.pi) % (2 * math.pi) - math.pi
    half = math.asin(min(1.0, OBJECT_R / max(dist, 1.0)))
    if abs(ang) > math.radians(25.0) + half:
        return SONAR_RANGE
    return max(0.0, dist - OBJECT_R)


class Env(object):
    """
    «Мир»: робот, трасса, объект. Шагаем одинаково с robot.py:
    drive(speed, steer) — как команды на моторы.
    """

    def __init__(self, cfg, seed=1, object_xy=(OBJECT_X, OBJECT_Y)):
        self.cfg = cfg
        self.rnd = random.Random(seed)
        self.track = make_track()
        self.object_xy = object_xy
        self.x, self.y = 150.0, 1320.0
        self.heading = -math.pi / 2          # вниз по схеме
        self.t = 0.0
        self.odometer = 0.0
        self.trail = []
        self.max_dev = 0.0

    def sensors(self):
        cx = self.x + SENSOR_FWD * math.cos(self.heading)
        cy = self.y + SENSOR_FWD * math.sin(self.heading)
        # 1 — ЛЕВЫЙ датчик: слева от курса (heading + 90°)
        lx = cx + SENSOR_HALF * math.cos(self.heading + math.pi / 2)
        ly = cy + SENSOR_HALF * math.sin(self.heading + math.pi / 2)
        # 2 — ПРАВЫЙ датчик: справа от курса (heading - 90°)
        rx = cx + SENSOR_HALF * math.cos(self.heading - math.pi / 2)
        ry = cy + SENSOR_HALF * math.sin(self.heading - math.pi / 2)
        refl_l = reflection_at(self.track, lx, ly, self.rnd)
        refl_r = reflection_at(self.track, rx, ry, self.rnd)
        dx, dy = self.object_xy[0] - cx, self.object_xy[1] - cy
        dist = math.hypot(dx, dy)
        ang = math.atan2(dy, dx) - self.heading
        ang = (ang + math.pi) % (2 * math.pi) - math.pi
        sonar = SONAR_RANGE
        if dist <= SONAR_RANGE:
            half = math.asin(min(1.0, OBJECT_R / max(dist, 1.0)))
            if abs(ang) <= math.radians(25.0) + half:
                sonar = max(0.0, dist - OBJECT_R)
        return refl_l, refl_r, sonar

    def step(self, speed, steer, dt=0.01):
        """Одна итерация: команды моторам → новое положение."""
        # дифференциальный привод: steer=+1 → левое быстрее правого
        v_left = speed * (1.0 - steer)
        v_right = speed * (1.0 + steer)
        v = (v_left + v_right) / 2.0
        omega = (v_right - v_left) / self.cfg.axle_track_mm     # рад/с
        self.heading += omega * dt + self.rnd.gauss(0, 0.0015)
        self.x += math.cos(self.heading) * v * dt
        self.y += math.sin(self.heading) * v * dt
        self.odometer += v * dt
        self.t += dt
        dev = self.track.dist(self.x, self.y)
        if dev > self.max_dev:
            self.max_dev = dev
        self.trail.append((self.x, self.y))

    def distance_to_object(self):
        return math.hypot(self.x - self.object_xy[0], self.y - self.object_xy[1])

    def clear_of_object(self):
        """Зазор от КВАДРАТА корпуса 200x200 до центра объекта."""
        dx = abs(self.object_xy[0] - self.x) - 100.0
        dy = abs(self.object_xy[1] - self.y) - 100.0
        if dx < 0 and dy < 0:
            return max(dx, dy)
        if dx < 0 or dy < 0:
            return max(0.0, dx) + max(0.0, dy)
        return math.hypot(dx, dy)


def run(cfg=None, seed=1, start=None, object_xy=(OBJECT_X, OBJECT_Y),
        verbose=True, keep_frames=False):
    """Прогон программы robot.py в симуляторе."""
    cfg = cfg or Settings()
    env = Env(cfg, seed, object_xy)
    if start:
        env.x, env.y, env.heading = start
    follower = LineFollower(cfg)

    dt = cfg.loop_ms / 1000.0
    frames = []
    result = {'note': 'лимит времени', 'time': 0.0}

    # ---------- 1. прямо 50 см ----------
    need = cfg.start_straight_mm
    odo0 = env.odometer
    while env.odometer - odo0 < need and env.t < 5.0:
        env.step(cfg.start_speed_mm_s, 0.0, dt)
    if verbose:
        print('старт: прямо %.0f мм за %.1f с' % (need, env.t))

    # ---------- 2. линия, пока не увидим объект ----------
    min_clear = 9999.0
    while env.t < 60.0:
        refl_l, refl_r, sonar = env.sensors()

        clear = env.clear_of_object()
        if clear < min_clear:
            min_clear = clear

        if sonar < cfg.stop_mm:
            result = {'note': 'объект стоп', 'time': env.t}
            break
        if env.distance_to_object() < 1e-6:
            result = {'note': 'наехали на объект', 'time': env.t}
            break

        speed, steer = follower.update(refl_l, refl_r, dt)
        if follower.state == 'lost':
            result = {'note': 'линия потеряна', 'time': env.t}
            break

        env.step(speed, steer, dt)
        if keep_frames:
            frames.append((env.x, env.y))

    res = {
        'note': result['note'],
        'time': result['time'],
        'x': env.x,
        'y': env.y,
        'max_dev': env.max_dev,
        'min_clear': min_clear,
        'trail': env.trail,
        'frames': frames if keep_frames else None,
        'state': follower.state,
    }
    if verbose:
        print('--- итог ---')
        print('время:        %.1f с' % res['time'])
        print('примечание:   %s' % res['note'])
        print('макс. откл. от линии: %.0f мм' % res['max_dev'])
        print('зазор до объекта:     %.0f мм (радиус 80)' % min_clear)
    return res


# ------------------------------------------------------------
#  Картинка + анимация
# ------------------------------------------------------------

def path_points(step_mm=6.0):
    """Вся трасса одной ломаной — чтобы рисовать без разрывов."""
    pts = []
    x, y = PATH[0][1], PATH[0][2]
    pts.append((x, y))
    for seg in PATH[1:]:
        if seg[0] == 'L':
            x1, y1 = seg[1], seg[2]
            n = max(1, int(math.hypot(x1 - x, y1 - y) / step_mm))
            for i in range(1, n + 1):
                pts.append((x + (x1 - x) * i / n, y + (y1 - y) * i / n))
            x, y = x1, y1
        else:
            _, cx, cy, r, a0, sweep = seg
            n = max(2, int(abs(math.radians(sweep)) * r / step_mm))
            for i in range(1, n + 1):
                a = math.radians(a0 + sweep * i / n)
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
            a = math.radians(a0 + sweep)
            x, y = cx + r * math.cos(a), cy + r * math.sin(a)
    return pts


def render(res, path, scale=0.45):
    from PIL import Image, ImageDraw
    img = Image.new('RGB', (int(FIELD_W * scale) + 20, int(FIELD_H * scale) + 20), 'white')
    d = ImageDraw.Draw(img)

    def P(x, y):
        return (10 + x * scale, 10 + (FIELD_H - y) * scale)

    d.line([P(x, y) for x, y in path_points()], fill='black',
           width=max(2, int(LINE_W * scale)), joint='curve')
    d.rectangle([P(0, 1500), P(300, 1200)], outline='green', width=2)
    ox, oy = P(OBJECT_X, OBJECT_Y)
    r = OBJECT_R * scale
    d.ellipse([ox - r, oy - r, ox + r, oy + r], outline='red', width=2)
    if res.get('trail'):
        d.line([P(x, y) for x, y in res['trail'][::3]], fill='blue', width=2)
    rx, ry = P(res['x'], res['y'])
    d.ellipse([rx - 5, ry - 5, rx + 5, ry + 5], fill='blue')
    img.save(path)
    return path


def animate(path='polygon1.gif', seed=1, cfg=None):
    """GIF-анимация прогона: видно робота, линию и объект."""
    from PIL import Image, ImageDraw
    cfg = cfg or Settings()
    res = run(cfg, seed=seed, keep_frames=True, verbose=False)
    frames = res['frames'] or []
    if not frames:
        print('нет кадров для анимации')
        return None

    w, h = 470, 450
    scale = 0.30
    obj = OBJECT_X, OBJECT_Y

    def P(x, y):
        return (10 + x * scale, 10 + (FIELD_H - y) * scale)

    base = Image.new('RGB', (w, h), 'white')
    d0 = ImageDraw.Draw(base)
    d0.line([P(x, y) for x, y in path_points()], fill='black', width=3, joint='curve')
    d0.rectangle([P(0, 1500), P(300, 1200)], outline='green', width=2)
    ox, oy = P(*obj)
    rr = OBJECT_R * scale
    d0.ellipse([ox - rr, oy - rr, ox + rr, oy + rr], outline='red', width=2)

    imgs = []
    step = max(1, len(frames) // 120)
    dt = cfg.loop_ms / 1000.0
    for i in range(0, len(frames), step):
        img = base.copy()
        d = ImageDraw.Draw(img)
        # след пути до текущего кадра
        if i > 1:
            d.line([P(x, y) for x, y in frames[:i:3]], fill='#4a90d9', width=2)
        x, y = frames[i]
        px, py = P(x, y)
        d.line([(px - 8, py - 8), (px + 8, py + 8)], fill='blue', width=3)
        d.line([(px - 8, py + 8), (px + 8, py - 8)], fill='blue', width=3)
        d.text((12, h - 18), 't = %.1f s' % (i * dt + 0.0), fill='black')
        imgs.append(img)
    imgs[0].save(path, save_all=True, append_images=imgs[1:], duration=60, loop=0)
    print('кадров: %d -> %s' % (len(imgs), path))
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--animate', action='store_true', help='сделать polygon1.gif')
    ap.add_argument('--render', default=None, help='картинка трассы с путём')
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--obj-y', type=float, default=OBJECT_Y,
                    help='где стоит объект по Y (по умолчанию 800)')
    args = ap.parse_args()

    res = run(seed=args.seed, object_xy=(OBJECT_X, args.obj_y))
    if args.render:
        render(res, args.render)
        print('картинка: %s' % args.render)
    if args.animate:
        animate('polygon1.gif', seed=args.seed)


if __name__ == '__main__':
    main()
