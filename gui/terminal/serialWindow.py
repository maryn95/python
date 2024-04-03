from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QGridLayout, QLineEdit, QPushButton, QComboBox, QLabel, QFrame
from PyQt6.QtSerialPort import QSerialPort, QSerialPortInfo
from PyQt6.QtGui import QIntValidator




class SerialWindow(QFrame):
    def __init__(self):
        super().__init__()
        self.__initUI() 
        

    def __initUI(self):
        self.setWindowTitle('Serial Info')
        self.setFixedSize(300, 190)
        self.setFrameShape(QFrame.Shape.Box)
        self.setLineWidth(2)
        
        class SerialSignal(QObject):
            '''
            Signal for triggering a serial port connection slot
            '''
            applySerial = pyqtSignal(QSerialPort)
        self.serialSignal = SerialSignal()

        self.buttonPorts = QPushButton('Scan')
        self.buttonPorts.clicked.connect(self.__scanPorts)
        self.comboPorts = QComboBox()
        self.__scanPorts()
        self.buttonApply = QPushButton('Apply')
        self.buttonApply.clicked.connect(self.__applySerialSettings)
        
        self.labelBaud = QLabel('BaudRate') # label for entering a custom baud
        self.comboBaud = QComboBox()
        self.comboBaud.addItems(('9600', '19200', '38400', '57600', '115200', 'custom'))
        self.comboBaud.setCurrentText('115200')
        self.baudCustom = QLineEdit()
        self.baudCustom.setValidator(QIntValidator(0, 9999999))
        self.baudCustom.setEnabled(False)
        self.comboBaud.currentIndexChanged.connect(self.__setCustomBaud)

        self.labelDataBits = QLabel('Data Bits')
        self.comboDataBits = QComboBox()
        self.comboDataBits.addItem('5', userData=QSerialPort.DataBits.Data5)
        self.comboDataBits.addItem('6', userData=QSerialPort.DataBits.Data6)
        self.comboDataBits.addItem('7', userData=QSerialPort.DataBits.Data7)
        self.comboDataBits.addItem('8', userData=QSerialPort.DataBits.Data8)
        self.comboDataBits.setCurrentText('8')

        self.labelParity = QLabel('Parity')
        self.comboParity = QComboBox()
        self.comboParity.addItem('no', userData=QSerialPort.Parity.NoParity)
        self.comboParity.addItem('even', userData=QSerialPort.Parity.EvenParity)
        self.comboParity.addItem('odd', userData=QSerialPort.Parity.OddParity)
        self.comboParity.setCurrentText('no')

        self.labelStopBits = QLabel('Stop Bits')
        self.comboStopBits = QComboBox()
        self.comboStopBits.addItem('1', userData=QSerialPort.StopBits.OneStop)
        self.comboStopBits.addItem('1.5', userData=QSerialPort.StopBits.OneAndHalfStop)
        self.comboStopBits.addItem('2', userData=QSerialPort.StopBits.TwoStop)
        self.comboStopBits.setCurrentText('1')

        self.labelFlowControl = QLabel('Flow Control')
        self.comboFlowControl = QComboBox()
        self.comboFlowControl.addItem('no', userData=QSerialPort.FlowControl.NoFlowControl)
        self.comboFlowControl.addItem('hardware', userData=QSerialPort.FlowControl.HardwareControl)
        self.comboFlowControl.addItem('software', userData=QSerialPort.FlowControl.SoftwareControl)
        self.comboFlowControl.setCurrentText('no')

        self.labelDirection = QLabel('Direction')
        self.comboDirection = QComboBox()
        self.comboDirection.addItem('all', userData=QSerialPort.Direction.AllDirections)
        self.comboDirection.addItem('input', userData=QSerialPort.Direction.Input)
        self.comboDirection.addItem('output', userData=QSerialPort.Direction.Output)
        self.comboDirection.setCurrentText('all')

        gLayout = QGridLayout()
        gLayout.addWidget(self.buttonPorts, 0, 0)
        gLayout.addWidget(self.comboPorts, 0, 1)
        gLayout.addWidget(self.buttonApply, 0, 2)

        gLayout.addWidget(self.labelBaud, 1, 0)
        gLayout.addWidget(self.labelDataBits, 1, 1)  
        gLayout.addWidget(self.labelParity, 1, 2)
        gLayout.addWidget(self.comboBaud, 2, 0)
        gLayout.addWidget(self.comboDataBits, 2, 1)  
        gLayout.addWidget(self.comboParity, 2, 2)   

        gLayout.addWidget(self.baudCustom, 3, 0)

        gLayout.addWidget(self.labelStopBits, 4, 0)
        gLayout.addWidget(self.labelFlowControl, 4, 1)  
        gLayout.addWidget(self.labelDirection, 4, 2)
        gLayout.addWidget(self.comboStopBits, 5, 0)
        gLayout.addWidget(self.comboFlowControl, 5, 1)  
        gLayout.addWidget(self.comboDirection, 5, 2) 
        
        self.setLayout(gLayout)


    def __scanPorts(self):
        '''
        Update available serial port names in comboPorts QComboBox
        '''
        self.comboPorts.clear()
        self.comboPorts.addItems([i.portName() for i in QSerialPortInfo.availablePorts()])


    def __setCustomBaud(self):
        '''
        Enable the custom baud QLineEdit for entering baud not presented in the comboBaud QComboBox
        '''
        if self.comboBaud.currentText() == 'custom':
            self.baudCustom.setEnabled(True)
        else:
            self.baudCustom.clear()
            self.baudCustom.setEnabled(False)


    def __applySerialSettings(self):
        '''
        Read all serial port settings and send it to the main window
        '''
        serialPort = QSerialPort()
        serialPort.setPortName(self.comboPorts.currentText())

        baud = 115200
        if not self.baudCustom.isEnabled():
            baud = int(self.comboBaud.currentText())
        elif self.baudCustom.text() != '':
            baud = int(self.baudCustom.text())

        serialPort.setBaudRate(baud, dir=self.comboDirection.currentData())
        serialPort.setDataBits(self.comboDataBits.currentData())
        serialPort.setParity(self.comboParity.currentData())
        serialPort.setStopBits(self.comboStopBits.currentData())
        serialPort.setFlowControl(self.comboFlowControl.currentData())

        self.serialSignal.applySerial.emit(serialPort)
        self.hide()
