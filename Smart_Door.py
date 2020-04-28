import RPi.GPIO as GPIO
import time as time
import serial
import LCD1602 as LCD
from picamera import PiCamera    
import PCF8591 as ADC
from datetime import datetime
from flask import Flask
from flask import send_file

smart_door_app = Flask(__name__) #variable to store the flask server

global buzzer_output
buzzer_output = 9

global Buzz #BUZZER

global TRIG #for ultrasonic out
TRIG = 27

global ECHO #for ultrasonic in
ECHO = 6

global ENABLE_PIN  #FOR RFID
ENABLE_PIN = 22
global SERIAL_PORT
SERIAL_PORT= '/dev/ttyS0'

global door_switch #We are assuming there is an external door controller which takes in 1 to open and 0 to close door
door_switch = 16

global ser #Serial communucation

global INTR_PIN  #interrupt pin for Swtich press to enter DOOR
INTR_PIN=10

global password
password= '12'

photo_path='/home/pi/Desktop/myImage.jpg'
video_path='/home/pi/Desktop/myVideo.h264'

def setup_board():          #SETUP The board  
    global Buzz #use the global var
    GPIO.setmode(GPIO.BCM) #Set mode to BCM
    GPIO.setwarnings(False) # call this function to avoid warnings
    
    #Switch 1 Parking
    GPIO.setup(door_switch,GPIO.OUT) #Set door_switch as OUTPUT  - High tells door to open and low tells door to close
   
    #Buzzer Setup
    GPIO.setup(buzzer_output,GPIO.OUT)
    Buzz= GPIO.PWM(buzzer_output,500) # buzzer output is the channel, initial frequency is 500

    #ultrasonic setup
    GPIO.setup(TRIG,GPIO.OUT)
    GPIO.setup(ECHO,GPIO.IN)
    #Setup RFID
    #This pin corresponds to GPIO22, which we'll use to turn the RFID reader on and off with.
    GPIO.setup(ENABLE_PIN, GPIO.OUT)
    GPIO.output(ENABLE_PIN,GPIO.LOW)
    global ser
    #Set up the serial port as per the Parallex reader's datasheet

    ser = serial.Serial(baudrate=2400,
                    bytesize= serial.EIGHTBITS,
                    parity= serial.PARITY_NONE,
                    port= SERIAL_PORT,
                    stopbits= serial.STOPBITS_ONE,
                    timeout =1)
    #IR Detector Interrupt setup
    GPIO.setup(INTR_PIN, GPIO.IN, pull_up_down = GPIO.PUD_)
    #interrupt call defintion
    GPIO.add_event_detect(INTR_PIN, GPIO.RISING, callback= door_bell_pressed,bouncetime=2000)

    #Keypad Setup According to the default connections
    GPIO.setup(19, GPIO.IN, pull_up_down = GPIO.PUD_UP) 
    GPIO.setup(20, GPIO.IN, pull_up_down = GPIO.PUD_UP) 
    GPIO.setup(21, GPIO.IN, pull_up_down = GPIO.PUD_UP) 
    GPIO.setup(22, GPIO.IN, pull_up_down = GPIO.PUD_UP) 

    GPIO.setup(23, GPIO.OUT) 
    GPIO.setup(24, GPIO.OUT) 
    GPIO.setup(25, GPIO.OUT) 
    GPIO.setup(26, GPIO.OUT)

    #initialize LCD
    LCD.init(0x27,1) #(slave address, background light)
    #ADC Initialization
    ADC.setup (0x48) #Address of the ADC on i2c in hex

def open_door():
    GPIO.output(door_switch,True) # open the door- High tells door controller to open door

def close_door():
    GPIO.output(door_switch,False) # close the door - Low tells door controller to close door

def take_image():
    Mycamera = PiCamera()     # Create an instance of PiCamera class called Mycamera                                                     
    time.sleep(5)  #  Adds a pause before capturing the image; gives time to the sensor to adjust in seconds    
    timestamp = datetime.now().isoformat()
    Mycamera.resolution= (1280,720)
    Mycamera.annotate_text = "Person entered at time %s" %timestamp #string to annotate photo
    Mycamera.capture(photo_path) # Captures the image and  stores it in /home/pi/Desktop path                                                        
    Mycamera.close()    #  Closes the camera instance and cleans up the resources  stops all recording

