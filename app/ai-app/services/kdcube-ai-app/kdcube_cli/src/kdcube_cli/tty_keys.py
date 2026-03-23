from __future__ import annotations

import os
import select
import sys
import termios
import tty


KEY_UP = "__UP__"
KEY_DOWN = "__DOWN__"
KEY_ENTER = "__ENTER__"
KEY_ESCAPE = "__ESCAPE__"
KEY_INTERRUPT = "__INTERRUPT__"
KEY_EOF = "__EOF__"


def read_tty_key() -> str:
    fd: int | None = None
    owns_fd = False
    old_attrs = None
    try:
        try:
            fd = os.open("/dev/tty", os.O_RDONLY)
            owns_fd = True
        except OSError:
            fd = sys.stdin.fileno()

        old_attrs = termios.tcgetattr(fd)
        tty.setraw(fd)

        first = os.read(fd, 1)
        if not first:
            return KEY_EOF
        if first == b"\x03":
            return KEY_INTERRUPT
        if first in {b"\r", b"\n"}:
            return KEY_ENTER
        if first != b"\x1b":
            return first.decode("utf-8", errors="ignore")

        seq = bytearray(first)
        while True:
            ready, _, _ = select.select([fd], [], [], 0.03)
            if not ready:
                break
            chunk = os.read(fd, 1)
            if not chunk:
                break
            seq.extend(chunk)
            if bytes(seq) in {b"\x1b[A", b"\x1b[B", b"\x1bOA", b"\x1bOB", b"\x1bk", b"\x1bj"}:
                break
            if len(seq) >= 3 and seq[:2] == b"\x1b[" and seq[-1:] in b"~ABCDHF":
                break

        raw = bytes(seq)
        if raw in {b"\x1b[A", b"\x1bOA"}:
            return KEY_UP
        if raw in {b"\x1b[B", b"\x1bOB"}:
            return KEY_DOWN
        if raw == b"\x1b":
            return KEY_ESCAPE
        return raw.decode("utf-8", errors="ignore")
    finally:
        if fd is not None and old_attrs is not None:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)
            except Exception:
                pass
        if owns_fd and fd is not None:
            try:
                os.close(fd)
            except Exception:
                pass
