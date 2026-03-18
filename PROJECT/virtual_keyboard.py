import cv2
from cvzone.HandTrackingModule import HandDetector
import numpy as np
import cvzone
from pynput.keyboard import Controller, Key
from playsound import playsound
import threading
import sounddevice as sd
import scipy.io.wavfile as wav
import speech_recognition as sr
import tempfile
from pymongo import MongoClient
from datetime import datetime
import time

# Setup
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("Error: Camera not available")
    exit(1)
cap.set(3, 1280)
cap.set(4, 720)

detector = HandDetector(detectionCon=0.8)
keyboard = Controller()

screen = 0
finalText = ""
voice_active = False

user_inputs = {
    "Virtual Keyboard": [],
    "Voice Input": []
}

try:
    client = MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=5000)
    client.server_info()  # Test connection
    db = client["virtual_keyboard_db"]
    collection = db["user_inputs"]
except Exception as e:
    print(f"MongoDB connection failed: {e}")
    client = None
    collection = None

def store_to_mongo(text, input_type="Virtual Keyboard"):
    if text.strip() and collection is not None:
        try:
            document = {
                "text": text.strip(),
                "input_type": input_type,
                "timestamp": datetime.utcnow()
            }
            collection.insert_one(document)
        except Exception as e:
            print(f"[MongoDB] Error storing data: {e}")

def playClickSound():
    try:
        threading.Thread(target=lambda: playsound("click.mp3"), daemon=True).start()
    except Exception as e:
        print(f"Audio error: {e}")

def listen_to_user(duration=5, samplerate=16000):
    import os
    print("Listening... Speak now.")
    recording = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1, dtype='int16')
    sd.wait()
    temp_file = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as f:
            temp_file = f.name
            wav.write(f.name, samplerate, recording)
        
        recognizer = sr.Recognizer()
        with sr.AudioFile(temp_file) as source:
            audio = recognizer.record(source)
        
        text = recognizer.recognize_google(audio)
        return text.lower()
    except sr.UnknownValueError:
        return ""
    except sr.RequestError as e:
        print(f"API error: {e}")
        return ""
    except Exception as e:
        print(f"Audio processing error: {e}")
        return ""
    finally:
        if temp_file and os.path.exists(temp_file):
            os.unlink(temp_file)

def voice_trigger_listener():
    global voice_active
    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as mic:
            while True:
                try:
                    recognizer.adjust_for_ambient_noise(mic)
                    audio = recognizer.listen(mic, timeout=5)
                    trigger = recognizer.recognize_google(audio).lower()
                    if "click voice" in trigger:
                        voice_active = True
                        handle_voice_commands()
                except (sr.UnknownValueError, sr.RequestError):
                    continue
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(f"Voice trigger error: {e}")
                    time.sleep(1)
    except Exception as e:
        print(f"Microphone initialization error: {e}")

def handle_voice_commands():
    global voice_active, finalText, caps_lock, shift_active, screen
    text = listen_to_user()
    if not text:
        voice_active = False
        return

    commands = text.split()

    if "clear text" in text:
        finalText = ""
    elif "click enter" in text:
        keyboard.press(Key.enter)
        user_inputs["Voice Input"].append(finalText)
        store_to_mongo(finalText, input_type="Voice Input")
        finalText += '\n'
    elif "click space" in text:
        keyboard.press(Key.space)
        finalText += ' '
        user_inputs["Voice Input"].append(" ")
    elif "click back" in text:
        keyboard.press(Key.backspace)
        finalText = finalText[:-1]
    elif "click shift" in text:
        shift_active = not shift_active
    elif "click caps" in text:
        caps_lock = not caps_lock
    elif "go to numbers" in text:
        screen = 1
    elif "go to symbols" in text:
        screen = 2
    else:
        keyboard.type(text)
        finalText += text
        user_inputs["Voice Input"].append(text)
        store_to_mongo(text, input_type="Voice Input")

    voice_active = False

class Button():
    def __init__(self, pos, text, size=[85, 85]):
        self.pos = pos
        self.size = size
        self.text = text

def drawAll(img, buttonList):
    for button in buttonList:
        x, y = button.pos
        w, h = button.size
        cvzone.cornerRect(img, (x, y, w, h), 20, rt=0)
        cv2.rectangle(img, button.pos, (x + w, y + h), (255, 0, 255), cv2.FILLED)
        cv2.putText(img, button.text, (x + 20, y + int(h * 0.7)),
                    cv2.FONT_HERSHEY_PLAIN, 3, (255, 255, 255), 3)
    return img

# QWERTY Keys
keysQWERTY = [["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P"],
              ["A", "S", "D", "F", "G", "H", "J", "K", "L", "."],
              ["Z", "X", "C", "V", "B", "N", "M", ",", "Back"],
              ["Caps", "Shift", "Space", "Enter"]]