def take_video():
    Mycamera = PiCamera()     # Create an instance of PiCamera class called Mycamera
    timestamp = datetime.now().isoformat()
    Mycamera.annotate_text = "Intruder attempted to enter at time %s" %timestamp #string to annotate video                                                   
    Mycamera.start_recording(video_path) # start recording and stores the video on video path   
    time.sleep(5) # capture the vieo for 5 seconds
    Mycamera.stop_recording()                                                        
    Mycamera.close()    #  Closes the camera instance and cleans up the resources  stops all recording

def validate_rfid(code):
    #a valid code will be 12 chars (bytes) long with the first char being
    #a line feed and last char being a carriage return.
    s= code.decode("ascii")
    if (len(s) ==12) and (s[0] == "\n") and (s[11] == "\r"):
        #We matched a valid code. Strip off the \n and \r and just
        #return the RFID code which 10 buts. Linefeed= 0A and CR=0D
        return s[1:-1]
    else:
        #We didnt match a valid code, so return False
        return False

#ultrasoncic read
def measure_distance():
    GPIO.output(TRIG,0) #LOW
    time.sleep(0.000002)
    #SET TRIG PIN HIGH FOR 10 us
    GPIO.output(TRIG,1) #Generate pulse of 10us
    time.sleep(0.00001)
    GPIO.output(TRIG,0)

    #Read ECHO pi signal and calc distance in cm
    while GPIO.input(ECHO) ==0:
        a=0
    time1= time.time()          #capture time 1
    while GPIO.input(ECHO) ==1:
        a=0
    time2= time.time()          #capture time 2
    duration = time2-time1 
    return duration*1000000/58#sensor eq
                                                              
    
def check_password(entered_pass):
    global password #use global vars
    if entered_pass == password: #if match, return true
        return True
    else:
        return False

def get_password_keypad():
    LCD.write(0,0,"Type Password on Keypad")  #print on LCD as required
    key1= keypad() #get first key
    time.sleep(1) #wait 1 second before next key to avoid glitches
    key2= keypad() #get 2nd key
    time.sleep(0.5)
    keyF= str(key1)+str(key2) #concatenate both keys
    return keyF

    

def change_password(old, new):
    global password #alter global variable
    if old == password:     # if old matches the password
        password = new         #change password and return True
        return True
    else:
        return False

def ring_buzzer():
    global Buzz #Use the global var
    Buzz.start(50) #init duty cycle is 50
    time.sleep(5) # ring for 5 seconds
    Buzz.stop() # stop the buzzer

#Interrupt Route
def door_bell_pressed():
    LCD.clear() #clear the LCD screen
    distance= measure_distance()
    d=distance() # distance is measured in cm
    while(d<100): # while distance < 100 cm
        LCD.write(0,0,"Come Closer to Door")
        d=distance()
        time.sleep(0.05) #50ms interval between each distance measured

    LCD.write(0,0,"prs 0 for keypad")
    LCD.write(0,1,"prs 1 for RFID")

    selection= keypad()
    if selection==0:  # if 0 is pressed
        LCD.clear() #clear the LCD screen
        if check_password(get_password_keypad()): # if the password is correct
            take_image()    # take a photo of the person
            open_door()     # open the door for the person-> the person will closee it by themselves

        else:
            take_video() # take a 5 second video  of the intruder
            ring_buzzer()   # ring the buzzer

    elif selection==1:
        LCD.clear() #clear the LCD screen
        LCD.write(0,0,"Scan RFID")  #print on LCD as required
        data= ser.read(12)
        code = validate_rfid(data)
        if code== "5400653CCF":
            take_image()    # take a photo of the person
            open_door()     # open the door for the person-> the person will closee it by themselves
        else:
            take_video() # take a 5 second video  of the intruder
            ring_buzzer()   # ring the buzzer
    else:
        LCD.clear()
        LCD.write(0,0,"Invalid Selection")  #print on LCD as required

#Flask Routes

