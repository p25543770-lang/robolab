#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================
 robot.py — полигон 1 «Большое путешествие»
 «Следование по линии с движущимся препятствием»
================================================================

ЧТО ДЕЛАЕТ РОБОТ

  1. Старт: едет ПРЯМО 50 см (выезжает из зелёной зоны A).
  2. Дальше ВЕДЁТ ПО ЛИНИИ — двумя датчиками отражённого света.
     Ведение сделано максимально «неубиваемым»: три скорости,
     ПИД с фильтрами, автокалибровка датчиков и продуманный
     поиск линии, если она всё-таки потерялась.
  3. Увидел ОБЪЕКТ впереди (ультразвук) ближе 250 мм —
     останавливается и пищит.

РАСКЛАДКА (как на роботе)

    1 — ЛЕВЫЙ датчик отражённого света  (снизу)
    2 — ПРАВЫЙ датчик отражённого света (снизу)
    3 — ультразвук ВПЕРЁД
    C — ЛЕВОЕ колесо   (мотор стоит зеркально → в программе реверс)
    B — ПРАВОЕ колесо

    Редуктор 2:1 на колёсах: 2 оборота мотора = 1 оборот колеса.

ЗАПУСК

    обычно          → поехали
    robot.py --check → проверка датчиков, моторы НЕ крутятся

