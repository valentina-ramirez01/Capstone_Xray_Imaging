
# Using the IMX415 MIPI camera Live preview; press 's' to save a frame, 'q' to quit

from picamera2 import Picamera2
import cv2

cam = Picamera2()
cam.configure(cam.create_preview_configuration(main={"size": (1280, 720)}))
cam.start()

while True:
    # Capture raw grayscale
    frame = cam.capture_array("main")

    # If shape has 3 channels (duplicated), reduce to one:
    if len(frame.shape) == 3:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    cv2.imshow("Monochrome Camera", frame)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('s'):
        cv2.imwrite("mono_frame.png", frame)
        print("Saved mono_frame.png")
    elif key == ord('q'):
        break

cam.stop()
cv2.destroyAllWindows()