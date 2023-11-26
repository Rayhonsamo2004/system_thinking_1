import os
import tensorflow as tf
import numpy as np
import cv2
from flask import Flask, render_template, request, Response, session, flash, jsonify, redirect, url_for
import firebase_admin
from firebase_admin import credentials, firestore
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from datetime import datetime



# Initialize Firebase Admin SDK
cred = credentials.Certificate("serviceaccountkey.json")
firebase_admin.initialize_app(cred)

# Get Firestore client
db = firestore.client()

app = Flask(__name__)
app.secret_key = "123"

# Gmail credentials
gmail_user = "rayhon@student.tce.edu"  # Update with your Gmail address
gmail_password = "ray@2004"  # Update with your app-specific password

# Global variable to store coordinates
global coordinates 

def send_email(subject, body, mail, password, image_path):
    sender_email = f"{gmail_user}"  # Update with your Gmail address
    recipient_email = f"{mail}"  # Update with the recipient's email address

    # Create the MIME object
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject

    # Attach the body of the email
    msg.attach(MIMEText(body, 'plain'))

    # Attach the image from the video
    with open(image_path, 'rb') as img_file:
        image_data = img_file.read()
        image = MIMEImage(image_data, name='fire_image.jpg')
        msg.attach(image)

    # Connect to the Gmail SMTP server
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(gmail_user, gmail_password)
        server.sendmail(sender_email, recipient_email, msg.as_string())

def save_frame_as_image(frame, image_path):
    cv2.imwrite(image_path, frame)

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

def update_firebase_document(mail, new_message):
    # Get the current messages from the document
    document_ref = db.collection("users").document(mail)
    doc = document_ref.get()
    
    if doc.exists:
        user_data = doc.to_dict()
        current_messages = user_data.get('messages', [])
    else:
        current_messages = []

    # Append the new message to the list
    current_messages.append(new_message)

    # Update the document in the 'users' collection with the updated messages
    document_ref.update({'messages': current_messages, 'message_sent': True, 'timestamp': datetime.now()})

