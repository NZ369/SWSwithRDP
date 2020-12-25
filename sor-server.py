
import sys
import getopt
import os.path
import pickle
import threading
import re
from socket import *
from select import *
import time
from datetime import datetime

'''
CSC 361 WINTER 2020
/* Assignment #3 */
/* Student name: Yuying Zhang (Nina) */
/* Student #: V00924070 
'''

clientAddress = ()
serverIP = 'h2'
serverPort = 8888
bufferSize = 4096
payloadLength = 1024

SeqNum = 0
Length = 0
Acks = 1
Window = 4096
responseMessage = ''

soc = socket(AF_INET, SOCK_DGRAM)


def inputArguments(inputArgs):
    global soc, serverIP, serverPort, bufferSize, payloadLength, Window
    serverIP = inputArgs[1]
    serverPort = int(inputArgs[2])
    bufferSize = int(inputArgs[3])
    payloadLength = int(inputArgs[4])
    soc.bind((serverIP, serverPort))
    Window = bufferSize


def sendTo(rdpContent, httpContent, address):
    msg = rdpContent[0] + '\r\nSequence: ' + str(rdpContent[1]) + '\r\nLength: ' + \
        str(rdpContent[2]) + '\r\nAcknowledgment: ' + str(rdpContent[3]) + \
        '\r\nWindow: ' + str(rdpContent[4]) + '\r\n'
    message = [msg, httpContent]
    message = pickle.dumps(message)
    soc.sendto(message, address)


def recvWith():
    message, address = soc.recvfrom(bufferSize)
    message = pickle.loads(message)

    t = []
    entry = re.split("\r\n", message)
    for e in entry:
        al = re.split(": ", e)
        if len(al) == 2:
            t.append(al[1])
        elif al[0] != '':
            t.append(al[0])

    t[1] = int(t[1])
    t[2] = int(t[2])
    t[3] = int(t[3])
    t[4] = int(t[4])

    #['SYN|DAT|ACK', '0', '48', '-1', '4096', 'GET /sws.py HTTP/1.0', 'keep-alive']
    return (t, address)


class messagePackets():
    storage = []


class fileReader():
    storage = []
    header = ''
    firstPacket = True
    packetNumber = 0
    segmentSize = 982

    def readSegment(self, file_object):
        while True:
            if self.firstPacket:
                self.segmentSize = payloadLength - utf8len(self.header)
                self.firstPacket = False
            else:
                self.segmentSize = payloadLength
            data = file_object.read(self.segmentSize)
            if not data:
                break
            yield data

    def reading(self, fileName):
        with open(fileName, 'r') as f:
            for piece in self.readSegment(f):
                self.storage.append(piece)
        self.packetNumber = len(self.storage)


def createDataPackets(readFile, header):
    packetStorage = fileReader()
    packetStorage.header = header
    packetStorage.storage = []
    packetStorage.reading(readFile)
    return packetStorage


def createPackets(path, connection):
    global clientAddress, responseMessage

    path = os.getcwd()+path
    if (os.path.isfile(path)):
        headerMsg = '\r\nHTTP/1.0 200 OK\r\nConnection: ' + \
            connection+'\r\n'
        packetStorage = createDataPackets(path, headerMsg)
        packetStorage.storage[0] = headerMsg + packetStorage.storage[0]
        responseMessage = 'HTTP/1.0 200 OK'
        return packetStorage
    else:
        packetStorage = messagePackets()
        msg = '\r\nHTTP/1.0 404 Not Found\r\nConnection: ' + \
            connection+'\r\n'
        packetStorage.storage.append(msg)
        packetStorage.storage.append('No data')
        responseMessage = 'HTTP/1.0 404 Not Found'
        return packetStorage


def utf8len(s):
    return len(s.encode('utf-8'))


