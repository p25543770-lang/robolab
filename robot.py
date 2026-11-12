#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================
 robot.py - polygon 1 "Big journey"
 "Line following with a moving obstacle"
================================================================

WHAT THE ROBOT DOES

  1. Start: drives STRAIGHT 50 cm (leaves the green start zone A).
  2. Then FOLLOWS THE LINE with two reflection light sensors.
     The line follower is made as unbreakable as possible:
     three speeds, PID with filters, auto-calibration of the
     sensors and a multi-phase line search.
  3. Sees an OBSTACLE ahead (front ultrasonic closer than 250 mm) -
     stops and beeps.
  4. Watches the RIGHT ultrasonic (port 4 / D): it detects an
     obstacle on the right side (prints a message, ready for the
     bypass later).

PORTS (as on this robot)

    1 - LEFT  reflection light sensor (bottom)
    2 - RIGHT reflection light sensor (bottom)
    3 - ultrasonic FRONT
    4 - ultrasonic RIGHT (port D)
    C - LEFT  motor (mounted mirrored -> reversed in the program)
    B - RIGHT motor

    Gear 2:1 on both wheels: 2 motor turns = 1 wheel turn.

RUN MODES (change MODE right below)

    'run'   - drive
    'check' - sensor check, motors DO NOT move
    'stay'  - do nothing

PLATFORMS

    ev3dev  : brickrun --directory="/home/robot/robolabs2" robot.py
    Pybricks: pybricksdev run usb robot.py   (or F5 in VS Code)
    PC      : python3 tools/sim.py

The file detects the platform by itself. All terminal messages are
pure ASCII on purpose: the EV3 console is ASCII-only and Cyrillic
text raises UnicodeEncodeError there.
================================================================
"""

import sys
import time

# ============================================================
#  RUN MODE
# ============================================================
MODE = 'run'

# ============================================================
#  PLATFORM DETECTION
#    EV3DEV   - standard ev3dev image + ev3dev2 library
#    PYBRICKS - Pybricks firmware
#    neither  - computer (simulator only)
# ============================================================
EV3DEV = False
PYBRICKS = False

try:                                   # --- ev3dev ---
    from ev3dev2.motor import LargeMotor, OUTPUT_B, OUTPUT_C
    from ev3dev2.sensor.lego import ColorSensor, UltrasonicSensor
    from ev3dev2.sensor import INPUT_1, INPUT_2, INPUT_3, INPUT_4
    from ev3dev2.sound import Sound
    EV3DEV = True
except ImportError:
    pass

if not EV3DEV:
    try:                               # --- Pybricks ---
        from pybricks.hubs import EV3Brick
        from pybricks.ev3devices import Motor, ColorSensor, UltrasonicSensor
        from pybricks.parameters import Port
        from pybricks.tools import wait as pb_wait
        PYBRICKS = True
    except ImportError:
        pass

HAS_ROBOT = EV3DEV or PYBRICKS


def log(text):
    """Safe print: the EV3 console is ASCII-only."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode('ascii', 'replace').decode('ascii'))


def wait_ms(ms):
    if PYBRICKS:
        pb_wait(ms)
    else:
        time.sleep(ms / 1000.0)


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

    # ---------- объект справа (датчик 4 / порт D) ----------
    side_near_mm = 350.0        # ближе — помеха рядом справа
    log_every = 0.5             # с — как часто печатать правый датчик в 'check'

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
#  HARDWARE: motors, sensors
#    The same Robot class works on ev3dev and on Pybricks.
#    Ports:  C = left motor, B = right motor,
#            1 = left light, 2 = right light,
#            3 = front sonar, 4 (D) = right sonar
# ============================================================

