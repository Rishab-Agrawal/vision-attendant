import cv2
import numpy as np
from googleapiclient.discovery import build
from google.oauth2 import service_account
import mediapipe as mp
import math
import time
import os
from dotenv import load_dotenv

load_dotenv()

SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE")
SAMPLE_SPREADSHEET_ID = os.getenv("SAMPLE_SPREADSHEET_ID")

CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", 0))

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
creds = None
creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes = SCOPES)

service = build('sheets','v4',credentials = creds)
sheet = service.spreadsheets()

result = sheet.values().get(spreadsheetId=SAMPLE_SPREADSHEET_ID,range = "Sheet1!C2:E4").execute()
values = result.get('values', [])

red_list = values[0]
yellow_list = values[1]
green_list = values[2]

numofyes = red_list.count('yes') + yellow_list.count('yes') + green_list.count('yes')

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

font = cv2.FONT_HERSHEY_COMPLEX
kernel = np.ones((5,5),np.uint8)
f_dist = 800
rating_table = 0
breakvar = 0

order_text = 'Serving order'
assistance_text = 'Assisting...'
rating_text = 'Reading the rating... Thank you!'

path_lower = np.array([115,35,60]) #for blue ink
path_upper = np.array([133,255,255])

ynb_lower = np.array([10,120,150]) #for yellow notebook
ynb_upper = np.array([90,255,255])

rnb_lower = np.array([0,115,145]) #for red notebook
rnb_upper = np.array([9,255,255])

gnb_lower = np.array([35,75,115]) #for green notebook
gnb_upper = np.array([55,255,255])

def lane_follow(a, b):
    largest = max(a, key = cv2.contourArea)
    x_2, y_2, w_2, h_2 = cv2.boundingRect(largest)

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
        print('go left')
        left_text = 'Go left'
        cv2.putText(b, left_text, (5, 50), font, 2, (0, 0, 255), 2, cv2.LINE_AA)

    elif tot_angle > 10:
        print('go right')
        right_text = 'Go right'
        cv2.putText(b, right_text, (5, 50), font, 2, (0, 0, 255), 2, cv2.LINE_AA)

    else:
        print('go straight')
        straight_text = 'Go straight'
        cv2.putText(b, straight_text, (5, 50), font, 2, (0, 0, 255), 2, cv2.LINE_AA)

