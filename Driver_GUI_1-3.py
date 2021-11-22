###########################################################################################################
### Actasys Driver GUI
### Written by Anthony Johnson and Patrick Berne
### Actasys Inc. 2021
###########################################################################################################

import sys
import serial
import serial.tools.list_ports
import scipy
import pandas as pd
import numpy as np
import time
import cv2
import traceback

from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from pyqtgraph import PlotWidget, plot
import pyqtgraph as pg

###########################################################################################################
### GLOBAL CONFIGURATION ###
###########################################################################################################

#----------------------#
# - INITIAL SETTINGS - #
#----------------------#

EXE_ENABLED = False #Enable for executable version; disable for build version
WAVEFORM_FILE_NAME_EXE = "Waveform_Excel.xlsx"

#WAVEFORM_FILE_NAME_BUILD = "Waveform_Excel_Standard.xlsx"
WAVEFORM_FILE_NAME_BUILD = "Waveform_Excel_Vibration.xlsx"

#DUAL_ACTUATOR_SCALER = 0.953 #Scales output voltage for dual setting; configure this based on hardware
DUAL_ACTUATOR_SCALER = 1.0 #No scaling (some hardware doesn't need scaling)

#------------------------------------------------#
# - OTHER SETTINGS -- CHANGE ONLY IF NECESSARY - #
#------------------------------------------------#

WINDOW_WIDTH = 1450
WINDOW_HEIGHT = 744

MAX_VOLTAGE = 0.8
VOLT_SCALER = 120.0/MAX_VOLTAGE

TEST_TIME = 90000 #milliseconds
if (not EXE_ENABLED):
	TEST_TIME *= 10

EMPTY_WAVEFORM = "0c05000.500.50p010.505050f050050050a0.000.000.001000w0000ff000000ww0aa05000.50"
VERIFY_WAVEFORM = "1c01800.50" + EMPTY_WAVEFORM[10:]
CONNECT_WAVEFORM = "2" + EMPTY_WAVEFORM[1:10]

###########################################################################################################
### TEENSY CONNECTION ###
###########################################################################################################
MANUAL_ATTEMPT = True
TEENSY_CONNECTED = False
TEENSY_SERIAL_PORT = ""
TEENSY_BAUD_RATE = 9600
try:
	TEENSY_SERIAL_PORT = open("COM_PORT.txt").readline()
except:
	TEENSY_SERIAL_PORT = "<NO PORT SELECTED>"
	print("COM_PORT.txt file not found --> No serial port will be selected.")
	MANUAL_ATTEMPT = False

try: # Manual Connection
	if (not MANUAL_ATTEMPT or TEENSY_SERIAL_PORT == ""): # Intentionally send an error if manual attempt skipped
		teensy = serial.Serial(
			port="ERROR",
			baudrate="ERROR"
		)
	print("Attempting manual connection to serial port " + TEENSY_SERIAL_PORT + "...")
	teensy = serial.Serial(
		port=TEENSY_SERIAL_PORT,
		baudrate=TEENSY_BAUD_RATE
	)
	teensy.write(EMPTY_WAVEFORM.encode())
	teensy.flush()
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
				teensy = serial.Serial(
					port=port[0],
					baudrate=TEENSY_BAUD_RATE
				) # Send data to device and read back teensy confirmation message
				print("Sending message: " + CONNECT_WAVEFORM)
				teensy.write(CONNECT_WAVEFORM.encode())
				teensy.flush()
				line = teensy.readline().decode().rstrip() # This will be the CONNECT_WAVEFORM string
				line = teensy.readline().decode().rstrip() # This will be the actual return message, so this is called twice
				print("Received message: " + line)
				if (line == "TEENSY CONNECTION CONFIRM" or line.__contains__("Initialization Complete")):
					TEENSY_CONNECTED = True
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

