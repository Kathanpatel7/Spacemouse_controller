#!/usr/bin/env python
# coding=utf-8
import usb.core
import usb.util
import logging
from time import gmtime, strftime
import signal
import threading
import socket

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class dev_3d(object):
    def __init__(self):
        self.dev = None
        self.ep_in = None
        self.ep_out = None
        self.reattach = False
        self.data = [0, 0, 0, 0, 0, 0, 0, 0]
        self.id = -1

def dealdata(data_new, data_rec):
    if data_new:
        logging.info(f"Received data: {data_new}")

    if data_new[0] == 1:
        # translation packet
        data_rec[0] = data_new[1] + (data_new[2]*256)
        
        data_rec[1] = data_new[3] + (data_new[4]*256)
        
        data_rec[2] = data_new[5] + (data_new[6]*256)
        

        if data_new[2] > 127:
            data_rec[0] -= 65536
        if data_new[4] > 127:
            data_rec[1] -= 65536
        if data_new[6] > 127:
            data_rec[2] -= 65536
        
        lx = data_rec[0]
        ly = data_rec[1]
        lz = data_rec[2]
        rx = data_rec[3]
        ry = data_rec[4]
        rz = data_rec[5]

    if data_new[0] == 2:
        # rotation packet
        data_rec[3] = data_new[1] + (data_new[2]*256)
        data_rec[4] = data_new[3] + (data_new[4]*256)
        data_rec[5] = data_new[5] + (data_new[6]*256)

        if data_new[2] > 127:
            data_rec[3] -= 65536
        if data_new[4] > 127:
            data_rec[4] -= 65536
        if data_new[6] > 127:
            data_rec[5] -= 65536
        
        lx = data_rec[0]
        ly = data_rec[1]
        lz = data_rec[2]
        rx = data_rec[3]
        ry = data_rec[4]
        rz = data_rec[5]

    if data_new[0] == 3:
        data_rec[6] = data_new[1] & 0x01
        data_rec[7] = (data_new[1] & 0x02) >> 1
        
        lx = data_rec[0]
        ly = data_rec[1]
        lz = data_rec[2]
        rx = data_rec[3]
        ry = data_rec[4]
        rz = data_rec[5]


    # Apply the logic for data_rec values
    for i in range(6):
        if data_rec[i] > 50:
            data_rec[i] = 1
        elif data_rec[i] < -50:
            data_rec[i] = -1
        else:
            data_rec[i] = 0
    kkp = [lx,ly,lz,rx,ry,rz,data_rec[6],data_rec[7]]
    # Return the processed data
    return kkp

def sigint_handler(signal, frame):
    global run
    run = False
    logging.info('Key interrupt')

def read_task(dev, client_socket):
    global run
    while run:
        try:
            data = dev.dev.read(dev.ep_in.bEndpointAddress, dev.ep_in.wMaxPacketSize, timeout=2000)
            if data:
                dev.data = dealdata(data, dev.data)
                # Send the processed data to the client
                client_socket.send(str(dev.data).encode('utf-8'))
            else:
                logging.info("No data received from the device.")
        except usb.core.USBError as e:
            logging.error(f"USB error: {e}")
        except Exception as e:
            logging.error(f"Read failed: {e}")

    usb.util.dispose_resources(dev.dev)

    if dev.reattach:
        dev.dev.attach_kernel_driver(0)


if __name__ == '__main__':
    global run
    global lx
    global ly
    global lz
    global rx
    global ry
    global rz
    
    run = True

    signal.signal(signal.SIGINT, sigint_handler)

    # Look for SpaceNavigator
    dev_it = usb.core.find(find_all=True, idVendor=0x256f, idProduct=0xc635)
    dev_list = []

    if dev_it is None:
        logging.error('SpaceNavigator not found')
        exit(1)
    else:
        logging.info('SpaceNavigator found')

    threads = []

    # Create a socket object
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Bind the socket to a public host and a well-known port
    host = '127.0.0.1'
    port = 12345
    server_socket.bind((host, port))

    # Listen for incoming connections (queue up to 5 requests)
    server_socket.listen(5)
    print(f"Server listening on {host}:{port}")

    # Accept a client connection
    client_socket, addr = server_socket.accept()
    print(f"Got a connection from {addr}")

    for i in dev_it:
        dev_list.append(dev_3d())
        index = len(dev_list) - 1
        dev_list[index].dev = i

        dev_list[index].reattach = False
        if dev_list[index].dev.is_kernel_driver_active(0):
            dev_list[index].reattach = True
            dev_list[index].dev.detach_kernel_driver(0)
        
        try:
            dev_list[index].ep_in = dev_list[index].dev[0][(0, 0)][0]
            dev_list[index].ep_out = dev_list[index].dev[0][(0, 0)][1]
        except Exception as e:
            logging.error(f"Endpoint setup error: {e}")
            continue

        dev_list[index].id = index

        t = threading.Thread(target=read_task, args=(dev_list[index], client_socket))
        threads.append(t)

    logging.info(f"Important! Exit by pressing Ctrl-C, total {len(dev_list)} device(s)")

    for t in threads:
        t.setDaemon(True)
        t.start()

    while True:
        try:
            pass
        except KeyboardInterrupt:
            break

    for t in threads:
        t.join()
    
    # Close the client socket
    client_socket.close()
    print("Client socket closed.")
    
    # Close the server socket
    server_socket.close()
    print("Server socket closed.")
