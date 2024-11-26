import bcrypt
import uuid
import datetime
from datetime import timedelta
import jwt
from elasticsearch import Elasticsearch
import server_properties
import logging
from helper import notification
import string
import secrets
from helper import constants

log = logging.getLogger(__name__)

# Elasticsearch connection configuration
es = Elasticsearch(
    hosts=[server_properties.ES_HOST],
    http_auth=(server_properties.ES_USER, server_properties.ES_PASSWORD)
)

log.info("Connected to Elasticsearch")
USER_INDEX = "users"

# JWT Configuration
SECRET_KEY = server_properties.SECRET_KEY  # Use a strong secret key in production
ALGORITHM = server_properties.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Password hashing functions
def hash_password(password: str) -> str:
    """
    Hash the password using bcrypt
    """
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(stored_hash: str, password: str) -> bool:
    """
    Verify the password with the stored hashed password
    """
    return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))

def create_access_token(user_id: str):
    """
    Create an access token for the user with user_id in the payload.
    """
    expires = datetime.datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"user_id": user_id, "exp": expires}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def generate_random_password(length=12):
    """
    Generate a secure random password.
    The default length is 12 characters, which can be adjusted as needed.
    Excludes backslash (\) and forward slash (/) from the password.
    """
    # Define the allowed characters, excluding \ and /
    characters = string.ascii_letters + string.digits + string.punctuation.replace('\\', '').replace('/', '')
    
    # Generate the random password
    password = ''.join(secrets.choice(characters) for _ in range(length))
    return password

