## Accelerometer DAQ
## Written by Patrick Berne for Actasys Inc
## 7/20/2021

# -------------- ADJUST THESE SETTINGS --------------------- #

## Sampling Settings
SAMPLE_RATE_HZ = 3200							# Samples to Gather per Second (This should match Teensy rate)
SAMPLE_TIME_SEC = 2 							# Number of Seconds to Run Data Acquisition

## Zeroing Settings
ZERO_ENABLED = True 							# Enable or Disable Zeroing during Data Acquisition
ZERO_SETTING = 1 								# 0 = Zeroing while still, 1 = Zeroing while shaking (e.g. on actuator)

## Noise Settings
NOISE_FILTER_ENABLED = True 					# Enable or Disabling Noise Margin
NOISE_MARGIN = 1.0 								# Noise Margin (m/s^2). Rejects Changes in Acceleration within +- this Value

## Calibration Settings
X_OFFSET = -1.25 								# These Calibration Values Are Obtained by:
X_INVERSE_GAIN = 31.5							# 1) Measuring the ADC values at +1 and -1g for each axis, and
Y_OFFSET = -0.5 								#	 taking the difference, then dividing by 2 to get the offset
Y_INVERSE_GAIN = 31.75							# 2) Adding the absolute value of the ADC values at +1 and -1g,
Z_OFFSET = 0.125 								#    then dividing by 2 to get the inverse gain value, then tweaking
Z_INVERSE_GAIN = 31								# ----> 2g Settings: -10.5, 254, -4.1, 254, 1.0, 249.5

## Teensy Connection Settings
TEENSY_SER_FILENAME = "COM_PORT_2.txt"			# Filename for Manual Connection
TEENSY_SERIAL_PORT = ""  						# Serial Port for Manual Serial Connection (Leave as "" for filename)

## Workbook Settings
WORKBOOK_ENABLED = True			   		 		# Enable or Disable Writing Data to Workbook
WORKBOOK_PATH = ".\\Acceleration_Data/"			# Workbook File Path
WORKBOOK_FILENAME = "acc_data"					# Workbook File Name (without timestamp)

## Plot Settings
PLOT_ENABLED = True								# Enable or Disable Plot Visualization
PLOT_TITLE = "Actuator Bracket Acceleration"	# Set Plot Title

# ---------------------------------------------------------- #

##############################################################
### LIBRARY IMPORTS ###
##############################################################

import sys
import os
import serial
import serial.tools.list_ports
import time
import math
import numpy as np
import matplotlib.pyplot as plt
import xlsxwriter
import datetime

##############################################################
### GENERAL SETTINGS ###
##############################################################

## Data Acquisition Parameters
SAMPLE_NUM = int(SAMPLE_RATE_HZ*SAMPLE_TIME_SEC)
X_COEF = (9.81/X_INVERSE_GAIN)
Y_COEF = (9.81/Y_INVERSE_GAIN)
Z_COEF = (9.81/Z_INVERSE_GAIN)

## Teensy Connection Parameters
MANUAL_ATTEMPT = True				# Manual Connection Flag
TEENSY_CONNECTED = False            # Connection Indicator
TEENSY_BAUD_RATE = 921600           # Serial Baud Rate
TEENSY = None 						# Initialize Serial.serial() Variable

############################+##################################
### TEENSY CONNECTION ###
##############################################################

MANUAL_ATTEMPT = True
TEENSY_CONNECTED = False
TEENSY_SERIAL_PORT = ""
TEENSY_BAUD_RATE = 9600
try:
	TEENSY_SERIAL_PORT = open(TEENSY_SER_FILENAME).readline()
except:
	TEENSY_SERIAL_PORT = "<NO PORT SELECTED>"
	print("COM_PORT.txt file not found --> No serial port will be selected.")
	MANUAL_ATTEMPT = False

try: # Manual Connection
	if (not MANUAL_ATTEMPT or TEENSY_SERIAL_PORT == ""):
		TEENSY = serial.Serial(
			port="ERROR", # Intentionally send error if manual attempt is skipped
			baudrate="ERROR"
		)
	print("Attempting manual connection to serial port " + TEENSY_SERIAL_PORT + "...")
	TEENSY = serial.Serial(
		port=TEENSY_SERIAL_PORT,
		baudrate=TEENSY_BAUD_RATE
	)
	TEENSY_CONNECTED = True
	print("Successfully connected to serial device at " + TEENSY_SERIAL_PORT + ".")
except: # Automatic Connection
	if (not MANUAL_ATTEMPT or TEENSY_SERIAL_PORT == ""):
		print("No serial port selected. Ignoring manual connection attempt.")
	else:
		print("Manual connection attempt failed.")
	print("\nAttempting automatic connection...")
	myports = [tuple(p) for p in list(serial.tools.list_ports.comports())]
	if (len(myports) == 0):
		print("No serial ports detected.")
		print("Automatic connection attempt failed.")
	else:
		print(str(len(myports)) + " serial port(s) detected:")
		for port in myports:
			print("\t", port)
		port_index = 0
		for port in myports:
			print("\nAttempting connection to " + port[1] + "...")
			port_index += 1
			try:
				TEENSY = serial.Serial(
					port=port[0],
					baudrate=TEENSY_BAUD_RATE
				)
				#line = TEENSY.readline().decode().rstrip()
				if (True): #if (line.__contains__("")): # Use this for specific programs
					TEENSY_CONNECTED = True
					TEENSY_SERIAL_PORT = port[1]
					print("Connection to " + port[1] + " succeeded.")
					break
				else:
					print("Connection to " + port[1] + " failed.")
					if (port_index >= len(myports)-1):
						print("Automatic connection attempts failed.")
			except:
				print("Connection to " + port[1] + " failed.")
				if (port_index >= len(myports)-1):
					print("Automatic connection attempts failed.")