buttonListQWERTY = []
for i in range(len(keysQWERTY)):
    for j, key in enumerate(keysQWERTY[i]):
        if i == 3:
            sizes = {"Caps": [150, 85], "Shift": [150, 85],
                     "Space": [300, 85], "Enter": [200, 85]}
            x_positions = {"Caps": 50, "Shift": 220,
                           "Space": 390, "Enter": 710}
            buttonListQWERTY.append(Button([x_positions[key], 100 * i + 50], key, size=sizes[key]))
        else:
            width = 200 if key == "Back" else 85
            buttonListQWERTY.append(Button([100 * j + 50, 100 * i + 50], key, size=[width, 85]))

buttonListQWERTY.append(Button([1050, 20], "num", size=[100, 60]))
buttonListQWERTY.append(Button([1160, 20], "Sym", size=[100, 60]))
buttonListQWERTY.append(Button([1050, 90], "Voice", size=[210, 60]))

# Numeric Pad
keysNumPad = [["7", "8", "9", "+"],
              ["4", "5", "6", "-"],
              ["1", "2", "3", "*"],
              ["0", "Clear", "", "/"]]

buttonListNumPad = []
for i in range(len(keysNumPad)):
    for j, key in enumerate(keysNumPad[i]):
        if key == "":
            continue
        width = 150 if key == "Clear" else 85
        buttonListNumPad.append(Button([j * 100 + 200, i * 100 + 100], key, size=[width, 85]))
buttonListNumPad.append(Button([50, 20], "<", size=[100, 60]))

# Symbols
keysSymbols = [["[", "]", "{", "}", "(", ")"],
               [";", ":", "'", '"', ",", "."],
               ["<", ">", "/", "?", "|", "Tab"],
               ["!", "@", "#", "$", "%", "^"],
               ["&", "*", "_", "=", "~"]]

buttonListSymbols = []
for i in range(len(keysSymbols)):
    for j, key in enumerate(keysSymbols[i]):
        if key == "":
            continue
        w = 120 if key == "Tab" else 85
        buttonListSymbols.append(Button([j * 100 + 100, i * 85 + 100], key, size=[w, 75]))
buttonListSymbols.append(Button([50, 20], "<", size=[100, 60]))

prevTipY = 0
coolDownCounter = 0
coolDownMax = 20
caps_lock = False
shift_active = False

# Start background listener for "click voice"
threading.Thread(target=voice_trigger_listener, daemon=True).start()

while True:
    success, img = cap.read()
    img = cv2.flip(img, 1)
    hands, img = detector.findHands(img)

    buttonList = buttonListQWERTY if screen == 0 else buttonListNumPad if screen == 1 else buttonListSymbols
    img = drawAll(img, buttonList)

    if hands:
        lmList = hands[0]['lmList']
        fingerX, fingerY = lmList[8][0], lmList[8][1]

        for button in buttonList:
            x, y = button.pos
            w, h = button.size
            if x < fingerX < x + w and y < fingerY < y + h:
                cv2.rectangle(img, (x - 5, y - 5), (x + w + 5, y + h + 5), (175, 0, 175), cv2.FILLED)
                cv2.putText(img, button.text, (x + 20, y + int(h * 0.7)),
                            cv2.FONT_HERSHEY_PLAIN, 3, (255, 255, 255), 3)

                if prevTipY != 0 and coolDownCounter == 0:
                    yDiff = fingerY - prevTipY
                    if yDiff < -30:
                        keyValue = button.text
                        playClickSound()

                        if keyValue == "num":
                            screen = 1
                        elif keyValue == "Sym":
                            screen = 2
                        elif keyValue == "<":
                            screen = 0
                        elif keyValue == "Space":
                            keyboard.press(Key.space)
                            finalText += ' '
                            user_inputs["Virtual Keyboard"].append(" ")
                        elif keyValue == "Back":
                            keyboard.press(Key.backspace)
                            finalText = finalText[:-1]
                        elif keyValue == "Caps":
                            caps_lock = not caps_lock
                        elif keyValue == "Shift":
                            shift_active = not shift_active
                        elif keyValue == "Enter":
                            keyboard.press(Key.enter)
                            user_inputs["Virtual Keyboard"].append(finalText)
                            store_to_mongo(finalText)
                            finalText += '\n'
                        elif keyValue == "Clear":
                            finalText = ""
                        elif keyValue == "Tab":
                            keyboard.press(Key.tab)
                            finalText += '\t'

                        elif keyValue == "Voice":
                            handle_voice_commands()
                        else:
                            char = keyValue.upper() if shift_active or caps_lock else keyValue
                            keyboard.type(char)
                            finalText += char
                            user_inputs["Virtual Keyboard"].append(char)

                        coolDownCounter = coolDownMax

        prevTipY = fingerY
    else:
        prevTipY = 0

    if coolDownCounter > 0:
        coolDownCounter -= 1

    lines = finalText.split('\n')
    cv2.rectangle(img, (50, 550), (1200, 650), (175, 0, 175), cv2.FILLED)
    for i, line in enumerate(lines):
        cv2.putText(img, line, (60, 590 + i * 30),
                    cv2.FONT_HERSHEY_PLAIN, 2.5, (255, 255, 255), 3)

    cv2.imshow("Virtual Keyboard", img)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Cleanup resources
cap.release()
cv2.destroyAllWindows()
if client:
    client.close()
