#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This is used for pose estimation with ArUco bundles.
"""

import numpy as np
import cv2
import rospy
import time
from sensor_msgs.msg import CameraInfo, Image
from tf2_msgs.msg import TFMessage
from cv_bridge import CvBridge


def camera_info_callback(info):
    # Obtaining the camera matrix and the distortion coefficients
    global cameraMatrix
    global distCoeffs
    cameraMatrix = np.array(info.K)
    np.reshape(cameraMatrix, (3, 3))
    distCoeffs = np.array(info.D)


def image_callback(image):
    # Acquiring and transforming the ROS Image messages into OpenCV BGR images
    global bgrImage
    bgrImage = bridge.imgmsg_to_cv2(image, "bgr8")


def estimate_pose(image, aruco_dictionary, aruco_board, camera_matrix, dist_coeffs, rvec=None, tvec=None):
    # Transforming the BGR images into gray-scale images
    gray_scale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # Setting detector parameters
    parameters = cv2.aruco.DetectorParameters_create()
    parameters.adaptiveThreshConstant = 10
    # Detecting markers
    corners, ids, rejectedImgPoints = cv2.aruco.detectMarkers(gray_scale, aruco_dictionary, parameters=parameters)
    # If at least one marker is detected, estimating the pose
    if len(corners) > 0 and len(ids) > 0:
        success, rvec, tvec = cv2.aruco.estimatePoseBoard(corners, ids, aruco_board,
                                                          camera_matrix, dist_coeffs, rvec, tvec)
        # if success:
        #     # Drawing quads and axes on the image
        #     cv2.aruco.drawDetectedMarkers(image, corners)
        #     cv2.aruco.drawAxis(image, camera_matrix, dist_coeffs, rvec, tvec, 0.01)
        #     cv2.imshow('Pose', image)
        # else:
        #     rospy.logwarn("Failed to estimate the pose!")

        # Obtaining translation and rotation components of the pose
        T_target2cam = tvec
        R_target2cam = cv2.Rodrigues(rvec)[0]
        R_target2cam = tfs.quaternions.mat2quat(R_target2cam)
        # Transforming the pose into tf
        tf = TFMessage()
        header = tf.transforms[0].header
        pose = tf.transforms[0].transform

        header.frame_id = "/camera_link"
        header.child_frame_id = "/aruco_board"

        pose.translation.x = T_target2cam[0]
        pose.translation.y = T_target2cam[1]
        pose.translation.z = T_target2cam[2]
        pose.rotation.w = R_target2cam[0]
        pose.rotation.x = R_target2cam[1]
        pose.rotation.y = R_target2cam[2]
        pose.rotation.z = R_target2cam[3]

        return tf

    else:
        return None


if __name__ == '__main__':
    rospy.init_node("hand_to_eye_calib_bundle", anonymous=True)
    # Parameters and Variables
    markersX = rospy.get_param("markers_per_row", default=5)  # The number of markers in each row
    markersY = rospy.get_param("markers_per_column", default=7)  # The number of markers in each column
    markerLength = rospy.get_param("marker_length", default=0.04)  # The length of each marker
    markerSeparation = rospy.get_param("marker_separation", default=0.01)  # The separation between any two markers
    dictionary = rospy.get_param("aruco_dictionary", default=cv2.aruco.DICT_4X4_100)  # The marker dictionary
    camera_info = rospy.get_param("camera_info", default="/camera/color/camera_info")  # The camera_info topic
    image_topic = rospy.get_param("image_topic", default="/camera/color/image_raw")  # The image topic
    bgrImage = None  # The OpenCV BGR images
    cameraMatrix = None  # The 3X3 camera matrix
    distCoeffs = None  # The distortion coefficients
    bridge = CvBridge()

    rospy.Subscriber(camera_info, CameraInfo, camera_info_callback, queue_size=10)
    rospy.Subscriber(image_topic, Image, image_callback, queue_size=10)
    pub = rospy.Publisher("/tf", TFMessage, queue_size=10)
    rate = rospy.Rate(5)

    # Creating a dictionary and a grid board
    arucoDictionary = cv2.aruco.Dictionary_get(dictionary)
    arucoBoard = cv2.aruco.GridBoard_create(markersX, markersY, markerLength, markerSeparation, arucoDictionary)

    rospy.sleep(1)

    while not rospy.is_shutdown():
        try:
            if bgrImage is None:
                rospy.logwarn("No image data available!")
                time.sleep(1)
                continue
            if cameraMatrix is None:
                rospy.logwarn("No camera matrix available!")
                time.sleep(1)
                continue
            if distCoeffs is None:
                rospy.logwarn("No distortion coefficients available!")
                time.sleep(1)
                continue
            # Estimating the pose
            estimatedPose = estimate_pose(bgrImage, arucoDictionary, arucoBoard, cameraMatrix, distCoeffs)
            if estimatedPose is None:
                rospy.logwarn("Pose estimation failed!")
                time.sleep(1)

            else:
                pub.publish(estimatedPose)
                rate.sleep()

        except rospy.ROSInterruptException:
            rospy.logwarn("No available data!")
            continue
