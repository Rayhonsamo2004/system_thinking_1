import os
import tensorflow as tf
import numpy as np
import cv2
from flask import Flask, render_template, request
import winsound
app = Flask(__name__)
app.secret_key = "123"

# Create a directory to store uploaded video files
if not os.path.exists('uploads'):
    os.makedirs('uploads')

# Load your CNN model for fire detection
loaded_model = tf.keras.models.load_model("fire_detector")

def preprocess_frame(frame, target_size=(196, 196)):
    # Resize the frame to the target size
    resized_frame = cv2.resize(frame, target_size)
    # Normalize the pixel values (optional)
    resized_frame = resized_frame / 255.0
    # Expand dimensions to match your model input shape
    resized_frame = np.expand_dims(resized_frame, axis=0)
    return resized_frame

# Replace with the correct IP address and port for your streaming software
ip_address = "192.168.97.229"
port = "8080"
text="No Fire Detected"
# Construct the correct video stream URL
video_url = f"http://{ip_address}:{port}/video"

# Create the video capture object
#cap = cv2.VideoCapture(video_url)

cap = cv2.VideoCapture(video_url)
@app.route("/", methods=['GET', 'POST'])
def home_page():
     if not cap.isOpened():
        return "Failed to open video stream."
     while True:
        ret, frame = cap.read()

        if not ret:
            break

        # Preprocess the frame
        img = preprocess_frame(frame)

        # Make a prediction using your CNN model
        predictions = loaded_model.predict(img)
        text = "Fire Detected" if predictions[0] > 0.5 else "No Fire Detected"

        # Draw the text on the frame
        cv2.putText(frame, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        # Display the processed frame
        cv2.imshow("Fire Detection", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

     cap.release()
     cv2.destroyAllWindows()
     # Set frequency to 2000 Hertz
     return "Video processing complete."

@app.route("/detect", methods=['POST'])
def detect():
    if not cap.isOpened():
        return "Failed to open video stream."

    while True:
        ret, frame = cap.read()

        if not ret:
            break

        # Preprocess the frame
        img = preprocess_frame(frame)

        # Make a prediction using your CNN model
        predictions = loaded_model.predict(img)
        text = "Fire Detected" if predictions[0] > 0.5 else "No Fire Detected"

        # Draw the text on the frame
        cv2.putText(frame, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        # Display the processed frame
        cv2.imshow("Alert !! Detection", frame)
        if text=="Fire Detected":
            frequency = 2000
            duration = 1500
            winsound.Beep(frequency,duration)
    
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

    return "Video processing complete."

if __name__ == "__main__":
    app.run(debug=True, port=4000)