def table_function(c, colour_low, colour_up, table_colour_list, range_1, range_2, rating_table_number, d, e):
    global numofyes, breakvar, rating_table
    colour_mask = cv2.inRange(c, colour_low, colour_up)
    colour_contours, hierarchy = cv2.findContours(colour_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if len(colour_contours) > 0:
        largest_colour = max(colour_contours, key = cv2.contourArea)
        x_colour, y_colour, w_colour, h_colour = cv2.boundingRect(largest_colour)

        if w_colour*h_colour > 200000:

            if table_colour_list[0] == 'yes':
                while True:
                    print(order_text)
                    ret, frame = cap.read()
                    cv2.putText(frame, order_text, (5, 50), font, 2, (0, 0, 255), 2, cv2.LINE_AA)
                    cv2.imshow('path video', frame)
                    key = cv2.waitKey(1)
                    if key == 27: #press esc to exit
                        break
                response = sheet.values().update(spreadsheetId=SAMPLE_SPREADSHEET_ID, range=range_1, valueInputOption="USER_ENTERED", body={"values": [['no']]}).execute()
                numofyes = numofyes - 1

            if table_colour_list[1] == 'yes':
                while True:
                    print(assistance_text)
                    ret, frame = cap.read()
                    cv2.putText(frame, assistance_text, (5, 50), font, 2, (0, 0, 255), 2, cv2.LINE_AA)
                    cv2.imshow('path video', frame)
                    key = cv2.waitKey(1)
                    if key == 27: #press esc to exit
                        break
                response = sheet.values().update(spreadsheetId=SAMPLE_SPREADSHEET_ID, range=range_2, valueInputOption="USER_ENTERED", body={"values": [['no']]}).execute()
                numofyes = numofyes - 1

            if table_colour_list[2] == 'yes':
                rating_table = rating_table_number
                numofyes = numofyes - 1
                breakvar = 1

        elif len(d) > 0:
            lane_follow(d, e)

        else:
            print('no path detected')
            nopath_text = 'no path detected'
            cv2.putText(e, nopath_text, (5, 50), font, 2, (0, 0, 255), 2, cv2.LINE_AA)

    elif len(d) > 0:
        lane_follow(d, e)

    else:
        print('no path detected')
        nopath_text = 'no path detected'
        cv2.putText(e, nopath_text, (5, 50), font, 2, (0, 0, 255), 2, cv2.LINE_AA)

def table_colour_function(tblclr, f, g, h):
    if tblclr == 'red':
        return table_function(f, rnb_lower, rnb_upper, red_list, "Sheet1!C2", "Sheet1!D2", 1, g, h)
    elif tblclr == 'yellow':
        return table_function(f, ynb_lower, ynb_upper, yellow_list, "Sheet1!C3", "Sheet1!D3", 2, g, h)
    elif tblclr == 'green':
        return table_function(f, gnb_lower, gnb_upper, green_list, "Sheet1!C4", "Sheet1!D4", 3, g, h)

while True:
    print(breakvar)
    print(numofyes)

    ret, frame = cap.read()
    (h, w) = frame.shape[:2]
    blur = cv2.GaussianBlur(frame,(5,5),cv2.BORDER_DEFAULT)
    hsvvid = cv2.cvtColor(blur, cv2.COLOR_BGR2HSV)

    path_mask = cv2.inRange(hsvvid, path_lower, path_upper)
    opening = cv2.morphologyEx(path_mask, cv2.MORPH_OPEN, kernel)
    erosion = cv2.erode(opening,kernel,iterations = 3)
    dilation = cv2.dilate(erosion,kernel,iterations = 5)
    path_contours, hierarchy = cv2.findContours(dilation, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if 'yes' in red_list:
        table_colour_function('red', hsvvid, path_contours, frame)
        if breakvar != 0:
            break

    if 'yes' in yellow_list:
        table_colour_function('yellow', hsvvid, path_contours, frame)
        if breakvar != 0:
            break

    if 'yes' in green_list:
        table_colour_function('green', hsvvid, path_contours, frame)
        if breakvar != 0:
            break

    cv2.imshow('path video', frame)
    key = cv2.waitKey(1)
    if key == 27 or numofyes == 0: #press esc to exit
        break

cap.release()
cv2.destroyAllWindows()

if rating_table != 0:
    class handDetector():

        def __init__(self, mode=False, maxHands=2, detectionCon=0.5, trackCon=0.5):

            self.mode = mode
            self.maxHands = maxHands
            self.detectionCon = detectionCon
            self.trackCon = trackCon
            self.mpHands = mp.solutions.hands
            self.hands = self.mpHands.Hands(
                            static_image_mode=self.mode,
                            max_num_hands=self.maxHands,
                            min_detection_confidence=self.detectionCon,
                            min_tracking_confidence=self.trackCon
                        )
            # self.hands = self.mpHands.Hands(self.mode, self.maxHands, self.detectionCon, self.trackCon)
            self.mpDraw = mp.solutions.drawing_utils

        def findHands(self, img, draw=True):

            imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            self.results = self.hands.process(imgRGB)

            if self.results.multi_hand_landmarks:

                for handLms in self.results.multi_hand_landmarks:

                    if draw:
                        self.mpDraw.draw_landmarks(img, handLms, self.mpHands.HAND_CONNECTIONS)

            return img

        def findPosition(self, img, handNo=0, draw=True):

            lmList = []

            if self.results.multi_hand_landmarks:

                myHand = self.results.multi_hand_landmarks[handNo]

                for id, lm in enumerate(myHand.landmark):

                    h, w, c = img.shape
                    cx, cy = int(lm.x * w), int(lm.y * h)
                    lmList.append([id, cx, cy])

                    if draw:
                        cv2.circle(img, (cx, cy), 15, (33, 32, 196), cv2.FILLED)

            return lmList


    wCam, hCam = 640, 480

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

    cap.set(3, 1280)
    cap.set(4, 720)
    detector = handDetector(detectionCon=0.75)

    # 🕒 Allow 3-second delay before capturing rating
    start_time = time.time()
    while time.time() - start_time < 3:
        success, img = cap.read()
        if not success:
            continue
        cv2.putText(img, "Show rating in...", (50, 100), cv2.FONT_HERSHEY_PLAIN, 3, (0, 0, 255), 3)
        seconds_left = 3 - int(time.time() - start_time)
        cv2.putText(img, f"{seconds_left}", (300, 200), cv2.FONT_HERSHEY_PLAIN, 6, (255, 0, 0), 4)
        cv2.imshow("Rating", img)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    tipIds = [4, 8, 12, 16, 20]
    rating = 0
    rating1 = 0
    rating2 = 0
    i = 0

    while True:

        rating2 = rating1
        success, img = cap.read()
        img = detector.findHands(img)
        lmList = detector.findPosition(img, draw=False)

        if len(lmList) != 0:

            fingers = []

            if lmList[tipIds[0]][1] > lmList[tipIds[0] - 1][1]:

                fingers.append(1)

            else:

                fingers.append(0)

            for id in range(1, 5):

                if lmList[tipIds[id]][2] < lmList[tipIds[id] - 2][2]:

                    fingers.append(1)

                else:

                    fingers.append(0)

            totalFingers = fingers.count(1)

            # print(totalFingers)

            if totalFingers == 0:
                h = '0'
                rating1 = 0
                cv2.putText(img, h, (100, 250), cv2.FONT_HERSHEY_PLAIN, 3, (255, 0, 0), 3)

            if totalFingers == 1:
                h = '1'
                rating1 = 1
                cv2.putText(img, h, (100, 250), cv2.FONT_HERSHEY_PLAIN, 3, (255, 0, 0), 3)

            if totalFingers == 2:
                h = '2'
                rating1 = 2
                cv2.putText(img, h, (100, 250), cv2.FONT_HERSHEY_PLAIN, 3, (255, 0, 0), 3)

            if totalFingers == 3:
                h = '3'
                rating1 = 3
                cv2.putText(img, h, (100, 250), cv2.FONT_HERSHEY_PLAIN, 3, (255, 0, 0), 3)

            if totalFingers == 4:
                h = '4'
                rating1 = 4
                cv2.putText(img, h, (100, 250), cv2.FONT_HERSHEY_PLAIN, 3, (255, 0, 0), 3)

            if totalFingers == 5:
                h = '5'
                rating1 = 5
                cv2.putText(img, h, (100, 250), cv2.FONT_HERSHEY_PLAIN, 3, (255, 0, 0), 3)

        #cv2.rectangle(img, (50, 200), (175, 270), (0, 255, 0), 2)
        #cv2.putText(img, 'Rating (Backhand)', (50, 185), cv2.FONT_HERSHEY_PLAIN, 2, (255, 0, 0), 3)
        cv2.putText(frame, rating_text, (5, 50), font, 2, (0, 0, 255), 2, cv2.LINE_AA)
        cv2.imshow("Rating", img)

        if rating1 == rating2:

            i += 1

            if i > 20:
                rating = rating1
                time.sleep(2)
                cv2.destroyAllWindows()
                cap.release()
                break

        elif rating1 != rating2:

            i = 0

        if cv2.waitKey(1) & 0xFF == ord('q'):
            cv2.destroyAllWindows()
            cap.release()
            break

    if rating_table == 1:
        response = sheet.values().update(spreadsheetId=SAMPLE_SPREADSHEET_ID, range="Sheet1!E2", valueInputOption="USER_ENTERED", body={"values": [['no']]}).execute()
        response = sheet.values().update(spreadsheetId=SAMPLE_SPREADSHEET_ID, range="Sheet1!F2", valueInputOption="USER_ENTERED", body={"values": [[rating]]}).execute()

    elif rating_table == 2:
        response = sheet.values().update(spreadsheetId=SAMPLE_SPREADSHEET_ID, range="Sheet1!E3", valueInputOption="USER_ENTERED", body={"values": [['no']]}).execute()
        response = sheet.values().update(spreadsheetId=SAMPLE_SPREADSHEET_ID, range="Sheet1!F3", valueInputOption="USER_ENTERED", body={"values": [[rating]]}).execute()

    elif rating_table == 3:
        response = sheet.values().update(spreadsheetId=SAMPLE_SPREADSHEET_ID, range="Sheet1!E4", valueInputOption="USER_ENTERED", body={"values": [['no']]}).execute()
        response = sheet.values().update(spreadsheetId=SAMPLE_SPREADSHEET_ID, range="Sheet1!F4", valueInputOption="USER_ENTERED", body={"values": [[rating]]}).execute()
