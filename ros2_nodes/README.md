# ROS2 Node Split

Bu klasor, sistemin ROS2 tabanli dagitik mimariye gecisi icin node iskeletlerini icerir.

## Node'lar

- mission_orchestrator_node.py
  - /mission/request topic'inden gorev talebi alir
  - OtonomService ile gorevi calistirir
  - /mission/result topic'ine JSON sonuc basar

- detector_bridge_node.py
  - YOLO runtime backend durumunu expose eder
  - /detector/image_request dinler
  - /detector/result yayinlar

## Calistirma

ROS2 ortaminin source edilmis olmasi gerekir.

```bash
python ros2_nodes/mission_orchestrator_node.py
python ros2_nodes/detector_bridge_node.py
```

Not: Production akista bu node'lar image transport, QoS ve lifecycle policy ile zenginlestirilmelidir.
