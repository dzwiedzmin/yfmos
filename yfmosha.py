'''

Home Assistant integration for Somfy Shutters

CODE BASED ON https://github.com/sehaas/yfmos

    
    0) IN ORDER TO USE THIS FIRST PAIR NEW REMOTE:
    -------------------------------------------------------------------------------------
    https://github.com/sehaas/yfmos
    https://pushstack.wordpress.com/somfy-rts-protocol/
    https://github.com/henrythasler/sdr/blob/master/somfy/transmitter.py

   I generated the buckets using a sniff of the Somfy Telis 4 Pure remote and Sonoff RF Bridge.
   The PROG command only worked when repeat set to 2, the other commands work best with repeat = 16 so keep in mind you may have to test different values.
   
    
    
    
    1) CONFIGURE PERSISTENT STORAGE FOR ROLLING CODE:
    -------------------------------------------------------------------------------------
    
input_number:
  somfy_remote_both:
    min: 39            #current rollingCode
    max: 0x111111      #device id
  somfy_remote_big:
    min: 4
    max: 0xAAAAAA
  somfy_remote_small:
    min: 4
    max: 0xBBBBBB    

#optional for debugging
logger:
  logs:
    homeassistant.components.python_script.yfmosha.py: info
    
    2) COPY THIS SCRIPT TO config/python_scripts/yfmosha.py
    -------------------------------------------------------------------------------------
    
    3) USAGE EXAMPLES: 
    -------------------------------------------------------------------------------------
    
    
somfy_down:
  sequence:
    - service: python_script.yfmosha
      data:
        entity_id: input_number.somfy_remote_both
        command: 0x40

somfy_up:
  sequence:
    - service: python_script.yfmosha
      data:
        entity_id: input_number.somfy_remote_both
        command: 0x20


    -------------------------------------------------------------------------------------    
Commands
    MY = 0x10
    UP = 0x20
    DOWN = 0x40
    PROG = 0x80    

    
    
    
'''


id       = data.get('entity_id')
command  = int(data.get('command'))

somfy = hass.states.get(id)
attr  = somfy.attributes
rollingCode = (float)(somfy.state)+1
rollingCode = (int)(rollingCode)
device = (int)(attr['max']) #device id stored in max atrribute

#rollingCode = 60


repeat      = 16
buckets     = [2540,4810,1270,630,27390]
hwSync      = '0'
swSync      = '1'
longPulse   = '2'
shortPulse  = '3'

def bin(x):
  out = []
  while x > 0:
    out.append('01'[x & 1])
    x = x >> 1
  out.append('0b')
  out.reverse()
  return ''.join(out)


def ManchesterEncode(longPulseArg, shortPulseArg, bitvec):
  longPulse = str(longPulseArg)
  shortPulse = str(shortPulseArg)
  encoded = ''

  prev = bitvec[0]
  for i in range(1, len(bitvec)):
    if bitvec[i] == prev:
      encoded = encoded + (shortPulse * 2)
    else:
      encoded = encoded + longPulse
    prev = bitvec[i]
  return encoded + '3'


def gen_payload(cmd, code, device):
  payload = {}
  payload[0] = 0xA1
  # Command
  payload[1] = cmd & 0xF0
  # Rollingcode
  payload[2] = (code >> 8) & 0xFF
  payload[3] = code & 0xFF
  # device ID
  payload[4] = (device >> 16) & 0xFF
  payload[5] = (device >> 8) & 0xFF
  payload[6] = device & 0xFF
  return payload

def calc_checksum(data):
  checksum = 0
  for i in range(len(data)):
      checksum = checksum ^ data[i] ^ (data[i] >> 4)
  data[1] = data[1] | checksum & 0x0F
  return data

def obfuscate(data):
  for i in range(1, len(data)):
      data[i] = data[i] ^ data[i-1]
  return data

def to_bitvec(data):
  out = ((data[0] << 48) | (data[1] << 40) | (data[2] << 32) |(data[3] << 24) | (data[4] << 16) | (data[5] << 8) | (data[6]))
  out = bin(out)  
  return out[2:]

def printFrame(frame):
  logger.info('Group       A       B       C       D       F         G        ')
  logger.info('Byte:       0H      0L      1H      1L      2       3       4       5       6    ')
  logger.info('  +-------+-------+-------+-------+-------+-------+-------+-------+-------+')
  logger.info('  !  0xA  + R-KEY ! C M D + C K S !  Rollingcode  ! Remote Handheld Addr. !')
  logger.info('  !  0x%01X  +  0x%01X  !  0x%01X  +  0x%01X  !    0x%04X     !       0x%06X  !' % ((frame[0] >> 4) & 0xF, frame[0] & 0xF, (frame[1] >> 4) & 0xF, frame[1] & 0xF, (frame[2] << 8) + frame[3], (frame[4] << 16) + (frame[5] << 8) + frame[6]))
  logger.info('  +-------+-------+-------+-------+MSB----+----LSB+LSB----+-------+----MSB+')


   
payload = gen_payload(command, rollingCode, device)
payload = calc_checksum(payload)
printFrame(payload)
payload = obfuscate(payload)
bitvec = to_bitvec(payload)
  
dataStr = ManchesterEncode(longPulse, shortPulse, bitvec)  
tmpStr = '05 %02X %04X %04X %04X %04X %04X %s%s%s%s4' % (repeat, buckets[0], buckets[1], buckets[2], buckets[3], buckets[4], hwSync * 14, swSync, longPulse, dataStr)
strLen = int(len(tmpStr.replace(' ', '')) / 2)

rfraw   = 'AA B0 %02X %s 55' % (strLen, tmpStr)
reset   = '177' #back to raw sniffing mode
backlog = 'RfRaw %s;RfRaw 0;RfRaw 177'% (rfraw)

hass.states.set(id, rollingCode, attr.copy())
logger.info("CMD=%s" % (rfraw))
#I use sonoff RF bridge with tasmota, so I publish mqtt command
hass.services.call('mqtt', 'publish', { "topic": "cmnd/DVES_A286E8_fb/RfRaw", "payload": rfraw}, False)
#logger.info("CMD=%s" % (reset))
#hass.services.call('mqtt', 'publish', { "topic": "cmnd/DVES_A286E8_fb/RfRaw", "payload": reset}, False)

#hass.services.call('mqtt', 'publish', { "topic": "cmnd/DVES_A286E8_fb/backlog", "payload": backlog}, False)