###########################################################################################################
### WAVEFORM PARSING FUNCTION ###
###########################################################################################################
def parseWaveforms(sheet, sheet_name, waves, notes, numbers):
	current_list = []
	num = 0
	temp_num = 0
	note_num = []
	notes_list = []

	for i in range (len(sheet.index)):
		if (sheet.iloc[num][0] == "Note:"):
			current_note = sheet.iloc[num][1]
			note_num.append(temp_num)
			notes_list.append(current_note)
			num += 1
			continue

		out = "1"

		if (int(sheet.iloc[num][1]) < 0):
			break
		elif (int(sheet.iloc[num][1]) == 0):
			VOLT_SCALER = 120.0/MAX_VOLTAGE
		elif (int(sheet.iloc[num][1]) == 1):
			VOLT_SCALER = 120.0/(MAX_VOLTAGE*DUAL_ACTUATOR_SCALER)

		out += 'c'
		out += str(sheet.iloc[num][1])
		out += str(sheet.iloc[num][2]).zfill(3)
		out += "0." + str(int(sheet.iloc[num][3]/VOLT_SCALER*100)).zfill(2)
		out += "0." + str(int(sheet.iloc[num][4]*100)).zfill(2)

		out += 'p'
		if (int(sheet.iloc[num][5]) < 0):
			out += "010.505050"
		else:
			out += '1'
			out += str(sheet.iloc[num][5])
			out += str(round(sheet.iloc[num][6], 2))
			if (round(sheet.iloc[num][6], 2)*10 % 1 == 0):
				out += '0'
			out += str(sheet.iloc[num][7]).zfill(2)
			out += str(sheet.iloc[num][8]).zfill(2)

		out += 'f'
		if (int(sheet.iloc[num][9]) < 0):
			out += "050050050"
		else:
			if (int(sheet.iloc[num][9]) == 1 or int(sheet.iloc[num][9]) == 3):
				out += '1'
			else:
				out += '0'
			out += str(sheet.iloc[num][10]).zfill(3)
			out += str(sheet.iloc[num][11]).zfill(3)
			out += str(sheet.iloc[num][12]).zfill(2)
			out += str(sheet.iloc[num][13]).zfill(4)

		out += 'a'
		if (int(sheet.iloc[num][9]) < 0):
			out += "0.000.000.001000"
		else:	
			if (int(sheet.iloc[num][9]) == 2 or int(sheet.iloc[num][9]) == 3):
				out += '1'
			else:
				out += '0'
			out += "0." + str(int(sheet.iloc[num][14]/VOLT_SCALER*100)).zfill(2)
			out += "0." + str(int(sheet.iloc[num][15]/VOLT_SCALER*100)).zfill(2)

		out += 'w'
		if (int(sheet.iloc[num][16]) < 0):
			out += '0000'
		else:
			out += str(sheet.iloc[num][16]).zfill(4)

		out += 'ff'
		if not (int(sheet.iloc[num][17]) == 1 or int(sheet.iloc[num][17]) == 3
				or int(sheet.iloc[num][17]) == 4 or int(sheet.iloc[num][17]) == 5):
			out += "050000"
		else:
			out += '1'
			out += str(sheet.iloc[num][18]).zfill(2)
			out += str(sheet.iloc[num][19]).zfill(3)

		out += "ww"
		if not (int(sheet.iloc[num][17]) == 4 or int(sheet.iloc[num][17]) == 5):
			out += "00.00"
		else:
			out += "1"
			out += str(sheet.iloc[num][20]).zfill(4)

		out += 'aa'
		if not (int(sheet.iloc[num][17]) == 2 or int(sheet.iloc[num][17]) == 3
				or int(sheet.iloc[num][17]) == 5):
			out += "05000.50"
		else:
			out += '1'
			out += str(sheet.iloc[num][21]).zfill(3)
			out += "0." + str(int(sheet.iloc[num][22]/VOLT_SCALER*100)).zfill(2)

		out += 'wav'
		if (str(sheet.iloc[num][23]) ==  "-1"):
			out += '0'
		else:
			out += '1'
			out += str(sheet.iloc[num][24]).zfill(4)
			out += str(sheet.iloc[num][23]).upper().rstrip()
			#^^This isnt last in the Excel sheet because it's a necessary configuration
			#But it should be the last string here because it allows for WAV filenames of various lengths
		
		num += 1
		current_list.append(out)
		temp_num += 1

	note_num[0] = 0
	note_num.append(temp_num)
	waves[sheet_name] = current_list
	notes[sheet_name] = notes_list
	numbers[sheet_name] = note_num

###########################################################################################################
### WAVEFORM FILE CHECK ###
###########################################################################################################
WAVEFORM_FILE_NAME = "Waveform_Excel.xlsx"
if (EXE_ENABLED):
	WAVEFORM_FILE_NAME = WAVEFORM_FILE_NAME_EXE
