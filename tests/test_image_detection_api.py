from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from otonom.api import app


client = TestClient(app)


def test_image_detection_endpoint() -> None:
    img = Image.new("RGB", (256, 256), color=(120, 200, 120))
    buf = BytesIO()
    img.save(buf, format="PNG")
    payload = buf.getvalue()

    response = client.post(
        "/api/v1/detection/image",
        files={"file": ("sample.png", payload, "image/png")},
    )

    assert response.status_code == 200
    data = response.json()
    assert "backend" in data
    assert len(data["detections"]) >= 1
