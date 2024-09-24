import paho.mqtt.client as mqttClient
import json
import sys
import time
import ssl

# Configuration
player_file = sys.argv[1]
current_player_id = int(player_file.split('-')[1].split('.')[0])

# Broker information
# broker_address = "127.0.0.1"
# broker_port = 1883

# Topics 
topic_root = "game/players/"
topic_status = f"{topic_root}status"
topic_death = f"{topic_root}death"
topic_join = f"{topic_root}join"


# Reading moves from given text file
def read_moves_from_files(filename):
    with open(filename, 'r') as f:
        lines = f.readlines()
    Number_Players = int(lines[0].strip())
    moves = [tuple(map(int, line.strip().split())) for line in lines[1:]]
    return Number_Players, moves

# getting No of players and all moves
Number_Players, moves = read_moves_from_files(player_file)
isAlive = True
player_positions = {}
player_joined = 0
killed_players = set()  # Set to track killed players

# MQTT Handlers
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"\n\tPlayer {current_player_id} connected to Game")
        client.subscribe([(topic_status, 0), (topic_death, 0), (topic_join+'/#', 0)])
    else:
        print(f"Connection failed with code {rc}")

def on_message(client, userdata, message):
    global isAlive, player_joined, killed_players
    topic = message.topic
    if message.payload.decode() != "":
        msg = json.loads(message.payload.decode())
        if topic == topic_death:
            victim = msg['victim']
            if victim == current_player_id:
                isAlive = False
                client.disconnect()
                print(f"\n\t******You have been killed by {msg['killer']}******")
            else:
                killed_players.add(victim)  # Track this player as killed
        elif topic == topic_status:
            status_update(msg)



# Publishing status info
def statusPublish(client, x, y, pow):
    if isAlive:
        msg = {'id': current_player_id, 'x': x, 'y': y, 'power': pow}
        client.publish(topic_status, json.dumps(msg))

# Updating status info
def status_update(msg):
    global player_positions
    player_positions[msg['id']] = (msg['x'], msg['y'], msg['power'])
    checkNeighbours(client, msg['id'], msg['x'], msg['y'], msg['power'])


# Checking given player neighbour or not
def is_neighbour(x, x1, y, y1):
    return abs(x - x1) <= 1 and abs(y - y1) <= 1

# Checking is_neighbour and power 
def checkNeighbours(client, playerID, x, y, pow):
    for other_id, (x1, y1, pow1) in player_positions.items():
        if playerID != other_id and is_neighbour(x, x1, y, y1):
            if pow == 1 and pow1 == 0:
                publishDeath(client, other_id, playerID)
            elif pow == 0 and pow1 == 1:
                publishDeath(client, playerID, other_id)

# Publishing Death info to all
def publishDeath(client, victim, killer):
    global killed_players
    if victim not in killed_players:
        killed_players.add(victim)
        msg = {'victim': victim, 'killer': killer}
        client.publish(topic_death, json.dumps(msg))
        if victim != current_player_id:
            print(f"\n\tPlayer {killer} eliminated Player {victim}")

# MQTT Client Setup
# client = mqttClient.Client(mqttClient.CallbackAPIVersion.VERSION1,client_id=f"player_{current_player_id}")
# client.on_connect = on_connect
# client.on_message = on_message
# client.connect(broker_address, broker_port)
# client.loop_start()

client_name = f"player-{current_player_id}"
#AWS_PART
client = mqttClient.Client(mqttClient.CallbackAPIVersion.VERSION1, client_name)  # create new instance
client.on_connect = on_connect  # attach function to callback
client.on_message = on_message  # attach function to callback

awshost = "ax8a2xqlbswvx-ats.iot.us-east-1.amazonaws.com" #replace
awsport = 8883

caPath = "./root-CA.crt" # Root certificate authority, comes from AWS (Replace)
certPath = "./Game.cert.pem" #Replace
keyPath = "./Game.private.key" #Replace

client.tls_set(caPath, 
    certfile=certPath, 
    keyfile=keyPath, 
    cert_reqs=ssl.CERT_REQUIRED, 
    tls_version=ssl.PROTOCOL_TLSv1_2, ciphers=None)

client.connect(awshost, port = awsport)  # connect to broker
#AWS PART ENDS

client.loop_start()

print("\n\tWaiting for all players to join. Match starts shortly...")

time.sleep(3)
print("\n\t*********Game Started**********")
try:
    for coordinat_x, coordinate_y, pow in moves:
        if isAlive:
            statusPublish(client, coordinat_x, coordinate_y, pow)
            time.sleep(2)
finally:
    for i in range(Number_Players):
        client.publish(topic_join + f"/{i+1}", b"", retain=True)
    client.loop_stop()
    client.disconnect()
    if isAlive:
        print(f"\n\t******Player {current_player_id} is the winner!******")

