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

    'run'    - drive
    'check'  - sensor check, motors DO NOT move
    'update' - download the newest robot.py from GitHub
    'stay'   - do nothing

PLATFORMS

    ev3dev  : brickrun --directory="/home/robot/robolabs2" robot.py
    Pybricks: pybricksdev run usb robot.py   (or F5 in VS Code)
    PC      : python3 tools/sim.py

The file detects the platform by itself. All terminal messages are
pure ASCII on purpose: the EV3 console is ASCII-only and Cyrillic
text raises UnicodeEncodeError there.

AUTO UPDATE FROM GITHUB

    The file updates itself. On every start (MODE = 'run') it asks
    GitHub for the newest robot.py and, if there is a newer one, it
    replaces itself and CONTINUES to drive with the new code.
    The previous version is kept next to it as robot.py.old.

    MODE = 'update'  - update only, then stop (does not drive).
    --update         - the same from the command line.
    --update-check   - only look, never write (safe on the computer).
    AUTO_UPDATE_AT_START = True in the settings below.
    AUTO_UPDATE_QUIET    = True - print only the result, not the details.
    No network / no GitHub -> a short warning, then the program drives.

    Which branch is used, in this order:
      1) AUTO_UPDATE_BRANCH below, if it is not ''
      2) the branch this file was downloaded from (".../robolab/
         arena/xxx/robot.py" -> "arena/xxx")
      3) the branch chosen by the download server (".../blob/main/
         robot.py" -> "main", ".../raw/main/robot.py" -> "main")
      4) 'main'

    Over the network the file itself cannot know its branch, so if
    the link said nothing useful set AUTO_UPDATE_BRANCH = 'main'.
================================================================
"""

import os
import sys
import time

# ============================================================
#  RUN MODE
# ============================================================
MODE = 'run'

# ------------------------------------------------------------
#  AUTO UPDATE FROM GITHUB
#    ''  - take the branch from the link this file came from
#          (see AUTO UPDATE in the header), by default 'main'
#    or set it by hand, e.g. 'main'
# ------------------------------------------------------------
AUTO_UPDATE_BRANCH = ''

#  True  - on every start (MODE = 'run') download the newest robot.py
#          and, if it is newer, replace this file and drive the new
#          code right away (old file stays as robot.py.old)
#  False - never touch the file, just drive
AUTO_UPDATE_AT_START = True

#  True  - only the result is printed (4 lines), False - full details
AUTO_UPDATE_QUIET = True

REPO_OWNER = 'p25543770-lang'
REPO_NAME = 'robolab'
REPO_FILE = 'robot.py'
UPDATE_TIMEOUT = 12          # seconds for one HTTP request (MODE = 'update')
UPDATE_TIMEOUT_START = 6     # the same at start: shorter, so a robot
                             # without Wi-Fi drives after a few seconds

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
    All numbers in one place. Change them here to change behaviour.
    Also possible in code: Settings(kp=3.0) - handy for tuning.
    """

    def __init__(self, **kw):
        for k, v in kw.items():
            if not hasattr(Settings, k):
                raise AttributeError('no such setting: ' + k)
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
    Line following with two sensors - the never-loses-the-line version.

    HOW THE ERROR IS COMPUTED

        error = (right - left) * 100          (from -100 to +100)

      error > 0 -> the robot went right (right sensor is whiter) -> steer left
      error < 0 -> it went left -> steer right

    WHAT MAKES IT NOT LOSE THE LINE

      1. Auto calibration: the "black..white" range is learned from the
         real readings, so it works both when the sensors sit on the
         edges of the line (they see "grey") and when they are wider
         than the line.

      2. Sensor smoothing and a dead band - sensor noise does not turn
         into steering twitching.

      3. Three speeds with hysteresis: off the line - speed drops at
         once, back on the line - fast again. It cannot overshoot a turn.

      4. If the line is BETWEEN the sensors (both see white, but the
         robot was driving straight a moment ago) - this is not a loss:
         keep driving with the last steering for up to blind_coast s.

      5. A real loss -> search in phases:
           0) half a turn on the spot to the right,
           1) a full turn on the spot to the left (covers everything),
           2) narrow arc right / left,
           3) wide arc,
           4) a look-around run forward,
           5) a spiral outwards,
           6) back up along its own tracks.
         With a shifted or angled start the line is found in 1-2 s.

    update(refl_left, refl_right, dt) -> (speed_mm_s, steer)
    steer: +1 - the right wheel spins faster (turn left), -1 - the other way.
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
        Auto calibration: the range starts with black_ref..white_ref and
        only WIDENS when the sensor sees something darker or brighter:

            lo = min(lo, reading)      hi = max(hi, reading)

        The range never drifts and never shrinks - so a robot whose
        sensors look at the edges of the line and see "grey" (45-55)
        still counts it as the line (about 0.45), and a white floor as
        white (about 0.97).
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
#  AUTO UPDATE FROM GITHUB
#    MODE = 'update'                -> force this update
#    MODE = 'run' + AUTO_UPDATE_AT_START
#                                   -> update first, then drive
#  Downloads REPO_FILE from the raw branch of the repository,
#  compares it with this file and replaces this file if newer.
#  Safety: the download is only accepted if the new file is
#  valid Python (compiles) and contains the marker RUN MODE.
#  The old file is kept next to this one as robot.py.old.
# ============================================================

