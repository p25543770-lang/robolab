# Запуск из Visual Studio Code (ev3dev, `brickrun`)

> **У вас прошивка ev3dev и запуск через `brickrun`.** Значит нужна первая
> конфигурация из списка F5 — **«EV3 (ev3dev): залить и запустить»**.
> Конфигурации с `pybricksdev` не подходят: на ev3dev они падают с ошибкой
> `usb.core.NoBackendError: No backend available` (это ошибка Windows-драйвера,
> а не робота).

## 0. Ещё проще — без VS Code

Одна команда в PowerShell скачивает проект и сама заливает его на кирпич:

```powershell
irm https://raw.githubusercontent.com/p25543770-lang/robolab/main/install.ps1 | iex
```

На вопрос «Залить на робота и запустить сейчас? [Y/n]» — **Enter**.

## 1. Что нужно (один раз)

**В Windows ничего доустанавливать не надо** — `ssh` и `scp` уже входят в
состав Windows 10/11 (OpenSSH Client). `pip install` не требуется.

**В VS Code:** открыть папку проекта целиком (**File → Open Folder** →
`robolab`) и поставить расширение **Python** (`ms-python.python`), если его нет.

**На кирпиче:** прошивка ev3dev (у вас уже есть). Кирпич подключён по USB.
Адрес кирпича по USB у ev3dev всегда `192.168.0.128`,
пользователь `robot`, пароль `maker`.

## 2. Что делать

1. Откройте папку `robolab` в VS Code.
2. Нажмите **F5** и выберите **«EV3 (ev3dev): залить и запустить»**.
3. В терминале:

```
brick : robot@192.168.0.128
1/2 creating /home/robot/robolabs2 on the brick ...
      copying robot.py ...
2/2 running on the brick:
      brickrun --directory="/home/robot/robolabs2" "python3 /home/robot/robolabs2/robot.py"
```

4. Если спросит пароль — введите `maker` (при вводе он не отображается).
5. Робот пискнет 2 раза и поедет, в терминале пойдёт его лог.

Остановить: **Ctrl+C** в терминале.

## 3. Что есть в `.vscode/launch.json`

| Название в списке F5 | Что делает |
|---|---|
| **EV3 (ev3dev): залить и запустить** | копирует `robot.py` на кирпич и запускает `brickrun` |
| **EV3 (ev3dev): залить и проверить датчики** | то же, но `MODE = 'check'`: моторы стоят, печатаются `S1/S2/S3/S4` |
| **EV3 (ev3dev): только залить (без запуска)** | копирует файл и выходит |
| **EV3 (ev3dev): обновить программу с GitHub** | запускает на кирпиче `--update`: кирпич сам скачает свежий `robot.py` |
| Компьютер: симулятор полигона | `tools/sim.py` на ПК (робот не нужен) |
| Компьютер: стресс-тест линии | `tools/stress.py` — 261 сценарий |
| Pybricks (только для прошивки Pybricks) | `pybricksdev run usb` — **вам не нужна** |

## 4. Адрес кирпича

По USB — `192.168.0.128`. Если кирпич в Wi-Fi, его адрес виден на экране
кирпича (*ev3dev: Settings → About → IP address*). Запуск с другим адресом:

```
python tools/upload.py --host 192.168.0.45
```

Искать кирпич в сети:

```
python tools/upload.py --list
```

Пароль можно передать сразу: `--password maker`.

## 5. Пошагово без VS Code (то же самое)

Из папки проекта в PowerShell или cmd:

```
python tools\upload.py                 # залить и запустить
python tools\upload.py --check         # залить и проверить датчики
python tools\upload.py --no-run        # только залить
python tools\upload.py --update        # обновить программу с GitHub
```

Всё это делает три вещи: `ssh mkdir`, `scp robot.py`, `ssh brickrun`.

## 6. Частые проблемы

| Симптом | Что делать |
|---|---|
| `usb.core.NoBackendError: No backend available` | вы нажали конфигурацию с `pybricksdev`. У вас ev3dev — выберите **«EV3 (ev3dev): …»** |
| `cannot log in to the brick` | проверьте кабель, что кирпич включён, адрес (`--host`). Пароль — `maker` |
| `Permission denied (publickey,password)` | ввели неверный пароль или на кирпиче другой пользователь: `--user robot` (по умолчанию так и есть) |
| `ssh / scp not found` | Windows: *Settings → Apps → Optional features → OpenSSH Client* → установить |
| `file not found: …/robot.py` | F5 запускает `tools/upload.py`, а он ищет `robot.py` в корне проекта — открывайте папку `robolab`, а не одиночный файл |
| Команда идёт, но робот молчит | смотрите лог в терминале: если он идёт, а робот стоит — проверьте `MODE` в начале файла (`'run'`) |
| Хочу пароль без ввода каждый раз | `ssh-keygen -t ed25519` и `ssh-copy-id robot@192.168.0.128` (на Windows есть в OpenSSH) |

## 7. Проверка датчиков

```
python tools\upload.py --check
```

или в списке F5 — **«EV3 (ev3dev): залить и проверить датчики»**. В терминале
побегут строки вида:

```
S1=  8  S2= 85  S3= 320 mm  S4= 900 mm  travel=0 mm
```

* рука у левого датчика — меняется `S1`;
* у правого — `S2`;
* перед «глазами» — `S3` (мм уменьшаются);
* справа — `S4`;
* `travel` — прокатите робота руками 50 см: должно стать ≈ 500 мм
  (если 250 — `gear_ratio = 1.0`, если 1000 — `gear_ratio = 4.0`).

## 8. Если прошивка всё-таки Pybricks

Тогда работает последняя конфигурация (`pybricksdev`), но её сначала надо
подготовить: `pip install pybricksdev` **и** драйвер WinUSB для кирпича
(через [Zadig](https://zadig.akeo.ie/) — именно из-за его отсутствия и
появляется `NoBackendError`). Проще остаться на ev3dev: там всё уже работает
без установки чего-либо.