class UserService:
    def __init__(self):
        self.es = es
        self.index = USER_INDEX

    def signup(self, username: str, password: str, email: str):
        """
        Handle user signup.
        Checks if the email already exists, hashes the password, and stores the user data in Elasticsearch.
        """
        email = email.lower()
        # Check if the user already exists based on email
        query = {
            "query": {
                "term": {
                    "email": email
                }
            }
        }

        res = self.es.search(index=self.index, body=query)

        if res['hits']['total']['value'] > 0:
            return {"success": False, "error": "User already exists"}

        # Hash the password before storing it
        hashed_password = hash_password(password)

        # Prepare user data for Elasticsearch document
        user_data = {
            "user_id": str(uuid.uuid4()),  # Unique UUID for each user
            "email": email,
            "username": username,
            "password": hashed_password,
            "created_at": datetime.datetime.utcnow().isoformat(),
        }

        # Index the user document in Elasticsearch
        self.es.index(index=self.index, document=user_data)

        # Send welcome notification
        subject = "Welcome! Your Guide to Local Restaurants is Here!"
        body = f"Hello {username},\n\nThank you for signing up! We're excited to have you on board."
        print("subject",subject,"body ",body)
        notification.send_notification(subject,body,email)  # Calling the function from notification.py

        # Return success with user_id and JWT token
        return {"success": True, "user_id": user_data["user_id"], "token": create_access_token(user_data["user_id"])}

    def login(self, email: str, password: str):
        """
        Handle user login.
        Verifies the user's credentials and returns a JWT token on successful login.
        """
        email = email.lower()
        # Check if the user exists based on email
        query = {
            "query": {
                "term": {
                    "email": email
                }
            }
        }

        res = self.es.search(index=self.index, body=query)

        if res['hits']['total']['value'] == 0:
            return {"success": False, "error": "User Doesn't Exist"}

        user_data = res['hits']['hits'][0]['_source']

        result = {
            "user_id":user_data["user_id"],
            "email":user_data["email"],
            "username":user_data["username"]
        }
        log.info(f"result {result}")

        # Verify the password against the stored hash
        if verify_password(user_data['password'], password):
            token = create_access_token(user_data["user_id"])
            return {"success": True, "result": result, "token": token}

        return {"success": False, "error": "Invalid Credentials"}

    def update_user(self, user_id: str, username: str = None, password: str = None):
        """
        Update the user's details (username or password).
        """
        # Get user data by user_id
        query = {
            "query": {
                "term": {
                    "user_id": user_id
                }
            }
        }

        res = self.es.search(index=self.index, body=query)

        if res['hits']['total']['value'] == 0:
            return {"success": False, "error": "User not found"}

        user_data = res['hits']['hits'][0]['_source']

        # Prepare the update data
        update_data = {}

        if username:
            update_data["username"] = username
        if password:
            update_data["password"] = hash_password(password)  # Hash the new password

        # Update the document in Elasticsearch
        update_query = {
            "doc": update_data
        }

        update_res = self.es.update(index=self.index, id=res['hits']['hits'][0]['_id'], body=update_query)

        return {"success": True}
    
    def update_password(self, email: str, old_password: str, new_password: str):

        email = email.lower()
        # Search for the user by email
        query = {
            "query": {
                "term": {
                    "email": email
                }
            }
        }

        res = self.es.search(index=self.index, body=query)

        if res['hits']['total']['value'] == 0:
            return {"success": False, "error": "User not found"}

        user_data = res['hits']['hits'][0]['_source']

        # Verify the old password
        if not verify_password(user_data['password'], old_password):
            return {"success": False, "error": "Old password is incorrect"}

        # email = user_data['email']
        # Hash the new password
        hashed_password = hash_password(new_password)

        # Prepare the update data
        update_data = {
            "password": hashed_password
        }

        # Update the document in Elasticsearch
        self.es.update(index=self.index, id=res['hits']['hits'][0]['_id'], body={"doc": update_data})

        # Send a notification email
        subject = "Your Password Has Been Changed Successfully"
        body = f"Hello {user_data['username']},\n\nYour password has been updated successfully. If you did not request this change, please contact support immediately."
        notification.send_notification(subject, body, email)

        return {"success": True}

    def forgot_password(self, email: str):
        """
        Generate a temporary password, update the user's password in Elasticsearch,
        and send the password via email.
        """
        email = email.lower()

        # Check if the user exists based on email
        query = {
            "query": {
                "term": {
                    "email": email
                }
            }
        }

        res = self.es.search(index=self.index, body=query)

        if res['hits']['total']['value'] == 0:
            return {"success": False, "error": "User not found"}

        user_data = res['hits']['hits'][0]['_source']
        user_id = user_data['user_id']

        # Generate a temporary password
        temporary_password = generate_random_password()
        hashed_password = hash_password(temporary_password)

        # Update the password in Elasticsearch
        update_data = {
            "password": hashed_password
        }
        self.es.update(index=self.index, id=res['hits']['hits'][0]['_id'], body={"doc": update_data})

        # Send an email with the new password
        subject = "Your OTP for Password Reset"
        body = (f"Hello {user_data['username']},\n\n"
                f"We've received your request to reset your password for your Eats Near You account.\n\n"
                f"Here is your OTP (One-Time Password): {temporary_password}\n\n"
                "Please enter this OTP on the password reset page to set a new password for your account.\n\n"
                "If you did not request this change, please contact support immediately.\n\n"
                "Thank you,\n"
                "The Eats Near You Team")
        notification.send_notification(subject, body, email)

        return {"success": True, "message": "An OTP has been sent to your email. Please use it to reset your password."}

    
    def submit_feedback(self,user_id,feedback):
        log.info("inside main logic")
        index = constants.FEEDBACK_INDEX
        document = {
            "user_id":user_id,
            "feedback":feedback,
            "created_at":datetime.datetime.utcnow().isoformat()
        }
        log.info(f"document {document}")
        es.index(index=index, document=document)
        log.info(f"Stored user feedback to {index} index")

        return {"success": True,"message":"Thank you for your feedback! It has been submitted successfully."}

    def google_auth(self, email: str, sub: str, username: str):
        """
        Handle Google Login or Signup.
        """
        email = email.lower()
        # Check if the user already exists
        query = {
            "query": {
                "term": {
                    "email": email
                }
            }
        }
        res = self.es.search(index=self.index, body=query)

        if res['hits']['total']['value'] > 0:
            # User exists, process login
            user_data = res['hits']['hits'][0]['_source']

            result = {
            "user_id":user_data["user_id"],
            "email":user_data["email"],
            "username":user_data["username"]
        }

            return {
                "success": True,
                "message": "Login successful via Google",
                "result": result
            }

        # User does not exist, process signup
        hashed_password = hash_password(sub)  # Hash the 'sub' as the password
        user_data = {
            "user_id": str(uuid.uuid4()),  # Generate a unique user ID
            "email": email,
            "username": username,
            "password": hashed_password,
            "created_at": datetime.datetime.utcnow().isoformat()
        }

        # Store the user in Elasticsearch
        self.es.index(index=self.index, document=user_data)

        # Send a welcome email
        subject = "Welcome! You Signed Up with Google!"
        body = (f"Hello {username},\n\n"
                "Thank you for signing up with Google! We're excited to have you with us.")
        notification.send_notification(subject, body, email)

        result = {
            "user_id":user_data["user_id"]
        }
    
        return {
            "success": True,
            "message": "Signup successful via Google",
            "result": result
        }