PY3 = (sys.version_info[0] >= 3)
UPDATE_MARKER = 'RUN MODE'          # must be in every valid version
OLD_SUFFIX = '.old'
BOM = b'\xef\xbb\xbf'

REPO_URL = ('https://github.com/%s/%s' % (REPO_OWNER, REPO_NAME))
ZIP_URL = ('https://github.com/%s/%s/archive/refs/heads/%%s.zip'
           % (REPO_OWNER, REPO_NAME))
RAW_URL = ('https://raw.githubusercontent.com/%s/%s/%%s/%%s'
           % (REPO_OWNER, REPO_NAME))
#  2nd way: the whole branch as a zip archive (works even when the raw
#  server is blocked - on some networks raw.githubusercontent.com is not
#  reachable, but codeload/github.com are)
ZIP_REF_URL = ('https://github.com/%s/%s/archive/refs/heads/%%s.zip'
               % (REPO_OWNER, REPO_NAME))
ZIP_CODELOAD_URL = ('https://codeload.github.com/%s/%s/zip/refs/heads/%%s'
                    % (REPO_OWNER, REPO_NAME))


def branch_from_url(url):
    """Guess the branch from the address this file was downloaded from."""
    if not url:
        return ''
    url = url.replace('\\', '/').strip().split('?')[0]
    # raw.githubusercontent.com/<owner>/<repo>/<branch...>/<file>
    if 'raw.githubusercontent.com/' in url:
        tail = url.split('raw.githubusercontent.com/', 1)[1]
        parts = [p for p in tail.split('/') if p]
        if len(parts) >= 4:
            return '/'.join(parts[2:-1])
        return ''
    for marker in ('/blob/', '/raw/', '/refs/heads/'):
        if marker in url:
            rest = url.split(marker, 1)[1]
            if '/' in rest:
                branch = rest.rsplit('/', 1)[0].strip('/')
            else:
                branch = rest.strip('/')
            if branch.endswith('.zip'):
                branch = branch[:-len('.zip')]
            return branch
    return ''


def branch_of_this_file():
    """Branch used for the update: AUTO_UPDATE_BRANCH, link, then 'main'."""
    if AUTO_UPDATE_BRANCH:
        return AUTO_UPDATE_BRANCH.strip('/')
    for arg in sys.argv:
        found = branch_from_url(arg)
        if found:
            return found
    this_dir = ''
    try:
        this_dir = globals().get('__file__') or ''
    except Exception:
        this_dir = ''
    found = branch_from_url(this_dir)
    if found:
        return found
    for var in ('VSCODE_CWD', 'PWD', 'OLDPWD', 'HOME'):
        try:
            found = branch_from_url(os.environ.get(var, ''))
        except Exception:
            found = ''
        if found:
            return found
    return 'main'


