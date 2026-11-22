import time

import measure
from constants import *

if __name__ == "__main__":

    while True:

        time.sleep(TIME_BETWEEN_PROBE)
        measures = measure.send_full_rtt_probe(BATCH_SIZE, True)