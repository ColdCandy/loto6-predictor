#!/usr/bin/env python3
"""招待パスワードの SHA-256 ハッシュを作る"""

from __future__ import annotations

import getpass
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from loto6_predictor.auth import password_hash


def main() -> int:
    if len(sys.argv) > 1:
        pw = sys.argv[1]
    else:
        pw = getpass.getpass("パスワード: ")
    if not pw:
        print("パスワードが空です", file=sys.stderr)
        return 1
    h = password_hash(pw)
    print()
    print("secrets.toml にこう書きます（password 行は不要）:")
    print()
    print("[[auth.invites]]")
    print('username = "your_id"')
    print(f'password_hash = "{h}"')
    print('label = "表示名"')
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
