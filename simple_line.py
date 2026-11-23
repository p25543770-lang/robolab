#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ПРОСТО «ИНВЕРСНАЯ ЛИНИЯ»: включил — и едет по линии.
# Поднеси робота к БЕЛОЙ и ЧЁРНОЙ клетке, впиши числа в WHITE_REF и BLACK_REF — и готово.
# Останавливается Ctrl+C в консоли (или выдерни провод).

from pybricks.hubs import EV3Brick
from pybricks.ev3devices import Motor, ColorSensor
from pybricks.parameters import Port, Direction
from pybricks.tools import wait

brick = EV3Brick()

# --- ЕДИНСТВЕННЫЕ НАСТРОЙКИ (подстрой под свои датчики) ---
WHITE_REF = 62     # отражение от белой клетки
BLACK_REF = 8      # отражение от чёрной клетки
BASE_POWER = 30    # мощность на прямой
KP, KD = 0.9, 1.5  # П и Д коэффициенты поворота

MID = (WHITE_REF + BLACK_REF) / 2.0
HYST = 8

# --- Порты: S1 слева, S2 справа, C левое колесо (зеркальное), B правое ---
left_eye = ColorSensor(Port.S1)
right_eye = ColorSensor(Port.S2)
motor_l = Motor(Port.C, Direction.COUNTERCLOCKWISE)
motor_r = Motor(Port.B)

white_cell = True   # старт на белой зоне
bg = float(WHITE_REF)
prev_err = 0.0

while True:
    l, r = left_eye.reflection(), right_eye.reflection()

    # Какого цвета клетка? (шахматка: цвет линии — наоборот клетки)
    avg = (l + r) / 2.0
    bg += 0.2 * (avg - bg)
    if l < MID - HYST and r < MID - HYST:
        white_cell = False            # обе тёмные -> чёрная клетка
    elif l > MID + HYST and r > MID + HYST:
        white_cell = bg >= MID        # обе яркие: белая клетка или белая линия на чёрной
    elif bg > MID + HYST:
        white_cell = True
    elif bg < MID - HYST:
        white_cell = False

    # Ошибка: > 0 -> линия слева, < 0 -> линия справа (знак верный на любой клетке)
    err = (r - l) if white_cell else (l - r)

    # ПД-регулятор, поворот подмешиваем к мощности
    turn = KP * err + KD * (err - prev_err)
    prev_err = err
    turn = max(-50, min(50, turn))
    power = BASE_POWER - 14 * min(1.0, abs(err) / 60.0)   # сбавляем ход на крутых поворотах
    motor_l.dc(max(-100, min(100, power - turn)))
    motor_r.dc(max(-100, min(100, power + turn)))

    # Если нужен стоп по кнопке — раскомментируй две строки:
    # if brick.buttons.pressed():
    #     break

    wait(10)
