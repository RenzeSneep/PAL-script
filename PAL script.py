import serial
import time
from datetime import datetime
import threading
import os
import json

development_mode = True

if development_mode == True:
    port = "blank"
else:
    port = serial.Serial("COM3", baudrate=9600, timeout=1)

setup_folder = "tray_setups"
setup_file = "default_setup.txt"
active_setup = os.path.join(setup_folder, setup_file)

class Tray:
    def __init__(self, name, x, y, z, length, width, columns, rows, depth, volume):
        self.name = name
        self.x = x
        self.y = y
        self.z = z
        self.length = length
        self.width = width
        self.columns = columns
        self.rows = rows
        self.max_position = columns*rows
        self.direction = "columns"
        self.depth = depth
        self.volume = volume
        self.number = 1

        if rows > 1:
            self.distance_y = length/(rows-1)
        else:
            self.distance_y = 0
        if columns > 1:
            self.distance_x = width/(columns-1)
        else:
            self.distance_x = 0
        
    def get_position(self, position):
        print(type(self.x))
        position -= 1
        if self.direction == "columns":
            x_pos = position // self.rows
            y_pos = position - (x_pos*self.rows)
            x_coordinate = int(self.x + x_pos * self.distance_x)
            y_coordinate = int(self.y + y_pos * self.distance_y)
            z_coordinate = self.z
            return x_coordinate, y_coordinate, z_coordinate
        else:
            y_pos = position // self.columns
            x_pos = position - (y_pos*self.columns)
            x_coordinate = int(self.x + x_pos * self.distance_x)
            y_coordinate = int(self.y + y_pos * self.distance_y)
            z_coordinate = self.z
            return x_coordinate, y_coordinate, z_coordinate
        
class Combined_tray:
    def __init__(self, name, trays):
        self.name = name
        self.trays = trays
        self.columns = self.trays[0].columns
        self.rows = self.trays[0].rows
        self.positions_per_tray = self.columns * self.rows
        self.length = self.trays[0].length
        self.width = self.trays[0].width
        self.depth = self.trays[0].depth
        self.direction = "columns"
        self.number = len(trays)
        self.max_position = self.number * self.positions_per_tray
        for i in trays:
            if i.columns != self.columns or i.rows !=self.rows:
                print("Trays for combined tray not compatible")

    def get_position(self, position):
        for i in self.trays:
            i.direction = self.direction
        tray = (position-1) // self.positions_per_tray
        position = (position-1) % (self.positions_per_tray) +1
        coordinates = self.trays[tray].get_position(position)
        return coordinates

def define_trays(active_setup):
    all_trays = {}
    with open(active_setup) as f:
        text = f.read()
    all_trays_dict = json.loads(text)
    trays = all_trays_dict["trays"]
    for key in trays:
        tray = trays[key]
        all_trays[key] = Tray(name=key, x=tray["x"], y=tray["y"], z = tray["z"], length=tray["length"], width=tray["width"], columns=tray["columns"], rows=tray["rows"], depth=tray["depth"], volume=tray["volume"])
    combined_trays = all_trays_dict["combined trays"]
    for key in combined_trays:
        combined_tray = [all_trays[i] for i in combined_trays[key]]
        all_trays[key] = Combined_tray(name=key, trays=combined_tray)
    return all_trays

def save_setup(trays, name):
    all_trays_dict = {"trays": {}, "combined trays": {}}
    for key in trays:
        tray = trays[key]
        if isinstance(tray, Tray):
            all_trays_dict["trays"][key] = {"x": tray.x, "y": tray.y, "z": tray.z, "length": tray.length, "width": tray.width, "columns": tray.columns, "rows": tray.rows, "depth": tray.depth, "volume": tray.volume}
        if isinstance(tray, Combined_tray):
            all_trays_dict["combined trays"][key] = [i.name for i in tray.trays]
    text = json.dumps(all_trays_dict, indent=0)
    data_path = os.path.join(setup_folder, name + ".txt")
    if not os.path.exists(data_path):
        with open(data_path, "w") as f:
            f.write(text)
    else:
        print("File already exists")

all_trays = define_trays(active_setup)