class Robot(object):

    def __init__(self, cfg=None):
        self.cfg = cfg or Settings()

        if EV3DEV:
            # ---------- ev3dev ----------
            self.left_motor = LargeMotor(OUTPUT_C)      # C - left
            self.right_motor = LargeMotor(OUTPUT_B)     # B - right
            self.sensor_left = ColorSensor(INPUT_1)     # 1 - left light
            self.sensor_right = ColorSensor(INPUT_2)    # 2 - right light
            self.sonar = UltrasonicSensor(INPUT_3)      # 3 - front
            self.sonar_side = UltrasonicSensor(INPUT_4)  # 4 / D - right
            self.sound = Sound()
            # ev3dev: reflected light is already 0..100 percent
            self._refl_scale = 1.0
            self._dist_units = 1.0          # ctypes distance is in 0.1 mm
        else:
            # ---------- Pybricks ----------
            self.brick = EV3Brick()
            self.left_motor = Motor(Port.C)
            self.right_motor = Motor(Port.B)
            self.sensor_left = ColorSensor(Port.S1)
            self.sensor_right = ColorSensor(Port.S2)
            self.sonar = UltrasonicSensor(Port.S3)
            self.sonar_side = UltrasonicSensor(Port.S4)
            self._refl_scale = 1.0
            self._dist_units = 1.0

        # motor degrees per 1 mm of travel (gear 2:1 taken into account)
        mm_per_wheel_turn = 3.14159265 * self.cfg.wheel_diameter_mm
        self.motor_deg_per_mm = (360.0 / mm_per_wheel_turn) * self.cfg.gear_ratio

        # motor signs (left motor is mirrored -> reverse in the program)
        self.left_sign = -1.0 if self.cfg.left_motor_reversed else 1.0
        self.right_sign = -1.0 if self.cfg.right_motor_reversed else 1.0

    # ---------- service ----------
    def beep(self, times=1):
        for _ in range(times):
            if EV3DEV:
                self.sound.beep()
            else:
                self.brick.speaker.beep(600, 120)
            if times > 1:
                wait_ms(120)

    def stop(self):
        if EV3DEV:
            self.left_motor.stop(stop_action='brake')
            self.right_motor.stop(stop_action='brake')
        else:
            self.left_motor.stop()
            self.right_motor.stop()

    def _angle_left(self):
        if EV3DEV:
            return self.left_motor.position
        return self.left_motor.angle()

    def _angle_right(self):
        if EV3DEV:
            return self.right_motor.position
        return self.right_motor.angle()

    def travel_mm(self):
        """Travelled distance in mm (average of both motors, signs applied)."""
        deg = (self.left_sign * self._angle_left()
               + self.right_sign * self._angle_right()) / 2.0
        return deg / self.motor_deg_per_mm

    def reset_travel(self):
        if EV3DEV:
            self.left_motor.reset()
            self.right_motor.reset()
        else:
            self.left_motor.reset_angle(0)
            self.right_motor.reset_angle(0)

    # ---------- movement ----------
    def drive(self, speed_mm_s, steer):
        """
        speed_mm_s - centre speed, mm/s (may be negative = backwards)
        steer      - +1 right wheel faster (turn left), -1 opposite, 0 straight
        """
        v_left = speed_mm_s * (1.0 - steer)
        v_right = speed_mm_s * (1.0 + steer)
        lim = self.cfg.motor_max_dps
        dl = clamp(self.left_sign * v_left * self.motor_deg_per_mm, -lim, lim)
        dr = clamp(self.right_sign * v_right * self.motor_deg_per_mm, -lim, lim)

        if EV3DEV:
            # ev3dev speed is in degrees per second
            self.left_motor.run_forever(speed_sp=dl)
            self.right_motor.run_forever(speed_sp=dr)
        else:
            self.right_motor.run(dr)
            self.left_motor.run(dl)

    def straight(self, distance_mm, speed_mm_s):
        """Drive straight for a given distance (wheel odometry)."""
        self.reset_travel()
        self.drive(speed_mm_s, 0.0)
        while abs(self.travel_mm()) < distance_mm:
            wait_ms(5)
        self.stop()
        wait_ms(150)

    # ---------- sensors ----------
    def reflection_left(self):
        if EV3DEV:
            return self.sensor_left.reflected_light_intensity_pc
        return self.sensor_left.reflection()

    def reflection_right(self):
        if EV3DEV:
            return self.sensor_right.reflected_light_intensity_pc
        return self.sensor_right.reflection()

    @staticmethod
    def _dist(obj, limit_mm):
        try:
            d = obj.distance_centimeters
            if d is None:
                return limit_mm
            mm = d * 10.0
        except Exception:
            return limit_mm
        if mm <= 0 or mm > limit_mm:
            return limit_mm
        return mm

    def distance_mm(self):
        """Front sonar (port 3). Far = sonar_max_mm."""
        return self._dist(self.sonar, self.cfg.sonar_max_mm)

    def distance_right_mm(self):
        """Right sonar (port 4 / D). Far = sonar_max_mm."""
        return self._dist(self.sonar_side, self.cfg.sonar_max_mm)


