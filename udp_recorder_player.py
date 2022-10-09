# SET TO TRUE WHEN RUNNING ON PI
pi = True


from dis import show_code
import time,socket,datetime,json, threading
if pi:
    from gpiozero import PWMOutputDevice, DigitalInputDevice
else:
    import random



# Set the incoming UPD port here
UDP_PORT = 6006
# Set the outgoing UDP port here
UDP_OUT_PORT = 6007


# Set the debug level
# 0 = no debug messages, 1 = INPUT, 2 = inverter messages, 3 = UDP, 4 = all
DEBUG = 3


# Set the to be loaded slots. 
# Has to be full paths or else it won't start on boot! 
if pi:
    play_1 = "/home/kb/Desktop/vermeulen/SLOT_1.json"
    play_2 = "/home/kb/Desktop/vermeulen/SLOT_2.json"
    path_settings = "/home/kb/Desktop/vermeulen/settings.json"
else:
    play_1 = "SLOT_1.json"
    play_2 = "SLOT_2.json"
    path_settings = "settings.json"    





# Set the gpio out and in. 
# Check pinout.xyz for the black pin numbers aka the board numbers these are used as strings e.g. "BOARD18".
# BCM numbering are usable as integers.  
if pi:
    inv_1 = PWMOutputDevice("BOARD12")
    inv_2 = PWMOutputDevice("BOARD13")
    play_button = DigitalInputDevice(21, pull_up=True)

if pi:
    print(f"Listening on port {UDP_PORT} for UDP messages from the recorder software.") 
    print("My IP address is hard coded at 192.168.178.9.")
    print("Commands are 'REC filename.json', 'EDIT', 'SHOW', 'STOP' and 'EXIT'.")
    print("Drivers can be controllers directly when in EDIT mode if inverters are connected and programmed on 0 - 3.3V input.")
    print(f"The outputs are {inv_1} and {inv_2}.")
else:
    print(f"Listening on port {UDP_PORT} for UDP messages from the recorder software.") 
    print("Commands are 'REC filename.json', 'EDIT', 'SHOW', 'STOP' and 'EXIT'.")
    print("Sending values when in EDIT mode works if inverters are connected and programmed on 0 - 3.3V input.")    


# Declare variables 
playing = False
pir_sensor = False
pir_sensor_active = False
standard_mode = False
stop_thread_slow = False
stop_thread_pir = False
interaction_stop = False
edit_stop = False
play_mode = 0
play_mode_active = False


# UDP setup for listening
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
sock.setblocking(1)
sock.bind(('', UDP_PORT))
#Set console color for easier UDP income reading
CRED = '\033[91m'
CEND = '\033[0m'



#load composition 1
def composition_load_pir():
    global play_1, recording_pir,rec_dict_pir, last_time_pir
    print(f"{datetime.datetime.now().time()}: opening {play_1}")
    try:
        f = open(play_1, "rb")
    except:
        print("The FIRST SLOT does not contain a file.")
    else:
        one_char = f.read(1) # read first character to check if it contains data 
        if one_char:
            f.seek(-1, 1)   # go back one character to make sure json.loads still understand the format
            recording_pir = json.loads(f.read())
            rec_dict_pir = {entry["time"]:entry["values"] for entry in recording_pir}
            if DEBUG == 2 or DEBUG == 4:
                print(rec_dict_pir) 
            last_time_pir = list(recording_pir)[-1]["time"]
            f.close()
            print(f"{datetime.datetime.now().time()}: {play_1} is {last_time_pir} seconds long")
        elif not one_char:
            print("The FIRST SLOT does not contain any data.")
composition_load_pir()

