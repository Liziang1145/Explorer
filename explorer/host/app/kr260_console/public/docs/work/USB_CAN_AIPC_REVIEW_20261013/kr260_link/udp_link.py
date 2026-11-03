#!/usr/bin/env python3
"""Small, independent UDP link for AI PC <-> KR260 bring-up.

This intentionally does not subscribe to ROS motor-control topics or access CAN.
Both computers run the same file. Each datagram is UTF-8 JSON with protocol,
version, kind, sequence, sender timestamp (ns), and an object payload. The
receiver acknowledges data; ping receives pong. Clocks are not assumed synced.
"""

from __future__ import annotations

import argparse
from collections import deque
import ipaddress
import json
import secrets
import socket
import sys
import threading
import time
from typing import Any, Callable


PROTOCOL = "apex-kr260"
VERSION = 1
MAX_DATAGRAM = 1200  # Stay below the usual Ethernet MTU without fragmentation.
KINDS = {"ping", "pong", "data", "ack"}


class ProtocolError(ValueError):
    pass


def ipv4(value: str) -> str:
    try:
        address = ipaddress.IPv4Address(value)
    except ipaddress.AddressValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    if address.is_unspecified or address.is_multicast or address == ipaddress.IPv4Address("255.255.255.255"):
        raise argparse.ArgumentTypeError("use a specific unicast IPv4 address, not 0.0.0.0 or broadcast")
    return str(address)


def port(value: str) -> int:
    number = int(value)
    if not 1 <= number <= 65535:
        raise argparse.ArgumentTypeError("port must be in 1..65535")
    return number


