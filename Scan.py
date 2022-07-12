import RFExplorer
from datetime import datetime, timedelta
import time
import matplotlib.pyplot as plt
import numpy as np

# ---------------------------------------------------------- #
#  Constants                                                 #
# ---------------------------------------------------------- #
SERIALPORT = None
BAUDRATE = 500000

START_FREQ = 486.0  # MHz
STOP_FREQ = 766.0   # MHz
RBW = 0.050         # MHz
SWEEP_TIME = 5      # Seconds
FREQ_SPAN = RBW * RFExplorer.RFE_Common.CONST_RFE_MIN_SWEEP_POINTS

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
    for freq, amplitudes in temp_data.items():
        temp_data[freq] = round(max(amplitudes), 2)
    # Append to data array
    for freq, amplitude in temp_data.items():
        data_array[0].append(freq)
        data_array[1].append(amplitude)


def main():
    """
        Do the things
    """
    # Initialize
    objRFE = RFExplorer.RFECommunicator()
    objRFE.AutoConfigure = False

    ax = plt.gca()
    plt.ylabel('Amplitude (dBm)')
    plt.xlabel('Frequency (MHz)')
    plt.ylim(ymin=-11, ymax=0)
    plt.xlim(xmin=START_FREQ, xmax=STOP_FREQ)
    ax.plot([[1], [1]])

    data = [[], []]

    try:
        objRFE.GetConnectedPorts()

        if objRFE.ConnectPort(SERIALPORT, BAUDRATE):
            # Reset unit
            print("Resetting")
            objRFE.SendCommand("r")
            while(objRFE.IsResetEvent):
                pass

            # Wait for unit to stabalize
            print("Waiting")
            time.sleep(3)

            # Request configuration
            objRFE.SendCommand_RequestConfigData()

            # Wait to recieve configuration and model details
            while(objRFE.ActiveModel == RFExplorer.RFE_Common.eModel.MODEL_NONE):
                objRFE.ProcessReceivedString(True)

            if (objRFE.IsAnalyzer()):
                currentStartFreq = round(START_FREQ, 3)
                currentStopFreq = round(START_FREQ + FREQ_SPAN)

                while currentStopFreq < STOP_FREQ+FREQ_SPAN:
                    # Update scan frequencies
                    objRFE.UpdateDeviceConfig(
                        currentStartFreq, currentStopFreq)
                    print("Scanning ", "{:.3f}".format(currentStartFreq), "MHz - ", "{:.3f}".format(currentStopFreq), "MHz", sep="")
                    # Wait untill frequency is set
                    while not objRFE.ProcessReceivedString(True) and objRFE.StartFrequency != currentStartFreq:
                        pass

                    # Sleeping while sweeping
                    time.sleep(SWEEP_TIME)
                    objRFE.ProcessReceivedString(True)
                    sweepCollection = objRFE.SweepData

                    # Store data
                    extract_data(sweepCollection, data)

                    # Clean to clear RAM
                    objRFE.CleanSweepData()

                    # Find next frequency span
                    currentStartFreq = round(currentStopFreq + RBW, 3)
                    currentStopFreq = round(currentStopFreq + FREQ_SPAN, 3)

                    # Update plot
                    del ax.lines[0]
                    ax.plot(data[0], data[1])
                    plt.pause(0.05)

    except Exception as obEx:
        print("Error:", str(obEx))

    finally:
        if objRFE is not None:
            objRFE.Close()

    filename = 'Scan.csv'
    with open(filename, 'w') as f:
        for i in range(len(data[0])):
            f.write("{:.3f}".format(data[0][i])+", " +
                    "{:.1f}".format(data[1][i])+"\n")

    print("File written to", filename)

    plt.show()


if __name__ == "__main__":
    main()