else:
	WAVEFORM_FILE_NAME = WAVEFORM_FILE_NAME_BUILD

WAVEFORM_CONNECTED = False
MAIN_SHEET_NAME = ""
WAVEFORM_SHEETS = {}
SHEET_LIST = []
WAVEFORM_STRINGS = {}
MESSAGE_NOTES = {}
MESSAGE_NUMS = {}

try:
	waveform_file = pd.ExcelFile(WAVEFORM_FILE_NAME)
	MAIN_SHEET_NAME = waveform_file.sheet_names[0]
	for name in waveform_file.sheet_names:
		SHEET_LIST.append(name)
		sheet = waveform_file.parse(name)
		sheet.fillna(-1, inplace = True)
		sheet = sheet.iloc[2:]
		WAVEFORM_SHEETS[name] = sheet
		parseWaveforms(sheet, name, WAVEFORM_STRINGS, MESSAGE_NOTES, MESSAGE_NUMS)
	WAVEFORM_CONNECTED = True
except:
	pass

###########################################################################################################
### GUI FUNCTIONS AND CLASSES ###
###########################################################################################################
def createLabel(label):
	label = QLabel(label)

	label.setStyleSheet("color: #538DD5;"
						"background-color: #17365D;"
						"height: 200 px;"
						"font: 30pt Arial;")

	label.setAlignment(Qt.AlignCenter)

	return label

class Worker(QRunnable):
	def __init__(self, fn):
		super(Worker, self).__init__()

		# Store constructor arguments (re-used for processing)
		self.fn = fn 

	@pyqtSlot()
	def run(self):
		try:
			result = self.fn()
		except:
			traceback.print_exc()
			exctype, value = sys.exc_info()[:2]
			self.signals.error.emit((exctype, value, traceback.format_exc()))

class TabBar(QTabBar):
	def tabSizeHint(self, index):
		size = QTabBar.tabSizeHint(self, index)
		w = int(self.width()/self.count())
		return QSize(w, size.height())

class VerifyWindow(QFrame):
	def __init__(self):
		super(VerifyWindow, self).__init__()

		self.setContentsMargins(0, 0, 0, 0)

		self.threadpool = QThreadPool()

		self.verify_layout = QGridLayout()

		self.title = QLabel("Verification")
		self.title.setStyleSheet("QLabel"
								 "{"
								 "color: #538DD5;"
								 "font: 22pt Arial;"
								 "border: 0px;"
								 "}")
		bolded = QFont()
		bolded.setBold(True)
		self.title.setFont(bolded)
		self.verify_layout.addWidget(self.title, 0, 0, 1, 1)

		self.verify_btn = QPushButton("START")
		self.verify_btn.setCheckable(True)
		self.verify_btn.setStyleSheet("QPushButton{"
									  "color: #538DD5;"
									  "background-color: #3F3F3F;"
								 	  "border: 1px solid #1F9ED4;"
									  "font: 40pt Arial;"
									  "height: 100 px;}"
								 	  "QPushButton::checked { background-color:#17365D;}"
								 	  "QPushButton::pressed{ background-color: #1E1E1E;}")
		self.verify_btn.clicked.connect(self.startVerify)
	
		self.verify_layout.addWidget(self.verify_btn, 1, 0, 2, 3) 
	
		self.current_label = QLabel("Current")
		self.current_label.setStyleSheet("border: 0px; color: #538DD5; font: 15pt Arial; height: 15 px")
		self.current_label.setAlignment(Qt.AlignCenter)
		self.verify_layout.addWidget(self.current_label, 0, 4, 1, 1)
	
		self.current = QLabel("Verification Paused")
		self.current.setAlignment(Qt.AlignCenter)
		self.current.setStyleSheet("QLabel{"
								   "color: #538DD5;"
								   "background-color: #262626;"
							  	   "border: 1px solid #1F9ED4;"
								   "font: 22pt Arial;}")
		self.verify_layout.addWidget(self.current, 1, 3, 2, 3)
	
		self.current_timer = QTimer()
		self.current_timer.setInterval(300)
		self.current_timer.timeout.connect(self.createVerifyWorker)

		self.setLayout(self.verify_layout)

	def startVerify(self):
		if (self.verify_btn.isChecked()):
			MainWindow.teensy_gui_write(MainWindow, VERIFY_WAVEFORM)
			self.current_timer.start()
			self.current.setText("Verification Running")
			self.verify_btn.setText("STOP")
		else:
			MainWindow.teensy_gui_write(MainWindow, EMPTY_WAVEFORM)
			self.current.setText("Verification Paused")
			self.verify_btn.setText("START")
			self.current_timer.stop()

	def createVerifyWorker(self):
		worker = Worker(self.updateWindow)
		self.threadpool.start(worker)

	def updateWindow(self):
		global TEENSY_CONNECTED
		if (TEENSY_CONNECTED):
			ser_bytes = teensy.readline()
			teensy_str = ser_bytes.decode("utf-8")
			teensy.flush()
		else:
			self.current.setText("Teensy Disconnected")


