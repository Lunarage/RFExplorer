"""
    Module used to scan frequency ranges
"""

from datetime import datetime
import time
# import matplotlib.pyplot as plt
import argparse
import numpy as np
import RFExplorer

# ---------------------------------------------------------- #
#  Constants                                                 #
# ---------------------------------------------------------- #
SERIALPORT = None
BAUDRATE = 500000

# ---------------------------------------------------------- #
#  Default Argument Values                                   #
# ---------------------------------------------------------- #

RBW = 0.025         # MHz
SWEEP_TIME = 3      # Seconds

# ---------------------------------------------------------- #
#  Argparse                                                  #
# ---------------------------------------------------------- #

parser = argparse.ArgumentParser(description="RFExplorer Scan")

# TODO: allow multiple frequency ranges
parser.add_argument("start_freq", type=float)
parser.add_argument("stop_freq", type=float)
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
    default="Scan " + datetime.now().isoformat(sep=" ", timespec="minutes") + ".csv",
    metavar="FILE",
    help="""
    Default 'Scan yyyy-mm-dd HH:MM.csv'
    """,
)
parser.add_argument(
    "-c",
    "--calculator",
    type=str,
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


def extract_data(data_collection, data_array):
    """
        Process collected data
    """
    temp_data = {}

    # Create array
    for k in range(data_collection.GetData(0).TotalSteps):
        sweep_data = data_collection.GetData(0)
        freq = round(sweep_data.GetFrequencyMHZ(k), 3)
        temp_data[freq] = []

    # Fill array with data
    for i in range(data_collection.Count):
        sweep_data = data_collection.GetData(i)
        for j in range(sweep_data.TotalSteps):
            freq = round(sweep_data.GetFrequencyMHZ(j), 3)
            amplitude = sweep_data.GetAmplitude_DBM(j)
            temp_data[freq].append(amplitude)
    # Choose max amplitude
    # TODO: also calculate average
    for freq, amplitudes in temp_data.items():
        temp_data[freq] = round(max(amplitudes), 2)
    # Append to data array
    for freq, amplitude in temp_data.items():
        data_array[0].append(freq)
        data_array[1].append(amplitude)


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
            print("Waiting")
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


def calculate_sub_ranges(start_freq, stop_freq, rbw):
    """
    Calculate subranges to scan
    """
    freq_span = rbw * RFExplorer.RFE_Common.CONST_RFE_MIN_SWEEP_POINTS
    start_freqs = np.arange(start_freq, stop_freq, freq_span+rbw).tolist()
    stop_freqs = np.arange(start_freq+freq_span, stop_freq+freq_span, freq_span+rbw).tolist()
    assert len(start_freqs) == len(stop_freqs)

    freq_ranges = []
    for i in range(len(start_freqs)):
        freq_ranges.append({"start": round(start_freqs[i], 3), "stop": round(stop_freqs[i], 3)})

    return freq_ranges


def scan(obj_rfe, freq_ranges, sweep_time):
    """
        The scanning procedure
    """
    data = [[], []]
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

            # Store data
            extract_data(sweep_collection, data)

            # Clean to clear RAM
            obj_rfe.CleanSweepData()

    return data


def save_file(file_name, data):
    """
        Saves data to file
    """
    # TODO: option to convert to WSM (Sennhiser) format
    with open(file_name, 'w', encoding="utf-8") as output_file:
        for i in range(len(data[0])):
            output_file.write("{:.3f}".format(data[0][i])+", " +
                              "{:.1f}".format(data[1][i])+"\n")
    print("File written to", file_name)


# ---------------------------------------------------------- #
#  Main Procedure                                            #
# ---------------------------------------------------------- #


def main():
    """
        Do the things
    """
    args = parser.parse_args()

    obj_rfe = initialize_device()

    try:
        ranges = calculate_sub_ranges(args.start_freq, args.stop_freq, args.rbw)
        data = scan(obj_rfe, ranges, args.time)

    except Exception as ex:
        print("Error:", str(ex))

    finally:
        if obj_rfe is not None:
            obj_rfe.Close()

    save_file(args.output, data)


if __name__ == "__main__":
    main()
