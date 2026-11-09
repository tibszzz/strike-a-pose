import cv2
from ultralytics import YOLO

# Load the pretrained YOLOv26 pose model
model = YOLO("yolo26n-pose.pt")
cap = cv2.VideoCapture(0)

while cap.isOpened():
    success, frame = cap.read()
    if not success:
        break
    results = model(frame)
    annotated_frame = results[0].plot()
    cv2.imshow("YOLOv26 Live Pose Detection", annotated_frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
