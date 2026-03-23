from __future__ import annotations

import json

from otonom.inference import YOLOModelRuntime

try:
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import String
except Exception as exc:  # pragma: no cover
    raise RuntimeError(
        "ROS2 dependencies missing. Source your ROS2 environment and install rclpy/std_msgs."
    ) from exc


class DetectorBridgeNode(Node):
    def __init__(self) -> None:
        super().__init__("detector_bridge_node")
        self.runtime = YOLOModelRuntime(model_path="models/weed_yolo.onnx", tensorrt_engine_path="models/weed_yolo.engine")
        self.subscription = self.create_subscription(String, "/detector/image_request", self.on_image_request, 10)
        self.publisher = self.create_publisher(String, "/detector/result", 10)
        self.get_logger().info(f"DetectorBridgeNode ready with backend={self.runtime.backend_name}")

    def on_image_request(self, msg: String) -> None:
        # Message is expected to carry base64 image bytes in production.
        # This bridge demonstrates the runtime contract and publishes backend status.
        response = {
            "backend": self.runtime.backend_name,
            "status": "ready",
            "message": "Use API /api/v1/detection/image for full image inference flow",
        }
        out = String()
        out.data = json.dumps(response)
        self.publisher.publish(out)


def main() -> None:
    rclpy.init()
    node = DetectorBridgeNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
