/bin/bash -l -c python3 -I - <<'PY'
import base64
import codecs
import json
import os
import stat as stat_module
import sys

path = "/checkout/target.txt"
offset = 1
limit = 10000
max_bytes = 262144
half = max_bytes // 2

def emit(value):
    sys.stdout.write(json.dumps(value, separators=(",", ":")))
    sys.stdout.flush()
    sys.exit(0)

try:
    if not stat_module.S_ISREG(os.stat(path).st_mode):
        emit({"status": "open_error"})
    source = open(path, "rb")
except OSError:
    emit({"status": "open_error"})

start = 0 if offset is None else offset - 1
end = None if limit is None else start + limit
decoder = codecs.getincrementaldecoder("utf-8")("strict")
size = 0
newlines = 0
# The newlines before and inside the selection, and the selection state: 0 before, 1 inside, 2 after.
seen = 0
state = 1 if start == 0 else 0
selected = 0
head = bytearray()
tail = bytearray()

def take(data):
    global selected
    selected += len(data)
    if len(head) <= max_bytes:
        head.extend(data[: max_bytes + 1 - len(head)])
    if half > 0:
        tail.extend(data[-half:])
        if len(tail) > half:
            del tail[: len(tail) - half]

def end_of_newline(data, index, count):
    for _ in range(count):
        index = data.index(b"\n", index) + 1
    return index

with source:
    first = True
    while True:
        data = source.read(1024 * 1024)
        if not data:
            break
        if first:
            first = False
            if data.startswith(b"\xef\xbb\xbf"):
                data = data[3:]
        try:
            decoder.decode(data)
        except UnicodeDecodeError:
            emit({"status": "invalid_utf8"})
        size += len(data)
        newlines += data.count(b"\n")
        index = 0
        if state == 0:
            found = data.count(b"\n")
            if found < start - seen:
                seen += found
                continue
            index = end_of_newline(data, 0, start - seen)
            seen = start
            state = 1
        if state == 1:
            found = data.count(b"\n", index)
            if end is None or found < end - seen:
                take(data[index:])
                seen += found
            else:
                stop = end_of_newline(data, index, end - seen)
                take(data[index : stop - 1])
                state = 2

try:
    decoder.decode(b"", True)
except UnicodeDecodeError:
    emit({"status": "invalid_utf8"})

def b64(data):
    return base64.b64encode(bytes(data)).decode("ascii")

if selected <= max_bytes:
    emit({"status": "whole", "size": size, "lines": newlines + 1, "text": b64(head)})
emit(
    {
        "status": "elided",
        "size": size,
        "lines": newlines + 1,
        "selectedBytes": selected,
        "head": b64(head[: half + 1]),
        "tail": b64(tail),
    }
)
PY
