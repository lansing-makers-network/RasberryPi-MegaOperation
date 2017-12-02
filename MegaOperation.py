#!/usr/bin/env python2

# python standard libraries
import __main__, sys, os, signal, pprint, configparser, argparse, logging, logging.handlers, time

# Raspberry Pi specific libraries
import pigpio, pygame, MPR121
#import RPi.GPIO as GPIO

# Setup format for pprint.
pp = pprint.PrettyPrinter(indent=4)

# Get filename of running script without path and or extension.
fn = os.path.splitext(os.path.basename(__main__.__file__))[0]

# Define command line arguments
parser = argparse.ArgumentParser(description='Raspberry Pi MegaOperation board game.')
parser.add_argument('--verbose', '-v', action='count', help='verbose multi level', default=1)
parser.add_argument('--config', '-c', help='specify config file', default=(os.path.join(os.path.dirname(os.path.realpath(__file__)), fn + ".ini")))
parser.add_argument('--stop', '-s', action='store_true', help='just initialize and stop')

# Read in and parse the command line arguments
args = parser.parse_args()

os.path.join(os.path.dirname(os.path.realpath(__file__)), args.config)


# Read in configuration file and create dictionary object
configParse = configparser.ConfigParser()
configParse.read(args.config)
config = {s:dict(configParse.items(s)) for s in configParse.sections()}

# Setup display and file logging with level support.
logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
logger = logging.getLogger()
fileHandler = logging.handlers.RotatingFileHandler("{0}/{1}.log".format('/var/log/'+ fn +'/', fn), maxBytes=2*1024*1024, backupCount=2)

fileHandler.setFormatter(logFormatter)
#fileHandler.setLevel(logging.DEBUG)
logger.addHandler(fileHandler)

consoleHandler = logging.StreamHandler()
#consoleHandler.setLevel(logging.DEBUG)
consoleHandler.setFormatter(logFormatter)
logger.addHandler(consoleHandler)

# Dictionary to translate Count of -v's to logging level
verb = { 0 : logging.WARN,
         1 : logging.INFO,
         2 : logging.DEBUG,
       }

# zero adjust for zero offset to make it easier to understand
args.verbose = int(args.verbose) - 1
try:
  # set logging level from command line arg.
  logger.setLevel(verb[(args.verbose)])
except:
  # if out of range use levels, and account for standard levels
  if (args.verbose - 2) > 0:
    logger.setLevel(logging.DEBUG - (args.verbose - 2))
  else:
    logger.setLevel(logging.DEBUG)

logger.info(u'Starting script ' + os.path.join(os.path.dirname(os.path.realpath(__file__)), __file__))
logger.info(u'config file = ' + args.config)
    
# log which levels of debug are enabled.
logger.log(logging.DEBUG-9, "discrete log level = " + str(logging.DEBUG-9))
logger.log(logging.DEBUG-8, "discrete log level = " + str(logging.DEBUG-8))
logger.log(logging.DEBUG-7, "discrete log level = " + str(logging.DEBUG-7))
logger.log(logging.DEBUG-6, "discrete log level = " + str(logging.DEBUG-6))
logger.log(logging.DEBUG-5, "discrete log level = " + str(logging.DEBUG-5))
logger.log(logging.DEBUG-4, "discrete log level = " + str(logging.DEBUG-4))
logger.log(logging.DEBUG-3, "discrete log level = " + str(logging.DEBUG-3))
logger.log(logging.DEBUG-2, "discrete log level = " + str(logging.DEBUG-2))
logger.log(logging.DEBUG-1, "discrete log level = " + str(logging.DEBUG-1))
logger.log(logging.DEBUG,   "discrete log level = " + str(logging.DEBUG  ))
logger.info(u'verbose = ' + str(args.verbose) + ", logger level = " + str(logger.getEffectiveLevel()))
logger.debug(u'debug level enabled')
logger.info(u'info  level enabled')
#logger.warn(u'warn  level enabled')
#logger.error(u'error  level enabled')
#logger.critical(u'critical  level enabled')

