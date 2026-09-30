"""Learning-stage scheduler: run immediately, then 5 minutes after each run.

Keep Terminal open and the Mac awake. Ctrl+C stops scheduling.
Runs are sequential. A failed run stops the scheduler for investigation.
"""
import fcntl
from pathlib import Path
import sys
import time

from sync_contacts import main as sync_once


def run_loop(sync=sync_once, sleep=time.sleep):
    print('Automatic sync started. Runs now, then waits 5 minutes after each successful run.', flush=True)
    print('Keep this Terminal open. Press Control+C to stop.', flush=True)
    while True:
        if sync(interactive=False) != 0:
            print('Automatic sync stopped after a failure. Check logs/sync.log, fix the problem, and restart.', flush=True)
            return 1
        print('Next sync in 5 minutes.', flush=True)
        sleep(300)


def main():
    directory = Path(__file__).parent / 'logs'
    directory.mkdir(exist_ok=True)
    with (directory / 'auto_sync.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('An automatic sync process is already running for this project.')
            return 1
        return run_loop()


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print('\nAutomatic sync stopped.')
        sys.exit(0)
