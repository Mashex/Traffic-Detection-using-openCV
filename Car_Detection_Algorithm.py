import cv2
import time
import uuid
import http.client

THRESHOLD_SENSITIVITY = 50
BLUR_SIZE = 40
BLOB_SIZE = 500
BLOB_WIDTH = 60
DEFAULT_AVERAGE_WEIGHT = 0.04
BLOB_LOCKON_DISTANCE_PX = 80
BLOB_TRACK_TIMEOUT = 0.7
# The left and right X positions of the "poles". These are used to
# track the speed of a vehicle across the scene.
LEFT_POLE_PX = 320
RIGHT_POLE_PX = 500
# Constants for drawing on the frame.
LINE_THICKNESS = 1
CIRCLE_SIZE = 5
RESIZE_RATIO = 0.4

from itertools import tee
try:
    from itertools import izip as zip
except ImportError: # will be 3.x series
    pass
def pairwise(iterable):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = tee(iterable)
    next(b, None)
    return zip(a, b)



avg = None
tracked_blobs = []


cv2.namedWindow("preview")
vc = cv2.VideoCapture(0)


if vc.isOpened(): 
    rval, frame = vc.read()
else:
    rval = False

timeout = time.time() + 10
while rval and time.time() < timeout:
	frame_time = time.time()
    #cv2.imshow("preview", frame)
	rval, frame = vc.read()

	hsvFrame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
   
	(_, _, grayFrame) = cv2.split(hsvFrame)

	grayFrame = cv2.GaussianBlur(grayFrame, (21, 21), 0)

	if avg is None:
		avg = grayFrame.copy().astype("float")
		continue


	cv2.accumulateWeighted(grayFrame, avg, DEFAULT_AVERAGE_WEIGHT)
	#cv2.imshow("average", cv2.convertScaleAbs(avg))


	differenceFrame = cv2.absdiff(grayFrame, cv2.convertScaleAbs(avg))
	#cv2.imshow("difference", differenceFrame)

	retval, thresholdImage = cv2.threshold(differenceFrame, THRESHOLD_SENSITIVITY, 255, cv2.THRESH_BINARY)
	thresholdImage = cv2.dilate(thresholdImage, None, iterations=2)
	cv2.imshow("threshold", thresholdImage)

	_, contours, hierarchy = cv2.findContours(thresholdImage, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

	blobs = filter(lambda c: cv2.contourArea(c) > BLOB_SIZE, contours)

	if blobs:
		for c in blobs:
			(x, y, w, h) = cv2.boundingRect(c)
			center = (int(x + w/2), int(y + h/2))

			closest_blob = None
			if tracked_blobs:
				closest_blobs = sorted(tracked_blobs, key=lambda b: cv2.norm(b['trail'][0], center))

				for close_blob in closest_blobs:
					distance = cv2.norm(center, close_blob['trail'][0])

                    # Check if the distance is close enough to "lock on"
					if distance < BLOB_LOCKON_DISTANCE_PX:
                        # If it's close enough, make sure the blob was moving in the expected direction
						expected_dir = close_blob['dir']
						if expected_dir == 'left' and close_blob['trail'][0][0] < center[0]:
							continue
						elif expected_dir == 'right' and close_blob['trail'][0][0] > center[0]:
							continue
						else:
							closest_blob = close_blob
							break

				if closest_blob:
                    # If we found a blob to attach this blob to, we should
                    # do some math to help us with speed detection
					prev_center = closest_blob['trail'][0]
					if center[0] < prev_center[0]:
                        # It's moving left
						closest_blob['dir'] = 'left'
						closest_blob['bumper_x'] = x
					else:
                        # It's moving right
						closest_blob['dir'] = 'right'
						closest_blob['bumper_x'] = x + w

                    # ...and we should add this centroid to the trail of
                    # points that make up this blob's history.
					closest_blob['trail'].insert(0, center)
					closest_blob['last_seen'] = frame_time

			if not closest_blob:
				b = dict(
					id=str(uuid.uuid4())[:8],
					first_seen=frame_time,
					last_seen=frame_time,
					dir=None,
					bumper_x=None,
					trail=[center],
				)
				tracked_blobs.append(b)

	if tracked_blobs:
		for i in range(len(tracked_blobs) - 1, -1, -1):
			if frame_time - tracked_blobs[i]['last_seen'] > BLOB_TRACK_TIMEOUT:
				del tracked_blobs[i]

	for blob in tracked_blobs:
		for (a, b) in pairwise(blob['trail']):
			cv2.circle(frame, a, 3, (255, 0, 0), LINE_THICKNESS)

			if blob['dir'] == 'left':
				cv2.line(frame, a, b, (255, 255, 0), LINE_THICKNESS)
			else:
				cv2.line(frame, a, b, (0, 255, 255), LINE_THICKNESS)

			bumper_x = blob['bumper_x']
			if bumper_x:
				cv2.line(frame, (bumper_x, 100), (bumper_x, 500), (255, 0, 255), 3)


	key = cv2.waitKey(20)
	if key == 27:
		 # exit on ESC
		break
print (len(tracked_blobs))
cv2.destroyWindow("preview")

