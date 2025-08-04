import cv2
import numpy as np
import math
import serial
import time
from dotenv import load_dotenv
import os

load_dotenv()

CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", 0))

SERIAL_PORT = os.getenv("SERIAL_PORT", "/dev/ttyACM0")  # fallback to /dev/ttyACM0

ser = serial.Serial(SERIAL_PORT, baudrate=9600, timeout=1)

READ_CAMERA_MAX_RETRIES = 5

read_camera_retry_count = 0
while read_camera_retry_count < READ_CAMERA_MAX_RETRIES:
    cap = cv2.VideoCapture(CAMERA_INDEX)
    if cap.isOpened():
        cap.set(3, 1280)
        cap.set(4, 720)
        break
    else:
        read_camera_retry_count += 1
        print(f"[Warning] Failed to open camera. Retrying ({read_camera_retry_count}/{READ_CAMERA_MAX_RETRIES})...")
        cap.release()
        time.sleep(1)

if read_camera_retry_count >= READ_CAMERA_MAX_RETRIES:
    print("[Error] Unable to open camera after multiple attempts. Exiting.")
    exit(1)

cap.set(3,1280)
cap.set(4,720)

path_lower = np.array([115,35,60]) #for blue ink
path_upper = np.array([133,255,255])

font = cv2.FONT_HERSHEY_COMPLEX
kernel = np.ones((5,5),np.uint8)

f_dist = 2*290

def lane_follow(a, b):
    largest = max(a, key = cv2.contourArea)
    x_2, y_2, w_2, h_2 = cv2.boundingRect(largest)
    cv2.rectangle(b, (x_2, y_2), (x_2 + w_2, y_2 + h_2), (0, 0, 255), 3)
    error = x_2 + (w_2/2) - w/2

    blackbox = cv2.minAreaRect(largest)
    (x_min, y_min), (w_min, h_min), ang = blackbox
    if ang > 45:
        ang = ang - 90
    if w_min < h_min and ang < 0:
        ang = 90 + ang
    if w_min > h_min and ang > 0:
        ang = ang - 90
    ang = int(ang)
    box = cv2.boxPoints(blackbox)
    box = box.astype(np.intp)

    if error != 0 and (abs(error)/f_dist) >= -1 and (abs(error)/f_dist) <= 1:
        error_angle = abs((180/math.pi)*math.asin(abs(error)/f_dist)/error)*error
    else:
        error_angle = 0

    tot_angle = ang + error_angle

    if tot_angle < -10:
        i = 'l'
        ser.write(i.encode())
        print('go left')
        left_text = 'Go left'
        cv2.putText(b, left_text, (5, 50), font, 2, (0, 0, 255), 2, cv2.LINE_AA)
        time.sleep(0.05)

    elif tot_angle > 10:
        i = 'r'
        ser.write(i.encode())
        print('go right')
        right_text = 'Go right'
        cv2.putText(b, right_text, (5, 50), font, 2, (0, 0, 255), 2, cv2.LINE_AA)
        time.sleep(0.05)

    else:
        i = 'f'
        ser.write(i.encode())
        print('go straight')
        straight_text = 'Go straight'
        cv2.putText(b, straight_text, (5, 50), font, 2, (0, 0, 255), 2, cv2.LINE_AA)
        time.sleep(0.175)

while True:
    read_camera_retry_count = 0
    ret, frame = cap.read()
    if not ret:
        read_camera_retry_count += 1
        print(f"[Warning] Camera read failed. Retrying ({read_camera_retry_count}/{READ_CAMERA_MAX_RETRIES})...")
        cap.release()
        time.sleep(1)
        cap = cv2.VideoCapture(CAMERA_INDEX)

        if read_camera_retry_count >= READ_CAMERA_MAX_RETRIES:
            print("[Error] Unable to access camera after multiple attempts. Exiting.")
            break
        continue

    (h, w) = frame.shape[:2]
    blur = cv2.GaussianBlur(frame,(5,5),cv2.BORDER_DEFAULT)
    hsvvid = cv2.cvtColor(blur, cv2.COLOR_BGR2HSV)

    path_mask = cv2.inRange(hsvvid, path_lower, path_upper)
    opening = cv2.morphologyEx(path_mask, cv2.MORPH_OPEN, kernel)
    erosion = cv2.erode(opening,kernel,iterations = 1)
    dilation = cv2.dilate(erosion,kernel,iterations = 5)
    path_contours, hierarchy = cv2.findContours(dilation, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if len(path_contours) > 0:
        lane_follow(path_contours, frame)
    else:
        i = 'r'
        ser.write(i.encode())
        print('looking for path')
        straight_text = 'looking for path'
        cv2.putText(frame, straight_text, (5, 50), font, 2, (0, 0, 255), 2, cv2.LINE_AA)
        time.sleep(0.05)

    cv2.imshow('path video', frame)
    key = cv2.waitKey(1)
    if key == 27: #press esc to exit
        break

cap.release()
cv2.destroyAllWindows()
