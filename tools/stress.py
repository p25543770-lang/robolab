#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================
 stress.py — проверка «линию не теряет»
================================================================

Гоняет ту же логику, что и robot.py (класс LineFollower), в тяжёлых
условиях и печатает честную статистику.

Что проверяется:
  * датчики стоят по-разному (близко к оси / шире линии);
  * шум датчиков (нормальный и сильный);
  * «провалы» датчика (блик, тень);
  * старт со сдвигом, под углом, на белом;
  * объект в разных местах трассы.

    python3 tools/stress.py            # полный прогон
    python3 tools/stress.py --quick    # быстрый
================================================================
"""

import argparse
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import sim                                        # noqa: E402
from robot import Settings                        # noqa: E402

# старты: (название, (x, y, курс))
STARTS = [
    ('ровно на линии', (150.0, 1320.0, -math.pi / 2)),
    ('сдвиг +50 мм', (200.0, 1320.0, -math.pi / 2)),
    ('сдвиг -50 мм', (100.0, 1320.0, -math.pi / 2)),
    ('сдвиг +75 мм', (225.0, 1320.0, -math.pi / 2)),
    ('угол +25°', (150.0, 1320.0, -math.pi / 2 + math.radians(25))),
    ('угол -25°', (150.0, 1320.0, -math.pi / 2 - math.radians(25))),
    ('угол +40°', (150.0, 1320.0, -math.pi / 2 + math.radians(40))),
    ('на белом 150 мм', (300.0, 1320.0, -math.pi / 2)),
]


def one(job):
    name, kw = job
    res = sim.run(Settings(), verbose=False, **kw)
    ok = res['note'] == 'объект стоп'
    return (name, ok, round(res['time'], 1), round(res['max_dev']))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--quick', action='store_true')
    ap.add_argument('--jobs', type=int, default=2)
    args = ap.parse_args()

    seeds = (1, 2) if args.quick else (1, 2, 3)
    halves = (12.0, 16.0) if args.quick else (8.0, 12.0, 16.0, 20.0, 24.0)
    noises = (1.0,) if args.quick else (1.0, 2.5, 3.5)
    objys = (800.0,) if args.quick else (500.0, 800.0, 1100.0)

    jobs = []

    # 1. обычная езда в разных условиях
    for half in halves:
        for noise in noises:
            for sd in seeds:
                for objy in objys:
                    jobs.append(('датчики %0.0f мм, шум %.1f'
                                 % (half, noise),
                                 dict(seed=sd, sensor_half=half, noise=noise,
                                      object_xy=(600.0, objy))))

    # 2. тяжёлые старты
    for name, st in STARTS:
        for half in halves:
            for sd in seeds:
                jobs.append(('старт: ' + name,
                             dict(seed=sd, sensor_half=half, start=st,
                                  object_xy=(600.0, 1250.0))))

    # 3. провалы датчика (блики/тени)
    for drop in (0.02, 0.05):
        for sd in seeds:
            jobs.append(('провалы датчика %.0f%%' % (drop * 100),
                         dict(seed=sd, sensor_half=16.0, noise=2.0,
                              dropout=drop, object_xy=(600.0, 800.0))))

    from multiprocessing import Pool
    with Pool(args.jobs) as pool:
        rows = pool.map(one, jobs)

    total = len(rows)
    good = sum(1 for r in rows if r[1])
    ts = sorted(r[2] for r in rows)
    print('=== проверка ведения по линии: %d сценариев ===' % total)
    print('доехал по линии до объекта: %d/%d (%.0f%%)'
          % (good, total, 100.0 * good / total))
    print('макс. отклонение от линии: %d мм' % max(r[3] for r in rows))
    print('время: медиана %.1f с, макс %.1f с' % (ts[len(ts) // 2], ts[-1]))

    # по группам «старт»
    print('\nстарты:')
    for name, _ in STARTS:
        sub = [r for r in rows if r[0] == 'старт: ' + name]
        g = sum(1 for r in sub if r[1])
        print('  %-18s %d/%d' % (name, g, len(sub)))

    bad = [r for r in rows if not r[1]]
    if bad:
        print('\nне прошли:')
        for r in bad[:15]:
            print('  %-32s %5.1f с  откл. %d мм' % (r[0], r[2], r[3]))
    else:
        print('\nвсе сценарии пройдены — линию не теряет')


if __name__ == '__main__':
    main()