# #load composition 2
# def composition_load_slow():
#     global play_2, recording_slow, rec_dict_slow, last_time_slow
#     print(f"{datetime.datetime.now().time()}: opening {play_2}")
#     try:
#         f = open(play_2, "rb")
#     except:
#         print("The SECOND SLOT does not contain a file.")
#     else:
#         one_char = f.read(1) # read first character to check if it contains data 
#         if one_char:        #if it has at least 1 character
#             f.seek(-1, 1)   # go back one character to make sure json.loads still understand the format
#             recording_slow = json.loads(f.read())
#             rec_dict_slow = {entry["time"]:entry["values"] for entry in recording_slow}
#             if DEBUG == 2 or DEBUG == 4:
#                 print(rec_dict_slow) 
#             last_time_slow = list(recording_slow)[-1]["time"]
#             f.close()
#             print(f"{datetime.datetime.now().time()}: {play_2} is {last_time_slow} seconds long")
#         elif not one_char:
#             print("The SECOND SLOT does not contain any data.")   
# composition_load_slow()


# the function that will be the player for both compositions
def player (thread_name, dict, last_entry, slot):
    global stop_thread_slow, stop_thread_pir
    global pir_sensor_active, standard_mode, playing, player_done
    global pi
    playing = True
    print(f"{datetime.datetime.now().time()}: Thread {thread_name} Starting composition from {slot} and will be playing for: {last_entry}s")
    t0 = time.time()
    player_done = False
    while True:
        t1 = time.time() - t0
        t_check = round(t1, 3)
        values = dict.get(t_check, None)
        if stop_thread_pir or stop_thread_slow: 
                break
        if values:
            if DEBUG == 2 or DEBUG == 4:
                print(f"{datetime.datetime.now().time()}: {thread_name} time: {t_check} values: {values}")   
            if pi:    
                inv_1.value = values[0]
                inv_2.value = values[1]                                         
        if t1 >= last_entry:
            print(f"{datetime.datetime.now().time()}: Thread {thread_name} done playing {slot}")
            t0 = 0
            t1 = 0
            player_done = True
            playing = False
            pir_sensor_active = False
            standard_mode = False
            break

def interaction():
    global stop_thread_pir, stop_thread_slow, interaction_stop
    global rec_dict_pir, rec_dict_slow, last_time_pir, last_time_slow, play_2, play_1
    global pir_sensor_active, pir_sensor, standard_mode
    # The loop that checks wether the pir sensor is active or not and starts, or kills, the corresponding threads    
    print("interaction has started")    
    print("standard_mode", standard_mode)
    print("pir_sensor_active", pir_sensor_active)
    print("pir_sensor", pir_sensor)
    while True:
        if interaction_stop:
            print(f"{datetime.datetime.now().time()}: Interaction thread is stopping")
            break
        if pir_sensor and not pir_sensor_active:
            pir_sensor_active = True
            print(f"{datetime.datetime.now().time()}: interaction thread and not pir_sensor_active pir_sensor:", pir_sensor)
            print(f"{datetime.datetime.now().time()}: Slow player killed")
            standard_mode = False
            stop_thread_slow = False
            try:
                t_pir = threading.Thread(target = player, args=("t_pir", rec_dict_pir, last_time_pir, play_1)) 
                t_pir.start()
            except:
                print("Could not start composition. Exitting")
                quit()
            # except:
            #     print("no pir composition is found, playing the slow composition")
            #     try:
            #         t_slow = threading.Thread(target = player, args=("t_slow", rec_dict_slow, last_time_slow, play_2 ))
            #         t_slow.start()
            #     except:
            #         print("No slow composition is found either. Please record a composition before starting the program.")

            

def stop_inv():
    global pi
    if pi:
        global inv_1, inv_2
        inv_1.value = 0
        inv_2.value = 0
    print(f"{datetime.datetime.now().time()}: inverters stopped")
    return

