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
_controller = None

ENCODER_POLL_MS = 1


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


async def _publish_encoder_action(client, action):
    await client.publish_to_topics('encoder_action/pepeunit', action)


def init_encoder(client):
    from encoder import EncoderButton

    pin_button = machine.Pin(int(client.settings.PIN_BUTTON), machine.Pin.IN, machine.Pin.PULL_UP)
    pin_encoder_clk = machine.Pin(int(client.settings.PIN_ENCODER_CLK), machine.Pin.IN, machine.Pin.PULL_UP)
    pin_encoder_dt = machine.Pin(int(client.settings.PIN_ENCODER_DT), machine.Pin.IN, machine.Pin.PULL_UP)

    def on_button(kind):
        asyncio.create_task(_publish_encoder_action(client, kind))
        return kind

    def on_rotate(direction):
        asyncio.create_task(_publish_encoder_action(client, direction))
        return direction

    return EncoderButton(
        pin_button=pin_button,
        pin_encoder_clk=pin_encoder_clk,
        pin_encoder_dt=pin_encoder_dt,
        encoder_enabled=True,
        button_debounce_ms=int(client.settings.BUTTON_DEBOUNCE_TIME),
        button_double_click_ms=int(client.settings.BUTTON_DOUBLE_CLICK_TIME),
        button_long_press_ms=int(client.settings.BUTTON_LONG_PRESS_TIME),
        encoder_debounce_ms=int(client.settings.ENCODER_DEBOUNCE_TIME),
        on_button=on_button,
        on_rotate=on_rotate,
    )


async def _encoder_poll_task(client, controller):
    while True:
        now_ms = client.time_manager.get_epoch_ms()
        controller.handle_encoder(now_ms)
        controller.handle_button(now_ms)
        await asyncio.sleep_ms(ENCODER_POLL_MS)


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
    global FULL_FRAME_TOPICS, _controller
    FULL_FRAME_TOPICS = client.schema.input_topic.get('full_frame/pepeunit') or ()

    client.set_mqtt_input_handler(input_handler)

    gc.collect()
    await client.mqtt_client.subscribe_all_schema_topics()
    client.set_output_handler(None)

    gc.collect()
    init_display(client)

    if client.settings.FF_ENCODER_ENABLE:
        gc.collect()
        _controller = init_encoder(client)
        asyncio.create_task(_encoder_poll_task(client, _controller))

    gc.collect()
    await client.run_main_cycle(100)


if __name__ == '__main__':
    try:
        freq = client.settings.FREQ
        machine.freq(freq)
        asyncio.run(main_async(client))
    except KeyboardInterrupt:
        raise
    except Exception as e:
        if getattr(e, 'errno', None) == 19:
            raise
        client.logger.critical("Error with reset: {}".format(e), file_only=True)
        client.restart_device()
