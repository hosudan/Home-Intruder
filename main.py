import picamera,time
import RPi.GPIO as GPIO
import datetime
import smbus
from fractions import Fraction
from bh2 import BH1750
from twilio.rest import Client 
import firebase_admin
from firebase_admin import credentials, firestore, storage
from settings import *

camera = picamera.PiCamera()
current_mode = -1
bus = smbus.SMBus(1)
lightsensor = BH1750(bus)

GPIO.setmode(GPIO.BCM)
led1 = 20
pir = 4

GPIO.setup(led1, GPIO.OUT)
GPIO.setup(pir,GPIO.IN,pull_up_down=GPIO.PUD_DOWN)


def getFileName():
    return datetime.datetime.now().strftime("%Y-%m-%d_%H.%M.%S.jpg")

def check_day_night():
    global camera
    global current_mode
    lightLevel=lightsensor.measure_high_res()
    print("Current light level = ",lightLevel," lx(lumen). Adjusting light settings for the camera.")
    if lightLevel > LIGHT_THRESHOLD and current_mode!=0:
        current_mode=0
        print("Loading daylight settings")
        camera.shutter_speed = 0
        camera.exposure_mode = 'auto'
        camera.ISO = 200
        camera.exposure_compensation = 25
        camera.awb_mode = 'auto'
        time.sleep(5)
    elif lightLevel < LIGHT_THRESHOLD and current_mode!=1:
        current_mode=1
        print("Loading night settings.")
        #w.i.p sometimes pictures are too bright;todo play with settings
        camera.framerate = Fraction(1, 6)
        camera.shutter_speed = 300000
        camera.exposure_mode = 'off'
        camera.ISO = 800
        camera.exposure_compensation = 25
        camera.awb_mode = 'off'
        camera.awb_gains = (2.0, 2.0)
        time.sleep(10)
    print("Adjusted light settings.")

def TAKE_PIC(pir):
    global camera
    if GPIO.input(pir):
        print("Motion Detected!")
        print("light on")
        GPIO.output(led1,GPIO.HIGH)
        time.sleep(1)
        print ("light off")
        GPIO.output(led1,GPIO.LOW)
        filename = getFileName()
        camera.resolution=(1920,1080)
        camera.capture(PATH+filename)
        print ("Picture saved at ISO: ", camera.ISO)
        send_image_to_phone(filename)
        

def send_image_to_phone(filename):
    db = firestore.client()

    bucket = storage.bucket()
    blob = bucket.blob("images/"+filename)
    blob.upload_from_filename(filename)
    url = blob.generate_signed_url(datetime.timedelta(seconds=3600), method='GET')
 
    account_sid = TWILIO_ACCOUNT_SID
    auth_token = TWILIO_AUTH_TOKEN
    client = Client(account_sid, auth_token) 
 
    message = client.messages.create(         
                              body='Intruder detected!',
                              media_url=url,
                              from_=TWILIO_FROM,
                              to=TWILIO_TO
                          )
    print("Message sent to user: SID = "+ message.sid)
    
try:
    cred=credentials.Certificate(FIREBASE_ADMIN_JSON)
    fs = firebase_admin.initialize_app(cred, {
    'storageBucket': STORAGE_BUCKET
    })
    print("acclimatizing to the infrared energy in the room.")
    time.sleep(10)
    print("process done")
    GPIO.add_event_detect(pir,GPIO.RISING, callback=TAKE_PIC,bouncetime=300)
    while 1:
        check_day_night()
        time.sleep(3600)
except KeyboardInterrupt:
    print("quit")
    GPIO.cleanup()
    camera.close()
