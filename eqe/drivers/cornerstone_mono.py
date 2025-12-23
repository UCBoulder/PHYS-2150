import threading

from common.utils import get_logger, get_error

# Module-level logger for monochromator driver
_logger = get_logger("eqe")

# Find a CornerstoneB connected to the USB.
def FindUsbCSB(rm, sernum_str="0", verbose=False):
    found_unit = False
    addr_str = ""

    # Get a list of all the instruments pyvisa can find connected to the computer.
    instr_list = rm.list_resources()

    if verbose:
        _logger.debug(f"USB instrument list: {instr_list}")

    # Examine each entry in the instrument list.
    for instr in instr_list:
        fields = instr.split('::')
        if verbose:
            _logger.debug(f"Examining: {fields}")

        if len(fields) == 5:  # 5 fields in a usbtmc device entry of the instrument list.
            if fields[0] == "USB0":  # ... should probably not care about the '0'...
                if fields[1] == "0x1FDE":  # Newport
                    if fields[2] == "0x0014" or fields[2] == "0x0006":  # CS260B or CS130B
                        if sernum_str == "0" or fields[3] == sernum_str:
                            addr_str = instr
                            found_unit = True
                            break  # Found one! Stop examining the instrument list

    if verbose and found_unit:
        _logger.debug(f"Found device: {fields[0]} {fields[1]} {fields[2]} at {addr_str}")

    return found_unit, addr_str

# Find a monochromator attached to the USB bus.
def GetUsbUnit(rm, sernum_str="0", verbose=False):
    bOk = True
    thisUnit = None

    if sernum_str != "0" and verbose:
        _logger.debug(f"Looking for serial number: {sernum_str}")

    bOk, addr_str = FindUsbCSB(rm, sernum_str, verbose)

    if bOk:
        if verbose:
            _logger.debug(f"Address: {addr_str}")

        thisUnit = rm.open_resource(addr_str)

    if verbose:
        if bOk:
            _logger.debug(f"Found monochromator: {thisUnit}")
        else:
            _logger.debug("Monochromator not found in USB scan")

    return bOk, thisUnit, addr_str

class Cornerstone_Mono:
    def __init__(self, rm, rem_ifc="usb", timeout_msec=1000, sernum_str="0", comport="COM1"):
        self.bFound, self.unit, self.addr_str = GetUsbUnit(rm, sernum_str)
        self.serial_number = self.extract_serial_number(self.addr_str)

        if self.bFound:
            _logger.info(f"Monochromator connected: {self.unit}")
            self.unit.timeout = timeout_msec
        else:
            _logger.error(f"Monochromator not found on {rem_ifc}")
            error = get_error("monochromator_not_found", "eqe")
            if error:
                _logger.student_error(error.title, error.message, error.causes, error.actions)

        # Use python's mutual exclusion feature to allow multiple threads to talk
        # safely with the unit. This is a real bacon-saver.
        self.lock = threading.Lock()

    def extract_serial_number(self, addr_str):
        fields = addr_str.split('::')
        if len(fields) == 5:
            return fields[3]
        return None

    def CloseSession(self):
        self.unit.close()

    def CS_Found(self):
        return self.bFound

    def SendCommand(self, cmd_str, verbose=False):
        self.lock.acquire()

        if verbose:
            _logger.debug(f"Mono cmd: {cmd_str.strip()}")

        self.unit.write(cmd_str)

        self.lock.release()

    def GetQueryResponse(self, qry_str, verbose=False):
        self.lock.acquire()

        try:
            if verbose:
                _logger.debug(f"Mono query: {qry_str.strip()}")

            qry_response = self.unit.query(qry_str)
        except:
            qry_response = " "
            _logger.warning(f"Monochromator query timeout: {qry_str.strip()}")

        self.lock.release()

        qry_response = qry_response.strip()

        return qry_response

    def GetID(self):
        id_str = self.GetQueryResponse("*idn?")
        return id_str

    def GetErrors(self, verbose=False):
        cmd_str = "system:error?"
        err_str = self.GetQueryResponse(cmd_str, verbose)
        if err_str == "0, No Error":
            bHasError = False
        else:
            bHasError = True
        return bHasError, err_str

    def WaitOpc(self, verbose=False):
        qry_str = "*opc?"
        err_str = self.GetQueryResponse(qry_str, verbose)

    def SetFilter(self, filter_num, verbose=False):
        cmd_str = "filter %d" % filter_num
        self.SendCommand(cmd_str, verbose)

    def SelectOutput(self, out_num, verbose=False):
        cmd_str = "outport %d" % out_num
        self.SendCommand(cmd_str, verbose)

    def SelectGrating(self, grating_number, verbose=False):
        cmd_str = "grating %d" % grating_number
        self.SendCommand(cmd_str, verbose)

    def UnitIdle(self, verbose=False):
        qry_str = "idle?"
        idle_str = self.GetQueryResponse(qry_str, verbose)
        # Handle empty string from timeout - assume not idle yet
        if not idle_str or not idle_str.strip():
            return False
        try:
            idle_val = int(idle_str)
            return idle_val == 1
        except ValueError:
            # If response can't be parsed, assume not idle
            return False

    def WaitForIdle(self, verbose=False):
        unit_idle = self.UnitIdle()
        while not unit_idle:
            unit_idle = self.UnitIdle()