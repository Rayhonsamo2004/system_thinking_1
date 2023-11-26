import os
import tensorflow as tf
import numpy as np
import cv2
from flask import Flask, render_template, request, Response,session,flash
import firebase_admin
from firebase_admin import credentials, firestore
from twilio.rest import Client

account_sid = "AC1f05cb7141e77e5a064f4768ebc96c4a"
auth_token = "a75d472238ec33608863692181e19720"
twilio_phone_number = "+13214413107"

client = Client(account_sid, auth_token)

global phone

# Initialize Firebase Admin SDK
cred = credentials.Certificate("serviceaccountkey.json")
firebase_admin.initialize_app(cred)

# Get Firestore client
db = firestore.client()

app = Flask(__name__)
app.secret_key = "123"

# Create a directory to store uploaded video files
if not os.path.exists('uploads'):
    os.makedirs('uploads')

# Load the anomaly detection model
loaded_model = tf.keras.models.load_model("fire_detector")

def preprocess_frame(frame, target_size=(196, 196)):
    # Resize the frame to the target size
    resized_frame = cv2.resize(frame, target_size)
    # Normalize the pixel values (optional)
    resized_frame = resized_frame / 255.0
    # Expand dimensions to match your model input shape
    resized_frame = np.expand_dims(resized_frame, axis=0)
    return resized_frame

def generate_frames(video_file_path):
    cap = cv2.VideoCapture(video_file_path)

    if not cap.isOpened():
        yield b'Failed to open video file.'

    while True:
        ret, frame = cap.read()

        if not ret:
            break

        # Preprocess the frame
        img = preprocess_frame(frame)

        # Make a prediction using your single anomaly detection model
        predictions = loaded_model.predict(img)

        # You can determine the detected anomaly based on your model's output
        # For example, you can define a threshold for classifying an anomaly
        # as detected based on the model's output probabilities
        threshold = 0.5  # Adjust this threshold as needed
        detected_anomaly = "Anomaly Detected" if predictions[0][0] > threshold else "No Anomaly Detected"

        if detected_anomaly == "Anomaly Detected":
            message = client.messages.create(
                body="Fire detected! Please evacuate immediately.",
                from_=twilio_phone_number,
                to="+91"+phone
            )
        # Draw the text on the frame
        cv2.putText(frame, detected_anomaly, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route("/", methods=['GET', 'POST'])
def home_page():
    global phone
    if request.method == 'POST':
        # Handle registration form submission
        name = request.form.get('name')
        mail = request.form.get('mail')
        phone = request.form.get('phone')  # Assign the value to the global variable
        password = request.form.get('password')
        user_ref = db.collection('users').document()
        user_ref.set({
            'name': name,
            'mail': mail,
            'password': password,
            'contact': phone
        })
        # Redirect to another page or render a success message
        return render_template("login.html", name=name, phone=phone)
    else:
        # Render the registration form
        return render_template("register.html")

@app.route("/login",methods=['POST','GET'])

def login():
    if request.method=='POST':
        name=request.form.get('name')
        password=request.form.get('password')
        user_ref=db.collection("users").where("name","==",name).limit(1)
        users=user_ref.stream()
        print(users)
        for user in users:
            user_data=user.to_dict()
            password_check=user_data.get("password")
            if password==password_check:
                msg="logged in successfully as {} and id is{}".format(name,password)
                session['name']=name
                session['password']=password
                flash(msg,category="success")
                return render_template("detect.html")
        flash("invalid username","danger")
        return render_template("login.html")
    else:
        return render_template("login.html")
@app.route("/detect", methods=['POST'])
def detect():
    # Check if a video file was uploaded
    if 'upload_file' in request.files:
        video_file = request.files['upload_file']
        video_file_path = os.path.join('uploads', video_file.filename)
        video_file.save(video_file_path)

        return Response(generate_frames(video_file_path), mimetype='multipart/x-mixed-replace; boundary=frame')

    return render_template("detect.html", text="No video file provided")

@app.route("/logout",methods=['GET','POST'])

def logout():
    session.pop("name",None)
    session.pop("password",None)
    return render_template("login.html")

if __name__ == "__main__":
    app.run(debug=True, port=4000)
