#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
upload.py - send robot.py to the EV3 (ev3dev) and run it with brickrun.

Run it on the COMPUTER, in the project folder:

    python tools/upload.py                    # upload + run
    python tools/upload.py --check            # upload + sensor check
    python tools/upload.py --mode check       # the same
    python tools/upload.py --no-run           # only upload (no run)
    python tools/upload.py --host 192.168.0.128
    python tools/upload.py --list             # find the brick on the network

Needs only what is already on Windows: OpenSSH (ssh.exe) and python.
No pip packages, no pybricksdev, no special USB driver.

The default address is ev3dev's own USB link: 192.168.0.128, user robot.
Over Wi-Fi use the brick address shown on its screen
(ev3dev: Settings -> About -> IP address).
"""

import os
import subprocess
import sys

REMOTE_DIR = '/home/robot/robolabs2'
REMOTE_FILE = 'robot.py'
DEFAULT_HOST = '192.168.0.128'
DEFAULT_USER = 'robot'          # ev3dev defaults: user "robot", password "maker"
DEFAULT_PASSWORD = 'maker'


def log(text):
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode('ascii', 'replace').decode('ascii'))


def parse_args(argv):
    opts = {
        'host': DEFAULT_HOST,
        'user': DEFAULT_USER,
        'password': DEFAULT_PASSWORD,
        'port': '22',
        'run': True,
        'mode': 'run',
        'list': False,
        'local': os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              os.pardir, REMOTE_FILE),
        'timeout': 300,
    }
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ('-h', '--help'):
            log(__doc__)
            sys.exit(0)
        elif arg == '--host' and i + 1 < len(argv):
            opts['host'] = argv[i + 1]
            i += 1
        elif arg == '--user' and i + 1 < len(argv):
            opts['user'] = argv[i + 1]
            i += 1
        elif arg == '--password' and i + 1 < len(argv):
            opts['password'] = argv[i + 1]
            i += 1
        elif arg == '--port' and i + 1 < len(argv):
            opts['port'] = argv[i + 1]
            i += 1
        elif arg == '--mode' and i + 1 < len(argv):
            opts['mode'] = argv[i + 1].lower()
            i += 1
        elif arg in ('--check', '-c'):
            opts['mode'] = 'check'
        elif arg in ('--update', '-u'):
            opts['mode'] = 'update'
        elif arg == '--no-run':
            opts['run'] = False
        elif arg == '--list':
            opts['list'] = True
        elif arg == '--timeout' and i + 1 < len(argv):
            opts['timeout'] = int(argv[i + 1])
            i += 1
        else:
            opts['local'] = arg
        i += 1
    opts['local'] = os.path.abspath(opts['local'])
    return opts


def need_program(name):
    """sshpass is not always there, so the password is typed by hand."""
    try:
        subprocess.call([name, '-V'], stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE)
        return True
    except OSError:
        return False


def ssh_options(opts, port_flag='-p'):
    """
    Common options for ssh / scp.
    Careful: ssh takes the port as -p, scp as -P.
    """
    return [port_flag, str(opts['port']),
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=' + os.devnull,
            '-o', 'ConnectTimeout=10',
            '-o', 'NumberOfPasswordPrompts=1',
            '-o', 'PubkeyAuthentication=no']


def find_bricks():
    """Scan the local network for ev3dev bricks (port 22 open)."""
    import socket
    found = []
    base = '192.168.0.'
    log('scanning %s1-254 ... (about 20 s)' % base)
    for last in range(1, 255):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.08)
        try:
            if sock.connect_ex((base + str(last), 22)) == 0:
                found.append(base + str(last))
                log('  found: %s%s' % (base, last))
        finally:
            sock.close()
    if not found:
        log('no brick found. Check USB cable / Wi-Fi and the IP on the brick screen.')
    return found


def main():
    opts = parse_args(sys.argv[1:])

    if opts['list']:
        find_bricks()
        return 0

    if not need_program('ssh') or not need_program('scp'):
        log('ssh / scp not found.')
        log('Windows: Settings -> Apps -> Optional features -> OpenSSH Client')
        log('Linux/Mac: install openssh-client')
        return 1

    if not os.path.isfile(opts['local']):
        log('file not found: %s' % opts['local'])
        return 1

    target = '%s@%s' % (opts['user'], opts['host'])
    ssh_opts = ssh_options(opts, '-p')
    scp_opts = ssh_options(opts, '-P')
    log('brick : %s' % target)
    log('file  : %s' % opts['local'])
    log('mode  : %s' % opts['mode'])
    log('')
    log('password for the brick is "maker" (ev3dev default) '
        'if it asks for one')

    # ---- 1. upload ----
    mkdir_cmd = ['ssh'] + ssh_opts + [target, 'mkdir -p ' + REMOTE_DIR]
    log('')
    log('1/2 creating %s on the brick ...' % REMOTE_DIR)
    if subprocess.call(mkdir_cmd) != 0:
        log('cannot log in to the brick.')
        log('Check: USB cable connected, brick is on, address is right '
            '(--host).')
        return 1

    scp_cmd = ['scp'] + scp_opts + [opts['local'],
                                    '%s:%s/%s' % (target, REMOTE_DIR,
                                                  REMOTE_FILE)]
    log('      copying robot.py ...')
    if subprocess.call(scp_cmd) != 0:
        log('copy failed.')
        return 1
    log('      done: %s/%s' % (REMOTE_DIR, REMOTE_FILE))

    if not opts['run']:
        log('')
        log('uploaded only. Run it on the brick with:')
        log('  brickrun --directory="%s" "%s/%s"'
            % (REMOTE_DIR, REMOTE_DIR, REMOTE_FILE))
        return 0

    # ---- 2. run ----
    mode_args = ''
    if opts['mode'] == 'check':
        mode_args = ' --check'
    elif opts['mode'] == 'update':
        mode_args = ' --update'
    run_cmd = ('brickrun --directory="%s" "python3 %s/%s%s"'
               % (REMOTE_DIR, REMOTE_DIR, REMOTE_FILE, mode_args))
    log('')
    log('2/2 running on the brick:')
    log('      %s' % run_cmd)
    log('-' * 60)
    try:
        return subprocess.call(['ssh'] + ssh_opts + [target, run_cmd])
    except KeyboardInterrupt:
        log('')
        log('stopped by user')
        return 130


if __name__ == '__main__':
    sys.exit(main())