def network_udp():
    global sock, addr, UDP_OUT_PORT
    global play_mode, play_mode_active, pir_sensor_active
    global path_settings
    global stop_thread_pir, stop_thread_slow, interaction_stop, standard_mode
    global pi
    if pi:
        global inv_1, inv_2
    data = '' # empty var for incoming data
    rec = 0
    while True:
        data_raw, addr = sock.recvfrom(1024)
        data = data_raw.decode()    # My test message is encoded
        if DEBUG == 3 or DEBUG == 4:
            print(f"{CRED}{datetime.datetime.now().time()} UDP MESSAGE: {data}{CEND}")    
        if data:                                                        # only do something when there's data
            if data.startswith("status"):
                show_mode = "play_mode " + str(play_mode)
                sock.sendto((bytes(show_mode, "utf-8")), (addr[0], UDP_OUT_PORT))
            if data.startswith("SHOW"):     
                try:
                    file_settings = open(path_settings, 'w')
                    file_settings.write(data)    
                    file_settings.close()                    
                except:
                    print("settings file cannot be opened or written.")
                standard_mode = False
                stop_thread_pir = False
                stop_thread_slow = False                
                interaction_stop = False
                play_mode_active = False
                pir_sensor_active = False                
                stop_inv() 
                play_mode = 2
                print("play_mode udp", play_mode)
            if data.startswith("EDIT"):
                try:
                    file_settings = open(path_settings, 'w')
                    file_settings.write(data)    
                    file_settings.close()                    
                except:
                    print("settings file cannot be opened or written.")
                stop_thread_slow = True
                stop_thread_pir = True
                interaction_stop = True
                play_mode_active = False
                pir_sensor_active = False
                stop_inv() 
                play_mode = 1 
                print("play_mode udp", play_mode)
            if play_mode == 1:
                decode_list = data.split()                              # byte decode the incoming list and split in two
                if decode_list[0].startswith("REC") and rec == 0:                    # if the first part of the list starts with "rec"
                    print(decode_list[0],decode_list[1])                    # for debug purposes
                    y = []                                                  # the list that is used to store everything, empty or start it when this is called
                    if pi:
                        loc_file = "/home/kb/Desktop/vermeulen/" + decode_list[1]
                    else:
                        loc_file = decode_list[1]
                    t0 = time.time()                                        # start the timer
                    f = open(loc_file, 'w+')                           # open or new file with the chosen file in the Recorder Software
                    rec = 1
                    sock.sendto(bytes("REC", "utf-8"), (addr[0], UDP_OUT_PORT))
                elif decode_list[0].startswith("VALUES"):   # if the first part of the list starts with "VALUES"
                    if pi:
                        inv_1.value = float(decode_list[1])
                        inv_2.value = float(decode_list[2])
                    if rec:
                        t1 = time.time() - t0
                        x = {                                                   # build a dict with the info from UDP
                            "time": round(t1, 3),
                            "values":[
                                    float(decode_list[1]),
                                    float(decode_list[2])                                                      
                                ]           
                            }
                        y.append(x)                                         # append the dict to the list 
                elif decode_list[0].startswith("ST_RC"):                 # if the list starts with "ST_RC"
                    print("RECEIVED STOP RECORDING ORDER")
                    rec = 0
                    try:    
                        json_dump = json.dumps(y, sort_keys=True, ensure_ascii=False) #transfer the list of dicts into a json format
                        f.write(json_dump)                                      # write it to the file opened in "rec"
                        f.close()                                               # close the file  
                        print("done writing file")                              
                        sock.sendto(bytes("load_mode 1", "utf-8"), (addr[0], UDP_OUT_PORT))
                        del y                                                   # double check to delete to free up memory
                        composition_load_pir()
                        # composition_load_slow() 
                        sock.sendto(bytes("load_mode 0", "utf-8"), (addr[0], UDP_OUT_PORT))
                    except:
                        print("The recording has not started yet. Try again.")
                    stop_inv()   
                    sock.sendto(bytes("STOPPED RECORDING", "utf-8"), (addr[0], UDP_OUT_PORT))
                elif decode_list[0].startswith("STOP"):                 # if the list starts with "STOP"
                    stop_inv()
                    if rec:
                        rec = 0
                        try:    
                            json_dump = json.dumps(y, sort_keys=True, ensure_ascii=False) #transfer the list of dicts into a json format
                            f.write(json_dump)                                      # write it to the file opened in "rec"
                            f.close()                                               # close the file  
                            print("done writing file")                              
                            del y                                                   # double check to delete to free up memory
                            composition_load_pir()
                            # composition_load_slow() 
                        except:
                            print("The recording has not started yet. Try again.")
                        stop_inv()   
                        sock.sendto(bytes("STOPPED RECORDING", "utf-8"), (addr[0], UDP_OUT_PORT))
