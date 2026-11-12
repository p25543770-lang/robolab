#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================
 robot.py — полигон 1: езда по линии + остановка перед объектом
================================================================

Что делает робот:

  1. Старт: едет ПРЯМО 50 см (выезжает из зелёной зоны старта).
  2. Дальше едет ПО ЛИНИИ (два датчика отражённого света снизу,
     простой П-регулятор), пока не увидит объект впереди.
  3. Увидел объект (ультразвук, порт 3) — останавливается и пищит.

Раскладка (как договорились):

    1 — ЛЕВЫЙ датчик отражённого света (снизу)
    2 — ПРАВЫЙ датчик отражённого света (снизу)
    3 — ультразвук ВПЕРЁД
    C — ЛЕВОЕ колесо
    B — ПРАВОЕ колесо

Файл самодостаточный: на EV3 заливаете только его (Pybricks).
Логику (класс LineFollower) использует и симулятор tools/sim.py,
поэтому здесь нет обязательных импортов pybricks — на компьютере
файл тоже читается.
================================================================
"""

# --- pybricks есть только на роботе; на ПК этот импорт просто не сработает ---
try:
    from pybricks.hubs import EV3Brick
    from pybricks.ev3devices import Motor, ColorSensor, UltrasonicSensor
    from pybricks.parameters import Port
    from pybricks.tools import wait
    HAS_ROBOT = True
except ImportError:                       # запуск на компьютере
    HAS_ROBOT = False


# ============================================================
#  НАСТРОЙКИ — всё, что может понадобиться подкрутить
# ============================================================

class Settings(object):
    """
    Все числа в одном месте. Меняете здесь — меняется поведение.
    Можно и в коде: Settings(kp=2.0) — удобно для подбора.
    """

    def __init__(self, **kw):
        for k, v in kw.items():
            if not hasattr(Settings, k):
                raise AttributeError('нет такого параметра: ' + k)
            setattr(self, k, v)

    # ---------- робот ----------
    wheel_diameter_mm = 56.0    # диаметр колеса (у больших колёс EV3 — 56)
    axle_track_mm = 150.0       # расстояние между центрами колёс — ИЗМЕРЬТЕ линейкой
    gear_ratio = 2.0            # редуктор 2:1 — малая шестерня на моторе,
                                # большая на колесе (колесо крутится в 2 раза медленнее)
    left_motor_reversed = True  # левый мотор стоит «наоборот» → в программе реверс
    right_motor_reversed = False

    # ---------- старт ----------
    start_straight_mm = 500.0   # проехать прямо 50 см
    start_speed_mm_s = 200.0    # мм/с на этом отрезке

    # ---------- езда по линии ----------
    cruise_mm_s = 200.0         # крейсерская скорость, мм/с
    motor_max_dps = 950.0       # предел мотора EV3, °/с (с редуктором 2:1 это
                                # ~230 мм/с — быстрее мотор не сможет)
    min_mm_s = 90.0             # самая маленькая скорость в повороте
    slow_k = 0.6                # насколько тормозим при большом отклонении

    kp = 1.6                    # «руль» на единицу ошибки (начните с 1.6)
    kd = 0.0                    # демпфирование (если виляет — 0.05...0.15)
    steer_limit = 1.0           # предел «руля» (1.0 = максимум)

    # ---------- датчики света ----------
    # Показания датчика: 0 — чёрная линия, 100 — белое поле.
    # Если робот «не видит» линию или рвётся в сторону — проверьте эти числа:
    # поставьте робота на линию, посмотрите значение (robot.py --check).
    black_ref = 8.0
    white_ref = 80.0
    lost_time = 0.25            # с — столько белого подряд = ищем линию
    search_steer = 0.9          # 0..1 — насколько резко крутимся в поиске
    search_speed = 60.0         # мм/с — ползём по дуге, пока ищем
    search_swap_time = 1.2      # с — через столько ищем в другую сторону
    search_max_time = 6.0       # с — дольше не ищем, останавливаемся

    # ---------- объект впереди ----------
    stop_mm = 250.0             # ближе — считаем, что впереди объект
    sonar_max_mm = 1200.0       # дальше этого не смотрим (шум датчика)

    # ---------- прочее ----------
    loop_ms = 10                # период цикла управления, мс


# ============================================================
#  ЛОГИКА ВЕДЕНИЯ ПО ЛИНИИ (без железа — её же гоняет симулятор)
# ============================================================

def clamp(x, lo, hi):
    return lo if x < lo else (hi if x > hi else x)


class LineFollower(object):
    """
    Два датчика света по бокам от линии.

    Каждый датчик переводим в «0 = чёрное, 1 = белое».
    Робот стоит ровно, когда оба датчика видят одинаково.

        ошибка = правый - левый

    Если робот съехал вправо, линия оказалась слева: левый датчик
    видит чёрное (0), правый — белое (1), ошибка = +1 → рулим влево
    (steer > 0 = правое колесо быстрее = поворот влево).

    update(...) возвращает (speed_mm_s, steer), где
    steer: -1 — влево на месте, +1 — вправо на месте, 0 — прямо.
    """

    def __init__(self, cfg=None):
        self.cfg = cfg or Settings()
        self.reset()

    def reset(self):
        self.last_error = 0.0
        self.deriv = 0.0
        self.white_time = 0.0
        self.search_time = 0.0
        self.search_dir = 1.0      # куда крутиться, если линия потеряна
        self.state = 'ok'          # 'ok' | 'search' | 'lost'

    # --- перевод показания датчика в 0..1 ---
    def norm(self, reflection):
        cfg = self.cfg
        span = max(1.0, cfg.white_ref - cfg.black_ref)
        return clamp((reflection - cfg.black_ref) / span, 0.0, 1.0)

    def update(self, refl_left, refl_right, dt):
        """
        Один шаг. Возвращает (speed_mm_s, steer).

        Если оба датчика долго видят белое — линия потеряна:
        крутимся на месте в ту сторону, где её видели последний раз.
        Как только датчик снова нашёл чёрное — едем дальше.
        """
        cfg = self.cfg
        if dt <= 0.0:
            dt = cfg.loop_ms / 1000.0

        left = self.norm(refl_left)
        right = self.norm(refl_right)
        black_left = left < 0.5
        black_right = right < 0.5

        # ---- потеря линии: оба датчика видят белое ----
        if (not black_left) and (not black_right):
            self.white_time += dt
        else:
            self.white_time = 0.0

        # ---- поиск линии ----
        if self.state == 'search' or self.white_time > cfg.lost_time:
            if black_left or black_right:
                # нашли — возвращаемся к обычной езде
                self.state = 'ok'
                self.white_time = 0.0
                self.last_error = 0.0
            else:
                self.state = 'search'
                self.search_time += dt
                if self.search_time > cfg.search_max_time:
                    self.state = 'lost'
                    return 0.0, 0.0
                # едем по дуге в сторону, где линия была последний раз:
                # при speed>0 и steer=±1 робот почти крутится на месте,
                # но всё же смещается — так линия быстрее попадёт под датчик
                if self.search_time > cfg.search_swap_time:
                    self.search_dir = -self.search_dir      # ищем в другую сторону
                    self.search_time = 0.0
                return cfg.search_speed, self.search_dir * cfg.search_steer

        error = right - left

        # запоминаем, с какой стороны была линия: если правый датчик
        # ещё на линии (чёрный), а левый уже нет — линия справа от нас
        if black_left and not black_right:
            self.search_dir = -1.0       # линия ушла влево от нас
        elif black_right and not black_left:
            self.search_dir = 1.0        # линия ушла вправо

        # П + Д: Д гасит виляние, но при шуме датчиков может мешать
        self.deriv = (error - self.last_error) / dt
        self.last_error = error

        steer = cfg.kp * error + cfg.kd * self.deriv
        steer = clamp(steer, -cfg.steer_limit, cfg.steer_limit)

        # в крутом повороте притормаживаем
        speed = cfg.cruise_mm_s * (1.0 - cfg.slow_k * abs(steer))
        speed = max(cfg.min_mm_s, speed)
        return speed, steer


# ============================================================
#  ЖЕЛЕЗО: моторы, датчики, поездки
# ============================================================

if HAS_ROBOT:

    class Robot(object):
        """Моторы B (правое) и C (левое), датчики 1, 2 и 3."""

        def __init__(self, cfg=None):
            self.cfg = cfg or Settings()
            self.brick = EV3Brick()
            self.left_motor = Motor(Port.C)      # C — левое колесо
            self.right_motor = Motor(Port.B)     # B — правое колесо
            self.sensor_left = ColorSensor(Port.S1)   # 1 — левый снизу
            self.sensor_right = ColorSensor(Port.S2)  # 2 — правый снизу
            self.sonar = UltrasonicSensor(Port.S3)    # 3 — ультразвук вперёд
            # сколько градусов должен провернуть МОТОР, чтобы робот проехал 1 мм
            #   колесо: 360° на оборот → pi*d мм за оборот
            #   редуктор 2:1 → мотор крутится в 2 раза быстрее колеса
            mm_per_wheel_turn = 3.14159265 * self.cfg.wheel_diameter_mm
            self.motor_deg_per_mm = (360.0 / mm_per_wheel_turn) * self.cfg.gear_ratio
            # знак левого мотора: если он стоит зеркально, шлём ему минус
            self.left_sign = -1.0 if self.cfg.left_motor_reversed else 1.0
            self.right_sign = -1.0 if self.cfg.right_motor_reversed else 1.0

        # ---------- служебное ----------
        def beep(self, times=1):
            for _ in range(times):
                self.brick.speaker.beep(600, 120)
                if times > 1:
                    wait(120)

        def stop(self):
            self.left_motor.stop()
            self.right_motor.stop()

        def travel_mm(self):
            """
            Сколько мм проехали (по среднему углу двух моторов).
            Угол левого мотора берём со знаком реверса — иначе колёса
            «тянут» счёт в разные стороны.
            """
            deg = (self.left_sign * self.left_motor.angle()
                   + self.right_sign * self.right_motor.angle()) / 2.0
            return deg / self.motor_deg_per_mm

        def reset_travel(self):
            self.left_motor.reset_angle(0)
            self.right_motor.reset_angle(0)

        # ---------- движение ----------
        def drive(self, speed_mm_s, steer):
            """
            speed_mm_s — скорость центра, мм/с (может быть < 0 — назад)
            steer — «руль»: +1 вправо на месте, -1 влево, 0 прямо
            """
            # steer > 0 → правое колесо быстрее → робот поворачивает влево
            # (так же считает и симулятор tools/sim.py)
            v_left = speed_mm_s * (1.0 - steer)
            v_right = speed_mm_s * (1.0 + steer)
            # градусы МОТОРА в секунду: мм/с → °/с (с учётом редуктора 2:1)
            lim = self.cfg.motor_max_dps
            dl = self.left_sign * v_left * self.motor_deg_per_mm
            dr = self.right_sign * v_right * self.motor_deg_per_mm
            self.left_motor.run(clamp(dl, -lim, lim))
            self.right_motor.run(clamp(dr, -lim, lim))

        def straight(self, distance_mm, speed_mm_s):
            """Проехать прямо заданное расстояние (по одометрии колёс)."""
            self.reset_travel()
            self.drive(speed_mm_s, 0.0)
            while abs(self.travel_mm()) < distance_mm:
                wait(5)
            self.stop()
            wait(150)

        # ---------- датчики ----------
        def reflection_left(self):
            return self.sensor_left.reflection()

        def reflection_right(self):
            return self.sensor_right.reflection()

        def distance_mm(self):
            d = self.sonar.distance()
            if d is None or d <= 0 or d > self.cfg.sonar_max_mm:
                return self.cfg.sonar_max_mm       # «далеко, ничего нет»
            return d

    # ========================================================
    #  ПРОГРАММА
    # ========================================================

    def main():
        cfg = Settings()
        robot = Robot(cfg)
        follower = LineFollower(cfg)

        print('=== полигон 1: линия + объект ===')
        print('старт: прямо %.0f мм' % cfg.start_straight_mm)
        robot.beep(2)

        # ---------- 1. выезд из зоны старта: 50 см прямо ----------
        robot.straight(cfg.start_straight_mm, cfg.start_speed_mm_s)
        print('проехали %.0f мм — включаю линию' % cfg.start_straight_mm)

        # ---------- 2. езда по линии, пока не увидим объект ----------
        # Период цикла задаём сами (wait в конце), поэтому dt известен
        # без всяких часов — проще и надёжнее на роботе.
        dt = cfg.loop_ms / 1000.0
        while True:
            # --- объект впереди? ---
            dist = robot.distance_mm()
            if dist < cfg.stop_mm:
                robot.stop()
                robot.beep(3)
                print('объект в %.0f мм — СТОП' % dist)
                return

            # --- едем по линии ---
            speed, steer = follower.update(robot.reflection_left(),
                                           robot.reflection_right(), dt)
            if follower.state == 'lost':
                robot.stop()
                robot.beep(2)
                print('линия потеряна — СТОП')
                return

            robot.drive(speed, steer)
            wait(cfg.loop_ms)

# ============================================================
#  РЕЖИМ ПРОВЕРКИ ДАТЧИКОВ: python3 robot.py --check (или Run на EV3)
# ============================================================

if HAS_ROBOT:
    def check_sensors():
        """Показывает датчики. Моторы НЕ крутятся — удобно проверять порты."""
        cfg = Settings()
        robot = Robot(cfg)
        print('проверка: 1-левый свет, 2-правый свет, 3-расстояние (Ctrl+C — выход)')
        while True:
            print('S1=%3d  S2=%3d   S3=%4d мм'
                  % (robot.reflection_left(), robot.reflection_right(),
                     robot.distance_mm()))
            wait(300)


# ============================================================
#  ЗАПУСК
# ============================================================

if __name__ == '__main__':
    if not HAS_ROBOT:
        print('Этот файл запускается на EV3 (Pybricks).')
        print('На компьютере можно прогнать симулятор:  python3 tools/sim.py')
    else:
        import sys
        if '--check' in sys.argv:
            check_sensors()
        else:
            main()