class Label(QWidget):
	def __init__(self, parent=None):
		super(Label, self).__init__(parent)
		self.img = QPixmap()
		self.low_x = 0
		self.high_x = 0
		self.low_y = 0
		self.high_y = 0

	def paintEvent(self, event):
		painter = QPainter(self)
		painter.drawPixmap(QPoint(), self.img)
		painter.end()

	def mousePressEvent(self, event):
		if event.button() == Qt.LeftButton:
			self.drawing = True
			painter = QPainter(self.img)
			painter.setPen(QPen(Qt.red, 3, Qt.SolidLine))
			painter.drawPoint(event.pos())
			self.update()
			painter.end()
			if (self.low_y + self.high_y + self.low_x + self.high_x == 0):
				self.low_x = event.x()
				self.high_x = event.x()
				self.low_y = event.y()
				self.high_y = event.y()
			if (event.y() < self.low_y): 
				self.low_y = event.y()
			if (event.y() > self.high_y): 
				self.high_y = event.y()
			if (event.x() < self.low_x): 
				self.low_x = event.x()
			if (event.x() > self.high_x): 
				self.high_x = event.x()

	def sizeHint(self):
		return self.img.size()

	def setPixmap(self, pix):
		self.img = QPixmap(pix)
		self.update()

	def getCoords(self):
		return self.low_x, self.high_x, self.low_y, self.high_y

	def reset(self):
		self.img = QPixmap()
		self.low_x = 0
		self.high_x = 0
		self.low_y = 0
		self.high_y = 0

	def height(self):
		return self.img.height()
	def width(self):
		return self.img.width()


