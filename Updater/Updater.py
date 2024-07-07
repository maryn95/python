import os

import struct
UNPACK_BIN_TAG = ('<HI2H2I10s', 28)
UNPACK_DEVICE_INFO = ('<BHI2H2I', 19)
PACK_DEVICE_INFO = '<2B'
UNPACK_START_UPLOAD = ('<2B', 2)
PACK_START_UPLOAD = '<2BHI2H2I10sI'
UNPACK_FW_PACKET = ('<2BI', 6)
PACK_FW_PACKET = '<2B3I'
UNPACK_FINISH_UPLOAD = ('<2B', 2)
PACK_FINISH_UPLOAD = '<2BIH'
PACK_SYSTEM_RESET = '<2B'

import collections
DeviceInfo = collections.namedtuple('DeviceInfo', ['BootVersion', 'DeviceId', 'MajorVersion', 'MinorVersion', 'FwPacketSize', 'FwMaxSize', 'BuildTime'])

import dataclasses
@dataclasses.dataclass(eq=False)
class FwInfo:
    fw: bytes
    size: int
    packetNum: int
    packetSize: int

import enum
class UpdaterCommands(enum.IntEnum):
    deviceInfo = 0x01
    startUpload = 0x02
    fwPacket = 0x03
    finishUpload = 0x04
    abortUpload = 0x05
    systemReset = 0x06

class UpdaterErrors(enum.IntEnum):
	success = 0x00
	packetSizeError = 0x01
	offsetError = 0x02
	eraseError = 0x03
	wrontPageNumError = 0x04
	fwSizeError = 0x05
	writeError = 0x06
	crcError = 0x07

	deviceIdError = 0x20
	versionError = 0x21
	deviceInfoError = 0x22

import sys
sys.path.append('../')
from Libs.Interface.IOnPacketReady import IOnPacketReady

DEVICE_INFO_TAG = bytes((0x11, 0x07, 0x5A, 0x78, 0x3B, 0x02, 0x96, 0xCC, 0xF0, 0xF0))
UPDATER_COMMAND = 0x01

