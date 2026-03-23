from __future__ import annotations

import json

from otonom.schemas import RunMissionRequest
from otonom.service import OtonomService

try:
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import String
except Exception as exc:  # pragma: no cover
    raise RuntimeError(
        "ROS2 dependencies missing. Source your ROS2 environment and install rclpy/std_msgs."
    ) from exc


class MissionOrchestratorNode(Node):
    def __init__(self) -> None:
        super().__init__("mission_orchestrator_node")
        self.service = OtonomService()
        self.subscription = self.create_subscription(String, "/mission/request", self.on_request, 10)
        self.publisher = self.create_publisher(String, "/mission/result", 10)
        self.get_logger().info("MissionOrchestratorNode ready")

    def on_request(self, msg: String) -> None:
        try:
            payload = RunMissionRequest.model_validate_json(msg.data)
            result = self.service.run_mission(payload)
            out = String()
            out.data = result.model_dump_json()
            self.publisher.publish(out)
        except Exception as exc:
            err = String()
            err.data = json.dumps({"state": "ERROR", "message": str(exc)})
            self.publisher.publish(err)


def main() -> None:
    rclpy.init()
    node = MissionOrchestratorNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
