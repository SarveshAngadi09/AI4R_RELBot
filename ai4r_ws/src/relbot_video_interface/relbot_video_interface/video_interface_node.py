#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Point
import gi
import numpy as np
import cv2
import onnxruntime as ort

gi.require_version('Gst', '1.0')
from gi.repository import Gst

CONF_THRESHOLD = 0.25
NMS_THRESHOLD  = 0.45
PERSON_CLASS   = 0   # COCO class index for 'person'
INPUT_SIZE     = 640


class VideoInterfaceNode(Node):
    def __init__(self):
        super().__init__('video_interface')
        self.position_pub = self.create_publisher(Point, '/object_position', 10)

        self.declare_parameter('gst_pipeline', (
            'udpsrc port=5000 caps="application/x-rtp,media=video,'
            'encoding-name=H264,payload=96" ! '
            'rtph264depay ! avdec_h264 ! videoconvert ! '
            'video/x-raw,format=RGB ! appsink name=sink'
        ))
        self.declare_parameter('model_path', '/ai4r_ws/model/yolov8n.onnx')

        pipeline_str = self.get_parameter('gst_pipeline').value
        model_path   = self.get_parameter('model_path').value

        # Load ONNX model
        self.session = ort.InferenceSession(
            model_path,
            providers=['CUDAExecutionProvider', 'CPUExecutionProvider']
        )
        self.input_name  = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name
        self.get_logger().info(f'Loaded ONNX model: {model_path}')

        # Initialize GStreamer and build pipeline
        Gst.init(None)
        self.pipeline = Gst.parse_launch(pipeline_str)
        self.sink = self.pipeline.get_by_name('sink')
        self.sink.set_property('drop', True)
        self.sink.set_property('max-buffers', 1)
        self.pipeline.set_state(Gst.State.PLAYING)

        self.timer = self.create_timer(1.0 / 30.0, self.on_timer)
        self.get_logger().info('VideoInterfaceNode initialized, streaming at 30Hz')

    def on_timer(self):
        # Pull the latest frame from the GStreamer appsink
        sample = self.sink.emit('pull-sample')
        if not sample:
            # No new frame available
            return

        buf = sample.get_buffer()
        caps = sample.get_caps()
        width = caps.get_structure(0).get_value('width')
        height = caps.get_structure(0).get_value('height')
        ok, mapinfo = buf.map(Gst.MapFlags.READ)
        if not ok:
            # Failed to map buffer data
            return

        # Convert raw buffer to numpy array [height, width, channels]
        frame = np.frombuffer(mapinfo.data, np.uint8).reshape(height, width, 3)
        buf.unmap(mapinfo)

        # frame is RGB from GStreamer; convert to BGR for OpenCV
        bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        # ── Preprocess: resize → float32 → normalize → BGR→RGB → CHW → NCHW ──
        resized = cv2.resize(bgr, (INPUT_SIZE, INPUT_SIZE))
        blob = resized.astype(np.float32) / 255.0          # [640,640,3]
        blob = blob[:, :, ::-1]                            # BGR → RGB
        blob = np.transpose(blob, (2, 0, 1))               # HWC → CHW
        blob = np.expand_dims(blob, axis=0)                # CHW → NCHW [1,3,640,640]
        blob = np.ascontiguousarray(blob)

        # ── Run inference ──────────────────────────────────────────────────────
        outputs = self.session.run([self.output_name], {self.input_name: blob})
        # output shape: [1, 84, 8400]  (4 box coords + 80 class scores × 8400 anchors)
        pred = outputs[0][0]           # [84, 8400]
        num_anchors = pred.shape[1]

        # ── Parse detections ───────────────────────────────────────────────────
        boxes, confidences = [], []
        for a in range(num_anchors):
            scores = pred[4:, a]
            best_class = int(np.argmax(scores))
            max_score  = float(scores[best_class])

            if max_score < CONF_THRESHOLD or best_class != PERSON_CLASS:
                continue

            cx = pred[0, a] / INPUT_SIZE
            cy = pred[1, a] / INPUT_SIZE
            w  = pred[2, a] / INPUT_SIZE
            h  = pred[3, a] / INPUT_SIZE

            left   = int((cx - 0.5 * w) * bgr.shape[1])
            top    = int((cy - 0.5 * h) * bgr.shape[0])
            bw     = int(w * bgr.shape[1])
            bh     = int(h * bgr.shape[0])

            boxes.append([left, top, bw, bh])
            confidences.append(max_score)

        # ── NMS + publish best detection ───────────────────────────────────────
        indices = cv2.dnn.NMSBoxes(boxes, confidences, CONF_THRESHOLD, NMS_THRESHOLD)

        if len(indices) > 0:
            idx = indices[0] if isinstance(indices[0], (int, np.integer)) else indices[0][0]
            x, y, bw, bh = boxes[idx]
            center_x = float(x + bw // 2)
            area     = float(bw * bh)

            cv2.rectangle(bgr, (x, y), (x + bw, y + bh), (0, 255, 0), 2)
            cv2.circle(bgr, (int(center_x), y + bh // 2), 5, (0, 0, 255), -1)
            cv2.putText(bgr, f'person x={int(center_x)}', (x, y - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            msg = Point()
            msg.x = center_x   # horizontal center of detected person (pixels)
            msg.y = 0.0        # unused (flat-ground assumption)
            msg.z = area       # bounding-box area; controller stops when z > 10000
            self.position_pub.publish(msg)
            self.get_logger().debug(f'Published position: ({msg.x:.1f}, {msg.y}, {msg.z:.1f})')

        cv2.imshow('Input Stream', bgr)
        cv2.waitKey(1)

    def destroy_node(self):
        # Cleanup GStreamer resources on shutdown
        self.pipeline.set_state(Gst.State.NULL)
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = VideoInterfaceNode()
    try:
        rclpy.spin(node)  # Keep node alive, invoking on_timer periodically
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()