---
name: testing-skill
description: Focused Docker-VPN rendering, isolation, lifecycle and native China client verification.
---
# Docker-VPN testing

Keep test output and temporary fixtures in the caller's task Cache. Never use production credentials in maintained fixtures.

| Purpose | Level | Relative owner / runner |
|---|---|---|
| Five public templates render into exactly five distinct inbounds with secrets kept separate | 1 | `.agents/skills/testing-skill/tests/test_contracts.py`; Python unittest |
| A failed stop restores the previous restart policy and running owner | 1 | Same contract suite; isolated mocked Docker failure boundary |
| Both real cores accept generated configuration | 2 | `runtime/supervisor.py check` in the built container |
| A real core exit ends its peer and the complete container | 2 | `runtime/supervisor.py serve/health`; task-owned network-disabled container through native Docker APIs |
| Current one-container endpoints authenticate and carry real traffic from China; client names use measured medians | 2 | `tools/shadowrocket_client.py` on the authorized macOS client |

Read the relevant contract and update an existing purpose before adding a duplicate. Use generated test secrets only in task Cache, and read back actual runtime/client identity. Full image construction and China download measurements run when deployment or user scope requires them.

For the lifecycle boundary, start one uniquely owned test container without published ports, wait for health, terminate its sing-box child identified by its own children.json, and verify Docker reports exit 1 with no running container. Remove only that test container. Never inject a fault into the production service for this check.