Файл самодостаточный: на EV3 заливается только он (Pybricks).
Логику ведения (класс LineFollower) использует и симулятор
tools/sim.py — поэтому импорт pybricks необязательный.
================================================================
"""

try:
    from pybricks.hubs import EV3Brick
    from pybricks.ev3devices import Motor, ColorSensor, UltrasonicSensor
    from pybricks.parameters import Port
    from pybricks.tools import wait
    HAS_ROBOT = True
except ImportError:                       # запуск на компьютере
    HAS_ROBOT = False


# ============================================================
#  НАСТРОЙКИ — всё в одном месте
# ============================================================

class Settings(object):
    """
    Все числа в одном месте. Меняете здесь — меняется поведение.
    Можно и в коде: Settings(kp=3.0) — удобно для подбора.
    """

    def __init__(self, **kw):
        for k, v in kw.items():
            if not hasattr(Settings, k):
                raise AttributeError('нет такого параметра: ' + k)
            setattr(self, k, v)

    # ---------- робот ----------
    wheel_diameter_mm = 56.0    # диаметр колеса (большие колёса EV3 — 56)
    axle_track_mm = 150.0       # между центрами колёс — ИЗМЕРЬТЕ линейкой
    gear_ratio = 2.0            # редуктор 2:1: 2 оборота мотора = 1 оборот колеса
    left_motor_reversed = True  # левый мотор зеркальный → реверс в программе
    right_motor_reversed = False
    motor_max_dps = 950.0       # предел мотора EV3, °/с

    # ---------- старт ----------
    start_straight_mm = 500.0   # проехать прямо 50 см
    start_speed_mm_s = 220.0    # мм/с на этом отрезке (=900 °/с на моторе)

    # ---------- скорости по линии ----------
    # Три ступени: чем дальше робот от линии, тем медленнее едет —
    # так он физически не успевает её «проскочить». Переключение
    # с гистерезисом, чтобы не дёргался между ступенями.
    v_fast = 220.0              # почти на линии (с редуктором 2:1 это ~900 °/с,
                                # предел мотора EV3 — 950 °/с: есть запас)
    v_mid = 150.0               # заметное отклонение
    v_slow = 95.0               # сильное отклонение / выход из поворота
    err_mid_on = 40.0           # ошибка больше → средняя скорость
    err_mid_off = 25.0          # ошибка меньше → снова быстрая
    err_slow_on = 70.0          # ошибка больше → самая медленная
    err_slow_off = 55.0         # ошибка меньше → обратно на среднюю

    # ---------- ПИД ----------
    kp = 2.4                    # основной «руль»
    kd = 0.25                   # демпфирование (гасит виляние)
    deriv_filter = 0.7          # сглаживание производной (0..0.95)
    deriv_limit = 300.0         # предел производной (не реагируем на всплеск)
    steer_limit = 1.0           # предел «руля» (1.0 = максимум)

    # ---------- датчики света ----------
    black_ref = 8.0             # показание на чёрной линии
    white_ref = 80.0            # показание на белом поле
    auto_calibrate = True       # подстраивать диапазон под освещение
    err_filter_time = 0.06      # с — сглаживание показаний датчиков
    err_deadband = 6.0          # ошибка меньше — это шум, а не отклонение
    black_edge = 0.65           # ниже этого показания датчик «на линии»

    # ---------- потеря линии и поиск ----------
    cent_time = 0.0             # (резерв)
    centered_err = 25.0         # последняя ошибка маленькая → ехали ровно
    blind_coast = 2.5           # с — столько едем ровно, если линия «между датчиками»
    blind_speed = 130.0         # мм/с — скорость при езде «вслепую»
    far_err = 45.0              # ошибка больше — линия далеко в стороне
    line_lost_time = 2.5        # с — ошибка не уменьшается → ищем линию
    fresh_line_time = 2.0       # с — линию видели недавно → это не «старт без линии»
    search_after = 0.55         # с — столько «подозрительно белого» до поиска
    settle_time = 0.15          # с — после находки едем тихо, пока не успокоится
    side_memory_err = 8.0       # ошибка больше → запоминаем, где была линия

    spin_speed = 150.0          # мм/с — разворот на месте (одно колесо стоит)
    search_spin_time = 3.4      # с — пол-оборота в одну сторону
    search_steer = 0.95         # «руль» узкой дуги (R ≈ 75 мм)
    search_speed = 90.0         # мм/с на узкой дуге
    search_steer_wide = 0.55    # «руль» широкой дуги (R ≈ 200 мм)
    search_speed_wide = 130.0   # мм/с на широкой дуге
    search_sweep_time = 4.0     # с — длительность одной фазы дуги
    search_scan_speed = 150.0   # мм/с — обзорный проезд вперёд
    search_spiral_speed = 185.0 # мм/с — спираль наружу
    search_spiral_steer = 0.7   # «руль» спирали (R ≈ 120 мм)
    recede_speed = 160.0        # мм/с — откат назад, если ничего не нашли
    search_max_time = 30.0      # с — дольше не ищем, останавливаемся

    # ---------- объект впереди ----------
    stop_mm = 250.0             # ближе — считаем, что впереди объект
    sonar_max_mm = 1200.0       # дальше не смотрим (шум датчика)

    # ---------- прочее ----------
    loop_ms = 10                # период цикла управления, мс


# ============================================================
#  ВЕДЕНИЕ ПО ЛИНИИ (без железа — эту же логику гоняет симулятор)
# ============================================================

def clamp(x, lo, hi):
    return lo if x < lo else (hi if x > hi else x)


class LineFollower(object):
    """
    Ведение по линии двумя датчиками — версия «не теряется».

    КАК СЧИТАЕТСЯ ОШИБКА

        error = (правый - левый) * 100        (от -100 до +100)

      error > 0 → робот сместился вправо (правый датчик белее) → рулим влево
      error < 0 → сместился влево → рулим вправо

    ЧТО ДЕЛАЕТ, ЧТОБЫ НЕ ТЕРЯТЬСЯ

      1. Автокалибровка: диапазон «чёрное..белое» запоминается по факту,
         поэтому робот работает и когда датчики стоят на краях линии
         (видят «серое»), и когда они разнесены шире линии.

      2. Сглаживание показаний и мёртвая зона — чтобы шум датчиков
         не превращался в дёрганье рулём.

      3. Три скорости с гистерезисом: ушёл от линии — сразу сбросил
         скорость, вернулся — снова быстро. В повороте не проскакивает.

      4. Если линия оказалась МЕЖДУ датчиками (оба видят белое, но робот
         только что шёл ровно) — это не потеря: едем дальше «вслепую»,
         повторяя последний руль, до blind_coast секунд.

      5. Настоящая потеря → поиск по фазам:
           0) пол-оборота на месте вправо,
           1) полный оборот на месте влево (перекрывает всё),
           2) узкая дуга вправо / влево,
           3) широкая дуга,
           4) обзорный проезд вперёд,
           5) спираль наружу,
           6) откат назад по своим следам.
         При старте со сдвигом/под углом линия находится за 1-2 секунды.

    update(refl_left, refl_right, dt) -> (speed_mm_s, steer)
    steer: +1 — правое колесо быстрее (поворот влево), -1 — наоборот.
    """

    def __init__(self, cfg=None):
        self.cfg = cfg or Settings()
        self.reset()

    def reset(self):
        cfg = self.cfg
        self.state = 'ok'             # 'ok' | 'search' | 'lost'

        # ошибка и её производная
        self.last_error = 0.0
        self.deriv = 0.0
        self.err_avg = 0.0

        # сглаженные показания датчиков
        self.filt_left = None
        self.filt_right = None

        # калибровка (свой диапазон на каждый датчик)
        self.lo, self.hi = cfg.black_ref, cfg.white_ref
        self.lo2, self.hi2 = cfg.black_ref, cfg.white_ref

        # память о линии
        self.last_side = 1.0          # где линия была: +1 справа, -1 слева
        self.last_shift_right = True  # робот был смещён вправо от линии
        self.last_known_err = 0.0     # последняя ошибка, когда линию видели
        self.last_steer = 0.0         # последний руль — повторяем «вслепую»
        self.since_line = 1e6         # с — когда последний раз видели линию
        self.had_line = False         # видели ли линию хоть раз

        # «вслепую»
        self.blind_time = 0.0
        self.suspect = 0.0

        # контроль «линия приближается»
        self.err_abs_now = 0.0
        self.err_abs_min = 100.0
        self.err_watch = 0.0

        # поиск
        self.search_time = 0.0
        self.phase = 0
        self.phase_time = 0.0
        self.spin_dir = 1.0
        self.settle = 0.0
        self.speed_mode = 'fast'

    # --------------------------------------------------------
    #  Показание датчика → 0..1  (0 — чёрное, 1 — белое)
    # --------------------------------------------------------
    def norm(self, reflection, which=0):
        """
        Автокалибровка: диапазон начинается с паспортных black_ref..white_ref
        и только РАСШИРЯЕТСЯ, если датчик увидел что-то темнее/светлее:

            lo = min(lo, показание)      hi = max(hi, показание)

        Диапазон не «уползает» и не сжимается — значит робот, у которого
        датчики смотрят на края линии и видят «серое» (45-55), всё равно
        считает это линией (≈0.45), а белое поле — белым (≈0.97).
        """
        cfg = self.cfg
        if which == 0:
            lo, hi = self.lo, self.hi
        else:
            lo, hi = self.lo2, self.hi2

        if cfg.auto_calibrate:
            if reflection < lo:
                lo = reflection
            if reflection > hi:
                hi = reflection

        if which == 0:
            self.lo, self.hi = lo, hi
        else:
            self.lo2, self.hi2 = lo, hi

        return clamp((reflection - lo) / max(10.0, hi - lo), 0.0, 1.0)

    # --------------------------------------------------------
    #  Основной шаг
    # --------------------------------------------------------
    def update(self, refl_left, refl_right, dt):
        cfg = self.cfg
        if dt <= 0.0:
            dt = cfg.loop_ms / 1000.0
        if self.since_line < 1e6:
            self.since_line += dt

        left = self.norm(refl_left, 0)
        right = self.norm(refl_right, 1)

        # сглаживание показаний: у реального датчика шум ±3-5%,
        # без фильтра робот дёргает рулём на каждом цикле
        if self.filt_left is None:
            self.filt_left, self.filt_right = left, right
        a = clamp(dt / max(cfg.err_filter_time, 1e-4), 0.0, 1.0)
        self.filt_left += (left - self.filt_left) * a
        self.filt_right += (right - self.filt_right) * a

        error = (self.filt_right - self.filt_left) * 100.0
        if abs(error) < cfg.err_deadband:
            error = 0.0                       # это шум, а не отклонение
        aerr = abs(error)
        self.err_avg += (error - self.err_avg) * min(1.0, dt / 0.05)

        on_line = (left < cfg.black_edge) or (right < cfg.black_edge)

        speed, steer = self._drive(error, aerr, on_line, dt)

        # копим «последний руль» — им едем, когда линия между датчиками
        self.last_steer = 0.85 * self.last_steer + 0.15 * steer
        return speed, steer

    # --------------------------------------------------------
    #  Мозги: сначала поиск, потом обычная езда
    # --------------------------------------------------------
    def _drive(self, error, aerr, on_line, dt):
        cfg = self.cfg

        # ================= ПОИСК ЛИНИИ =================
        if self.state == 'search':
            if on_line:
                # нашли — короткая «успокоительная» пауза и обычная езда
                self.state = 'ok'
                self.search_time = 0.0
                self.phase = 0
                self.phase_time = 0.0
                self.settle = cfg.settle_time
                self.deriv = 0.0
                self.last_error = error
                self.speed_mode = 'fast'
                self.suspect = 0.0
                self.blind_time = 0.0
            else:
                return self._search_step(dt)

        # ================= ОБЫЧНАЯ ЕЗДА =================
        # 1) линию давно не видно (старт со сдвигом, под углом, на белом)
        if not on_line and self.since_line > cfg.fresh_line_time:
            self.spin_dir = -1.0 if self.last_shift_right else 1.0
            self._start_search()
            return cfg.spin_speed, self.spin_dir

        if on_line:
            return self._follow(error, aerr, dt)

        # 2) оба датчика видят белое. Два разных случая:
        #    а) робот шёл ровно → линия «между датчиками», едем вслепую;
        #    б) робот уходил в сторону → линию проскочил, ищем сразу.
        if abs(self.last_known_err) < cfg.centered_err:
            self.blind_time += dt
            if self.blind_time > cfg.blind_coast:
                self._start_search()
                return cfg.spin_speed, self.spin_dir
            return cfg.blind_speed, self.last_steer

        self.suspect += dt
        if self.suspect > cfg.search_after:
            self._start_search()
            return cfg.spin_speed, self.spin_dir
        return cfg.blind_speed, self.last_steer

    def _start_search(self):
        self.state = 'search'
        self.search_time = 0.0
        self.phase = 0
        self.phase_time = 0.0
        self.settle = 0.0

    # --------------------------------------------------------
    #  Обычное ведение: ПИД + ступени скорости
    # --------------------------------------------------------
    def _follow(self, error, aerr, dt):
        cfg = self.cfg
        self.suspect = 0.0
        self.blind_time = 0.0
        self.since_line = 0.0
        self.had_line = True
        self.last_known_err = error
        if aerr > cfg.side_memory_err:
            self.last_side = 1.0 if error > 0 else -1.0
            self.last_shift_right = error > 0

        # контроль «линия приближается»: если 2.5 с ошибка не падает,
        # значит под датчиками не наша линия (край поля, чужая трасса)
        if self.err_abs_now > cfg.far_err:
            self.err_watch = 0.0
        elif self.err_abs_now < self.err_abs_min - 2.0:
            self.err_abs_min = self.err_abs_now
            self.err_watch = 0.0
        else:
            self.err_watch += dt
        self.err_abs_now = aerr
        if self.err_watch > cfg.line_lost_time:
            self.err_watch = 0.0
            self.err_abs_min = 100.0
            self.spin_dir = 1.0 if error > 0 else -1.0
            self._start_search()
            return cfg.spin_speed, self.spin_dir

        # ---- ПИД ----
        raw = (error - self.last_error) / dt
        self.last_error = error
        raw = clamp(raw, -cfg.deriv_limit, cfg.deriv_limit)
        self.deriv = cfg.deriv_filter * self.deriv + (1.0 - cfg.deriv_filter) * raw
        steer = cfg.kp * error / 100.0 + cfg.kd * self.deriv / 100.0
        steer = clamp(steer, -cfg.steer_limit, cfg.steer_limit)

        # ---- ступени скорости с гистерезисом ----
        mode = self.speed_mode
        if mode == 'fast':
            if aerr > cfg.err_slow_on:
                mode = 'slow'
            elif aerr > cfg.err_mid_on:
                mode = 'mid'
        elif mode == 'mid':
            if aerr > cfg.err_slow_on:
                mode = 'slow'
            elif aerr < cfg.err_mid_off:
                mode = 'fast'
        else:
            if aerr < cfg.err_mid_off:
                mode = 'fast'
            elif aerr < cfg.err_slow_off:
                mode = 'mid'
        self.speed_mode = mode
        if mode == 'fast':
            speed = cfg.v_fast
        elif mode == 'mid':
            speed = cfg.v_mid
        else:
            speed = cfg.v_slow

        if self.settle > 0.0:
            self.settle -= dt
            speed = min(speed, cfg.v_slow)
        if abs(steer) > 0.85:
            speed = min(speed, cfg.v_slow)     # руль в упоре — сбрасываем скорость

        self.state = 'ok'
        return speed, steer

    # --------------------------------------------------------
    #  Поиск линии по фазам
    # --------------------------------------------------------
    def _search_step(self, dt):
        cfg = self.cfg
        self.search_time += dt
        self.phase_time += dt
        if self.search_time > cfg.search_max_time:
            self.state = 'lost'
            return 0.0, 0.0

        # длительность фазы
        if self.phase == 0:
            limit = cfg.search_spin_time
        elif self.phase == 1:
            limit = cfg.search_spin_time * 2.0
        else:
            limit = cfg.search_sweep_time

        if self.phase_time > limit:
            self.phase_time = 0.0
            self.phase += 1
            if self.phase == 1:
                self.spin_dir = -self.spin_dir      # теперь в другую сторону

        # 0, 1 — разворот на месте.
        # ВАЖНО: speed>0 и steer=±1 → одно колесо стоит, второе крутится.
        # При speed=0 колёса просто встают, и робот НЕ поворачивается.
        if self.phase in (0, 1):
            return cfg.spin_speed, self.spin_dir

        # 2, 3 — узкие дуги в разные стороны
        if self.phase == 2:
            return cfg.search_speed, self.spin_dir * cfg.search_steer
        if self.phase == 3:
            return cfg.search_speed, -self.spin_dir * cfg.search_steer

        # 4 — широкая дуга
        if self.phase == 4:
            return cfg.search_speed_wide, self.spin_dir * cfg.search_steer_wide

        # 5 — обзорный проезд вперёд: робота могли поставить далеко
        if self.phase == 5:
            return cfg.search_scan_speed, 0.0

        # 6 — спираль наружу: просматривает всё поле вокруг
        if self.phase == 6:
            return cfg.search_spiral_speed, self.spin_dir * cfg.search_spiral_steer

        # всё перепробовали — назад по своим следам
        self.phase = 6
        return -cfg.recede_speed, 0.0


# ============================================================
#  ЖЕЛЕЗО: моторы, датчики, движения
# ============================================================

if HAS_ROBOT:

    class Robot(object):
        """Моторы B (правое) и C (левое), датчики 1, 2, 3."""

        def __init__(self, cfg=None):
            self.cfg = cfg or Settings()
            self.brick = EV3Brick()
            self.left_motor = Motor(Port.C)            # C — левое колесо
            self.right_motor = Motor(Port.B)           # B — правое колесо
            self.sensor_left = ColorSensor(Port.S1)    # 1 — левый снизу
            self.sensor_right = ColorSensor(Port.S2)   # 2 — правый снизу
            self.sonar = UltrasonicSensor(Port.S3)     # 3 — ультразвук вперёд

            # сколько градусов МОТОРА на 1 мм пути (учитывая редуктор)
            mm_per_wheel_turn = 3.14159265 * self.cfg.wheel_diameter_mm
            self.motor_deg_per_mm = (360.0 / mm_per_wheel_turn) * self.cfg.gear_ratio

            # знаки моторов (левый стоит зеркально → реверс)
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
            """Сколько мм проехали (по среднему углу моторов, с их знаками)."""
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
            steer — «руль»: +1 → правое колесо быстрее (поворот влево),
                            -1 → наоборот, 0 → прямо
            """
            v_left = speed_mm_s * (1.0 - steer)
            v_right = speed_mm_s * (1.0 + steer)
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
        print('редуктор %.0f:1 — на 1 оборот колеса нужно %.0f° мотора'
              % (cfg.gear_ratio, 360.0 * cfg.gear_ratio))
        print('на %.0f мм: мотор %.0f° (%.2f оборота), колесо %.2f оборота'
              % (cfg.start_straight_mm,
                 cfg.start_straight_mm * robot.motor_deg_per_mm,
                 cfg.start_straight_mm * robot.motor_deg_per_mm / 360.0,
                 cfg.start_straight_mm / (3.14159265 * cfg.wheel_diameter_mm)))
        robot.beep(2)

        # ---------- 1. выезд из зоны старта: 50 см прямо ----------
        robot.straight(cfg.start_straight_mm, cfg.start_speed_mm_s)
        print('проехали %.0f мм — включаю линию' % cfg.start_straight_mm)

        # ---------- 2. линия, пока не увидим объект ----------
        # Период цикла задаём сами (wait в конце), поэтому dt известен
        # без всяких часов — проще и надёжнее на роботе.
        dt = cfg.loop_ms / 1000.0
        while True:
            dist = robot.distance_mm()
            if dist < cfg.stop_mm:
                robot.stop()
                robot.beep(3)
                print('объект в %.0f мм — СТОП' % dist)
                return

            speed, steer = follower.update(robot.reflection_left(),
                                           robot.reflection_right(), dt)
            if follower.state == 'lost':
                robot.stop()
                robot.beep(2)
                print('линия потеряна — СТОП')
                return

            robot.drive(speed, steer)
            wait(cfg.loop_ms)

    # ========================================================
    #  ПРОВЕРКА ДАТЧИКОВ (моторы не крутятся)
    # ========================================================

    def check_sensors():
        cfg = Settings()
        robot = Robot(cfg)
        print('проверка: 1-левый свет, 2-правый свет, 3-расстояние (Ctrl+C — выход)')
        print('на линии S1 и S2 маленькие (0-25), на белом поле — большие (70-95)')
        robot.reset_travel()
        while True:
            print('S1=%3d  S2=%3d   S3=%4d мм   путь=%.0f мм'
                  % (robot.reflection_left(), robot.reflection_right(),
                     robot.distance_mm(), robot.travel_mm()))
            wait(300)


# ============================================================
#  ЗАПУСК
# ============================================================

if __name__ == '__main__':
    if not HAS_ROBOT:
        print('Этот файл запускается на EV3 (Pybricks).')
        print('На компьютере прогоните симулятор: python3 tools/sim.py')
        print('Проверка надёжности линии:        python3 tools/stress.py')
    else:
        import sys
        if '--check' in sys.argv:
            check_sensors()
        else:
            main()