class Updater():
    '''
    Firmware updater class.

    There are five stages of uploading mcu firmware:
    1. request a device info and process an answer
    2. search for appropriate binary files in a firmware dictionaty and send a start upload request
    3. read firmware binary file, divide it into pieces of the required length and send firmware packets one by one
    4. calculate crc of an uploading firmware and send a finish upload request
    5. send a system reset request

    Constructor: need to pass a path to directory with firmware files, a function to be calculating a firmware crc
    and an interface to be passing data to logic (a main class that contains an Updater object)
    '''
    def __init__(self, fwDir: str, calcCrc, onPacketReady: IOnPacketReady) -> None:
        self.__fwDict = {}
        self.__appCallback = onPacketReady
        self.__calcCrc = calcCrc
        self.__isUpdating = False
        self.__newDevInfo = None
        self.__fwInfo = None

        self.__searchFirmwareFiles(fwDir)
        if len(self.__fwDict) == 0:
            return

        self.__log('Firmware binary files:')
        for name, devInfo in self.__fwDict.items():
            self.__log(f'{name.split("/")[-1]}: BootVersion={devInfo.BootVersion}, DeviceId={devInfo.DeviceId}, ' + 
                  f'MajorVersion={devInfo.MajorVersion}, MinorVersion={devInfo.MinorVersion}, FwPacketSize={devInfo.FwPacketSize}, ' +
                  f'FwMaxSize={devInfo.FwMaxSize}, BuildTime={devInfo.BuildTime.decode("latin-1")}')


    def receiveAnswer(self, packet: bytes) -> None:
        '''
        Process packets from an embedded device
        '''
        command = packet[0]
        if command == UpdaterCommands.deviceInfo:
            self.__processDeviceInfo(packet)

        elif command == UpdaterCommands.startUpload:
            self.__processStartUpload(packet)

        elif command == UpdaterCommands.fwPacket:
            self.__processFwPacket(packet)

        elif command == UpdaterCommands.finishUpload:
            self.__processFinishUpload(packet)
        
        elif command == UpdaterCommands.abortUpload:
            pass


    def __processDeviceInfo(self, packet: bytes) -> None:
        '''
        Process a device info answer from mcu
        '''
        if not self.__isUpdating:
            if len(packet) != UNPACK_DEVICE_INFO[1]:
                self.__log('Received wrong device info structure')
            devInfoAnswer = struct.unpack(UNPACK_DEVICE_INFO[0], packet)
            self.__log(f'Received device info: {devInfoAnswer}')
            newDevInfo = self.__getNewDeviceInfo(devInfoAnswer[0])
            if newDevInfo == None:
                self.__log('There aren\'t appropriate firmware files')
                return
            self.__newDevInfo = newDevInfo
            self.__startUpload()
        else:
            self.__log('Already updating')


    def __processStartUpload(self, packet: bytes) -> None:
        '''
        Process a start upload answer from mcu
        '''
        if len(packet) != UNPACK_START_UPLOAD[1]:
            self.__log('Received wrong start upload structure')
        startAnswer = struct.unpack(UNPACK_START_UPLOAD[0], packet)
        self.__log(f'Received start upload answer: status={startAnswer[1]}')
        if startAnswer[1] == UpdaterErrors.success:
            self.__isUpdating = True
            self.__sendFirmwarePacket(0)
        else:
            pass #TODO handling errors


    def __processFwPacket(self, packet: bytes) -> None:
        '''
        Process a fw packet answer from mcu
        '''        
        if len(packet) != UNPACK_FW_PACKET[1]:
            self.__log('Received wrong fw packet structure')
        fwPacketAnswer = struct.unpack(UNPACK_FW_PACKET[0], packet)
        self.__log(f'Received firmware packet answer: status={fwPacketAnswer[1]}')
        if fwPacketAnswer[1] == UpdaterErrors.success:
            if self.__fwInfo.size > 0:
                self.__sendFirmwarePacket(self.__fwInfo.packetNum)
            else:
                self.__finishUpload()
        elif fwPacketAnswer[1] == UpdaterErrors.wrontPageNumError:
            self.__sendFirmwarePacket(fwPacketAnswer[2])
        else:
            pass #TODO handling errors


    def __processFinishUpload(self, packet: bytes) -> None:
        '''
        Process a finish upload answer from mcu
        '''
        if len(packet) != UNPACK_FINISH_UPLOAD[1]:
            self.__log('Received wrong finish upload structure')
        finishAnswer = struct.unpack(UNPACK_FINISH_UPLOAD[0], packet)
        self.__log(f'Received finish upload answer: status={finishAnswer[1]}')
        if finishAnswer[1] == UpdaterErrors.success:
            self.__mcuSystemReset()
        else:
            pass #TODO handling errors


    def deviceInfoRequest(self) -> None:
        '''
        Request for a device info
        '''
        self.__log('Request for a device info')
        self.__appCallback(struct.pack(PACK_DEVICE_INFO, UPDATER_COMMAND, UpdaterCommands.deviceInfo))


    def __startUpload(self) -> None:
        '''
        Start upload request to mcu
        '''
        fw = open(self.__newDevInfo[0], 'rb')
        self.__fwInfo = FwInfo(fw.read(), 0, 0, self.__newDevInfo[1].FwPacketSize)
        fw.close()
        self.__fwInfo.size = len(self.__fwInfo.fw)
        # self.__newDevInfo = tuple((self.__newDevInfo[0], self.__newDevInfo[1]._replace(FwSize = self.__fwInfo.size)))
        self.__log(f'Send start upload packet: __newDevInfo={self.__newDevInfo[1]}')
        self.__appCallback(struct.pack(PACK_START_UPLOAD, UPDATER_COMMAND, UpdaterCommands.startUpload, *self.__newDevInfo[1], self.__fwInfo.size))


    def __sendFirmwarePacket(self, packetNum: int) -> None:
        '''
        Calculate an offset and send firmware packet
        '''
        dataOffset = packetNum * self.__fwInfo.packetSize
        packetSize = self.__fwInfo.packetSize if self.__fwInfo.size > self.__fwInfo.packetSize else self.__fwInfo.size
        self.__fwInfo.size -= packetSize
        if self.__fwInfo.size < 0:
            self.__fwInfo.size = 0
        self.__log(f'Send firmware packet: packetNum={packetNum}, packetSize={self.__fwInfo.packetSize}, dataOffset={dataOffset}')
        packet = struct.pack(PACK_FW_PACKET, UPDATER_COMMAND, UpdaterCommands.fwPacket, packetNum, self.__fwInfo.packetSize, dataOffset)
        if packetSize < self.__fwInfo.packetSize:
            addition = bytes((0xFF,)) * (self.__fwInfo.packetSize - packetSize) # the last packet must be extended with 0xFF-s      
            self.__appCallback(packet + self.__fwInfo.fw[dataOffset:dataOffset+packetSize] + addition)
        else:
            self.__appCallback(packet + self.__fwInfo.fw[dataOffset:dataOffset+packetSize])

        self.__fwInfo.packetNum = packetNum + 1


    def __finishUpload(self) -> None:
        '''
        Calculate a whole firmware crc and send a finish upload command
        '''
        fwCrc = self.__calcCrc(self.__fwInfo.fw)
        self.__log(f'Send finish upload packet: firmwareCrc={fwCrc}')
        self.__appCallback(struct.pack(PACK_FINISH_UPLOAD, UPDATER_COMMAND, UpdaterCommands.finishUpload, len(self.__fwInfo.fw), fwCrc))


    def __mcuSystemReset(self) -> None:
        '''
        Send a system reset command to mcu
        '''
        self.__log('Send a system reset request')
        self.__appCallback(struct.pack(PACK_SYSTEM_RESET, UPDATER_COMMAND, UpdaterCommands.systemReset))


    def __searchFirmwareFiles(self, fwDir: str) -> None:
        '''
        Search for firmware bin files in a passed directory
        '''
        self.__fwDict.clear()
        if not isinstance(fwDir, str):
            self.__log('Invalid directory name')
            return
        if not os.path.exists(fwDir):
            self.__log('Directory is not exist')
            return
        
        fwList = []
        for fileName in os.listdir(fwDir):
            fullName = os.path.join(fwDir, fileName)
            if not os.path.isfile(fullName):
                continue
            if '.bin' in fileName:
                fwList.append(fullName)

        if len(fwList) == 0:
            self.__log('There aren\'t bin files in a firmware directory')
            return
        
        try:
            for name in fwList:
                fw = open(name, 'rb')
                data = fw.read()
                fw.close()
                if not DEVICE_INFO_TAG in data:
                    continue

                devInfoIndex = data.index(DEVICE_INFO_TAG) + len(DEVICE_INFO_TAG)
                devInfo = DeviceInfo._make(struct.unpack(UNPACK_BIN_TAG[0], data[devInfoIndex:devInfoIndex+UNPACK_BIN_TAG[1]]))
                self.__fwDict[name] = devInfo
        except:
            self.__log('Error parsing device info')


    def __getNewDeviceInfo(self, deviceId: int) -> tuple:
        '''
        Search for a new firmware in __fwDict
        ret: tup(absPath, deviceInfo)
        '''
        if len(self.__fwDict) == 0:
            return None
        
        devInfoList = [devInfo for devInfo in self.__fwDict.values() if devInfo[2] == deviceId]
        if len(devInfoList) == 0:
            return None

        dct = {k: v for k, v in self.__fwDict.items() if v[2] == deviceId}
        if len(dct) > 0:
            return {k: v for k, v in sorted(self.__fwDict.items(), key=lambda item: (item[1][4], item[1][3]))}.popitem()
    
        # from operator import itemgetter
        # return(sorted(devInfoList, key=itemgetter(4, 3))[-1])


    def __log(self, info: str) -> None:
        if not isinstance(info, str):
            return
        print(info)
        

if __name__ == '__main__':
    updater = Updater( os.path.join( os.path.dirname(os.path.realpath(__file__)), 'firmware' ), None, None )