def generate_frames(ip_address, mail, password):
    # Use OpenCV to capture video from the IP webcam
    video_stream_url = f"http://{ip_address}/video"
    cap = cv2.VideoCapture(video_stream_url)

    if not cap.isOpened():
        yield b'Failed to open video stream.'
    frame_count = 0
    skip_frames = 5  # Adjust this value based on your preference
    while True:
        ret, frame = cap.read()

        if not ret:
            break
         # Adjust video resolution
        frame = cv2.resize(frame, (640, 480))  # Set your preferred resolution

        if frame_count % skip_frames == 0:
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
                # Save the frame as an image
                save_frame_as_image(frame, 'fire_image.jpg')

                # Get the Firestore document reference
                document_ref = db.collection("messages").document(mail)

                # Check if the document exists
                if not document_ref.get().exists:
                    # If the document doesn't exist, create a new one
                    document_ref.set({'messages': []})

                # Get the current timestamp
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # Append the message to the 'messages' array in the document
                document_ref.update({
                    'messages': firestore.ArrayUnion([{
                        'subject': 'Fire Detected',
                        'body': 'Fire detected! Please evacuate immediately.{}'.format(mail),
                        'timestamp': timestamp
                    }])
                })

                # Send email with the attached image
                send_email("Fire Detected", "Fire detected! Please evacuate immediately.", mail, password, 'fire_image.jpg')

            # Draw the text on the frame

            cv2.putText(frame, detected_anomaly, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            ret, buffer = cv2.imencode('.jpg', frame , [cv2.IMWRITE_JPEG_QUALITY, 80])
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        frame_count += 1

@app.route("/", methods=['GET', 'POST'])
def home_page():
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

@app.route("/login", methods=['POST', 'GET'])
def login():
    if request.method == 'POST':
        mail = request.form.get('mail')
        password = request.form.get('password')
        user_ref = db.collection("users").where("mail", "==", mail).limit(1)
        users = user_ref.stream()
        for user in users:
            user_data = user.to_dict()
            password_check = user_data.get("password")
            if password == password_check:
                msg = "logged in successfully as {} and id is {}".format(mail, password)
                session['mail'] = mail
                session['password'] = password
                flash(msg, category="success")
                # Fetch device information
                devices_ref = db.collection("devices").document(mail)
                devices_data = devices_ref.get().to_dict()
                print(devices_data)
                return render_template("detect.html",mail=mail,password=password,devices=devices_data)
        flash("invalid username", "danger")
        return render_template("login.html")
    else:
        return render_template("login.html")

@app.route("/detect", methods=['POST'])
def detect():
    # Check if an IP address is provided
    if 'ip_address' in request.form and 'mail' in session:
        selected_option = request.form['ip_address']

        # Split the selected option into device name and IP address
        device_name, ip_address = selected_option.split('--')

        # Pass device name, IP address, mail, and password to the generate_frames function
        return Response(generate_frames(ip_address, session.get('mail'), session.get('password')),
                        mimetype='multipart/x-mixed-replace; boundary=frame')


    return render_template("detect.html", text="No IP address provided")

@app.route("/logout", methods=['GET', 'POST'])
def logout():
    session.pop("mail", None)
    session.pop("password", None)
    return render_template("login.html")

@app.route("/notification", methods=['GET', 'POST'])
def notification():
    msg = None  # Initialize msg with a default value

    if 'mail' in session:
        print("mail is found")
        document_ref = db.collection("messages").document(session.get('mail'))
        doc = document_ref.get()
        print("doc")
        if doc.exists:
            msg = doc.to_dict().get('messages', [])
            print("mess")
            print(msg)

    return render_template("notification.html", msg=msg if msg is not None else [])

@app.route("/locate",methods=['GET','POST'])
def map_locate():
    if 'mail' in session:
        return render_template("map.html")
    else:
        return render_template("login.html")

@app.route('/device')
def device():
    if 'mail' in  session:
       # Extract the latitude and longitude from the query parameters
        lat = request.args.get('lat')
        lng = request.args.get('lng')
        # Pass the coordinates to the template
        return render_template('device.html', mail=session['mail'],lat=lat, lng=lng)
    else:
        return render_template("login.html")

@app.route("/add_device", methods=['GET', 'POST'])
def add_device():
    if request.method == "POST":
        mail = request.form.get('mail')
        latitude = request.form.get('lat')
        longitude = request.form.get('lng')
        ip_address=request.form.get('ip_address')
        name=request.form.get('name')
        doc_ref = db.collection("devices").document(mail)

        if not doc_ref.get().exists:
            doc_ref.set({f"$mail": []})

        # Check if the device is already allocated
        allocated_devices = doc_ref.get().to_dict().get('$mail', [])
        for device in allocated_devices:
            if device['latitude'] == latitude and device['longitude'] == longitude:
                msg = "Device already allocated at these coordinates"
                flash(msg, category="danger")
                return render_template("device.html")

        # Check if other users are allocated at the same coordinates
        all_devices_ref = db.collection("devices")
        all_devices = all_devices_ref.stream()

        for user_device in all_devices:
            user_device_data = user_device.to_dict().get('$mail', [])
            for device in user_device_data:
                if device['latitude'] == latitude and device['longitude'] == longitude:
                    # Alert that other users are also allocated at these coordinates
                    msg = "Other users are also allocated at these coordinates"
                    flash(msg, category="warning")
                    break

        # Update the devices in Firestore
        doc_ref.update({
            f'$mail': firestore.ArrayUnion([{
                'latitude': latitude,
                'longitude': longitude,
                'ip_address':ip_address,
                'name':name,
                'ram': 10,
                'allocated': True  # Mark the device as allocated
            }])
        })
        msg = "Successfully device is allocated"
        flash(msg, category="success")
        return render_template("device.html")


if __name__ == "__main__":
    app.run(debug=True, port=4000)
