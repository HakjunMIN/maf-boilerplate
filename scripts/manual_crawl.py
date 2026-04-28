from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIRECTORY = REPO_ROOT / "src"
if str(SRC_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SRC_DIRECTORY))

from homestyle_ingestion.manual_crawl_cli import main  # noqa: E402


if __name__ == "__main__":
    main()
