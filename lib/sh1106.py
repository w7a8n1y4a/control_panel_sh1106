from micropython import const


_SET_DISP = const(0xAE)
_SET_PAGE_ADDRESS = const(0xB0)
_LOW_COLUMN_ADDRESS = const(0x00)
_HIGH_COLUMN_ADDRESS = const(0x10)


class SH1106_I2C:
    def __init__(self, width, height, i2c, addr=0x3C):
        self.width = width
        self.height = height
        self.pages = height // 8
        self.bufsize = self.pages * width
        self.i2c = i2c
        self.addr = addr
        self.renderbuf = bytearray(self.bufsize)

        self._cmd1 = bytearray(2)
        self._cmd1[0] = 0x80

        self._page_tx = bytearray(width + 7)
        self._page_tx[0] = 0x80
        self._page_tx[2] = 0x80
        self._page_tx[4] = 0x80
        self._page_tx[6] = 0x40

        self._init_display()

    def _write_cmd(self, cmd):
        b = self._cmd1
        b[1] = cmd
        self.i2c.writeto(self.addr, b)

    def _init_display(self):
        self._write_cmd(_SET_DISP | 0x01)
        rb = self.renderbuf
        for i in range(self.bufsize):
            rb[i] = 0
        self.render_full_frame(rb)

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