def encode(kind: str, seq: int, payload: dict[str, Any] | None = None) -> bytes:
    if kind not in KINDS or isinstance(seq, bool) or not isinstance(seq, int) or not 0 <= seq < 2**32:
        raise ProtocolError("invalid kind or sequence")
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ProtocolError("payload must be a JSON object")
    packet = {
        "protocol": PROTOCOL,
        "version": VERSION,
        "kind": kind,
        "seq": seq,
        "time_ns": time.time_ns(),
        "payload": payload,
    }
    try:
        raw = json.dumps(packet, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ProtocolError(f"payload is not valid JSON: {exc}") from exc
    if len(raw) > MAX_DATAGRAM:
        raise ProtocolError(f"datagram is {len(raw)} bytes; limit is {MAX_DATAGRAM}")
    return raw


def decode(raw: bytes) -> dict[str, Any]:
    if len(raw) > MAX_DATAGRAM:
        raise ProtocolError("datagram exceeds size limit")
    try:
        packet = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ProtocolError("invalid UTF-8 JSON") from exc
    if not isinstance(packet, dict) or set(packet) != {"protocol", "version", "kind", "seq", "time_ns", "payload"}:
        raise ProtocolError("invalid packet fields")
    if packet["protocol"] != PROTOCOL or type(packet["version"]) is not int or packet["version"] != VERSION:
        raise ProtocolError("unsupported protocol/version")
    if not isinstance(packet["kind"], str) or packet["kind"] not in KINDS:
        raise ProtocolError("invalid packet kind")
    if type(packet["seq"]) is not int or not 0 <= packet["seq"] < 2**32:
        raise ProtocolError("invalid sequence")
    if type(packet["time_ns"]) is not int or packet["time_ns"] < 0:
        raise ProtocolError("invalid timestamp")
    if not isinstance(packet["payload"], dict):
        raise ProtocolError("payload must be an object")
    return packet


class LinkServer:
    def __init__(
        self,
        bind_ip: str,
        bind_port: int,
        allowed_peer_ip: str,
        on_data: Callable[[dict[str, Any], tuple[str, int]], None] | None = None,
    ) -> None:
        self.allowed_peer_ip = allowed_peer_ip
        self.on_data = on_data or self._print_data
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((bind_ip, bind_port))
        self.socket.settimeout(0.2)
        self._seen_order: deque[int] = deque()
        self._seen: set[int] = set()

    @property
    def address(self) -> tuple[str, int]:
        return self.socket.getsockname()

    @staticmethod
    def _print_data(payload: dict[str, Any], source: tuple[str, int]) -> None:
        print(f"DATA from {source[0]}:{source[1]}: {json.dumps(payload, ensure_ascii=False)}", flush=True)

    def close(self) -> None:
        self.socket.close()

    def serve_forever(self, stop: threading.Event | None = None) -> None:
        print(f"Listening on {self.address[0]}:{self.address[1]}, allowing {self.allowed_peer_ip}", flush=True)
        while stop is None or not stop.is_set():
            try:
                raw, source = self.socket.recvfrom(MAX_DATAGRAM + 1)
            except socket.timeout:
                continue
            except OSError:
                if stop is not None and stop.is_set():
                    break
                raise
            if source[0] != self.allowed_peer_ip:
                continue
            try:
                packet = decode(raw)
            except ProtocolError as exc:
                print(f"Ignored invalid packet from {source[0]}: {exc}", file=sys.stderr, flush=True)
                continue
            kind, seq = packet["kind"], packet["seq"]
            if kind == "ping":
                self.socket.sendto(encode("pong", seq), source)
            elif kind == "data":
                if seq not in self._seen:
                    try:
                        self.on_data(packet["payload"], source)
                    except Exception as exc:
                        print(f"Failed to process data from {source[0]}: {exc}", file=sys.stderr, flush=True)
                        continue  # No ACK: sender may retry after the application recovers.
                    if len(self._seen_order) == 256:
                        self._seen.remove(self._seen_order.popleft())
                    self._seen_order.append(seq)
                    self._seen.add(seq)
                self.socket.sendto(encode("ack", seq), source)


def request(
    bind_ip: str,
    peer_ip: str,
    peer_port: int,
    kind: str,
    payload: dict[str, Any] | None = None,
    timeout: float = 1.0,
    retries: int = 3,
) -> float:
    if kind not in {"ping", "data"} or timeout <= 0 or retries < 1:
        raise ValueError("request must be ping/data with positive timeout and retries")
    seq = secrets.randbits(32)
    raw = encode(kind, seq, payload)
    expected_kind = "pong" if kind == "ping" else "ack"
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((bind_ip, 0))
        for _ in range(retries):
            start = time.monotonic()
            sock.sendto(raw, (peer_ip, peer_port))
            deadline = start + timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                sock.settimeout(remaining)
                try:
                    response, source = sock.recvfrom(MAX_DATAGRAM + 1)
                except socket.timeout:
                    break
                if source != (peer_ip, peer_port):
                    continue
                try:
                    reply = decode(response)
                except ProtocolError:
                    continue
                if reply["seq"] == seq and reply["kind"] == expected_kind:
                    return (time.monotonic() - start) * 1000.0
    raise TimeoutError(f"no {expected_kind} from {peer_ip}:{peer_port} after {retries} attempts")


def main() -> int:
    parser = argparse.ArgumentParser(description="Safe AI PC / KR260 UDP link test (no robot actuation)")
    modes = parser.add_subparsers(dest="mode", required=True)
    listen = modes.add_parser("listen", help="receive data and return ACK; answer ping")
    listen.add_argument("--bind-ip", type=ipv4, required=True)
    listen.add_argument("--port", type=port, required=True)
    listen.add_argument("--allow-ip", type=ipv4, required=True)

    for name in ("ping", "send"):
        command = modes.add_parser(name)
        command.add_argument("--bind-ip", type=ipv4, required=True)
        command.add_argument("--peer-ip", type=ipv4, required=True)
        command.add_argument("--peer-port", type=port, required=True)
        command.add_argument("--timeout", type=float, default=1.0)
        command.add_argument("--retries", type=int, default=3)
        if name == "send":
            content = command.add_mutually_exclusive_group(required=True)
            content.add_argument("--text")
            content.add_argument("--json", help="JSON object, e.g. '{\"sensor\":\"test\",\"value\":1}'")

    args = parser.parse_args()
    try:
        if args.mode == "listen":
            server = LinkServer(args.bind_ip, args.port, args.allow_ip)
            try:
                server.serve_forever()
            finally:
                server.close()
            return 0
        payload = None
        if args.mode == "send":
            payload = {"text": args.text} if args.text is not None else json.loads(args.json)
            if not isinstance(payload, dict):
                raise ProtocolError("--json must be a JSON object")
        kind = "data" if args.mode == "send" else "ping"
        rtt_ms = request(args.bind_ip, args.peer_ip, args.peer_port, kind, payload, args.timeout, args.retries)
        print(f"{args.mode} confirmed by {args.peer_ip}:{args.peer_port}, RTT={rtt_ms:.3f} ms")
        return 0
    except (OSError, ValueError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
