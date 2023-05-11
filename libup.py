
# import random
import time, logging, sys

from paho.mqtt import client as mqtt_client

broker = 'localhost'
port = 1883

class MqttSwitch:

    def __init__(self, topic):

        logging.info("start MQTT switch!")

        self.topic = topic

        self.connected = False

        # xxx base
        self.client = mqtt_client.Client("clientid99")
        # client.username_pw_set(username, password)
        self.client.on_connect = self.on_connect
        self.client.connect(broker, port)
        self.client.loop_start()

        self.state = None
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
                self.nextUpdate = t + 60
            else:
                logging.info(f"Failed to send message to topic {self.topic}")
            return status

        if t >= self.nextUpdate:

            # result: [0, 1]
            status = self.client.publish(self.topic, msg)[0]
            if status == 0:
                logging.info(f"Send `{msg}` to topic `{self.topic}` ok")
                self.nextUpdate = t + 60
            else:
                logging.info(f"Failed to send message to topic {self.topic}")

        else:

            logging.info(f"throttling publish() {self.nextUpdate - t}...")

        return status

# logging.basicConfig(level=logging.DEBUG)
# m = MqttSwitch("cmnd/tasmota_exess_power/POWER")
# while not m.connected:
    # time.sleep(1)
# m.publish(sys.argv[1])

