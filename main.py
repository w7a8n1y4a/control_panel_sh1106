import gc
import machine
import sh1106
import time
import uasyncio as asyncio

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

_B64_TABLE = bytearray(256)
for _i in range(256):
    _B64_TABLE[_i] = 0xFF
for _i, _c in enumerate(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"):
    _B64_TABLE[_c] = _i
del _i, _c

def _decode_full_frame_base64_into(payload, out_buf):
    if payload is None:
        raise ValueError("empty payload")
    if isinstance(payload, str):
        payload = payload.strip().encode()

    out_idx = 0
    quad_idx = 0
    quad0 = 0
    quad1 = 0
    quad2 = 0
    pad = 0
    seen_pad = False

    for b in payload:
        if b <= 32:
            continue
        if b == 61:  # '='
            seen_pad = True
            pad += 1
            if pad > 2:
                raise ValueError("incorrect padding")
            v = 0
        else:
            if seen_pad:
                raise ValueError("incorrect padding")
            v = _B64_TABLE[b]
            if v == 0xFF:
                raise ValueError("bad base64 char")

        if quad_idx == 0:
            quad0 = v
            quad_idx = 1
            continue
        if quad_idx == 1:
            quad1 = v
            quad_idx = 2
            continue
        if quad_idx == 2:
            quad2 = v
            quad_idx = 3
            continue

        out_buf[out_idx] = (quad0 << 2) | (quad1 >> 4)
        out_idx += 1
        if pad < 2:
            out_buf[out_idx] = ((quad1 & 0x0F) << 4) | (quad2 >> 2)
            out_idx += 1
        if pad == 0:
            out_buf[out_idx] = ((quad2 & 0x03) << 6) | v
            out_idx += 1

        quad_idx = 0
        pad = 0

    if quad_idx != 0:
        raise ValueError("incorrect padding")
    if out_idx != len(out_buf):
        raise ValueError("bad frame size: got %d, expected %d" % (out_idx, len(out_buf)))
    return out_buf


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
            gc.collect()
            if gc.mem_free() < 500:
                return
            with client.mqtt_client.drop_input():
                # Decode directly into display.renderbuf — saves 1024 bytes vs separate frame_buf
                rb = display.renderbuf
                _decode_full_frame_base64_into(msg.payload, rb)
                await asyncio.sleep_ms(0)
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
    await client.run_main_cycle(10)


if __name__ == '__main__':
    try:
        asyncio.run(main_async(client))
    except KeyboardInterrupt:
        raise
    except Exception as e:
        client.logger.critical("Error with reset: {}".format(e), file_only=True)
        client.restart_device()