class MainWindow(QWidget):
	global WAVEFORM_SHEETS, WAVEFORM_STRINGS, SHEET_LIST, WINDOW_WIDTH
	global WINDOW_HEIGHT, MESSAGE_NOTES, MESSAGE_NUMS

	def __init__(self, parent = None):
		super(MainWindow, self).__init__(parent)

		self.reset_timer = QTimer()
		self.reset_timer.setInterval(TEST_TIME)
		self.reset_timer.timeout.connect(self.stopWaveform)

		self.setStyleSheet("background-color: #17365D;") 
		self.setContentsMargins(0, 0, 0, 0)

		self.window_layout = QVBoxLayout(self)
		self.window_layout.setContentsMargins(0, 0, 0, 0)

		self.tabs = QTabWidget()
		self.tabs.setContentsMargins(0, 0, 0, 0)
		self.tabs.setStyleSheet("QTabBar"
								"{"
								"color: #538DD5;"
								"font: 30pt Arial"
								"}"
								"QTabBar::tab {"
								"background: #3F3F3F; "
								"border: 1px solid #1F9ED4;"
								"height: 80px;"
								"width: " + str(WINDOW_WIDTH/(len(SHEET_LIST)+2)) + ";"
								"} "
								"QTabBar::tab:selected { "
								"border: 1px solid #1F9ED4;"
								"background: #262626; "
								"}")
		self.tabs.updateGeometry()
		self.tab_array = []

		self.pause_buttons = []

		self.verify = VerifyWindow()
		self.verify.setStyleSheet("QFrame{border: 1px dashed #558ED5}")

		self.empty_label = QLabel()
		self.empty_label.setStyleSheet("background-color: #17365D;")

		self.window_layout.addWidget(self.tabs)

		for sheet_name in SHEET_LIST:
			self.verify = VerifyWindow()
			self.verify.setStyleSheet("QFrame{border: 1px dotted #558ED5;}")

			self.new_tab = QWidget()
			self.new_tab.setContentsMargins(0, 0, 0, 0)

			self.tab_layout = QGridLayout()
			self.new_tab.setLayout(self.tab_layout)

			self.radio_layout = QGridLayout()
			radio_button = QRadioButton("STOP")
			radio_button.num = -1
			radio_button.setChecked(True)
			radio_button.setStyleSheet("QRadioButton"
									   "{"
									   "border: 0px;"
									   "color: #538DD5;"
									   "font: 15pt Arial;"
									   "width: 130px"
									   "}"
									   "QRadioButton::indicator"
									   "{"
									   "border-radius: 14px;"
									   "width : 28px;"
									   "height : 28px;"
									   "border : 1px solid #1F9ED4"
									   "}"
									   "QRadioButton::indicator::checked"
									   "{"
										 "background-color : #17365D;"
									   "}"
									   "QRadioButton::indicator::unchecked"
									   "{"
									   "background-color : #3F3F3F;"
									   "}") 
			radio_button.toggled.connect(self.onClicked)

			self.radio_layout.addWidget(radio_button, 0, 3)
			self.radio_layout.setContentsMargins(10, 10, 10, 10)
			self.pause_buttons.append(radio_button)

			self.title = QLabel("Test Plan")
			self.title.setStyleSheet("QLabel"
									 "{"
									 "color: #538DD5;"
									 "font: 22pt Arial;"
									 "border: 0px;"
									 "}")
			bolded = QFont()
			bolded.setBold(True)
			self.title.setFont(bolded)
			self.radio_layout.addWidget(self.title, 0, 0, 1, 1)

			for i in range(len(WAVEFORM_STRINGS[sheet_name])):
				radio_button = QRadioButton("T" + str(i+1))
				radio_button.setChecked(False)
				radio_button.num = i
				radio_button.setStyleSheet("QRadioButton"
										  "{"
										  "border: 0px;"
										  "color: #538DD5;"
										  "font: 15pt Arial;"
										  "width: 130px"
										  "}"
										  "QRadioButton::indicator"
										  "{"
										  "border-radius: 14px;"
										  "width : 28px;"
										  "height : 28px;"
										  "border : 1px solid #1F9ED4"
										  "}"
										  "QRadioButton::indicator::checked"
										  "{"
									  	  "background-color : #17365D;"
										  "}"
										  "QRadioButton::indicator::unchecked"
										  "{"
										  "background-color : #3F3F3F;"
										  "}") 

				radio_button.toggled.connect(self.onClicked)
		
				self.radio_layout.addWidget(radio_button, int(i/4 + 1), i%4)

			if (sheet_name == MAIN_SHEET_NAME):
				self.message_layout = QVBoxLayout()
				self.title = QLabel("Messages")
				self.title.setStyleSheet("QLabel"
										 "{"
										 "color: #538DD5;"
										 "font: 22pt Arial;"
										 "border: 0px;"
										 "}")
				bolded = QFont()
				bolded.setBold(True)
				self.title.setFont(bolded)
				self.message_layout.addWidget(self.title, 1)

				self.messages = QLabel()
				self.messages.setStyleSheet("QLabel"
											"{"
											"border: 0px;"
											"height: 200px;"
											"font: 15pt Arial;"
											"color: #538DD5;"
											"}")
				self.temp_string = ""

				for i in range(0, len(MESSAGE_NOTES[sheet_name])):
					self.temp_string += ("T" + str(MESSAGE_NUMS[sheet_name][i] + 1))
					if (MESSAGE_NUMS[sheet_name][i]+1 != MESSAGE_NUMS[sheet_name][i+1]):
						self.temp_string += ("-T" + str(MESSAGE_NUMS[sheet_name][i+1]))
					self.temp_string += ": " + MESSAGE_NOTES[sheet_name][i] + "\n"
				
				self.messages.setText(self.temp_string)

				self.message_layout.addWidget(self.messages, 4)

				self.message_widget = QWidget()
				self.message_widget.setStyleSheet("QWidget"
												  "{"
												  "border: 1px dashed #558ED5;"
												  "}")
				self.message_widget.setLayout(self.message_layout)

				self.tab_layout.addWidget(self.message_widget, 1, 1, 1, 1)
			else:
				self.empty_label = QLabel()
				self.empty_label.setStyleSheet("background-color: #17365D;")
				self.tab_layout.addWidget(self.empty_label, 2, 0, 2, 1)

			self.radio_widget = QWidget()
			self.radio_widget.setLayout(self.radio_layout)
			self.radio_widget.setStyleSheet("QWidget"
											"{"
											"border: 1px dashed #558ED5;"
											"}")
			if (sheet_name == MAIN_SHEET_NAME):
				self.tab_layout.addWidget(self.radio_widget, 0, 0, 4, 1)
			else:
				self.tab_layout.addWidget(self.radio_widget, 0, 0, 2, 1)



			self.tab_layout.addWidget(self.verify, 0, 1, 1, 1)

			self.tab_array.append(sheet_name)
			self.tabs.addTab(self.new_tab, sheet_name)

		self.verify = VerifyWindow()
		self.verify.setStyleSheet("QFrame{border: 1px dashed #558ED5}")

		self.empty_label = QLabel()
		self.empty_label.setStyleSheet("background-color: #17365D;")

		self.empty_label = QLabel()
		self.empty_label.setStyleSheet("background-color: #17365D;")

	def onClicked(self):
		global MESSAGE_NUMS, TEENSY_CONNECTED
		radio_button = self.sender()
		if radio_button.isChecked():
			if (radio_button.num == -1):
				self.teensy_gui_write(EMPTY_WAVEFORM)
				self.reset_timer.stop()
			else:
				w = WAVEFORM_STRINGS[SHEET_LIST[self.tabs.currentIndex()-1]][radio_button.num]
				self.teensy_gui_write(w)
				self.reset_timer.start()

	def stopWaveform(self):
		global EMPTY_WAVEFORM
		self.reset_timer.stop()
		self.teensy_gui_write(EMPTY_WAVEFORM)

	def teensy_gui_write(self, waveform_str):
		global TEENSY_CONNECTED, EMPTY_WAVEFORM
		if (TEENSY_CONNECTED):
			try:
				teensy.write(waveform_str.encode())
				teensy.flush()
				if (waveform_str == EMPTY_WAVEFORM):
					print("Waveform Paused")
				elif (waveform_str == VERIFY_WAVEFORM):
					print("Running Verification Waveform")
				else:
					print("Running Waveform: " + waveform_str)
			except:
				print("\nERROR: Cannot write to Teensy.")
				print("RECOMMENDED FIX:")
				print("\t1) Turn off power to the driver.")
				print("\t2) Disconnect, then reconnect the USB cable.")
				print("\t3) Relaunch the GUI.")
				print("\t4) Turn the driver back on when GUI is open.")
				TEENSY_CONNECTED = False
				self.error_msg = QMessageBox();
				self.error_msg.setWindowTitle("ERROR")
				self.error_msg.setText("\rCannot write to Teensy\
										\n\rRECOMMENDED FIX:\
										\n\r\t1) Turn off power to the driver.\
										\n\r\t2) Disconnect, then reconnect the USB cable.\
										\n\r\t3) Relaunch the GUI.\
										\n\r\t4) Turn the driver back on when the GUI is open.")
				self.error_msg.exec()

###########################################################################################################
### MAIN FUNCTION ###
###########################################################################################################
if __name__ == '__main__':
	if (TEENSY_CONNECTED and WAVEFORM_CONNECTED):
		print("\nInitialization Successful! Starting GUI...")
		app = QApplication(sys.argv)
		player = MainWindow()
		player.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
		player.showMaximized()
		teensy.write(EMPTY_WAVEFORM.encode())
		teensy.flush()
		print("GUI Started")
		sys.exit(app.exec_())
	else:
		print("\nERROR(s) FOUND:")
		if (not TEENSY_CONNECTED):
			print("\tTeensy not connected. Please connect or reconnect USB and restart program.")
		if (not WAVEFORM_CONNECTED):
			print("\tWaveform file either not present or contains an input error. Please acquire a working \"" + WAVEFORM_FILE_NAME + "\" and restart program.")
		if (EXE_ENABLED):
			user_input = input() #Infinitely wait
