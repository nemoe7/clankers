---
name: gpt-quirks
description: Automatically apply verified quirks in GPT and connected tool behavior when relevant.
---

# GPT Quirks

Apply only verified quirks relevant to the current task.

## Documented quirks

### Plugin Creator file uploads

Plugin Creator file inputs require a host-uploaded file reference.

- A local path is not a valid host-uploaded reference.
- A Files/Library `file_*` ID is not interchangeable with a Plugin Creator host-uploaded reference.
- Use the host-uploaded reference returned for the archive before passing it to Plugin Creator.

An error for one file-reference type does not prove another type valid.
