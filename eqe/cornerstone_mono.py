import threading

# Find a CornerstoneB connected to the USB.
# The 'list_resources' function of the resource manager returns a list of strings
# identifying the instruments that visa sees. The Cornerstone CS130B string looks like:
# "USB0::0x1FDE::0x0006::nnnn::INSTR" ("nnnn" is the serial number).
# If the caller leaves the sernum_str parameter blank, any CornerstoneB on the usb will do.
def FindUsbCSB( rm, sernum_str="0", verbose=False ):
  found_unit = False
  addr_str = ""

  # Get a list of all the instruments pyvisa can find connected to the computer.
  instr_list = rm.list_resources( )

  if verbose:
    print( "usb instr list:", instr_list )

  # Examine each entry in the instrument list.
  for instr in instr_list :
    fields = instr.split('::')
    if verbose:
     print( fields, len(fields))

    if( len(fields) == 5 ):         # 5 fields in a usbtmc device entry of the instrument list.
      if( fields[0] == "USB0" ):      # ... should probably not care about the '0'...
        if( fields[1] == "0x1FDE" ):    # Newport
          if(( fields[2] == "0x0014" ) or( fields[2] == "0x0006")):    # CS260B or CS130B
            if( sernum_str == "0" ) or (( fields[ 3 ] == sernum_str )):
             addr_str = instr
             found_unit = True
             break   # Found one! Stop examining the instrument list 

  if verbose and found_unit:
    print( fields[0], fields[1], fields[2], addr_str )

  return found_unit, addr_str

# Find a monochromator attached to the USB bus.
def GetUsbUnit( rm, sernum_str="0", verbose=False ):
  bOk       = True
  thisUnit  = None

  if( sernum_str != "0" ) and verbose:
    print( "get looking for sn ", sernum_str )

  bOk, addr_str = FindUsbCSB( rm, sernum_str, verbose )

  if bOk:
    if verbose:
      print( "addr_str:", addr_str )

    thisUnit = rm.open_resource( addr_str )

  if verbose:
    if (bOk):
      print( "Found Monochromator:", thisUnit )
    else:
      print( "unit not found!" )

  return bOk, thisUnit



'''
 This is an example implementation of a Cornerstone B mono class and some access member functions. 
 See the __main__ function (below) for an example of how to use this class.
'''
class Cornerstone_Mono:
  def __init__ ( self, rm, rem_ifc="usb", timeout_msec=1000, sernum_str="0", comport="COM1" ):

    self.bFound, self.unit = GetUsbUnit( rm, sernum_str )

    if( self.bFound ):
      print( "Found Monochromator:", self.unit )
      self.unit.timeout = timeout_msec
    else:
      print( "Did not find Monochromator on", rem_ifc,"- make sure it is turned on and connected to the computer." )

    # Use python's mutual exclusion feature to allow multiple threads to talk
    # safely with the unit. This is a real bacon-saver.
    self.lock = threading.Lock( )

  def CloseSession( self ):
    self.unit.close( )

  def CS_Found( self ):
    return self.bFound

  # Send a command string to the unit. 
  # Note: pyvisa's default terminator is the same as the Cornerstone's (CR-LF),
  # so we don't need to specify it.
  def SendCommand( self, cmd_str, verbose=False ):
    self.lock.acquire( )

    if verbose:
      print( "cmd:", cmd_str.strip( ))

    self.unit.write( cmd_str )

    self.lock.release( )

  def GetQueryResponse( self, qry_str, verbose=False ):
    self.lock.acquire( )

    # catch timeout error without completely exploding.
    try:
      if verbose:
        print( "query:", qry_str.strip( ))

      qry_response = self.unit.query( qry_str )
    except:
      qry_response = " "
      print( "possible timeout:", qry_str )

    self.lock.release( )

    # remove pesky carriage return and linefeed.
    qry_response = qry_response.strip( )

    return qry_response

  def GetID( self ):
    id_str = self.GetQueryResponse( "*idn?" )
    return id_str

  def GetErrors( self, verbose=False ):
    cmd_str  = "system:error?"
    err_str = self.GetQueryResponse( cmd_str, verbose )
    if( err_str == "0, No Error"):
      bHasError = False
    else:
      bHasError = True
    return bHasError, err_str

  def WaitOpc( self, verbose=False ):
    qry_str = "*opc?"
    err_str = self.GetQueryResponse( qry_str, verbose )

  def SetFilter( self, filter_num, verbose=False ):
    cmd_str = "filter %d" % filter_num
    self.SendCommand( cmd_str, verbose )

  def SelectOutput( self, out_num, verbose=False ):
    cmd_str = "outport %d" % out_num
    self.SendCommand( cmd_str, verbose )

  def SelectGrating( self, grating_number, verbose=False ):
    cmd_str = "grating %d" % grating_number
    self.SendCommand( cmd_str, verbose )

  def UnitIdle( self, verbose=False ):
    qry_str = "idle?"
    idle_str = self.GetQueryResponse( qry_str, verbose )
    idle_val = int( idle_str )
    if idle_val == 1:
      return True
    else:
      return False

  def WaitForIdle( self, verbose=False ):
    unit_idle = self.UnitIdle( )
    while not unit_idle:
      unit_idle = self.UnitIdle( )