# extra levels of DEBUG of configuration file.
logger.log(logging.DEBUG-1, "list of config sections = \r\n" + pp.pformat(config.keys()))
first_section_key = config.keys()[0]
logger.log(logging.DEBUG-2, "first section name = " + pp.pformat(first_section_key))
first_section_dict = config[first_section_key]
logger.log(logging.DEBUG-3, "list of first sections items = \r\n" + pp.pformat(first_section_dict))
first_sections_first_item = first_section_dict.keys()[0]
logger.log(logging.DEBUG-4, "config["+first_section_key+"]["+first_sections_first_item+"] = " + config[first_section_key][first_sections_first_item])
logger.log(logging.DEBUG-5, "config = " + pp.pformat(config))

# handle ctrl+c gracefully
def signal_handler(signal, frame):
  logger.info(u'Exiting script ' + os.path.join(os.path.dirname(os.path.realpath(__file__)), __file__))
  sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# initialize and connect to Pi GPIO daemon. 
pi = pigpio.pi()
if not pi.connected:
  logger.critical(u'Unable to connect to TCP Pi GPIO Daemon')
  sys.exit(1)
else:
  logger.info(u'Connection to pigpio daemon successfully established')

# Connect to and initialize the PiCap's MPR121 hardware. 
try:
  sensor = MPR121.begin()
  logger.info(u'MPR121 successfully initialized')
except Exception as e:
  logger.critical(u'Unable to connect to initial the MPR121 on the PiCap')
  logger.critical(e)
  sys.exit(1)

num_electrodes = 12

# this is the touch threshold - setting it low makes it more like a proximity trigger default value is 40 for touch
touch_threshold = 40

# this is the release threshold - must ALWAYS be smaller than the touch threshold default value is 20 for touch
release_threshold = 20

# set the thresholds
sensor.set_touch_threshold(touch_threshold)
sensor.set_release_threshold(release_threshold)
  
# define Big Dome pins
BIG_DOME_LED_PIN = 25
BIG_DOME_PUSHBUTTON_PIN = 24

# initialize the GPIO on the Pi Proto Board
# Big Dome LED
pi.set_mode(BIG_DOME_LED_PIN, pigpio.OUTPUT)
# Big Dome Button
pi.set_mode(BIG_DOME_PUSHBUTTON_PIN, pigpio.INPUT)
pi.set_pull_up_down(BIG_DOME_PUSHBUTTON_PIN, pigpio.PUD_UP)
pi.set_glitch_filter(BIG_DOME_PUSHBUTTON_PIN, 1000)

big_dome_led = 0
pi.write(BIG_DOME_LED_PIN, big_dome_led)

prv_button = pi.read(BIG_DOME_PUSHBUTTON_PIN)

print "config[Butterflies in Stomach][sensor] = " + config["Butterflies in Stomach"]['sensor']


if args.stop : 
  logger.info(u'Option set to just initialize and then quit')
  quit()
  
while True:

  # check if a sensor changed
  if sensor.touch_status_changed():
    sensor.update_touch_data()
    is_any_touch_registered = False

    # scan each of the sensors to see which one changed.
    #for i in range(num_electrodes):
    for key in config.iterkeys():
      logger.log(logging.DEBUG-1, "config[" + key + "]['sensor'] = " + str(config[key]['sensor']))
      i = int(config[key]['sensor'])
      if sensor.get_touch_data(i):
        # check if touch is registred to set the led status
        is_any_touch_registered = True
      if sensor.is_new_touch(i):
        # play sound associated with that touch
        logger.info("detected sensor  = " + str(i))

      if sensor.is_new_touch(i):
        print "electrode {0} was just touched".format(i)
      elif sensor.is_new_release(i):
        print "electrode {0} was just released".format(i)
        
        
        
        
        
    if is_any_touch_registered:
      pi.write(BIG_DOME_LED_PIN, not(pi.read(BIG_DOME_LED_PIN)))
    else:
      pi.write(BIG_DOME_LED_PIN, not(pi.read(BIG_DOME_LED_PIN)))

  button = pi.read(BIG_DOME_PUSHBUTTON_PIN)
  if (prv_button != button) :
    logger.info("BIG_DOME_PUSHBUTTON_PIN changed from " + str(prv_button) + " to " + str(button))
    pi.write(BIG_DOME_LED_PIN, not(button))
    prv_button = button
  
  time.sleep(0.01)

