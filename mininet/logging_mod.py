'''Logging functions for Mininet.'''

import logging
import types

LEVELS = {'debug': logging.DEBUG,
          'info': logging.INFO,
          'warning': logging.WARNING,
          'error': logging.ERROR,
          'critical': logging.CRITICAL}

# change this to logging.INFO to get printouts when running unit tests
LOG_LEVEL_DEFAULT = logging.WARNING

#default: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_MSG_FORMAT = '%(message)s'



# Modified from python2.5/__init__.py
class StreamHandlerNoNewline(logging.StreamHandler):
    '''StreamHandler that doesn't print newlines by default.

    Since StreamHandler automatically adds newlines, define a mod to more
    easily support interactive mode when we want it, or errors-only logging for
    running unit tests.
    '''

    def emit(self, record):
        '''
        Emit a record.

        If a formatter is specified, it is used to format the record.
        The record is then written to the stream with a trailing newline
        [N.B. this may be removed depending on feedback]. If exception
        information is present, it is formatted using
        traceback.print_exception and appended to the stream.
        '''
        try:
            msg = self.format(record)
            fs = '%s' # was '%s\n'
            if not hasattr(types, 'UnicodeType'): #if no unicode support...
                self.stream.write(fs % msg)
            else:
                try:
                    self.stream.write(fs % msg)
                except UnicodeError:
                    self.stream.write(fs % msg.encode('UTF-8'))
            self.flush()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)


def set_loglevel(level_name = None):
    '''Setup loglevel.

    @param level_name level name from LEVELS
    '''
    level = LOG_LEVEL_DEFAULT
    if level_name != None:
        if level_name not in LEVELS:
            raise Exception('unknown loglevel seen in set_loglevel')
        else:
            level = LEVELS.get(level_name, level)

    lg.setLevel(level)
    if len(lg.handlers) != 1:
        raise Exception('lg.handlers length not zero in logging_mod')
    lg.handlers[0].setLevel(level)


def _setup_logging():
    '''Setup logging for Mininet.'''
    global lg

    # create logger if first time
    if 'lg' not in globals():
        lg = logging.getLogger('mininet')
        # create console handler
        ch = StreamHandlerNoNewline()
        # create formatter
        formatter = logging.Formatter(LOG_MSG_FORMAT)
        # add formatter to ch
        ch.setFormatter(formatter)
        # add ch to lg
        lg.addHandler(ch)
    else:
        raise Exception('setup_logging called twice')

    set_loglevel()


# There has to be some better way to ensure we only ever have one logging
# variable.  If this check isn't in, the order in which imports occur can
# affect whether a program runs, because the variable lg may get rebound.
if 'lg' not in globals():
    _setup_logging()
