#!/usr/bin/env python2

# python standard libraries
import __main__, sys, os, signal, pprint, configparser, argparse, logging, logging.handlers, time, threading, random, copy, pygame

# Raspberry Pi specific libraries
import MPR121
import RPi.GPIO as GPIO

#### Global Variables ####

# ws2812svr constants
channel = 2
led_count = 0 # will be calculated later, from the INI file
led_type = 1
invert = 0
global_brightness = 255
gpionum = 13

# define Big Dome pins
BIG_DOME_LED_PIN = 25
BIG_DOME_PUSHBUTTON_PIN = 24

colors = { 'off' : '000000',
           'red' : 'FF0000',
           'grn' : '00FF00',
           'blu' : '0000FF',
           'ylw' : 'FFFF00',
           'brw' : '7F2805',
           'prp' : 'B54A8F',
           'wht' : 'FFFFFF'
         }

pp = pprint.PrettyPrinter(indent=4) # Setup format for pprint.
fn = os.path.splitext(os.path.basename(__main__.__file__))[0]
args = None
config = None
pi = None
sensor = None

def setup_gpio():
  global pi

  #### initialize Pi GPIO
  GPIO.setmode(GPIO.BCM)
  GPIO.setwarnings(False)
  
  # initialize the GPIO on the Pi Proto Board
  # Big Dome LED
  big_dome_led = 0
  GPIO.setup(BIG_DOME_LED_PIN, GPIO.OUT)
  GPIO.output(BIG_DOME_LED_PIN, big_dome_led)

  # Big Dome Button
  GPIO.setup(BIG_DOME_PUSHBUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def setup_mpr121():
  global sensor

  #### Connect to and initialize the PiCap's MPR121 hardware.
  try:
    sensor = MPR121.begin()
    logger.info(u'MPR121 successfully initialized')
  except Exception as e:
    logger.critical(u'Unable to connect to initial the MPR121 on the PiCap')
    logger.critical(e)
    sys.exit(1)

  # this is the touch threshold - setting it low makes it more like a proximity trigger default value is 40 for touch
  touch_threshold = 40

  # this is the release threshold - must ALWAYS be smaller than the touch threshold default value is 20 for touch
  release_threshold = 20

  # set the thresholds
  sensor.set_touch_threshold(touch_threshold)
  sensor.set_release_threshold(release_threshold)
  
def main():
  global pi
  global sensor
  global led_count
  button = False
  prv_button = False
  current_Nose_LED = False
  prv_Nose_LED = False

  
  ParseArgs()
  setupLogging()
  setup_gpio()
  setup_mpr121()
  
  # initialize mixer and pygame
  if not args.noSound:
    pygame.mixer.pre_init(frequency = 44100/4, channels = 64, buffer = 1024)
    pygame.init()

    sound = pygame.mixer.Sound('/home/pi/MegaOperation/sounds/.wavs/buzzer.wav')
    sound.play()

  # initialize CTRL-C Exit handler
  signal.signal(signal.SIGINT, signal_handler)

  # pre-initialize not yet used timer threads into config object for testing, later in main loop.
  # and determine maximum LED position
  led_count = 0
  for section in config.iterkeys():
    config[section]['thread'] = threading.Thread(target=sectionWorker, args=(config[section],))

    maxTemp = int(config[section]['led_start']) + int(config[section]['led_length'])
    if maxTemp > led_count:
      led_count = maxTemp
  logger.debug("Max LED position found to be " + str(led_count))

  #### POST - NeoPixel Pre Operating Self Tests ####
  logger.debug("initializing ws2812svr")
  write_ws281x('setup {0},{1},{2},{3},{4},{5}\ninit\n'.format(channel, led_count, led_type, invert, global_brightness, gpionum))

  logger.debug("POST LED test of ALL red")
  write_ws281x('fill ' + str(channel) + ',' + colors['red'] + '\nrender\n')
  time.sleep(args.postDelay)

  logger.debug("POST LED test of ALL grn")
  write_ws281x('fill ' + str(channel) + ',' + colors['grn'] + '\nrender\n')
  time.sleep(args.postDelay)

  logger.debug("POST LED test of ALL blu")
  write_ws281x('fill ' + str(channel) + ',' + colors['blu'] + '\nrender\n')
  time.sleep(args.postDelay)

  logger.debug("POST LED test of ALL off")
  write_ws281x('fill ' + str(channel) + ',' + colors['off'] + '\nrender\n')

  #### used to locate LEDs on device
  if args.walkLED:
    walk_leds()
  
  #### stop if command line requested.
  if args.stop :
    logger.info(u'Option set to just initialize and then quit')
    quit()

  #### Main Loop
  while True:

    # check if a sensor changed
    if sensor.touch_status_changed():
      sensor.update_touch_data()

      # scan each of the sensors to see which one changed.
      for section in config.iterkeys():
        logger.log(logging.DEBUG-1, "config[" + section + "]['sensor'] = " + str(config[section]['sensor']))
        # if sensor.get_touch_data(i):
          # check if touch is registred to set the led status
        doMagic = False
        if config[section]['sensor'].isdigit(): # Only Digits are Touch Sensors.
          i = int(config[section]['sensor'])
          logging.info("electrode {0} was just touched".format(i))
          if sensor.is_new_touch(i):
            doMagic = True
          elif sensor.is_new_release(i):
            logging.info("electrode {0} was just released".format(i))
        
        if doMagic:
          # play sound associated with that touch
          if not config[section]['thread'].is_alive():
            config[section]['thread'] = threading.Thread(target=sectionWorker, args=(config[section],))
            config[section]['thread'].setName(section)
            config[section]['thread'].start()

    is_any_sensor_thread_alive = any(config[section]['thread'].is_alive() for section in config.iterkeys() )

    button = GPIO.input(BIG_DOME_PUSHBUTTON_PIN)
    if (prv_button != button) :
      logger.info("BIG_DOME_PUSHBUTTON_PIN changed from " + str(prv_button) + " to " + str(button))
      prv_button = button

    current_Nose_LED = is_any_sensor_thread_alive or not(button)
    if current_Nose_LED != prv_Nose_LED:
      if current_Nose_LED:
        write_ws281x('fill ' + str(channel) + ',' + \
        colors['wht']  + ',' + \
        str(config['Nose']['led_start']) + ',' + \
        str(config['Nose']['led_length']) + \
        '\nrender\n')
      else:
        write_ws281x('fill ' + str(channel) + ',' + \
        colors['off']  + ',' + \
        str(config['Nose']['led_start']) + ',' + \
        str(config['Nose']['led_length']) + \
        '\nrender\n')
      prv_Nose_LED = current_Nose_LED

    time.sleep(0.01)
#end of main():

def walk_leds():
  global led_count
  for pos in range(led_count):
    write_ws281x('fill ' + str(channel) + ',' + \
                           colors['red']  + ',' + \
                           str(pos) + ',' + \
                           '1' + \
                           '\nrender\n')
    logger.debug(u'LED Index = ' + str(pos))

    try:
        input("Press enter to continue")
    except SyntaxError:
        pass
    
    write_ws281x('fill ' + str(channel) + ',' + colors['off'] + '\nrender\n')
    pos = pos + 1
  exit()

def ParseArgs():
  global args
  global config
  global fn
  
  # Get filename of running script without path and or extension.

  # Define command line arguments
  parser = argparse.ArgumentParser(description='Raspberry Pi MegaOperation board game.')
  parser.add_argument('--verbose', '-v', action='count', help='verbose multi level', default=1)
  parser.add_argument('--config', '-c', help='specify config file', default=(os.path.join(os.path.dirname(os.path.realpath(__file__)), fn + ".ini")))
  parser.add_argument('--ws281x', '-w', help='specify ws281x file handle', default="/dev/ws281x")
  parser.add_argument('--stop', '-s', action='store_true', help='just initialize and stop')
  parser.add_argument('--postDelay', '-p', help='specify the LED delays at startup', type=float, default="1.0")
  parser.add_argument('--noSound', '-n', action='store_true', help='Run with out sound')
  parser.add_argument('--singleSound', '-S', action='store_true', help='Only play one Sound at a time')
  parser.add_argument('--walkLED', '-L', action='store_true', help='move LED increamentally, with standard input, used for determining LED positions.')

  # Read in and parse the command line arguments
  args = parser.parse_args()

  os.path.join(os.path.dirname(os.path.realpath(__file__)), args.config)


  # Read in configuration file and create dictionary object
  configParse = configparser.ConfigParser()
  configParse.read(args.config)
  config = {s:dict(configParse.items(s)) for s in configParse.sections()}
# end of ParseArgs():

logger = None
def setupLogging():
  global args
  global config
  global fn
  global logger
  
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
  logger.info(u'ws281x file handle = ' + args.ws281x)
  logger.info(u'POST Delays = ' + str(args.postDelay) + " seconds")

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
# end of setupLogging():

def write_ws281x(cmd):
  with open(args.ws281x, 'w') as the_file:
    logger.debug("ws281x cmd: " + cmd.replace("\n", "\\n"))
    the_file.write(cmd)
    # file closes with unindent.
    # close needed for ws2812svr to process file handle
# end of write_ws281x():

def sectionWorker(config):
  section = threading.currentThread().getName()
  logger.debug('Started Thread "' + section + \
               '" led_on_time = ' + str(config['led_on_time']) + \
               '" led_start = ' + str(config['led_start']) + \
               '" led_length = ' + str(config['led_length']) + \
               '" music_fnpath = ' + str(config['music_fnpath']) \
               )
               
  tmp_color = copy.deepcopy(colors)
  if 'off' in tmp_color: del tmp_color['off']
  if config['led_color'].lower() == 'random' :
    # remove 'off', as not to get randomly
    color = tmp_color[random.choice(list(tmp_color))]
  else:
    try:
      color = tmp_color[config['led_color'].lower()]
    except:
      color = tmp_color[random.choice(list(tmp_color))]

  write_ws281x('fill ' + str(channel) + ',' + \
                         color  + ',' + \
                         str(config['led_start']) + ',' + \
                         str(config['led_length']) + \
                         '\nrender\n')

  if (not args.noSound) and ('music_fnpath' in config) and (os.path.isfile(config['music_fnpath'])):
    # only play if allowed and valid file is defined.
    sound = pygame.mixer.Sound(config['music_fnpath'])
    if (not pygame.mixer.get_busy()) or (not args.singleSound):
      # play when no other is playing or play blindly if multi is allowed.
      sound.play()

  time.sleep(int(config['led_on_time']))
  
  write_ws281x('fill ' + str(channel) + ',' + \
                         colors['off'] + ',' + \
                         str(config['led_start']) + ',' + \
                         str(config['led_length']) + \
                         '\nrender\n')
# end of sectionWorker():

def signal_handler(signal, frame):
  # handle ctrl+c gracefully
  logger.info("CTRL+C Exit LED test of ALL off")
  write_ws281x('fill ' + str(channel) + ',' + colors['off'] + '\nrender\n')

  logger.info(u'Exiting script ' + os.path.join(os.path.dirname(os.path.realpath(__file__)), __file__))
  for section in config.iterkeys():
    if config[section]['thread'].is_alive():
      logger.info("waiting for thread : " + config[section]['thread'].getName() + " to end")

  sys.exit(0)
# end of signal_handler():

main()