def script_path():
    """Full path of this file."""
    try:
        path = os.path.abspath(globals().get('__file__') or REPO_FILE)
    except Exception:
        path = REPO_FILE
    if not os.path.isdir(os.path.dirname(path) or '.'):
        return os.path.join(os.getcwd(), REPO_FILE)
    return path


def http_get(url, timeout=UPDATE_TIMEOUT):
    """Download a URL -> bytes (or None). Tries https, then http, then curl/wget."""
    # 1) urllib over https
    try:
        import ssl
        import urllib.request
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE      # old EV3 root certificates
        req = urllib.request.Request(url, headers={'User-Agent': 'EV3-robolab'})
        return urllib.request.urlopen(req, timeout=timeout, context=ctx).read()
    except Exception as err:
        if _UPDATE_VERBOSE:
            log('  https download failed: %s' % err)
    # 2) urllib over plain http
    if url.startswith('https://'):
        try:
            import urllib.request
            plain = 'http://' + url[len('https://'):]
            req = urllib.request.Request(plain, headers={'User-Agent': 'EV3-robolab'})
            return urllib.request.urlopen(req, timeout=timeout).read()
        except Exception as err:
            if _UPDATE_VERBOSE:
                log('  http download failed: %s' % err)
    # 3) curl / wget from the shell
    for cmd in (['curl', '-L', '--max-time', str(timeout)], ['wget', '-qO', '-']):
        try:
            import subprocess
            out = subprocess.Popen(cmd + [url], stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE).communicate()[0]
            if out:
                return out
        except Exception:
            pass
    return None


def script_from_zip(data, name=REPO_FILE):
    """Take one file out of a GitHub zip archive -> str (or None)."""
    if not data or len(data) < 4 or data[:2] != b'PK':
        return None
    try:
        import io
        import zipfile
        archive = zipfile.ZipFile(io.BytesIO(data))
    except Exception as err:
        log('  zip cannot be opened: %s' % err)
        return None
    for item in archive.namelist():
        if item.endswith('/' + name) or item == name:
            try:
                return text_of(archive.read(item))
            except Exception as err:
                log('  zip file cannot be read: %s' % err)
                return None
    log('  %s is not inside the archive' % name)
    return None


def download_program(branch):
    """Newest version of REPO_FILE for a branch -> str (or None)."""
    return text_of(http_get(RAW_URL % (branch, REPO_FILE)))


def text_of(data):
    """bytes -> str, tolerant to BOM and broken bytes."""
    if data is None:
        return None
    if data.startswith(BOM):
        data = data[len(BOM):]
    try:
        return data.decode('utf-8')
    except Exception:
        return None


def data_of(text):
    """str -> bytes for saving, keeps the file ASCII-safe."""
    if PY3:
        return text.encode('utf-8')
    return text


def line_count(text):
    return len(text.replace('\r\n', '\n').split('\n'))


def is_valid_program(text):
    """The download may replace this file only if it looks like the program."""
    if not text or len(text) < 2000:
        return 'file is too short (%d bytes)' % (0 if not text else len(text))
    if UPDATE_MARKER not in text or 'def main(' not in text:
        return 'no RUN MODE / main() in the file - not this program'
    try:
        compile(text.replace('\r\n', '\n'), REPO_FILE, 'exec')
    except SyntaxError as err:
        return 'downloaded file has a syntax error: %s' % err
    except Exception as err:
        return 'downloaded file cannot be checked: %s' % err
    return ''


def read_local(path):
    try:
        handle = open(path, 'rb')
    except IOError:
        return None
    try:
        return text_of(handle.read())
    finally:
        try:
            handle.close()
        except Exception:
            pass


def write_local(path, text):
    """Write through a temporary file + rename (a crash keeps the old file)."""
    folder = os.path.dirname(path) or '.'
    if not os.access(folder, os.W_OK):
        raise IOError('folder %s is read-only (copy robot.py to /home/robot)'
                      % folder)
    tmp = path + '.new'
    out = open(tmp, 'wb')
    try:
        out.write(data_of(text))
        out.flush()
        try:
            out.flush()
            os.fsync(out.fileno())
        except Exception:
            pass
    finally:
        try:
            out.close()
        except Exception:
            pass
    if os.path.exists(path):
        if os.path.exists(path + OLD_SUFFIX):
            os.remove(path + OLD_SUFFIX)
        os.rename(path, path + OLD_SUFFIX)
    os.rename(tmp, path)


