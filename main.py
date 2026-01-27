import gc
import machine
import ubinascii
import sh1106
import time

from pepeunit_micropython_client.client import PepeunitClient
from pepeunit_micropython_client.enums import SearchTopicType, SearchScope


display = None
frame_count = 0
pending_payload = None
render_frame = None
render_page = 0

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

def output_handler(client: PepeunitClient):
    global pending_payload, render_frame, render_page
    global display

    if display is None:
        return

    if render_frame is not None:
        try:
            _write_frame_page(display, render_frame, render_page)
            render_page += 1
            if render_page >= display.pages:
                render_frame = None
                render_page = 0
                if gc.mem_free() < 9000:
                    gc.collect()
        except Exception as e:
            render_frame = None
            render_page = 0
            try:
                client.logger.warning("full_frame render error: %s" % (e,), file_only=True)
            except Exception:
                pass
        return

    if pending_payload is None:
        return
    payload = pending_payload
    pending_payload = None

    try:
        render_frame = _decode_full_frame_base64(payload, display.bufsize)
        render_page = 0
        payload = None
    except Exception as e:
        render_frame = None
        render_page = 0
        try:
            client.logger.warning("full_frame decode error: %s" % (e,), file_only=True)
        except Exception:
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


def _write_frame_page(display, frame, page):
    w = display.width
    mv = memoryview(frame)
    display.write_cmd(0xB0 | page, 0x00 | 2, 0x10 | 0)
    start = page * w
    display.write_data(mv[start:(start + w)])

def input_handler(client: PepeunitClient, msg):
    global frame_count, pending_payload
    topics = client.schema.input_topic.get('full_frame/pepeunit')
    if msg.topic in topics:
        global display
        if display is None:
            return

        if client.settings.PU_MIN_LOG_LEVEL == 'Debug':
            print("Frame", frame_count, "Time", time.ticks_ms(), "Free",
                  gc.mem_free(), "Alloc", gc.mem_alloc(), "Len", len(msg.payload))
        frame_count += 1
        pending_payload = msg.payload


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
