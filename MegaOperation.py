#!/usr/bin/env python2

#from __future__ import absolute_import
import __main__, os, pprint, configparser, argparse, logging, logging.handlers


from pigpio import pi, OUTPUT, INPUT, PUD_UP, EITHER_EDGE
from time import time, sleep
pp = pprint.PrettyPrinter(indent=4)

fn = os.path.splitext(os.path.basename(__main__.__file__))[0]

parser = argparse.ArgumentParser(description='Mikes Play Ground')
parser.add_argument('--verbose', '-v', action='count', help='verbose level', default=1)
parser.add_argument('--config', '-c', help='specify config file', default=(fn + ".ini"))
args = parser.parse_args()

config = configparser.ConfigParser()
config.read(args.config)
config_dict = {s:dict(config.items(s)) for s in config.sections()}

logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
logger = logging.getLogger()
fileHandler = logging.handlers.RotatingFileHandler("{0}/{1}.log".format('/var/log/'+ fn +'/', fn), maxBytes=2000, backupCount=10)

fileHandler.setFormatter(logFormatter)
#fileHandler.setLevel(logging.DEBUG)
logger.addHandler(fileHandler)

consoleHandler = logging.StreamHandler()
#consoleHandler.setLevel(logging.DEBUG)
consoleHandler.setFormatter(logFormatter)
logger.addHandler(consoleHandler)

verb = { 0 : logging.WARN,
         1 : logging.INFO,
         2 : logging.DEBUG,
       }
logger.setLevel(logging.INFO)
logger.info(u'Script Started')
logger.info(u'config file = ' + args.config)

try:
  args.verbose = int(args.verbose) - 1
  logger.setLevel(verb[(args.verbose)])
except:
  logger.setLevel(logging.DEBUG)

# 'application' code
logger.info(u'verbose = ' + str(args.verbose))
logger.debug(u'debug level enabled')
logger.info(u'info  level enabled')
logger.warn(u'warn  level enabled')
logger.error(u'error  level enabled')
logger.critical(u'critical  level enabled')

# extra levels of DEBUG
logger.debug("config.sections() = " + pp.pformat(config.sections()))
if args.verbose > 2 :
  logger.debug("config._sections['General'] = " + pp.pformat(config._sections['General']))
if args.verbose > 3 :
  logger.debug("config.get('General', 'Volume') = " + pp.pformat(config.get('General', 'Volume')))
if args.verbose > 4 :
  logger.debug("config_dict = " + pp.pformat(config_dict))

pi = pi()
if not pi.connected:
    exit(0)

pi.set_mode(25, OUTPUT)

pi.set_mode(24, INPUT)
pi.set_pull_up_down(24, PUD_UP)
pi.set_glitch_filter(24, 1000)

while (1):
    logger.debug( u"pi.read(24) = " + unicode(pi.read(24)) )
    logger.debug( u"LED -> off" )
    pi.write(25, 0) # set local Pi's GPIO 4 low
    sleep(0.5)
    logger.debug( u"LED ->  on" )
    pi.write(25, 1) # set local Pi's GPIO 4 low
    sleep(0.5)
