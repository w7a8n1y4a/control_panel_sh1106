import gc
import machine
import ubinascii
import sh1106
import time

from pepeunit_micropython_client.client import PepeunitClient
from pepeunit_micropython_client.enums import SearchTopicType, SearchScope


display = None
frame_count = 0

def parse_i2c_address(value):
    if isinstance(value, str):
        s = value.strip().lower()
        if s.startswith("0x"):
            return int(s, 16)
    raise TypeError("I2C_ADDRESS in env.json must be str with format \"0x3c\"")

def init_display(client):
    global display
    i2c = machine.I2C(
            scl=machine.Pin(client.settings.PIN_SCL),
            sda=machine.Pin(client.settings.PIN_SDA),
            freq=client.settings.I2C_FREQUENCY
        )
    display = sh1106.SH1106_I2C(
            client.settings.DISPLAY_WIDTH,
            client.settings.DISPLAY_HEIGHT,
            i2c,
            machine.Pin(16), 
            addr=parse_i2c_address(client.settings.I2C_ADDRESS)
        )
    display.fill(0)
    gc.collect()

def output_handler(client: PepeunitClient):
    pass

def _decode_full_frame_base64(payload_str, expected_size):
    if payload_str is None:
        raise ValueError("empty payload")

    s = payload_str.strip()
    if not s:
        raise ValueError("empty payload")

    raw = ubinascii.a2b_base64(s)
    if len(raw) != expected_size:
        raise ValueError("bad frame size: got %d, expected %d" % (len(raw), expected_size))
    return raw

def _write_frame_direct(display, frame):
    w = display.width
    pages = display.pages
    mv = memoryview(frame)
    for page in range(pages):
        display.write_cmd(0xB0 | page, 0x00 | 2, 0x10 | 0)
        start = page * w
        display.write_data(mv[start:(start + w)])

def input_handler(client: PepeunitClient, msg):
    global frame_count
    parts = msg.topic.split('/')

    if len(parts) == 3:
        topic_name = client.schema.find_topic_by_unit_node(parts[1], SearchTopicType.UNIT_NODE_UUID, SearchScope.INPUT)

        if topic_name == 'full_frame/pepeunit':
            global display
            if display is None:
                return

            if client.settings.PU_MIN_LOG_LEVEL == 'Debug':
                print(f"Frame {frame_count}, Time {time.ticks_ms()}")
                frame_count += 1

            try:
                frame = _decode_full_frame_base64(msg.payload, display.bufsize)
                try:
                    display.write_frame(frame)
                except AttributeError:
                    _write_frame_direct(display, frame)
            except Exception as e:
                try:
                    client.logger.warning("full_frame decode/show error: %s" % (e,), file_only=True)
                except Exception:
                    pass


def main(client: PepeunitClient):
    client.set_mqtt_input_handler(input_handler)
    client.mqtt_client.connect()
    client.subscribe_all_schema_topics()
    client.set_output_handler(output_handler)

    init_display(client)

    global display

    display.sleep(False)
    display.fill(0)
    display.text("Run cycle", 0, 0, 1)
    display.show()
    
    client.run_main_cycle()


if __name__ == '__main__':
    try:
        main(client)
    except KeyboardInterrupt:
        raise
    except Exception as e:
        client.logger.critical(f"Error with reset: {str(e)}", file_only=True)
        client.restart_device()