@smart_door_app.route("/")  #Welcome index route- this is like our first default page
def indexroute():
    Temp_units=ADC.read(0) #Read ADC units on chn 0 
    Temp_volts=(Temp_units*3.3)/256 #Convert to voltage based on ADC resolution (vref+-vref-)/2^N
    temp = Temp_volts/0.01 # using temperature sensor eqn: 10mV/1C
    ADC.write(Temp_units)   # write to dac to adjust LED brightness
    Hum_units=ADC.read(1) #Read ADC units on chn 1
    Hum_volts=(Hum_units*3.3)/256 #Convert to voltage based on ADC resolution (vref+-vref-)/2^N
    humidity = (Hum_volts - 0.985)/0.0307  # using humidity sensor eqn
    return "Welcome! The current temp is %2.2f and the humidity is %2.2f" %(temp,humidity) #Return the temp and humidty

@smart_door_app.route("/whoentered")  #static route 1
def whoEntered():
    response = send_file(photo_path, mimetype = 'image/jpg') #Send the image of the last person who entered
    return response

@smart_door_app.route("/intruder")  #Static route 2 
def intruder():
    response = send_file(video_path, mimetype = 'video/h.264') # return 5 second video of the intruder
                    
                    # codec that requires a video container to host the encoded video.
    return response

@smart_door_app.route("/changepassword/<old_password>/<new_password>")  #Dynamic route 1 - change system password
def change_password_flask(old_password,new_password): #Take in the old and new password
    if check_password(old_password): #Make sure the old password is correct
        change_password(old_password,new_password) #call function to update password
        return "Password has been changed" #return succuess msg
    else: #Retun failure message
        return "password validation failed"

@smart_door_app.route("/opendoor/<pwd>")  #Dynamic route 2 - Open door Contactless
def opendoor(pwd): #Take the passwrod from user
    if check_password(pwd):  #If the password is correct
        open_door() #Open door and send success message
        return "Door is Opened"
    else:
        return "Wrong Password" #If wrong password, send failure msg

#key pad function as presented in the lecture
def keypad(): 
    while(True): #Scan each column, and return appropriate value
        GPIO.output(26, GPIO.LOW)
        GPIO.output(25, GPIO.HIGH)
        GPIO.output(24, GPIO.HIGH)
        GPIO.output(23, GPIO.HIGH)
        if (GPIO.input(22)==0):
            return 1
            
        if (GPIO.input(21)==0):
            return 4
            
        if (GPIO.input(20)==0):
            return 7
            
        if (GPIO.input(19)==0):
            return(0xE)
            
        GPIO.output(26, GPIO.HIGH)
        GPIO.output(25, GPIO.LOW)
        GPIO.output(24, GPIO.HIGH)
        GPIO.output(23, GPIO.HIGH)

        if (GPIO.input(22)==0):
            return 2
            
        if (GPIO.input(21)==0):
            return 5
         
        if (GPIO.input(20)==0):
            return 8
            
        if (GPIO.input(19)==0):
            return 0
           
        GPIO.output(26, GPIO.HIGH)
        GPIO.output(25, GPIO.HIGH)
        GPIO.output(24, GPIO.LOW)
        GPIO.output(23, GPIO.HIGH)

        if (GPIO.input(22)==0):
            return 3
        
        if (GPIO.input(21)==0):
            return 6

        #Scan row 2
        if (GPIO.input(20)==0):
            return 9
           
        if (GPIO.input(19)==0):
            return (0XF)
           
        GPIO.output(26, GPIO.HIGH)
        GPIO.output(25, GPIO.HIGH)
        GPIO.output(24, GPIO.HIGH)
        GPIO.output(23, GPIO.LOW)

        if (GPIO.input(22)==0):
            return(0XA)
           
        if (GPIO.input(21)==0):
            return(0XB)
            
        if (GPIO.input(20)==0):
            return(0XC)
            
        if (GPIO.input(19)==0):
            return(0XD)
            

if __name__ == "__main__":#Main function - start the app on port 5060
    setup_board() #Setup ALL GPIOS and Communicaiton ports, LCD, RFID, ADC
    smart_door_app.run(debug=True, host = '0.0.0.0', port = 5060) 