class Head:
    def __init__(self,x, y, z, port):
        self.home_x = x
        self.home_y = y
        self.home_z = z
        self.x = x
        self.y = y
        self.z = z
        self.syringe = 10
        self.port = port

    def send_command(self, command):
        while True:
            self.port.write(command.encode())
            if "BUSY" in self.port.readline().decode('utf-8'):
                continue
            else:
                break
    
    def beep(self, frequency, duration):
        command = f"beep({frequency}, {duration})\r\n"
        self.send_command(command)
        
    def no_move(self, location, position):
        location = all_trays[location]
        x_tray, y_tray, z_tray = location.get_position(position)      

    def move_to(self, location, position):
        command = 'MOVE_ABS(,,0)\r\n'
        self.send_command(command)
        x_tray, y_tray, z_tray = location.get_position(position)
        command = f'MOVE_ABS({x_tray},{y_tray},{z_tray})\r\n'
        self.send_command(command)
        self.x = x_tray
        self.y = y_tray
        self.z = z_tray

    def move_free(self, x, y, z):
        command = f'MOVE_ABS({x},{y},{z})\r\n'
        self.send_command(command)
        self.x = x
        self.y = y
        self.z = z
        
    def return_z(self):
        command = "MOVE_ABS(,,0)\r\n"
        self.send_command(command)
        
    def move_rel(self, x, y, z):
        command = f'MOVE_REL({x},{y},{z})\r\n'
        self.send_command(command)
        
    def penetrate(self, penetration=33000):
        command = f"MOVE_REL(0,0,{penetration})\r\n"
        self.send_command(command)

    def get_penetration(self, location):
        if isinstance(location, str):
            location = all_trays[location]
        penetration = location.depth
        offsets = {10: 0,
                   100: -8500,
                   1000: -7500}
        penetration = location.depth + offsets[self.syringe]
        if penetration > 48000:
            penetration = 48000
        return penetration
            
    def motor(self, height, speed=5000):
        command = f"MOT_ABS(MPlgMed, {height}, {speed})\r\n"
        self.send_command(command)

    def get_height_per_ul(self, syringe):
        heights_per_ul = {10: 1900,
                          25: 790,
                          100: 198,
                          1000: 19.8}
        height_per_ul = heights_per_ul[syringe]
        return height_per_ul
    
    def get_speed_per_syringe(self, syringe):
        speeds_per_syringe = {10: 5000,
                              25: 5000,
                              100: 4000,
                              1000: 5000}
        speed = speeds_per_syringe[syringe]
        return speed
    
    def move_plunger(self, volume, speed=2000):
        height_per_ul = self.get_height_per_ul(self.syringe)
        height = round(volume*height_per_ul)
        self.motor(height, speed)
            
    def take_sample(self, location, position, volume, penetration=None, speed=None):
        if isinstance(location, str):
            location = all_trays[location]
        height_per_ml = self.get_height_per_ul(self.syringe)
        if not penetration:
            penetration = self.get_penetration(location)
        self.move_to(location, position)
        self.penetrate(penetration)
        height = round(volume*height_per_ml)
        if not speed:
            speed = self.get_speed_per_syringe(self.syringe)
        self.motor(height, speed)
        self.move_rel(0,0,(penetration+10000)*-1)
        
    def put_sample(self, location, position, penetration=None):
        if isinstance(location, str):
            location = all_trays[location]
        if not penetration:
            penetration = self.get_penetration(location)
        self.move_to(location, position)
        self.penetrate(penetration)
        speed = self.get_speed_per_syringe(self.syringe)
        if self.syringe == 10 or self.syringe == 100:
            speed = 100000
        self.motor(0, speed)
        
    def put_sample_rinse(self, location, position_to, penetration=None):
        if isinstance(location, str):
            location = all_trays[location]
        if not penetration:
            penetration = self.get_penetration(location)
        self.move_to(location, position_to)
        self.penetrate(penetration)
        speed = self.get_speed_per_syringe(self.syringe)
        if self.syringe == 10:
            speed = 100000
        self.motor(0, speed)
        self.move_plunger(5, 5000)
        self.motor(0, speed)
        
            
    def home(self):
        command = "MOVE_ABS(0,0,0)\r\n"
        self.send_command(command)
        self.x = self.home_x
        self.y = self.home_y
        self.z = self.home_z
        command = "MOT_ABS(MPlgMed, 0, 5000)\r\n"
        self.send_command(command)

head1 = Head(-1,0,0,port)

home1 = all_trays["home1"]
wash1 = all_trays["wash1"]
waste1 = all_trays["waste1"]

def time_stamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def wash(number):
    for i in range(number):
        head1.take_sample(wash1, 1, 50, speed=10000)
        head1.put_sample(waste1, 1, 25000)
    head1.home()

def home():
    head1.home()

def change():
    head1.move_free(-150000, 0, 60000)
    head1.motor(6000)

def sample_cycle(location_from, position_from, location_to, position_to, volume, syringe=25):
    head1.take_sample(location_from, position_from, volume)
    head1.put_sample(location_to, position_to)
    head1.home()

def sample_cycle_no_home(location_from, position_from, location_to, position_to, head, volume):
    head.take_sample(location_from, position_from, volume)
    head.put_sample(location_to, position_to)
    
def full_cycle(location_from, position_from, location_to, position_to, volume, number_of_washes, syringe=25):
    sample_cycle(location_from, position_from, location_to, position_to, volume)
    for i in range(number_of_washes):
        head1.wash(1, volume)
    head1.home()
    head1.beep(1968,1000)

def run_kinetics(number_of_reactions, location_from, position_from, location_to, number_of_samples, interval, number_of_washes, volume, starting_vial=1, syringe=25):
    for i in range(number_of_samples):
        start = time.time()
        print(f"Cycle: {str(i+1)} - Time: {time_stamp()}")
        for j in range(number_of_reactions):
            position_to = i+starting_vial+number_of_samples*j
            full_cycle(location_from, j+position_from, location_to, position_to, volume, number_of_washes, syringe=syringe)
        total_duration = time.time()-start
        print(f"Cycle duration: {str(total_duration)} seconds")
        wait_time = interval - total_duration
        if wait_time < 0:
            print(f"Duration {str(abs(wait_time))} longer than wait time")
            wait_time = 0
        time.sleep(wait_time)
        
def beep():
    head1.beep(1000, 1000)
    
if __name__ == "__main__":
    beep()
    # run_kinetics(number_of_reactions=2, location_from="49alu_tray1", position_from=1, location_to="sfc_tray1", number_of_samples=4, interval=60, number_of_washes=3, volume=3)
