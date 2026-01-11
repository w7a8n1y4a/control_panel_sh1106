from micropython import const
import utime as time
import framebuf


# a few register definitions
_SET_CONTRAST        = const(0x81)
_SET_NORM_INV        = const(0xa6)
_SET_DISP            = const(0xae)
_SET_SCAN_DIR        = const(0xc0)
_SET_SEG_REMAP       = const(0xa0)
_LOW_COLUMN_ADDRESS  = const(0x00)
_HIGH_COLUMN_ADDRESS = const(0x10)
_SET_PAGE_ADDRESS    = const(0xB0)


class SH1106(framebuf.FrameBuffer):

    def __init__(self, width, height, external_vcc, rotate=0):
        self.width = width
        self.height = height
        self.external_vcc = external_vcc
        self.flip_en = rotate == 180 or rotate == 270
        self.rotate90 = rotate == 90 or rotate == 270
        self.pages = self.height // 8
        self.bufsize = self.pages * self.width
        self.renderbuf = bytearray(self.bufsize)
        self.pages_to_update = 0
        self.delay = 0

        if self.rotate90:
            self.displaybuf = bytearray(self.bufsize)
            # HMSB is required to keep the bit order in the render buffer
            # compatible with byte-for-byte remapping to the display buffer,
            # which is in VLSB. Else we'd have to copy bit-by-bit!
            super().__init__(self.renderbuf, self.height, self.width,
                             framebuf.MONO_HMSB)
        else:
            self.displaybuf = self.renderbuf
            super().__init__(self.renderbuf, self.width, self.height,
                             framebuf.MONO_VLSB)

        # flip() was called rotate() once, provide backwards compatibility.
        self.rotate = self.flip
        self.init_display()

    # abstractmethod
    def write_cmd(self, *args, **kwargs):
        raise NotImplementedError

    # abstractmethod
    def write_data(self,  *args, **kwargs):
        raise NotImplementedError

    def init_display(self):
        self.reset()
        self.fill(0)
        self.show()
        self.poweron()
        # rotate90 requires a call to flip() for setting up.
        self.flip(self.flip_en)

    def poweroff(self):
        self.write_cmd(_SET_DISP | 0x00)

    def poweron(self):
        self.write_cmd(_SET_DISP | 0x01)
        if self.delay:
            time.sleep_ms(self.delay)

    def flip(self, flag=None, update=True):
        if flag is None:
            flag = not self.flip_en
        mir_v = flag ^ self.rotate90
        mir_h = flag
        self.write_cmd(_SET_SEG_REMAP | (0x01 if mir_v else 0x00))
        self.write_cmd(_SET_SCAN_DIR | (0x08 if mir_h else 0x00))
        self.flip_en = flag
        if update:
            self.show(True) # full update

    def sleep(self, value):
        self.write_cmd(_SET_DISP | (not value))

    def contrast(self, contrast):
        self.write_cmd(_SET_CONTRAST)
        self.write_cmd(contrast)

    def invert(self, invert):
        self.write_cmd(_SET_NORM_INV | (invert & 1))

    def show(self, full_update = False):
        # self.* lookups in loops take significant time (~4fps).
        (w, p, db, rb) = (self.width, self.pages,
                          self.displaybuf, self.renderbuf)
        if self.rotate90:
            for i in range(self.bufsize):
                db[w * (i % p) + (i // p)] = rb[i]
        if full_update:
            pages_to_update = (1 << self.pages) - 1
        else:
            pages_to_update = self.pages_to_update
        #print("Updating pages: {:08b}".format(pages_to_update))
        db_mv = memoryview(db)
        for page in range(self.pages):
            if (pages_to_update & (1 << page)):
                # SH1106 expects 3 commands per page; send them in one go to reduce bus overhead.
                self.write_cmd(
                    _SET_PAGE_ADDRESS | page,
                    _LOW_COLUMN_ADDRESS | 2,   # SH1106 column offset
                    _HIGH_COLUMN_ADDRESS | 0,
                )
                start = w * page
                self.write_data(db_mv[start:(start + w)])
        self.pages_to_update = 0

    def pixel(self, x, y, color=None):
        if color is None:
            return super().pixel(x, y)
        else:
            super().pixel(x, y , color)
            page = y // 8
            self.pages_to_update |= 1 << page

    def text(self, text, x, y, color=1):
        super().text(text, x, y, color)
        self.register_updates(y, y+7)

    def line(self, x0, y0, x1, y1, color):
        super().line(x0, y0, x1, y1, color)
        self.register_updates(y0, y1)

    def hline(self, x, y, w, color):
        super().hline(x, y, w, color)
        self.register_updates(y)

    def vline(self, x, y, h, color):
        super().vline(x, y, h, color)
        self.register_updates(y, y+h-1)

    def fill(self, color):
        super().fill(color)
        self.pages_to_update = (1 << self.pages) - 1

    def blit(self, fbuf, x, y, key=-1, palette=None):
        super().blit(fbuf, x, y, key, palette)
        self.register_updates(y, y+self.height)

    def scroll(self, x, y):
        # my understanding is that scroll() does a full screen change
        super().scroll(x, y)
        self.pages_to_update =  (1 << self.pages) - 1

    def fill_rect(self, x, y, w, h, color):
        super().fill_rect(x, y, w, h, color)
        self.register_updates(y, y+h-1)

    def rect(self, x, y, w, h, color):
        super().rect(x, y, w, h, color)
        self.register_updates(y, y+h-1)

    def ellipse(self, x, y, xr, yr, color):
        super().ellipse(x, y, xr, yr, color)
        self.register_updates(y-yr, y+yr-1)

    def register_updates(self, y0, y1=None):
        # this function takes the top and optional bottom address of the changes made
        # and updates the pages_to_change list with any changed pages
        # that are not yet on the list
        start_page = max(0, y0 // 8)
        end_page = max(0, y1 // 8) if y1 is not None else start_page
        # rearrange start_page and end_page if coordinates were given from bottom to top
        if start_page > end_page:
            start_page, end_page = end_page, start_page
        for page in range(start_page, end_page+1):
            self.pages_to_update |= 1 << page

    def reset(self, res=None):
        if res is not None:
            res(1)
            time.sleep_ms(1)
            res(0)
            time.sleep_ms(20)
            res(1)
            time.sleep_ms(20)


class SH1106_I2C(SH1106):
    def __init__(self, width, height, i2c, res=None, addr=0x3c,
                 rotate=0, external_vcc=False, delay=0):
        self.i2c = i2c
        self.addr = addr
        self.res = res
        # Pre-allocated buffers to avoid per-call allocations (critical for speed on ESP8266).
        # Use 0x80 (Co=1, D/C#=0) like the original driver did; it's the most compatible.
        self._cmd1_buf = bytearray(2)  # [0x80, cmd]
        self._cmd1_buf[0] = 0x80
        self._cmd2_buf = bytearray(4)  # [0x80, c1, 0x80, c2]
        self._cmd2_buf[0] = 0x80
        self._cmd2_buf[2] = 0x80
        self._cmd3_buf = bytearray(6)  # [0x80,c1,0x80,c2,0x80,c3]
        self._cmd3_buf[0] = 0x80
        self._cmd3_buf[2] = 0x80
        self._cmd3_buf[4] = 0x80
        self._page_buf = bytearray(width + 1)  # 1 control + 128 bytes data
        self._page_buf[0] = 0x40               # Co=0, D/C#=1 (data stream)
        # Fast per-page TX: [0x80, page, 0x80, low_col, 0x80, high_col, 0x40, <width bytes>]
        # Important: using 0x80 (Co=1) allows switching to 0x40 (data) inside the same I2C transaction.
        self._page_tx = bytearray(width + 7)
        self._page_tx[0] = 0x80
        self._page_tx[2] = 0x80
        self._page_tx[4] = 0x80
        self._page_tx[6] = 0x40
        self.delay = delay
        if res is not None:
            res.init(res.OUT, value=1)
        super().__init__(width, height, external_vcc, rotate)

    def write_cmd(self, *cmds):
        # Support multiple commands per I2C transaction to reduce overhead.
        n = len(cmds)
        if n == 1:
            self._cmd1_buf[1] = cmds[0]
            self.i2c.writeto(self.addr, self._cmd1_buf)
            return
        if n == 2:
            b = self._cmd2_buf
            b[1] = cmds[0]
            b[3] = cmds[1]
            self.i2c.writeto(self.addr, b)
            return
        if n == 3:
            b = self._cmd3_buf
            b[1] = cmds[0]
            b[3] = cmds[1]
            b[5] = cmds[2]
            self.i2c.writeto(self.addr, b)
            return
        # Fallback for uncommon longer command sequences.
        tmp = bytearray(n * 2)
        j = 0
        for c in cmds:
            tmp[j] = 0x80
            tmp[j + 1] = c
            j += 2
        self.i2c.writeto(self.addr, tmp)

    def write_data(self, buf):
        # Fast path: full page writes (width bytes). Avoids allocating b'\x40'+buf each call.
        if len(buf) == (len(self._page_buf) - 1):
            self._page_buf[1:] = buf
            self.i2c.writeto(self.addr, self._page_buf)
            return
        # Fallback for non-standard lengths.
        tmp = bytearray(len(buf) + 1)
        tmp[0] = 0x40
        tmp[1:] = buf
        self.i2c.writeto(self.addr, tmp)

    def show(self, full_update=False):
        # Faster I2C show(): 1 I2C transaction per updated page (cmds+data together).
        (w, p, db, rb) = (self.width, self.pages, self.displaybuf, self.renderbuf)
        if self.rotate90:
            for i in range(self.bufsize):
                db[w * (i % p) + (i // p)] = rb[i]

        if full_update:
            pages_to_update = (1 << self.pages) - 1
        else:
            pages_to_update = self.pages_to_update

        if not pages_to_update:
            return

        # Optional optimization: caller may provide per-page dirty column ranges.
        # Expected format: {page: (x0, x1)} where x0/x1 are inclusive byte columns in [0..width-1].
        ranges = getattr(self, "_page_ranges", None)

        tx = self._page_tx
        tx_mv = memoryview(tx)
        db_mv = memoryview(db)
        for page in range(self.pages):
            if pages_to_update & (1 << page):
                tx[1] = _SET_PAGE_ADDRESS | page
                if ranges is not None and page in ranges:
                    x0, x1 = ranges[page]
                    if x0 < 0:
                        x0 = 0
                    if x1 >= w:
                        x1 = w - 1
                    if x1 < x0:
                        continue
                    n = (x1 - x0 + 1)
                    # If the changed range is "almost full page", treat it as full page:
                    # avoids memoryview slicing (alloc) and keeps a constant-size I2C write.
                    if n >= (w - 8):
                        tx[3] = _LOW_COLUMN_ADDRESS | 2
                        tx[5] = _HIGH_COLUMN_ADDRESS | 0
                        start = page * w
                        tx[7:] = db_mv[start:(start + w)]
                        self.i2c.writeto(self.addr, tx)
                    else:
                        col = x0 + 2  # SH1106 column offset
                        tx[3] = _LOW_COLUMN_ADDRESS | (col & 0x0F)
                        tx[5] = _HIGH_COLUMN_ADDRESS | ((col >> 4) & 0x0F)
                        start = (page * w) + x0
                        tx[7:(7 + n)] = db_mv[start:(start + n)]
                        self.i2c.writeto(self.addr, tx_mv[:(7 + n)])
                else:
                    tx[3] = _LOW_COLUMN_ADDRESS | 2
                    tx[5] = _HIGH_COLUMN_ADDRESS | 0
                    start = page * w
                    tx[7:] = db_mv[start:(start + w)]
                    self.i2c.writeto(self.addr, tx)

        self.pages_to_update = 0
        if ranges is not None:
            # Avoid accidentally reusing stale ranges on the next show().
            self._page_ranges = None  # noqa: SLF001

    def reset(self,res=None):
        super().reset(self.res)


class SH1106_SPI(SH1106):
    def __init__(self, width, height, spi, dc, res=None, cs=None,
                 rotate=0, external_vcc=False, delay=0):
        dc.init(dc.OUT, value=0)
        if res is not None:
            res.init(res.OUT, value=0)
        if cs is not None:
            cs.init(cs.OUT, value=1)
        self.spi = spi
        self.dc = dc
        self.res = res
        self.cs = cs
        self.delay = delay
        super().__init__(width, height, external_vcc, rotate)

    def write_cmd(self, *cmds):
        if self.cs is not None:
            self.cs(1)
            self.dc(0)
            self.cs(0)
            if len(cmds) == 1:
                self.spi.write(bytearray([cmds[0]]))
            else:
                self.spi.write(bytearray(cmds))
            self.cs(1)
        else:
            self.dc(0)
            if len(cmds) == 1:
                self.spi.write(bytearray([cmds[0]]))
            else:
                self.spi.write(bytearray(cmds))

    def write_data(self, buf):
        if self.cs is not None:
            self.cs(1)
            self.dc(1)
            self.cs(0)
            self.spi.write(buf)
            self.cs(1)
        else:
            self.dc(1)
            self.spi.write(buf)

    def reset(self, res=None):
        super().reset(self.res)