try:
    network_udp_worker = threading.Thread(target=network_udp)
    network_udp_worker.start()
except:
    print (f"{datetime.datetime.now().time()}: Error: unable to start network_udp_worker thread. Exit.")
    quit()


# the function that will spawn as a thread continiously checking the pir sensor
def pir_input():
    global pi, pir_sensor, play_button, addr, UDP_OUT_PORT
    print(f"{datetime.datetime.now().time()}: Detecting pir sensor")
    while True: 
        if pi:
            pir_sensor = play_button.value 
            if pir_sensor and DEBUG == 1 or pir_sensor and DEBUG == 4:
                print(f"{datetime.datetime.now().time()}: pir sensor: {pir_sensor}")
        else:
            time.sleep(40)   # DEBUG for non pi checking
            pir_sensor = random.getrandbits(1) # DEBUG for non pi checking
            print(f"{datetime.datetime.now().time()}: pir sensor: {pir_sensor}")
# start the pir sensor thread 
try:
    pir_sensor_worker = threading.Thread(target=pir_input)
    pir_sensor_worker.start()
except:
    print (f"{datetime.datetime.now().time()}: Error: unable to start PIR SENSOR thread. Exit.")
    quit()



# FILE SETTINGS
try:
    file_settings = open(path_settings, 'r')
except:
    print (f"{datetime.datetime.now().time()}: Error: Could not find a settings file at {path_settings}. Will create a new one.")
    file_settings = open(path_settings, 'w+')
    file_settings.write("SHOW")
finally:
    all_char = file_settings.read(20) # read file
    print(all_char)
    if all_char.startswith("EDIT"):
        print("record mode")
        play_mode = 1
    elif all_char.startswith("SHOW"):
        print("play mode")
        play_mode = 2
    file_settings.close()

# def keyboard_switcher():
#     global play_mode
#     key_input = input("type SHOW or EDIT for their modes")
#     if key_input.startswith("EDIT"):
#         print("keyboard swichted mode to EDIT")
#         play_mode = 1 
#     elif key_input.startswith("SHOW"):
#         print("keyboard swichted mode to SHOW")
#         play_mode = 2
# # start the pir sensor thread 
# try:
#     keyboard_switcher_worker = threading.Thread(target=keyboard_switcher)
#     keyboard_switcher_worker.start()
# except:
#     print (f"{datetime.datetime.now().time()}: Error: unable to start keyboard_switcher thread. Exit.")
#     quit()
# keyboard_switcher()


while True:
    # key_input = input("type SHOW or EDIT for their modes")
    # if key_input.startswith("EDIT"):
    #     print("keyboard swichted mode to EDIT")
    #     play_mode = 1 
    # elif key_input.startswith("SHOW"):
    #     print("keyboard swichted mode to SHOW")
    #     play_mode = 2
    if play_mode == 2 and not play_mode_active: 
        play_mode_active = True
        edit_stop = True
        print("beginning play_mode")
        try:
            interaction_worker = threading.Thread(target=interaction)
            interaction_worker.start()
        except:
            print (f"{datetime.datetime.now().time()}: Error: unable to start INTERACTION thread. Exit.")
            quit()