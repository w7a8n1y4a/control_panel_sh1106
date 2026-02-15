import gc
import machine
import sh1106
import time
import uasyncio as asyncio
import ubinascii

from pepeunit_micropython_client.client import PepeunitClient


display = None
frame_count = 0
FULL_FRAME_TOPICS = ()

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


async def input_handler(client: PepeunitClient, msg):
    global frame_count
    if msg.topic in FULL_FRAME_TOPICS:
        global display
        if display is None:
            return

        if client.settings.PU_MIN_LOG_LEVEL == 'Debug':
            print("Frame", frame_count, "Time", time.ticks_ms(), "Free",
                  gc.mem_free(), "Alloc", gc.mem_alloc(), "Len", len(msg.payload))
        frame_count += 1
        try:
            if gc.mem_free() < 5000:
                gc.collect()
            if gc.mem_free() < 500:
                return
            with client.mqtt_client.drop_input():
                rb = display.renderbuf
                decoded = ubinascii.a2b_base64(msg.payload)
                if len(decoded) != len(rb):
                    raise ValueError("bad frame size: got %d, expected %d" % (len(decoded), len(rb)))
                rb[:] = decoded
                del decoded
                display.render_full_frame(rb)
        except Exception as e:
            try:
                client.logger.warning("full_frame decode error: %s" % (e,), file_only=True)
            except Exception:
                pass


async def main_async(client: PepeunitClient):
    global FULL_FRAME_TOPICS
    FULL_FRAME_TOPICS = client.schema.input_topic.get('full_frame/pepeunit') or ()

    client.set_mqtt_input_handler(input_handler)

    gc.collect()
    await client.mqtt_client.connect()

    gc.collect()
    await client.mqtt_client.subscribe_all_schema_topics()
    client.set_output_handler(None)

    gc.collect()
    init_display(client)

    gc.collect()
    await client.run_main_cycle(100)


if __name__ == '__main__':
    try:
        asyncio.run(main_async(client))
    except KeyboardInterrupt:
        raise
    except Exception as e:
        client.logger.critical("Error with reset: {}".format(e), file_only=True)
        client.restart_device()