UPDATE_CACHE_MIN = 30       # do not ask GitHub more often than this (minutes)
_UPDATE_VERBOSE = True      # False while the update runs in quiet mode
UPDATE_CACHE_FILE = 'robot.check'


def update_cache_path():
    """Where the result of the last successful check is stored."""
    path = script_path()
    return os.path.join(os.path.dirname(path) or '.', UPDATE_CACHE_FILE)


def text_stamp(text):
    """
    Short fingerprint of the file contents (no hashlib: it may be absent
    on Pybricks). It answers one question: did somebody edit robot.py
    by hand after the last update?
    """
    if not text:
        return '0-0'
    flat = text.replace('\r\n', '\n')
    acc = 0
    for char in flat:
        acc = (acc * 131 + ord(char)) % 1000000007
    return '%d-%d' % (len(flat), acc)


def read_cache(cache):
    """
    -> (stamp that was on the disk, age in minutes) or None.
    The EV3 has no battery clock, so the age comes from the file time.
    """
    try:
        info = os.stat(cache)
        age_min = (time.time() - info.st_mtime) / 60.0
        handle = open(cache, 'rb')
        try:
            saved = (text_of(handle.read()) or '').strip()
        finally:
            handle.close()
    except Exception:
        return None
    if not saved:
        return None
    return saved, age_min


def write_cache_stamp(cache, text_now_on_disk):
    """Remember what the file looks like right after a check/update."""
    try:
        handle = open(cache, 'wb')
        try:
            handle.write(data_of(text_stamp(text_now_on_disk)))
        finally:
            handle.close()
    except Exception:
        pass


def run_update(fetch_only=False, show_head=False, quiet=False,
               quick=False, force=False):
    """
    Check GitHub for a new robot.py and install it.
      fetch_only = True  -> only look, never write anything
      show_head  = True  -> print the head of the downloaded file
      quiet      = True  -> a few lines instead of the full log
      quick      = True  -> one short attempt (used on start: a robot
                            without Wi-Fi must drive, not wait)
      force      = True  -> install even if robot.py was edited by hand
                            (MODE = 'update' / --update do this)
    Returns True only when this file on the disk was really replaced.
    """
    global _UPDATE_VERBOSE
    _UPDATE_VERBOSE = not quiet
    branch = branch_of_this_file()
    path = script_path()
    url = RAW_URL % (branch, REPO_FILE)
    old = read_local(path)

    if quiet:
        log('update: checking GitHub (%s, branch %s) ...' % (REPO_NAME, branch))
    else:
        log('=== auto update from GitHub ===')
        log('repo   : %s' % REPO_URL)
        log('branch : %s' % branch)
        log('file   : %s' % path)
        log('url    : %s' % url)
        log('local line count: %d' % (0 if old is None else line_count(old)))
        log('downloading ...')

    # ---- 1. was this file edited by hand since the last check?
    # ----    then an automatic update must not overwrite the changes
    cache = update_cache_path()
    cached = read_cache(cache)
    edited = False
    if cached and old is not None:
        cached_stamp, age_min = cached
        edited = (cached_stamp != text_stamp(old))
        if edited and not force and not fetch_only:
            log('update: robot.py was edited on this robot - auto update skipped')
            log('update: to update anyway set MODE = \'update\' in the file')
            return False
        # ---- 2. checked recently? do not ask GitHub again
        if (not edited) and age_min <= UPDATE_CACHE_MIN and not fetch_only:
            if quiet:
                log('update: checked less than %d min ago - skipping'
                    % UPDATE_CACHE_MIN)
            else:
                log('update: the last check was %d min ago - skipping'
                    % int(age_min))
            return False

    if quick:
        text = text_of(http_get(RAW_URL % (branch, REPO_FILE),
                                timeout=UPDATE_TIMEOUT_START))
    else:
        text = download_program(branch)
        if text is None:
            if not quiet:
                log('raw file is not reachable - trying the zip archive of the branch')
            text = script_from_zip(http_get(ZIP_REF_URL % branch))
        if text is None:
            text = script_from_zip(http_get(ZIP_CODELOAD_URL % branch))
    if text is None:
        log('update: no answer from GitHub (no network?) - driving the current version')
        if not quiet:
            log('Download by hand: %s/blob/%s/%s' % (REPO_URL, branch, REPO_FILE))
            log('Or the archive  : %s' % (ZIP_URL % branch))
        return False

    problem = is_valid_program(text)
    if problem:
        log('update: %s' % problem)
        log('update: this file is left untouched - driving the current version')
        return False

    new_lines = line_count(text)
    if not quiet:
        log('network line count: %d' % new_lines)

    if show_head:
        log('--- first 25 lines of the downloaded file ---')
        for row in text.replace('\r\n', '\n').split('\n')[:25]:
            log(row)

    if old is not None and old.replace('\r\n', '\n') == text.replace('\r\n', '\n'):
        write_cache_stamp(cache, text)
        log('update: this is the newest version')
        return False

    if fetch_only:
        log('update IS available (%d -> %d lines)' % (line_count(old or ''), new_lines))
        log('run again with MODE = \'run\' (or MODE = \'update\') to install it')
        return False

    try:
        write_local(path, text)
    except Exception as err:
        log('FAILED to write the file: %s' % err)
        log('The program itself is still fine - just not updated.')
        log('Put robot.py into /home/robot (that folder is writable).')
        return False

    write_cache_stamp(cache, text)
    log('update: UPDATED to the newest version (%d -> %d lines)'
        % (0 if old is None else line_count(old), new_lines))
    if not quiet:
        log('old version saved as %s%s' % (path, OLD_SUFFIX))
        log('undo: rename %s%s back to %s'
            % (path, OLD_SUFFIX, os.path.basename(path)))
    return True


