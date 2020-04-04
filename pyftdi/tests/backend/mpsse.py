"""PyUSB virtual FTDI device."""

# Copyright (c) 2020, Emmanuel Blot <emmanuel.blot@free.fr>
# All rights reserved.

from logging import getLogger
from struct import unpack as sunpack
from pyftdi.tracer import FtdiMpsseEngine, FtdiMpsseTracer


class VirtMpsseTracer(FtdiMpsseTracer):
    """Reuse MPSSE tracer as a MPSSE command decoder engine.
    """

    def __init__(self, port: 'VirtFtdiPort', version: int):
        super().__init__(version)
        self.log = getLogger('pyftdi.virt.mpsse')
        self._port = port

    def _get_engine(self, iface: int):
        iface -= 1
        try:
            self._engines[iface]
        except IndexError:
            raise ValueError('No MPSSE engine available on interface %d' %
                             iface)
        if not self._engines[iface]:
            self._engines[iface] = VirtMpsseEngine(self, self._port)
        return self._engines[iface]


class VirtMpsseEngine(FtdiMpsseEngine):

    def __init__(self, tracer: VirtMpsseTracer, port: 'VirtFtdiPort'):
        super().__init__(port.iface)
        # self.log = getLogger('pyftdi.virt.mpsse')
        self._tracer = tracer
        self._port = port
        self._width = port.width
        self._mask = (1 << self._width) - 1
        self._cfunc = None

    def complete(self):
        if not self._cfunc:
            self.log.debug('No post completion')
            return
        self._cfunc = None

    def _cmd_get_bits_low(self):
        super()._cmd_get_bits_low()
        byte = self._port.gpio & 0xff
        buf = bytes([byte])
        self._port.write_from_mpsse(self, buf)
        return True

    def _cmd_get_bits_high(self):
        super()._cmd_get_bits_high()
        byte = (self._port.gpio >> 8) & 0xff
        buf = bytes([byte])
        self._port.write_from_mpsse(self, buf)
        return True

    def _cmd_set_bits_low(self):
        self._cfunc = None
        buf = self._trace_tx[1:3]
        if not super()._cmd_set_bits_low():
            return False
        port = self._port
        byte, direction = sunpack('BB', buf)
        gpi = port.gpio & ~direction & self._mask
        gpo = byte & direction & self._mask
        msb = port.gpio & ~0xFF
        gpio = gpi | gpo | msb
        port.update_gpio(self, False, direction, gpio)
        self.log.info('. bbwl %04x: %s', port.gpio, f'{port.gpio:016b}')
        return True

    def _cmd_set_bits_high(self):
        self._cfunc = None
        buf = self._trace_tx[1:3]
        if not super()._cmd_set_bits_high():
            return False
        port = self._port
        byte, direction = sunpack('BB', buf)
        byte <<= 8
        direction <<= 8
        gpi = port.gpio & ~direction & self._mask
        gpo = byte & direction & self._mask
        lsb = port.gpio & 0xFF
        gpio = gpi | gpo | lsb
        port.update_gpio(self, False, direction, gpio)
        self.log.info('. bbwh %04x: %s', port.gpio, f'{port.gpio:016b}')
        return True