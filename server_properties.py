import os
from dotenv import load_dotenv

load_dotenv()

def get_env_variable(var_name):
    try:
        return os.environ[var_name]
    except KeyError:
        error_msg = "Set the %s environment variable" % var_name
        raise Exception(error_msg)


GOOGLE_API_KEY = get_env_variable('GOOGLE_API_KEY')
GOOGLE_PLACES_API_BASE_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
GOOGLE_GEOCODE_API_BASE_URL = 'https://maps.googleapis.com/maps/api/geocode/json'
ES_HOST = get_env_variable('ES_HOST')
ES_USER = get_env_variable('ES_USERNAME')
ES_PASSWORD = get_env_variable('ES_PASSWORD')
SECRET_KEY = get_env_variable('SECRET_KEY')
ALGORITHM = get_env_variable('ALGORITHM')
# Email configuration
MAIL_HOST = 'smtp.gmail.com'
MAIL_PORT = 587
MAIL_USERNAME = get_env_variable('MAIL_USERNAME')  # Replace with your method of securely getting the email
MAIL_PASSWORD = get_env_variable('MAIL_PASSWORD')  # Replace with your method of securely getting the password
MAIL_USE_TLS = True
MAIL_USE_AUTH = True