# ============================================================
#  PROGRAM
# ============================================================

def main():
    cfg = Settings()
    robot = Robot(cfg)
    follower = LineFollower(cfg)

    log('=== polygon 1: line + obstacle ===')
    log('gear %.0f:1 - one wheel turn needs %.0f deg of motor'
        % (cfg.gear_ratio, 360.0 * cfg.gear_ratio))
    log('for %.0f mm: motor %.0f deg (%.2f turns), wheel %.2f turns'
        % (cfg.start_straight_mm,
           cfg.start_straight_mm * robot.motor_deg_per_mm,
           cfg.start_straight_mm * robot.motor_deg_per_mm / 360.0,
           cfg.start_straight_mm / (3.14159265 * cfg.wheel_diameter_mm)))
    robot.beep(2)

    # ---------- 1. leave the start zone: 50 cm straight ----------
    robot.straight(cfg.start_straight_mm, cfg.start_speed_mm_s)
    log('drove %.0f mm - line follower on' % cfg.start_straight_mm)

    # ---------- 2. follow the line until the obstacle ----------
    dt = cfg.loop_ms / 1000.0
    side_timer = 0.0
    while True:
        # front obstacle?
        dist = robot.distance_mm()
        if dist < cfg.stop_mm:
            robot.stop()
            robot.beep(3)
            log('obstacle at %.0f mm - STOP' % dist)
            return

        # right sonar (port 4 / D): for information and future bypass
        side = robot.distance_right_mm()
        side_timer += dt
        if side_timer >= 1.0:
            side_timer = 0.0
            if side < cfg.side_near_mm:
                log('right sensor: %.0f mm (obstacle on the right)' % side)

        speed, steer = follower.update(robot.reflection_left(),
                                       robot.reflection_right(), dt)
        if follower.state == 'lost':
            robot.stop()
            robot.beep(2)
            log('line lost - STOP')
            return

        robot.drive(speed, steer)
        wait_ms(cfg.loop_ms)


# ============================================================
#  SENSOR CHECK (motors do not move)
# ============================================================

def check_sensors():
    cfg = Settings()
    robot = Robot(cfg)
    log('check: 1=left light, 2=right light, 3=front sonar, 4=right sonar')
    log('on the line S1/S2 are small (0-25), on white floor big (70-95)')
    robot.reset_travel()
    while True:
        log('S1=%3d  S2=%3d  S3=%4d mm  S4=%4d mm  travel=%.0f mm'
            % (robot.reflection_left(), robot.reflection_right(),
               robot.distance_mm(), robot.distance_right_mm(),
               robot.travel_mm()))
        wait_ms(300)


# ============================================================
#  START
# ============================================================

if __name__ == '__main__':
    if MODE == 'stay':
        log('MODE = stay: nothing to do')
    elif not HAS_ROBOT:
        log('No robot libraries found (PC).')
        log('Simulator: python3 tools/sim.py')
        log('Stress test: python3 tools/stress.py')
    elif MODE == 'check' or '--check' in sys.argv:
        check_sensors()
    else:
        main()
