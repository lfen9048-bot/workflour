#!/bin/bash
set -euo pipefail
exec '/Applications/DeepSeek Harness.app/Contents/Resources/runtime/cli/bin/dsh' --profile omb-coordinator --patch /Users/a1/Documents/a/workflour/tests/fixtures/fallback/cordis.patch.yml