def restart_with_new_code():
    """
    The file on the disk was just replaced by the newest version.
    Run that new code right now (the running copy is the old one):
    this is a plain exec, so no clock, no network and no extra
    modules are needed - it works the same on ev3dev and Pybricks.
    """
    path = script_path()
    text = read_local(path)
    problem = is_valid_program(text)
    if problem:
        log('update: the new file is not usable (%s) - driving the old code' % problem)
        main()
        return
    log('update: starting the new version now')
    namespace = {'__name__': 'robot_after_update', '__file__': path}
    try:
        code = compile(text.replace('\r\n', '\n'), path, 'exec')
        exec(code, namespace)
        entry = namespace.get('start')
        if entry is None:
            entry = namespace.get('main')
        if entry is None:
            log('update: the new file has no start() - driving the old code')
            main()
            return
        entry()
        return
    except SystemExit:
        return
    except Exception as err:
        log('update: the new version failed (%s) - driving the old code' % err)
        main()


# ============================================================
#  START
# ============================================================

def start():
    if MODE == 'stay':
        log('MODE = stay: nothing to do')
        return
    if MODE == 'update' or '--update' in sys.argv:
        run_update(force=True)
        return
    if '--update-check' in sys.argv:
        run_update(fetch_only=True)
        return
    if MODE == 'check' or '--check' in sys.argv:
        if not HAS_ROBOT:
            log('No robot libraries found (PC) - sensor check needs the robot.')
            return
        check_sensors()
        return
    if not HAS_ROBOT:
        log('No robot libraries found (PC).')
        log('Simulator: python3 tools/sim.py')
        log('Stress test: python3 tools/stress.py')
        log('Update check: python3 robot.py --update-check')
        return
    # ---- normal start: update itself, then drive ----
    if AUTO_UPDATE_AT_START:
        updated = run_update(quiet=AUTO_UPDATE_QUIET, quick=True)
        if updated:
            # the file on the disk is new now; drive exactly the code
            # that just arrived (the running copy is still the old one)
            restart_with_new_code()
            return
    main()


if __name__ == '__main__':
    start()