def transferOperator(message, packetStorage):
    global clientAddress, SeqNum, Length, Acks, Window
    currPacket = 0
    packetsAcked = []

    # Sends first packet
    packetsAcked.append(message)
    Acks += message[2]
    Length = utf8len(packetStorage.storage[currPacket])
    rdpHeader = ['ACK|SYN|DAT', SeqNum, Length, Acks, Window]
    sendTo(rdpHeader, packetStorage.storage[currPacket], clientAddress)

    while True:

        currPacket = len(packetsAcked)

        try:
            data, address = recvWith()
        except:
            continue

        if len(packetsAcked) == 1 and data[0] == 'SYN|DAT|ACK':
            Length = payloadLength
            currPacket = 0
            rdpHeader = ['ACK|SYN|DAT', SeqNum, Length, Acks, Window]
            sendTo(rdpHeader, packetStorage.storage[currPacket], clientAddress)

        elif data[0] == 'ACK' and packetStorage.storage[1] == 'No data':
            SeqNum = data[3]
            Length = 0
            rdpHeader = ['FIN|ACK', SeqNum, Length, Acks, Window]
            sendTo(rdpHeader, '', clientAddress)

        elif data[4] >= payloadLength and data[0] == 'ACK':
            if data not in packetsAcked:
                packetsAcked.append(data)
            else:
                currPacket -= 1

            if currPacket < packetStorage.packetNumber:
                SeqNum = data[3]
                Length = utf8len(packetStorage.storage[currPacket])
                rdpHeader = ['ACK|DAT', SeqNum, Length, Acks, Window]
                sendTo(
                    rdpHeader, packetStorage.storage[currPacket], clientAddress)

            else:
                SeqNum = data[3]
                Length = 0
                rdpHeader = ['FIN|ACK', SeqNum, Length, Acks, Window]
                sendTo(rdpHeader, '', clientAddress)

        elif data[0] == 'FIN|ACK':
            packetsAcked.append(data)
            SeqNum = data[3]
            Acks += 1
            Length = 0
            rdpHeader = ['ACK', SeqNum, Length, Acks, Window]
            sendTo(rdpHeader, '', clientAddress)
            sendTo(rdpHeader, '', clientAddress)
            sendTo(rdpHeader, '', clientAddress)
            sendTo(rdpHeader, '', clientAddress)
            sendTo(rdpHeader, '', clientAddress)
            SeqNum += 1
            break


def connectionAlive():
    global Acks
    message, address = recvWith()
    Acks = message[3] + 2
    processRequest(message, address)


def connectionReset():
    global SeqNum, Length, Acks, Window, bufferSize
    SeqNum = 0
    Length = 0
    Acks = 1
    Window = bufferSize


def processRequest(message, address):
    global Length, clientAddress
    clientAddress = address

    if message[0] == 'SYN|DAT|ACK':
        Length = message[2]
    else:
        badRequest()

    httpRequest = message[5]
    lines = httpRequest.lower()
    (request,  # get
     path,     # /readFile
     version  # http/1.0
     ) = lines.split(' ')

    if request != 'get' or version != 'http/1.0':
        badRequest()
    elif message[6] == 'keep-alive' or message[6] == 'close':
        packetStorage = createPackets(path, message[6])
        printConnection(message)
        try:
            transferOperator(message, packetStorage)
        except:
            os._exit(0)
        if message[6] == 'keep-alive':
            connectionAlive()
            return
        else:
            return


def badRequest():
    msg = "\nHTTP/1.0 400 Bad Request\n"
    print(msg)
    os._exit(0)


def printConnection(message):
    global responseMessage
    currTime = datetime.now()
    timeStamp = currTime.strftime("%a %b %d %H:%M:%S PST 2020")
    msg = timeStamp + ": " + \
        str(clientAddress[0]) + ":" + str(clientAddress[1]) + \
        " " + str(message[5]) + "; " + responseMessage
    print(msg)


def serveForever():

    while True:
        message, address = recvWith()
        try:
            processRequest(message, address)
        except:
            break
        connectionReset()


# Main: Starts the server
if __name__ == '__main__':
    inputArguments(sys.argv)
    serveForever()
