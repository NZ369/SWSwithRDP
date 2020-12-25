#!/usr/bin/python
import sys
import getopt
import os.path
import pickle
import random
import time
import re
import socket
import select
from socket import *
from datetime import datetime
from threading import Timer

'''
CSC 361 WINTER 2020
/* Assignment #3 */
/* Student name: Yuying Zhang (Nina) */
/* Student #: V00924070 
'''

serverIP = 'h2'
serverPort = 8888
bufferSize = 4096
payloadLength = 1024
requestFiles = []
requestIdx = 0

running = True
nextSeq = 0

SeqNum = 0
Length = 0
Acks = -1
Window = 4096
lossOccured = False

soc = socket(AF_INET, SOCK_DGRAM)
soc.settimeout(0.3)


def inputArguments(inputArgs):
    global running, lossOccured, Window, serverIP, serverPort, bufferSize, payloadLength, requestFiles

    if len(inputArgs) % 2 != 0:
        try:
            lossOccured = False
            serverIP = inputArgs[1]
            serverPort = int(inputArgs[2])
            bufferSize = int(inputArgs[3])
            Window = bufferSize
            payloadLength = int(inputArgs[4])
            for i in range(5, len(inputArgs)):
                requestFiles.append(inputArgs[i])
        except:
            print('<< Error: Missing input arguments >>')
            running = False
            return
    else:
        print('<< Error: Missing input arguments >>')
        running = False
        return


def utf8len(s):
    return len(s.encode('utf-8'))


def sendTo(rdpContent, httpContent, address):
    msg = rdpContent[0] + '\r\nSequence: ' + str(rdpContent[1]) + '\r\nLength: ' + \
        str(rdpContent[2]) + '\r\nAcknowledgment: ' + str(rdpContent[3]) + \
        '\r\nWindow: ' + str(rdpContent[4]) + '\r\n'
    message = msg + httpContent
    message = pickle.dumps(message)
    soc.sendto(message, address)


def recvWith():
    message, address = soc.recvfrom(bufferSize)
    message = pickle.loads(message)

    t = []
    entry = re.split("\r\n", message[0])
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
    t.append(message[1])

    return (t, address)


def printSend(header):
    currTime = datetime.now()
    timeStamp = currTime.strftime("%a %b %d %H:%M:%S PST %Y")
    msg = timeStamp + ': '+'Send; '+header[0]+'; Sequence: '+str(SeqNum)+'; Length: ' + \
        str(Length)+'; Acknowledgment: ' + str(Acks) + '; Window: ' + \
        str(Window)
    print(msg)


def writeData(data):
    with open(requestFiles[requestIdx+1], '+a') as f:
        f.write(data)
        f.close


def printRecieve(header):
    currTime = datetime.now()
    timeStamp = currTime.strftime("%a %b %d %H:%M:%S PST %Y")
    msg = timeStamp + ': '+'Receive; '+header[0]+'; Sequence: '+str(header[1])+'; Length: ' + \
        str(header[2])+'; Acknowledgment: ' + str(header[3]) + '; Window: ' + \
        str(header[4])
    print(msg)


def serveForever():
    global serverIP, serverPort, requestIdx, nextSeq, requestFiles, SeqNum, Length, Acks, Window, running, lossOccured
    serverAddr = (serverIP, serverPort)
    establishedConnection = False
    packetsReceived = []
    firstPacket = True
    verified = []
    buffer = 0
    lastRead = 0
    serverFinished = False
    noFile = False
    currWindow = (bufferSize / payloadLength) - 2

    pos = requestIdx + 2
    if pos != len(requestFiles):
        connType = 'keep-alive'
    else:
        connType = 'close'

    while establishedConnection == False:

        requests = len(requestFiles)-1
        if requestIdx < requests:
            httpHeader = '\r\nGET /' + requestFiles[requestIdx] + \
                ' HTTP/1.0\r\nConnection: '+connType + '\r\n'
        Length = utf8len(httpHeader)
        rdpHeader = ['SYN|DAT|ACK', SeqNum, Length, Acks, Window]
        sendTo(rdpHeader, httpHeader, serverAddr)
        if lossOccured == False:
            printSend(rdpHeader)
        establishedConnection = True

    while True:

        try:
            data, address = recvWith()
            if firstPacket == True and data[0] == 'ACK':
                continue
            lossOccured = False
            printRecieve(data)
        except timeout:
            lossOccured = True
            #print('LOSS OCCURED')
            if len(packetsReceived) == 0:
                return
            data = packetsReceived[-1]

        if data[0] == 'ACK|DAT' or data[0] == 'ACK|SYN|DAT':

            responseMessage = data[5][:50]
            if '404 Not Found' in responseMessage:
                noFile = True

            if firstPacket:
                i = 33+len(connType)
                data[5] = data[5][i:]
                firstPacket = False

            if data[1] == nextSeq and data[5] not in verified:
                packetsReceived.append(data)
                buffer += 1
                nextSeq = data[1] + data[2]
            else:
                lossOccured = True
                data = packetsReceived[-1]

            if buffer > currWindow:
                for idx in range(lastRead, len(packetsReceived)):
                    writeData(packetsReceived[idx][5])
                    lastRead += 1
                    verified.append(packetsReceived[idx][5])
                Window = bufferSize
                buffer = 0

            Acks = data[1]+data[2]
            SeqNum = data[3]
            Length = 0
            if lossOccured == False:
                Window -= data[2]
            rdpHeader = ['ACK', SeqNum, Length, Acks, Window]
            sendTo(rdpHeader, '', serverAddr)
            if lossOccured == False:
                printSend(rdpHeader)

        elif data[0] == 'FIN|ACK':

            if noFile == False:
                if lastRead < len(packetsReceived):
                    for idx in range(lastRead, len(packetsReceived)):
                        writeData(packetsReceived[idx][5])
                        lastRead += 1
                        verified.append(packetsReceived[idx][5])
                    Window = bufferSize

            packetsReceived.append(data)
            buffer += 1
            Acks = data[1]+1
            SeqNum = data[3]
            Window = bufferSize
            Length = 0
            rdpHeader = ['FIN|ACK', SeqNum, Length, Acks, Window]
            sendTo(rdpHeader, '', serverAddr)
            serverFinished = True
            printSend(rdpHeader)

        elif data[0] == 'ACK':
            if serverFinished == False:
                continue
            pos = requestIdx + 2
            if pos == len(requestFiles):
                soc.close()
                running = False
                break
            else:
                requestIdx += 2
                Acks += 1
                SeqNum = data[3]
                nextSeq = data[1] + 1
                return


if __name__ == '__main__':
    inputArguments(sys.argv)
    start = time.perf_counter()
    while running:
        serveForever()
    end = time.perf_counter()
    soc.close()
    diff = end-start
    print('Runtime in seconds: ', diff)
    os._exit(0)