##############################################################
### MAIN FUNCTION ###	
##############################################################
if __name__ == '__main__':
    print("----------------------------------------------------")
    ## Data Acquisition
    if (TEENSY_CONNECTED):
    	print("Sample Time: {} Second(s)".format(SAMPLE_TIME_SEC))
    	print("Acquiring Data...", end = " ")

    	# Establish Variables
    	try:
    		incoming_str = TEENSY.readline().decode()
    	except:
    		print("ERROR: TEENSY DISCONNECTED")
    	x = np.empty(SAMPLE_NUM)
    	y = np.empty(SAMPLE_NUM)
    	z = np.empty(SAMPLE_NUM)
    	time_arr = np.empty(SAMPLE_NUM)
    	index_y = index_z = 0

    	# Read Serial Data, Add to Arrays
    	start = time.time()
    	for i in range(SAMPLE_NUM):
    		incoming_str = TEENSY.readline().decode()
    		index_y = incoming_str.index("y")
    		index_z = incoming_str.index("z")
    		x[i] = float(incoming_str[:index_y])
    		y[i] = float(incoming_str[index_y+1:index_z])
    		z[i] = float(incoming_str[index_z+1:])

    	# Print Time Elapsed
    	end = time.time()
    	print("Done!")
    	print("Time Elapsed:", round(end - start, 4), "Seconds")

    	# Obtain Zeroing Offset
    	x_zero_offset = y_zero_offset = z_zero_offset = 0
    	if (ZERO_ENABLED):
    		# Zeroing while standing still
    		if (ZERO_SETTING == 0):
    			x_zero_offset = -(x[0] + X_OFFSET)
		    	y_zero_offset = -(y[0] + Y_OFFSET)
		    	z_zero_offset = -(z[0] + Z_OFFSET)
		    # Zeroing while shaking
    		if (ZERO_SETTING == 1):
		    	x_zero_offset = -(np.average(x) + X_OFFSET)
		    	y_zero_offset = -(np.average(y) + Y_OFFSET)
		    	z_zero_offset = -(np.average(z) + Z_OFFSET)

    	# Apply Gains, Offsets, and Filters to Readings, and Populate Time Array
    	for i in range(SAMPLE_NUM):
    		x[i] += X_OFFSET
    		y[i] += Y_OFFSET
    		z[i] += Z_OFFSET
    		if (ZERO_ENABLED):
    			x[i] += x_zero_offset
    			y[i] += y_zero_offset
    			z[i] += z_zero_offset
    		x[i] *= X_COEF
    		y[i] *= Y_COEF
    		z[i] *= Z_COEF
    		if (NOISE_FILTER_ENABLED and i > 0):
    			if (abs(x[i] - x[i-1]) <= NOISE_MARGIN):
    				x[i] = x[i-1]
    			if (abs(y[i] - y[i-1]) <= NOISE_MARGIN):
    				y[i] = y[i-1]
    			if (abs(z[i] - z[i-1]) <= NOISE_MARGIN):
    				z[i] = z[i-1]
    		time_arr[i] = round(i/SAMPLE_NUM*SAMPLE_TIME_SEC, 4)
    	time_arr[-1] = SAMPLE_TIME_SEC

    	## Print Average Readings (for calibration purposes)
    	print("\nX:", round(np.average(x), 2))
    	print("Y:", round(np.average(y), 2))
    	print("Z:", round(np.average(z), 2))
    	print("Magnitude:", round(math.sqrt(np.average(x)**2 + np.average(y)**2 + np.average(z)**2), 2), end="\n\n")

    	## Print to Workbook
    	if (WORKBOOK_ENABLED):
    		# Create Directory (if it doesn't exist)
	        try:
	       		os.mkdir(WORKBOOK_PATH, 0o666)
	        except:
	       		pass

	    	# Create Headers
	        workbook_dir = WORKBOOK_PATH + WORKBOOK_FILENAME +'_{}.xlsx'\
	        			   .format(str(datetime.datetime.now().strftime("%H_%M_%S")))
	        workbook = xlsxwriter.Workbook(workbook_dir)
	        data_sheet = workbook.add_worksheet("Data")
	        bold_format = workbook.add_format({'bold': True})
	        data_sheet.write(0, 0, 'Time (s)', bold_format)
	        data_sheet.write(0, 1, 'X (m/s^2)', bold_format)
	        data_sheet.write(0, 2, 'Y (m/s^2)', bold_format)
	        data_sheet.write(0, 3, 'Z (m/s^2)', bold_format)

	        # Write Data
	        for i in range(SAMPLE_NUM):
		        data_sheet.write(i+1, 0, time_arr[i])
		        data_sheet.write(i+1, 1, x[i])
		        data_sheet.write(i+1, 2, y[i])
		        data_sheet.write(i+1, 3, z[i])

			# Close the Workbook
	        print("Workbook Saved to " + workbook_dir)
	        workbook.close()

	    ## Display Accelerometer Graph
    	if (PLOT_ENABLED):
	        plt.plot(time_arr, x, "r", label="x")
	        plt.plot(time_arr, y, "g", label="y")
	        plt.plot(time_arr, z, "b", label="z")
	        plt.title(PLOT_TITLE)
	        plt.xlabel("Time (s)")
	        plt.ylabel("Accleration (m/s^2)")
	        plt.legend()
	        print("Showing Plot...")
	        plt.show()

    ## Connection Check
    else:
        print("Teensy not connected.\nPlease reconnect USB and restart program.\n")