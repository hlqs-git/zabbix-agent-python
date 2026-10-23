"""Install dependencies with the current Python interpreter."""
from pathlib import Path
import subprocess
import sys


def main():
    requirements = Path(__file__).resolve().with_name('requirements.txt')
    return subprocess.call([sys.executable, '-m', 'pip', 'install', '-r', str(requirements)])


if __name__ == '__main__':
    raise SystemExit(main())
