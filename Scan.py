#!/usr/bin/env python3
"""
    Module used to scan frequency ranges
"""

from datetime import datetime
import time
# import matplotlib.pyplot as plt
import argparse
import re
import numpy as np
import RFExplorer

# ---------------------------------------------------------- #
#  Constants                                                 #
# ---------------------------------------------------------- #
SERIALPORT = None
BAUDRATE = 500000
ILLEGAL_FILE_NAME_CHARACTERS = "#%&{}\<>*?/ $+`|'\"=:@" # Because windows

# ---------------------------------------------------------- #
#  Default Argument Values                                   #
# ---------------------------------------------------------- #

RBW = 0.025         # MHz
SWEEP_TIME = 3      # Seconds

# ---------------------------------------------------------- #
#  Argparse                                                  #
# ---------------------------------------------------------- #

parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="""
RFExplorer Scan Script
Scan with an RFExplorer and output a csv-file ready to import in WWB.
        """,
        epilog="""
Example: Scan.py --rbw 0.05 --time 5 518 526 550 566
This will scan the ranges 518 MHz - 526 MHz and 550 MHz - 566 MHz
with an RBW of 0.050 MHz and scanning for 5 seconds in each sub-range.
        """
        )

parser.add_argument("frequencies", nargs='+', type=float, help="Pairwise list of frequencies denote ranges")
parser.add_argument(
    "--rbw",
    type=float,
    action="store",
    default=RBW,
    help="""
    Default 0.025 MHz.
    Resolution Bandwidth.
    Increasing this number makes the scan faster, but lowers the accuracy.
    """,
)
parser.add_argument(
    "-t",
    "--time",
    type=int,
    action="store",
    default=SWEEP_TIME,
    help="""
    Default 3 seconds.
    Amount of seconds to collect data in each subrange.
    """,
)
parser.add_argument(
    "-o",
    "--output",
    type=str,
    action="store",
    default="Scan_" + datetime.now().isoformat(sep="_", timespec="minutes").replace(":", '') + ".csv",
    metavar="FILE",
    help="""
    Default 'Scan yyyy-mm-dd HH:MM.csv'
    """,
)
parser.add_argument(
    "-c",
    "--calculator",
    type=str,
    choices=["MAX", "AVG"],
    action="store",
    default="MAX",
    help="""
    Default MAX. The calculation method to use.
    Available calculators:
    MAX takes the maximum value of the scan data,
    AVG takes the average value of the scan data.
    """,
)

# ---------------------------------------------------------- #
#  Functions                                                 #
# ---------------------------------------------------------- #


def initialize_device():
    """
        Initialize device
    """
    obj_rfe = RFExplorer.RFECommunicator()
    obj_rfe.AutoConfigure = False

    try:
        obj_rfe.GetConnectedPorts()
        if obj_rfe.ConnectPort(SERIALPORT, BAUDRATE):
            # Reset unit
            print("Resetting")
            obj_rfe.SendCommand("r")
            while obj_rfe.IsResetEvent:
                pass

            # Wait for unit to stabalize
            time.sleep(3)

            # Request configuration
            obj_rfe.SendCommand_RequestConfigData()

            # Wait to recieve configuration and model details
            while obj_rfe.ActiveModel == RFExplorer.RFE_Common.eModel.MODEL_NONE:
                obj_rfe.ProcessReceivedString(True)

    except Exception as ex:
        print("Error:", str(ex))
        return None

    return obj_rfe


def calculate_ranges(freqs, rbw):
    """
        Calculate all scan ranges from a pairwise list of frequencies
    """
    ranges = []
    for start_freq, stop_freq in zip(freqs[0::2], freqs[1::2]):
        ranges += calculate_sub_ranges(start_freq, stop_freq, rbw)
    return ranges


def calculate_sub_ranges(start_freq, stop_freq, rbw):
    """
    Calculate subranges to scan
    """
    freq_span = rbw * RFExplorer.RFE_Common.CONST_RFE_MIN_SWEEP_POINTS
    start_freqs = np.arange(start_freq, stop_freq, freq_span+rbw).tolist()
    stop_freqs = np.arange(start_freq+freq_span, stop_freq+freq_span, freq_span+rbw).tolist()

    freq_ranges = []
    for sub_start_freq, sub_stop_freq in zip(start_freqs, stop_freqs, strict=True):
        freq_ranges.append({"start": round(sub_start_freq, 3), "stop": round(sub_stop_freq, 3)})

    return freq_ranges


def scan(obj_rfe, freq_ranges, sweep_time):
    """
        The scanning procedure
    """
    data = []
    if obj_rfe.IsAnalyzer():
        for freq_range in freq_ranges:
            # Update scan frequencies
            obj_rfe.UpdateDeviceConfig(
                freq_range["start"], freq_range["stop"])
            print("Scanning ",
                  f'{freq_range["start"]:.3f}', " MHz - ",
                  f'{freq_range["stop"]:.3f}', " MHz",
                  sep="")

            # Wait untill frequency is set
            while not obj_rfe.ProcessReceivedString(True) and obj_rfe.StartFrequency != freq_range.start:
                pass

            # Sleeping while sweeping
            time.sleep(sweep_time)
            obj_rfe.ProcessReceivedString(True)
            sweep_collection = obj_rfe.SweepData
            for index in range(sweep_collection.Count):
                data.append(sweep_collection.GetData(index))

            # Clean to clear RAM
            obj_rfe.CleanSweepData()

    return data


def restructure_scan_data(scan_data):
    """
        Process collected data
    """
    structured_data = {}
    for sweep_data in scan_data:
        for step in range(sweep_data.TotalSteps):
            freq = round(sweep_data.GetFrequencyMHZ(step), 3)
            amplitude = sweep_data.GetAmplitude_DBM(step)
            if freq in structured_data:
                structured_data[freq].append(amplitude)
            else:
                structured_data[freq] = [amplitude]

    return structured_data


def process_data(data, method):
    """
    Do some calculations on the dataset
    """
    for frequency, amplitudes in data.items():
        if method == "MAX":
            data[frequency] = max(amplitudes)
        elif method == "AVG":
            data[frequency] = sum(amplitudes) / len(amplitudes)
        else:
            print("Invalid calculator")
    return data


def save_file(file_name, data):
    """
        Saves data to file
    """
    # TODO: option to convert to WSM (Sennhiser) format
    with open(file_name, 'w', encoding="utf-8") as output_file:
        for frequency, amplitude in data.items():
            output_file.write(f'{frequency:.3f}'+", " +
                              f'{amplitude:.1f}'+"\n")
    print("File written to", file_name)


# ---------------------------------------------------------- #
#  Main Procedure                                            #
# ---------------------------------------------------------- #


def main():
    """
        Do the things
    """
    args = parser.parse_args()
    if not len(args.frequencies) % 2 == 0:
        raise Exception("Odd number of frequencies entered")
    # TODO: check if filename is legal (especially on windows)

    ranges = calculate_ranges(args.frequencies, args.rbw)

    try:
        obj_rfe = initialize_device()
        scan_data = scan(obj_rfe, ranges, args.time)
        data = process_data(restructure_scan_data(scan_data), args.calculator)

    except Exception as ex:
        print("Error:", str(ex))

    finally:
        if obj_rfe is not None:
            obj_rfe.Close()

    save_file(args.output, data)


if __name__ == "__main__":
    main()
