"""MQTT broker subscriber — ingests sensor events from starscream/nodes/+/events."""

from __future__ import annotations

import logging
import os
import signal
import sys

from starscream.sensor.ingest import SensorEventIn, resolve_audio_bytes, submit_sensor_event
from starscream.sensor.mqtt_handler import MQTT_TOPIC_PREFIX, parse_mqtt_payload

logger = logging.getLogger(__name__)

DEFAULT_BROKER = os.environ.get("MQTT_BROKER_HOST", "localhost")
DEFAULT_PORT = int(os.environ.get("MQTT_BROKER_PORT", "1883"))
DEFAULT_TOPIC = os.environ.get("MQTT_TOPIC", f"{MQTT_TOPIC_PREFIX}/+/events")


def _handle_message(payload: bytes) -> None:
    from fastapi import HTTPException

    from starscream.db.session import get_session_factory

    event = SensorEventIn.model_validate(
        parse_mqtt_payload(payload.decode("utf-8")).model_dump()
    )
    try:
        audio_bytes = resolve_audio_bytes(event, None)
    except HTTPException as exc:
        raise ValueError(exc.detail) from exc

    session = get_session_factory()()
    try:
        recording = submit_sensor_event(db=session, event=event, audio_bytes=audio_bytes)
        logger.info("MQTT ingest OK: recording %s from node %s", recording.id, event.node_id)
    finally:
        session.close()


def main() -> int:
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        print("MQTT subscriber requires paho-mqtt: pip install -e '.[sensor]'")
        return 1

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    def on_connect(client, userdata, flags, reason_code, properties=None):
        del userdata, flags, properties
        if reason_code != 0:
            logger.error("MQTT connect failed: %s", reason_code)
            return
        client.subscribe(DEFAULT_TOPIC)
        logger.info("Subscribed to %s", DEFAULT_TOPIC)

    def on_message(client, userdata, msg):
        del client, userdata
        try:
            _handle_message(msg.payload)
        except Exception as exc:
            logger.exception("MQTT message handling failed: %s", exc)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message

    stop = {"running": True}

    def _shutdown(signum, frame):
        del signum, frame
        stop["running"] = False
        client.disconnect()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    logger.info("Connecting to MQTT broker %s:%s", DEFAULT_BROKER, DEFAULT_PORT)
    client.connect(DEFAULT_BROKER, DEFAULT_PORT, keepalive=60)
    client.loop_start()

    try:
        while stop["running"]:
            signal.pause()
    except AttributeError:
        # Windows has no signal.pause — block on loop
        import time

        while stop["running"]:
            time.sleep(1)

    client.loop_stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
