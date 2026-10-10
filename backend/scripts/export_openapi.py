"""Step 1 of type generation: dump the OpenAPI spec (built from app.schemas) to shared/openapi.json.
Step 2 (frontend): openapi-typescript ../shared/openapi.json -o src/api/schema.ts
Run both with `npm run gen:types` from the repo root. No server needed.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import REPO_ROOT  # noqa: E402
from app.main import app  # noqa: E402

out = REPO_ROOT / "shared" / "openapi.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
print(f"wrote {out.relative_to(REPO_ROOT)}")
