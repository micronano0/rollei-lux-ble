#!/usr/bin/env python3
"""Nicht blockierende, geordnete Rollei-Befehle für die Fotobox.

Aufruf: python3 ~/rollei_fotobox.py on [KELVIN HELLIGKEIT]
        python3 ~/rollei_fotobox.py save
        python3 ~/rollei_fotobox.py off
        python3 ~/rollei_fotobox.py status

Jeder Auftrag wird zuerst in SQLite gespeichert. Ein kurzlebiger Hintergrund-
Worker führt die Aufträge in Einfügereihenfolge aus und beendet sich danach.
"""
import fcntl
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from datetime import datetime

HOME = Path.home()
SCRIPT = HOME / 'rollei_effekte_auto.py'
DB = HOME / '.rollei_fotobox_queue.sqlite3'
LOCK = HOME / '.rollei_fotobox_worker.lock'
LOG = HOME / 'rollei_fotobox.log'
STATUS = HOME / 'rollei_status.json'
SAVED = HOME / '.rollei_fotobox_cct.json'


def read_manual_cct():
    """Read actual manually set CCT, never infer it from EFF/HSI."""
    try:
        data = json.loads(STATUS.read_text(encoding='utf-8'))
        if data.get('active_mode') != 'CCT':
            return None
        cct = data['cct']
        k, b = int(cct['kelvin']), int(cct['brightness'])
        if 2500 <= k <= 9000 and 1 <= b <= 100:
            return k, b
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def save_cct(k, b):
    tmp = SAVED.with_suffix('.tmp')
    tmp.write_text(json.dumps({'kelvin': k, 'helligkeit': b}) + '\n', encoding='utf-8')
    os.replace(tmp, SAVED)


def load_cct():
    try:
        data = json.loads(SAVED.read_text(encoding='utf-8'))
        k, b = int(data['kelvin']), int(data['helligkeit'])
        if 2500 <= k <= 9000 and 1 <= b <= 100:
            return k, b
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def connection():
    con = sqlite3.connect(str(DB), timeout=15)
    con.execute('PRAGMA busy_timeout=15000')
    con.execute('CREATE TABLE IF NOT EXISTS jobs ('
                'id INTEGER PRIMARY KEY AUTOINCREMENT, '
                'command TEXT NOT NULL, '
                'state TEXT NOT NULL DEFAULT "pending", '
                'created TEXT NOT NULL, '
                'started TEXT, finished TEXT, returncode INTEGER)')
    con.commit()
    return con


def now():
    return datetime.now().isoformat(timespec='seconds')


def log(message):
    with LOG.open('a', encoding='utf-8') as f:
        f.write(f'{now()} {message}\n')


def worker():
    # Nur ein Worker darf Rollei-Befehle ausführen.
    with LOCK.open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        con = connection()
        # Nach unerwartetem Worker-Abbruch einen begonnenen Auftrag nicht
        # erneut senden (kein unbeabsichtigtes Einschalten nach einem OFF).
        con.execute("UPDATE jobs SET state='interrupted', finished=? "
                    "WHERE state='running'", (now(),))
        con.commit()
        try:
            while True:
                row = con.execute("SELECT id, command FROM jobs "
                                  "WHERE state='pending' ORDER BY id LIMIT 1").fetchone()
                if row is None:
                    break
                job_id, command = row
                con.execute("UPDATE jobs SET state='running', started=? WHERE id=?",
                            (now(), job_id))
                con.commit()
                args = [sys.executable, str(SCRIPT), *command.split()]
                log(f'START #{job_id}: {command}')
                try:
                    with LOG.open('a', encoding='utf-8') as output:
                        result = subprocess.run(args, cwd=str(HOME),
                                                stdout=output, stderr=subprocess.STDOUT,
                                                check=False)
                    code = result.returncode
                except Exception as exc:
                    log(f'FEHLER #{job_id}: {exc!r}')
                    code = 127
                con.execute('UPDATE jobs SET state=?, finished=?, returncode=? WHERE id=?',
                            ('done' if code == 0 else 'failed', now(), code, job_id))
                con.commit()
                log(f'ENDE #{job_id}: Exitcode {code}')
        finally:
            con.close()


def main():
    argv = sys.argv[1:]
    if argv == ['--worker']:
        worker()
        return
    if argv == ['save']:
        values = read_manual_cct()
        if values is None:
            raise SystemExit('Bitte Rollei zuerst manuell in CCT mit Helligkeit > 0 einstellen.')
        save_cct(*values)
        print(f'CCT gespeichert: {values[0]} K, {values[1]} %')
        return
    if argv == ['status']:
        con = connection()
        for id_, command, state, code in con.execute(
                'SELECT id, command, state, returncode FROM jobs ORDER BY id DESC LIMIT 8'):
            print(f'#{id_} {command}: {state}' + (f' (Exitcode {code})' if code is not None else ''))
        con.close()
        print('Gespeicherte CCT-Werte:', load_cct())
        return
    if not argv or argv[0] not in ('on', 'off'):
        raise SystemExit('Aufruf: rollei_fotobox.py on [KELVIN HELLIGKEIT] | off | status')
    if argv[0] == 'off' and len(argv) != 1:
        raise SystemExit('OFF benötigt keine Parameter.')
    if argv[0] == 'on' and len(argv) not in (1, 3):
        raise SystemExit('ON benötigt keine oder genau zwei Parameter.')
    if argv == ['off']:
        # Capture manual changes before OFF overwrites monitor brightness with 0.
        values = read_manual_cct()
        if values is not None:
            save_cct(*values)
    if argv == ['on']:
        values = read_manual_cct() or load_cct()
        if values is None:
            raise SystemExit('Keine CCT-Werte vorhanden. Erst manuell einstellen und save, oder on KELVIN HELLIGKEIT.')
        argv = ['on', str(values[0]), str(values[1])]
    if len(argv) == 3:
        try:
            kelvin, brightness = int(argv[1]), int(argv[2])
        except ValueError:
            raise SystemExit('Kelvin und Helligkeit müssen ganze Zahlen sein.')
        if not 2500 <= kelvin <= 9000 or not 1 <= brightness <= 100:
            raise SystemExit('Kelvin: 2500–9000, Helligkeit: 1–100 %.')
        argv = ['on', str(kelvin), str(brightness)]
        if sys.argv[1] == 'on' and len(sys.argv) == 4:
            save_cct(kelvin, brightness)
    if not SCRIPT.is_file():
        raise SystemExit(f'Rollei-Hauptskript fehlt: {SCRIPT}')
    command = ' '.join(argv)
    con = connection()
    cur = con.execute('INSERT INTO jobs (command, created) VALUES (?, ?)', (command, now()))
    con.commit()
    job_id = cur.lastrowid
    con.close()
    try:
        subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--worker'],
                         cwd=str(HOME), stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True, close_fds=True)
    except OSError as exc:
        raise SystemExit(f'Auftrag #{job_id} gespeichert, Worker-Start fehlgeschlagen: {exc}')
    print(f'Rollei-Auftrag #{job_id} angenommen: {command}')


if __name__ == '__main__':
    main()
