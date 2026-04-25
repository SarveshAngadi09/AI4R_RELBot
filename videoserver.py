# This is server code to send video frames over UDP
import sys
import cv2, socket
import numpy as np
import time
import base64
import json

# Constants
BUFF_SIZE = 65535
CHUNK_SIZE = 65535        # Set the chunk size to 9216 bytes to be compliant with MacOS
HOST_IP = '0.0.0.0'
PORT = 9999
WIDTH = 640               # It should not be necessary to change these. The dimensions
HEIGHT = 480              # can be changed as parameter of the cam2image node.
QUALITY_FACTOR = 80
FPS = 30.0

# Setting up Server connection
server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFF_SIZE)
host_name = socket.gethostname()
print(HOST_IP)
socket_address = (HOST_IP, PORT)
server_socket.bind(socket_address)
print('Listening at:', socket_address)

# Video Capture                                # If you have issues with getting a camera feed
vid = cv2.VideoCapture(0)                      # on Windows, comment this line
# vid = cv2.VideoCapture(0, cv2.CAP_DSHOW)     # and uncomment this line.
vid.set(cv2.CAP_PROP_FPS, FPS)
fps, start_time, frames_to_count, count = (0, 0, 20, 0)
do_cap = True
width = WIDTH
height = HEIGHT

while do_cap:
    msg, client_addr = server_socket.recvfrom(BUFF_SIZE)
    print('Got connection from ', client_addr)
    # Process frame size
    if msg == b'Hello':
        print("Connection established")
        dec_msg = "Hello"
    else:
        dec_msg = base64.b64decode(msg)
    try:
        json_object = json.loads(dec_msg)
        width = json_object["width"]
        height = json_object["height"]
    except ValueError:  # includes simplejson.decoder.JSONDecodeError
        print('Decoding JSON has failed. Using default dimensions')

    # Limit size to prevent buffer issues
    if width > WIDTH:
        width = WIDTH
    if height > HEIGHT:
        height = HEIGHT

    vid.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    vid.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    print(f"Capture dimension set to {width}x{height}")
    failure_counter = 0

    while vid.isOpened():
        _, frame = vid.read()
        if type(frame) == type(None):
            continue
        else:
            encoded, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, QUALITY_FACTOR])
            # encoded, buffer = cv2.imencode(".png", frame)
        message = base64.b64encode(buffer)

        
        # Split the message into chunks of size CHUNK_SIZE
        chunks = [message[i:i + CHUNK_SIZE] for i in range(0, len(message), CHUNK_SIZE)]
        # print(len(chunks))
        for chunk in chunks:
            try:
                server_socket.sendto(chunk, client_addr)
            except OSError:
                print("Message not sent because message size: " + str(sys.getsizeof(message)) + " bigger than buffer size: " + str(BUFF_SIZE))
                failure_counter+=1
        # Send end-of-frame marker
        server_socket.sendto(b'EOF', client_addr)

        frame = cv2.putText(frame, 'FPS: ' + str(fps), (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        cv2.imshow('TRANSMITTING VIDEO', frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or failure_counter >= 60:
            print("Shutting down video stream due to instability") if failure_counter >= 60 else print("Shut down by user")
            server_socket.sendto(b'EOS', client_addr)  # Sends an end of stream signal to the client
            server_socket.close()
            do_cap = False
            break
        if count == frames_to_count:
            try:
                fps = round(frames_to_count / (time.time() - start_time))
                start_time = time.time()
                count = 0
            except:
                pass
        count += 1

print("Shutting down, releasing video capture...")
vid.release()
cv2.destroyAllWindows()