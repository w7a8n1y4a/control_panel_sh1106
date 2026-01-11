import gc
import machine
import ubinascii
import time

import sh1106

from pepeunit_micropython_client.client import PepeunitClient
from pepeunit_micropython_client.enums import SearchTopicType, SearchScope


display = None
inc = 0

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
    display._prev_frame = bytearray(display.bufsize)  # noqa: SLF001 (micropython style)
    display._prev_frame_valid = False  # noqa: SLF001
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

def input_handler(client: PepeunitClient, msg):
    global inc
    parts = msg.topic.split('/')

    if len(parts) == 3:
        topic_name = client.schema.find_topic_by_unit_node(parts[1], SearchTopicType.UNIT_NODE_UUID, SearchScope.INPUT)

        if topic_name == 'full_frame/pepeunit':
            global display
            if display is None:
                return

            try:
                one = time.ticks_ms()
                frame = _decode_full_frame_base64(msg.payload, display.bufsize)
                two = time.ticks_ms()
                w = display.width
                pages = display.pages
                prev = display._prev_frame  # noqa: SLF001
                if not display._prev_frame_valid:  # noqa: SLF001
                    pages_to_update = (1 << pages) - 1
                    display.renderbuf[:] = frame
                    prev[:] = frame
                    display._prev_frame_valid = True  # noqa: SLF001
                else:
                    pages_to_update = 0
                    for page in range(pages):
                        start = page * w
                        end = start + w
                        if frame[start:end] != prev[start:end]:
                            pages_to_update |= 1 << page
                            display.renderbuf[start:end] = frame[start:end]
                            prev[start:end] = frame[start:end]

                three = time.ticks_ms()
                if pages_to_update:
                    display.pages_to_update = pages_to_update
                    display.show(False)
                four = time.ticks_ms()

                updated_pages = 0
                m = pages_to_update
                while m:
                    updated_pages += (m & 1)
                    m >>= 1

                print(f"{one} - {inc} - {two} - {three} - {four} : {two-one} + {three-two} + {four-three} (pages {updated_pages})")
                inc += 1
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
    display.text("Hello World", 0, 0, 1)
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
