from micropython import const
import utime as time


_SET_DISP = const(0xAE)
_SET_PAGE_ADDRESS = const(0xB0)
_LOW_COLUMN_ADDRESS = const(0x00)
_HIGH_COLUMN_ADDRESS = const(0x10)


class SH1106_I2C:
    def __init__(
        self,
        width,
        height,
        i2c,
        res=None,
        addr=0x3C,
        rotate=0,
        external_vcc=False,
        delay=0,
    ):
        # rotate/external_vcc kept for compatibility with existing constructor calls.
        self.width = width
        self.height = height
        self.pages = height // 8
        self.bufsize = self.pages * width
        self.i2c = i2c
        self.addr = addr
        self.res = res
        self.delay = delay
        self.renderbuf = bytearray(self.bufsize)

        # [0x80, cmd]
        self._cmd1 = bytearray(2)
        self._cmd1[0] = 0x80

        # [0x80, page, 0x80, low_col, 0x80, high_col, 0x40, <width bytes>]
        self._page_tx = bytearray(width + 7)
        self._page_tx[0] = 0x80
        self._page_tx[2] = 0x80
        self._page_tx[4] = 0x80
        self._page_tx[6] = 0x40

        if res is not None:
            res.init(res.OUT, value=1)

        self._init_display()

    def _write_cmd(self, cmd):
        b = self._cmd1
        b[1] = cmd
        self.i2c.writeto(self.addr, b)

    def _init_display(self):
        self.reset()
        self.sleep(False)
        # Clear screen once at start.
        rb = self.renderbuf
        for i in range(self.bufsize):
            rb[i] = 0
        self.render_full_frame(rb)

    def reset(self):
        res = self.res
        if res is None:
            return
        res(1)
        time.sleep_ms(1)
        res(0)
        time.sleep_ms(20)
        res(1)
        time.sleep_ms(20)

    def sleep(self, value):
        self._write_cmd(_SET_DISP | (0x00 if value else 0x01))
        if not value and self.delay:
            time.sleep_ms(self.delay)

    def render_full_frame(self, frame):
        if len(frame) != self.bufsize:
            raise ValueError("bad frame size: got %d, expected %d" % (len(frame), self.bufsize))

        w = self.width
        tx = self._page_tx
        tx_mv = memoryview(tx)
        frame_mv = memoryview(frame)
        for page in range(self.pages):
            tx[1] = _SET_PAGE_ADDRESS | page
            tx[3] = _LOW_COLUMN_ADDRESS | 2  # SH1106 column offset
            tx[5] = _HIGH_COLUMN_ADDRESS | 0
            start = page * w
            tx[7:] = frame_mv[start:(start + w)]
            self.i2c.writeto(self.addr, tx_mv)
