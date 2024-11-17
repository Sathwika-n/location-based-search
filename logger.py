import logging.config
import sys
log_config = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'DEBUG',
            'formatter': 'simple',
            'stream': 'ext://sys.stdout'
        },
    },
    'loggers': {
        '': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True
        }
    }
}

logging.config.dictConfig(log_config)

# Handling case where __file__ is not set
if hasattr(sys.modules['__main__'], '__file__'):
    name = str(sys.modules['__main__'].__file__).split("/")[-1].split('.')[0]
else:
    name = '__main__'  # Fallback when __file__ is not available

def get_logger():
    return logging.getLogger(name)
