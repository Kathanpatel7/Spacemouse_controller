#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jun  2 02:38:10 2024
@author: kathanpatel
"""

import socket
import json

def connectETController(ip, port=8055):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((ip, port))
        return True, sock
    except Exception as e:
        sock.close()
        return False, None

def disconnectETController(sock):
    if sock:
        sock.close()

def sendCMD(sock, cmd, params=None, id=1):
    if not params:
        params = []
    else:
        params = json.dumps(params)
    sendStr = '{{"method":"{0}","params":{1},"jsonrpc":"2.0","id":{2}}}\n'.format(cmd, params, id)
    try:
        sock.sendall(sendStr.encode('utf-8'))
        ret = sock.recv(1024)
        jdata = json.loads(ret.decode('utf-8'))
        if 'result' in jdata:
            return True, json.loads(jdata['result']), jdata['id']
        elif 'error' in jdata:
            return False, jdata['error'], jdata['id']
        else:
            return False, None, None
    except Exception as e:
        return False, None, None

def set_v(data, robot_speed, omega):
    global current_pose
    
    for i in range(6):
        if data[i] == 1:
            current_pose[i] = robot_speed
        elif data[i] == -1:
            current_pose[i] = -robot_speed
        else:
            current_pose[i] = 0        
    
    return current_pose

def main():
    global robot_speed
    global omega
    global current_pose

    robot_speed = 10
    omega = 10
    current_pose = [0] * 8  # Initialize current_pose array
    final_matrix = [0] * 6

    robot_ip = '192.168.1.200'
    conSuc, robot_sock = connectETController(robot_ip)
    if not conSuc:
        print('Failed to connect to the robot.')
        return

    sendCMD(robot_sock, 'set_servo_status', {'status': 1})
    # Set the loop mode to single loop
    suc, result, id = sendCMD(robot_sock, 'setCycleMode', {'cycle_mode': 2})
    suc, result, id = sendCMD(robot_sock, 'setCurrentCoord', {'coord_mode': 1})

    if conSuc:
        suc, result_pose, id = sendCMD(robot_sock, 'get_tcp_pose', {'coordinate_num': 2, 'tool_num': 4})
        print(result_pose)
        # current_pose = result_pose
        suc, result, id = sendCMD(robot_sock, 'setSysVarV', {'addr': 1, 'pose': current_pose})

    # suc, result , id = sendCMD(robot_sock, "run")

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    host = '127.0.0.1'
    port = 12345
    client_socket.connect((host, port))

    try:
        while True:
            data = client_socket.recv(1024)
            if not data:
                decoded_data = [0] * 8
            else:
                decoded_data = json.loads(data.decode('utf-8'))

            for i in range(6):
                if decoded_data[i] > 50:
                    decoded_data[i] = 1
                elif decoded_data[i] < -50:
                    decoded_data[i] = -1
                else:
                    decoded_data[i] = 0
            
            if decoded_data != [0] * 8:
                if decoded_data[6] == 1 and robot_speed > 0 and omega > 0:
                    robot_speed -= 5
                    omega -= 2
                    print('Speed Decreased to:', robot_speed)
                elif decoded_data[7] == 1 and robot_speed < 200 and omega < 150:
                    robot_speed += 5
                    omega += 2
                    print('Speed increased to:', robot_speed)
                else:
                    temp = set_v(decoded_data, robot_speed, omega)
                    final_matrix = temp[:6]
                    final_matrix[0] = - final_matrix[0]
                    final_matrix[2] = - final_matrix[2]
                    final_matrix[3] = - final_matrix[3]
                    #final_matrix[4] = - final_matrix[4 ]
                    final_matrix[5] = - final_matrix[5]
                    if len(decoded_data) == 8:
                        print(f'Received: {final_matrix}')
                        suc, result, id = sendCMD(robot_sock, 'moveBySpeedl', {'v': final_matrix, 'acc': 50, 'arot': 10, 't': 0.1})
                        print(suc, result, id)
            else:
                #suc, result, id = sendCMD(robot_sock, "stopl", {"acc": 190})
                decoded_data = [0] * 8
                
    except KeyboardInterrupt:
        print('Client stopped.')
    finally:
        client_socket.close()
        disconnectETController(robot_sock)

if __name__ == '__main__':
    main()
