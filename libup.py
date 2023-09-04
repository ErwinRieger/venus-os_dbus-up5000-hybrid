
# import random
import time, logging, sys

from paho.mqtt import client as mqtt_client

broker = 'localhost'
port = 1883

class MqttSwitch:

    def __init__(self, clientId, topic, rate=60):

        logging.info("start MQTT switch!")

        self.topic = topic

        self.connected = False

        # xxx base
        self.client = mqtt_client.Client(clientId)
        # client.username_pw_set(username, password)
        self.client.on_connect = self.on_connect
        self.client.connect(broker, port)
        self.client.loop_start()

        self.state = None
        self.rate = rate
        self.nextUpdate = time.time()

    # xxx base
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logging.info("Connected to MQTT Broker!")
            self.connected = True
        else:
            logging.info("Failed to connect, return code %d\n", rc)

    # xxx base
    def publish(self, msg):

        if not self.connected:
            logging.info(f"MqttSwitch.publish(): not connected!")
            return 1

        t = time.time()
        status = 0

        if msg != self.state:
            # publish instantly
            status = self.client.publish(self.topic, msg)[0]
            if status == 0:
                logging.info(f"Send `{msg}` to topic `{self.topic}` ok")
                self.state = msg
                self.nextUpdate = t + self.rate
            else:
                logging.info(f"Failed to send message to topic {self.topic}")
            return status

        if t >= self.nextUpdate:

            # result: [0, 1]
            status = self.client.publish(self.topic, msg)[0]
            if status == 0:
                logging.info(f"Send `{msg}` to topic `{self.topic}` ok")
                self.nextUpdate = t + self.rate
            else:
                logging.info(f"Failed to send message to topic {self.topic}")

        else:

            logging.info(f"throttling publish() {self.nextUpdate - t}...")

        return status

class TasmotaSwitch:

    def __init__(self, topic):

        logging.info("start TasmotaSwitch !")

        self.topic = topic

        self.connected = False

        # xxx base
        self.client = mqtt_client.Client(topic)
        # client.username_pw_set(username, password)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.connect(broker, port)

        self.state = None
        self.start = 0

    # xxx base
    def on_connect(self, client, userdata, flags, rc):
      try:
        if rc == 0:
            logging.info("Connected to MQTT Broker!")
            self.connected = True
            self.subscribe()
        else:
            logging.info("Failed to connect, return code %d\n", rc)
      except:
          print("EXCEPTION in on_connect()!\n")

    # xxx base
    def on_disconnect(client, userdata,rc=0):
        logging.debug("mqtt: DisConnected !\n")
        self.connected = False

    # xxx base
    def publish(self, msg):

        if self.start:
            print("TasmotaSwitch.publish(): already started, ignoring call\n")
            return

        if not self.connected:
            logging.info(f"MqttSwitch.publish(): not connected!")
            return 1

        topic="cmnd/"+self.topic

        t = time.time()
        status = 0

        if msg != self.state:
            status = self.client.publish(topic, msg, 1, True)[0]
            if status == 0:
                logging.info(f"Send `{msg}` to topic `{topic}` ok")
                self.state = msg
                # self.nextUpdate = t + self.rate
                self.start = t
            else:
                logging.info(f"Failed to send message to topic {topic}")
            return status

        return status

    def subscribe(self):
        # self.start, timeout
        def on_message(client, userdata, msg):

            state = msg.payload.decode().lower()
            print(f"Received `{state}` from `{msg.topic}` topic")
            self.state = state
            self.start = 0

        topic="stat/"+self.topic

        res = self.client.subscribe(topic)[0]
        print(f"subscribe '{topic}', res: ", res)
        self.client.on_message = on_message

    def update(self):

        # print("update: calling mqtt.loop...\n")
        self.client.loop()

        if self.start:

            t = time.time()
            d = t - self.start
            if self.start and d > 5:
                print(f"mqtt[{self.topic}]: timeout ({d}s) waiting for ack...")
                self.start = 0
                return False

        return True

    def running(self):
        return self.start

class OnOffSwitch:

    def __init__(self, topic, switch):

        logging.info("start OnOffSwitch !")

        self.switch = TasmotaSwitch(topic+"/"+switch)
        self.state = None

    def pulse(self):
        if self.switch.publish("on") == 0:
            self.state = "on"

    def connected(self):
        return self.switch.connected

    def running(self):
        return self.switch.running()

    def update(self):

        # print("update: calling mqtt.loop...\n")

        self.switch.update()

        if self.state == "on":
            if not self.switch.running():
                # on phase done, switch off
                if self.switch.publish("off") == 0:
                    self.state = "off"
        elif self.state == "off":
            if not self.switch.running():
                # of phase done, pulse done
                self.state = None

# logging.basicConfig(level=logging.DEBUG)
# m = MqttSwitch("cmnd/tasmota_exess_power/POWER")
# while not m.connected:
    # time.sleep(1)
# m.publish(sys.argv[1])

