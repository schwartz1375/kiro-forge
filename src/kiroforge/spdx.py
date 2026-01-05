from __future__ import annotations

SPDX_LICENSES = {
    "MIT",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "GPL-3.0-only",
    "GPL-3.0-or-later",
    "LGPL-3.0-only",
    "LGPL-3.0-or-later",
    "MPL-2.0",
    "AGPL-3.0-only",
    "AGPL-3.0-or-later",
}


def is_spdx_license(value: str) -> bool:
    return value in SPDX_LICENSES
