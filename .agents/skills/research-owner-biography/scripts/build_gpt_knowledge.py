"""Retired command: GPT output is no longer generated."""
import sys


def main() -> int:
    print(
        "GPT generation is deprecated. Run python tools/build_plugin.py "
        "from the repository root to refresh plugin references; use --check "
        "to verify them or --package to build the plugin ZIP. "
        "The historical GPT files are in archive/owner-biography-gpt/.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
