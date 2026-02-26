import machine
import time


class EncoderButton:
    _ENC_TRANSITIONS = (
        0, -1,  1,  0,
        1,  0,  0, -1,
       -1,  0,  0,  1,
        0,  1, -1,  0,
    )

    def __init__(
        self,
        *,
        pin_button,
        pin_encoder_clk=None,
        pin_encoder_dt=None,
        button_debounce_ms=20,
        button_double_click_ms=250,
        button_long_press_ms=400,
        encoder_enabled=True,
        steps_per_detent=4,
        on_button=None,
        on_rotate=None,
    ):
        if pin_button is None:
            raise ValueError("pin_button is required")

        self.pin_button = pin_button
        self.pin_encoder_clk = pin_encoder_clk
        self.pin_encoder_dt = pin_encoder_dt

        self.button_debounce_ms = int(button_debounce_ms)
        self.button_double_click_ms = int(button_double_click_ms)
        self.button_long_press_ms = int(button_long_press_ms)
        self.steps_per_detent = int(steps_per_detent)

        self.encoder_enabled = bool(encoder_enabled) and (pin_encoder_clk is not None) and (pin_encoder_dt is not None)

        self.on_button = on_button if on_button is not None else (lambda kind: kind)
        self.on_rotate = on_rotate if on_rotate is not None else (lambda direction: direction)

        self._enc_last_state = 0
        self._enc_accum = 0
        if self.encoder_enabled:
            a = self.pin_encoder_clk.value()
            b = self.pin_encoder_dt.value()
            self._enc_last_state = (a << 1) | b
            trigger = machine.Pin.IRQ_RISING | machine.Pin.IRQ_FALLING
            self.pin_encoder_clk.irq(trigger=trigger, handler=self._enc_irq)
            self.pin_encoder_dt.irq(trigger=trigger, handler=self._enc_irq)

        raw = self.pin_button.value()
        self._btn_stable = raw
        self._btn_raw_last = raw
        self._btn_raw_change_ms = 0
        self._btn_press_start_ms = None
        self._btn_long_fired = False
        self._btn_click_count = 0
        self._btn_one_deadline_ms = None
        self.pin_button.irq(
            trigger=machine.Pin.IRQ_RISING | machine.Pin.IRQ_FALLING,
            handler=self._btn_irq,
        )

    def _enc_irq(self, pin):
        a = self.pin_encoder_clk.value()
        b = self.pin_encoder_dt.value()
        state = (a << 1) | b
        prev = self._enc_last_state
        if state != prev:
            self._enc_last_state = state
            self._enc_accum += self._ENC_TRANSITIONS[(prev << 2) | state]

    def _btn_irq(self, pin):
        val = pin.value()
        if val != self._btn_raw_last:
            self._btn_raw_last = val
            self._btn_raw_change_ms = time.ticks_ms()

    def _commit_short_click(self, count):
        if count <= 0:
            return None
        if count == 1:
            return self.on_button("One")
        if count == 2:
            return self.on_button("Double")
        return None

    def handle_encoder(self):
        if not self.encoder_enabled:
            return None

        irq_state = machine.disable_irq()
        accum = self._enc_accum
        self._enc_accum = 0
        machine.enable_irq(irq_state)

        emitted = None

        while accum >= self.steps_per_detent:
            accum -= self.steps_per_detent
            emitted = self.on_rotate("Right")

        while accum <= -self.steps_per_detent:
            accum += self.steps_per_detent
            emitted = self.on_rotate("Left")

        if accum != 0:
            irq_state = machine.disable_irq()
            self._enc_accum += accum
            machine.enable_irq(irq_state)

        return emitted

    def handle_button(self):
        now_ms = time.ticks_ms()
        raw = self._btn_raw_last

        emitted = None

        if raw != self._btn_stable:
            if (now_ms - self._btn_raw_change_ms) >= self.button_debounce_ms:
                self._btn_stable = raw

                if self._btn_stable == 0:
                    self._btn_press_start_ms = now_ms
                    self._btn_long_fired = False
                else:
                    if self._btn_long_fired:
                        self._btn_press_start_ms = None
                        self._btn_long_fired = False
                        return None

                    if self._btn_press_start_ms is None:
                        return None

                    press_dur = now_ms - self._btn_press_start_ms
                    self._btn_press_start_ms = None

                    if press_dur >= self.button_long_press_ms:
                        self._btn_click_count = 0
                        self._btn_one_deadline_ms = None
                        emitted = self.on_button("Long")
                        return emitted

                    self._btn_click_count += 1
                    if self._btn_click_count == 1:
                        self._btn_one_deadline_ms = now_ms + self.button_double_click_ms
                    elif self._btn_click_count == 2:
                        emitted = self._commit_short_click(2)
                        self._btn_click_count = 0
                        self._btn_one_deadline_ms = None
                        return emitted
                    else:
                        emitted = None
                        self._btn_click_count = 0
                        self._btn_one_deadline_ms = None
                        return emitted

        if self._btn_stable == 0 and (not self._btn_long_fired) and self._btn_press_start_ms is not None:
            if (now_ms - self._btn_press_start_ms) >= self.button_long_press_ms:
                self._btn_long_fired = True
                self._btn_click_count = 0
                self._btn_one_deadline_ms = None
                emitted = self.on_button("Long")

        if self._btn_one_deadline_ms is not None and now_ms >= self._btn_one_deadline_ms:
            emitted = self._commit_short_click(1)
            self._btn_click_count = 0
            self._btn_one_deadline_ms = None

        return emitted

    def deinit(self):
        if self.encoder_enabled:
            self.pin_encoder_clk.irq(handler=None)
            self.pin_encoder_dt.irq(handler=None)
        self.pin_button.irq(handler=None)
