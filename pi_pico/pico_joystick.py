# Author: Steffen Rogne
# Brief:  Test software, read canbus with filter. Read Analog Joystick, send joystick values over can.
# 
#==================================================
#
#

import board
import analogio
import busio
from digitalio import DigitalInOut
from adafruit_mcp2515.canio import Message
from adafruit_mcp2515 import MCP2515 as CAN
import asyncio
import struct
import math
import time

##RS485 PINS
# MISO - Pin 21 (GP16)
# CS - Pin 22 (GP17)
# SCK - Pin 24 (GP18)
# MOSI - Pin 25 (GP19)
# LED Out - Pin 34(GP 28)
# 3v3 Out - Pin 36
# GND - Pin 38

cs = DigitalInOut(board.GP17)
cs.switch_to_output()
spi = busio.SPI(board.GP18, board.GP19, board.GP16)
yaxi = analogio.AnalogIn(board.GP26_A0)
xaxi = analogio.AnalogIn(board.GP27_A1)
can_bus = CAN(spi, cs)
joy_res = 12

##To use can filters, 2 filters can be used
class Match:
    def __init__(self,address,mask,extended: bool):
        self.address = address
        self.mask = mask
        self.extended = extended

##Send joystick values, adapted to receiving software.
async def send_joystick_position(x, y):
    id = 0x18fdd6F1 ##Modify ID
    
    #x = ((x/65536.0) * 2048) - 1024 ##Tested for 1024
    #y = ((y/65536.0) * 2048) - 1024 ##Tested for 1024
    #x = ((x/65536.0) * 8192) - 4096 ##Tested for 4096
    #y = ((y/65536.0) * 8192) - 4096 ##Tested for 4096
    
    x = ((x/2**16)*(2**(joy_res+1)))-(2**joy_res) ##Works pretty good 12bit 4096
    y = ((y/2**16)*(2**(joy_res+1)))-(2**joy_res) ##Works pretty good 12bit 4096

    data = [0x01, 0x00, 0x01, 0x00, 0xff, 0x00, 0x00, 0x1f]
    if joy_res == 12:
        data[0] = 0x03
        data[2] = 0x03

    elif joy_res == 10:   
        data[0] = 0x03
        data[2] = 0x00
    else:
        data[0] = 0x00
        data[2] = 0x00

    if x < 0: data[0] = data[0] | 0x10
    if y < 0: data[2] = data[2] | 0x10

    tmp = int(abs(x)).to_bytes(2,'big', signed=False)
    data[0] = data[0] | ((tmp[0] << 6) & 0xC0)  # 10 bit ...
    data[0] = data[0] | (tmp[0] & 0x0c)         # 12 bit ...
    data[1] = tmp[1]                            #  8 bit...

    tmp = int(abs(y)).to_bytes(2,'big', signed=False)
    data[2] = data[2] | ((tmp[0] << 6) & 0xC0)
    data[2] = data[2] | (tmp[0] & 0x0c)
    data[3] = tmp[1]
    #print(bytes(data))  ##Debugging print
    #print(x,y)
    message = Message(id=id, data=bytes(data), extended=True)
    can_bus.send(message)
    await asyncio.sleep(0.1)    ##10hz

##Read the joystick values, making using the midle of 10 readings.
async def read_joystick_position():
    while True:
        x_list = []
        y_list = []
        for i in range(10):
            x_list.append(xaxi.value)
            y_list.append(yaxi.value)
        x_list.sort()
        y_list.sort()
        x = x_list[5]
        y = y_list[5]
        await send_joystick_position(x, y)

##Listening on bus for filtered messages.
async def listen_can(listener):
    while True:
        message_count = listener.in_waiting()
        for _i in range(message_count):
            msg = listener.receive()
            print("Message from: ", hex(msg.id))
            print(msg.data)

            #do something with the data
               
        await asyncio.sleep(0)

##Running main program, setup filters to subscribe
async def main():
    matches = [
           Match(0x777,0xFF,True),
           Match(0x666,0xFFF,True),
           ]
    with can_bus.listen(matches) as listener:
        task1 = asyncio.create_task(listen_can(listener))
        task2 = asyncio.create_task(read_joystick_position())
        await asyncio.gather(task1, task2)
try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("Program ended")