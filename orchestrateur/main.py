import time

import measure
from constants import *

if __name__ == "main.py":
    while True:
        time.sleep(TIME_BETWEEN_PROBE)
        measure.send_full_rtt_probe(BATCH_SIZE)