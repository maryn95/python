# pyinstaller -F --add-data "./icon:." terminal.py # to build executable

from PyQt6.QtCore import Qt, QIODevice, QTimer
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPlainTextEdit, QPushButton, QLabel, QCheckBox, QSizePolicy
from PyQt6.QtSerialPort import QSerialPort
from PyQt6.QtGui import QAction, QIcon
from serialWindow import SerialWindow
from datetime import datetime
import sys

import os
def iconPath(iconName: str) -> str:
    '''
    Path to the icon
    '''
    try:
        basePath = sys._MEIPASS
    except Exception:
        basePath = os.path.abspath('./icon')

    return os.path.join(basePath, iconName)




class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.__initUI()


    def __initUI(self):
        self.setWindowTitle('Serial Terminal')
        self.setMinimumSize(500, 400)

        exitAction = QAction(QIcon(iconPath('exit.png')), 'Exit', self)
        exitAction.setShortcut('Ctrl+Q')
        exitAction.triggered.connect(QApplication.instance().quit)

        # menuBar = self.menuBar()
        # fileMenu = menuBar.addMenu('&File')
        # fileMenu.addAction(exitAction)

        openSerialInfoAction = QAction(QIcon(iconPath('open.png')), 'Open serial port info', self)
        openSerialInfoAction.triggered.connect(self.__showSerialWindow)

        closeSerialAction = QAction(QIcon(iconPath('close.png')), 'Close serial port', self)
        closeSerialAction.triggered.connect(self.__closeSerialPort)

        toolBar = self.addToolBar('Toolbar')
        toolBar.setStyleSheet('QToolBar {background: rgb(240, 240, 240)}')
        toolBar.setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)
        toolBar.addAction(openSerialInfoAction)
        toolBar.addAction(closeSerialAction)
        tbSpacer = QWidget() # right alignment of the exit action 
        tbSpacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        toolBar.addWidget(tbSpacer)
        toolBar.addAction(exitAction)

        self.logTextEdit = QPlainTextEdit()
        self.logTextEdit.setReadOnly(True)

        self.hexCB = QCheckBox() # if checked log is displayed as hex
        self.hexCB.setChecked(True)
        self.hexLabel = QLabel('HEX')
        self.ASCIICB = QCheckBox() # if checked log is displayed as latin-1
        self.ASCIICB.setChecked(False)
        self.ASCIILabel = QLabel('ASCII')
        self.hexCB.stateChanged.connect(lambda checked: self.ASCIICB.setChecked(not checked))
        self.ASCIICB.stateChanged.connect(lambda checked: self.hexCB.setChecked(not checked))
        self.autoscrollCB = QCheckBox()
        self.autoscrollCB.setChecked(True)
        self.autoscrollLabel = QLabel('Autoscroll')
        self.clearLog = QPushButton('Clear') # clear serial port log
        self.clearLog.clicked.connect(self.logTextEdit.clear)
        hTopLayout = QHBoxLayout()
        hTopLayout.addWidget(self.hexCB)
        hTopLayout.addWidget(self.hexLabel)
        hTopLayout.addWidget(self.ASCIICB)
        hTopLayout.addWidget(self.ASCIILabel)
        hTopLayout.addWidget(self.autoscrollCB)
        hTopLayout.addWidget(self.autoscrollLabel)
        hTopLayout.addStretch(1)
        hTopLayout.addWidget(self.clearLog)
        
        self.lineEdit = QLineEdit()
        self.sendButton = QPushButton('Send')
        hLayout = QHBoxLayout()
        hLayout.addWidget(self.lineEdit)
        hLayout.addWidget(self.sendButton)

        mainWidget = QWidget() # main layout widget
        vLayout = QVBoxLayout()
        vLayout.addLayout(hTopLayout)
        vLayout.addWidget(self.logTextEdit)
        vLayout.addLayout(hLayout)
        vLayout.setContentsMargins(2, 2, 2, 2)
        mainWidget.setLayout(vLayout)
        self.setCentralWidget(mainWidget)

        self.serialWindow = SerialWindow()
        self.serialWindow.serialSignal.applySerial.connect(self.openSerialPort)
        self.serialWindow.hide()
        self.serialPort = QSerialPort()
        self.serialTimer = QTimer() # timer for triggering the __readSerial slot
        self.serialTimer.timeout.connect(self.__readSerial)

        self.sendButton.clicked.connect(self.__transmitLineEdit)
        self.lineEdit.returnPressed.connect(self.__transmitLineEdit)


    def __showSerialWindow(self) -> None:
        '''
        Opens a window for entering serial port settings
        '''
        if self.serialWindow.isVisible():
            self.serialWindow.hide()
        else:
            self.serialWindow.show()


    def openSerialPort(self, port):
        self.serialPort = port

        serialSettings = f'serial settings: name={port.portName()}, baud={port.baudRate()}, databits={port.dataBits()} ' + \
            f'parity={port.parity()}, stopbits={port.stopBits()}, flowcontrol={port.flowControl()}'
        self.__writeLog('info', serialSettings)

        if self.serialPort.open(QIODevice.OpenModeFlag.ReadWrite):
            self.__writeLog('info', 'serial port has been open')
            self.serialTimer.setInterval(100)
            self.serialTimer.start()
        else:
            self.__writeLog('info', 'error opening serial port')


    def __closeSerialPort(self):
        if self.serialPort.isOpen():
            self.serialPort.close()
            self.serialTimer.stop()
            self.__writeLog('info', 'serial port has been closed')


    def __readSerial(self):
        '''
        Read all input data from a serial port
        '''
        if self.serialPort.isOpen():
            data = self.serialPort.readAll()
            if data.isEmpty():
                return

            data = bytes(data)
            if self.hexCB.isChecked():
                separator = bytes((0x2d,)) # 0x2d = '-'
                # self.__writeLog(dtime + str(data.toHex(separator))) # without converting QByteArray
                self.__writeLog('received', str(data.hex(separator)))
            else:
                self.__writeLog('received', data.decode('latin-1'))
        else:
            self.__writeLog('info', 'serial port was disconnected')
            self.serialTimer.stop()

        if self.autoscrollCB.isChecked():
            self.logTextEdit.verticalScrollBar().setValue(self.logTextEdit.verticalScrollBar().maximum())


    def __transmitLineEdit(self):
        '''
        Write data to a serial port from the bottom QLineEdit
        '''      
        data = self.lineEdit.text()
        if data == '':
            return
        
        if self.hexCB.isChecked():
            try:
                data = ''.join(data.split())
                data = bytes([ int(data[i:i+2], 16) for i in range(0, len(data), 2) ])
                if self.writeSerial(data) > 0:
                    separator = bytes((0x2d,)) # 0x2d = '-'
                    self.__writeLog('transmitted', str(data.hex(separator)))
            except ValueError:
                self.__writeLog('transmitted', 'invalid data to send')
        else:
            if self.writeSerial(data.encode('latin-1')) > 0:
                self.__writeLog('transmitted', data)

        self.lineEdit.clear()


    def writeSerial(self, data: bytes) -> int:
        if not self.serialPort.isOpen():
            return 0
        
        if not isinstance(data, bytes):
            return 0
        
        return self.serialPort.writeData(data)


    def __writeLog(self, type: str, text: str) -> None:
        '''
        Write log to the logTextEdit with current time, message type and text
        '''
        dtime = datetime.strftime(datetime.now(), r'%H:%M:%S:%f')
        self.logTextEdit.appendPlainText(f'[{dtime}] [{type}] {text}')




if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    app.exec()
