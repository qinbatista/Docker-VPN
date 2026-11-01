# DockerVPN

Five independent VPN modes in one Linux Docker container. Xray serves VLESS REALITY / Vision; sing-box serves Hysteria2, Hysteria2 with Salamander, TUIC v5 and Trojan TLS.

| Directory | Public port | Mode |
|---|---|---|
| `vless-reality/` | TCP 443 | VLESS REALITY / Vision |
| `hysteria2/` | UDP 7000 | Hysteria2 |
| `hysteria2-salamander/` | UDP 7001 | Hysteria2 + Salamander |
| `tuic/` | UDP 7002 | TUIC v5 / BBR |
| `trojan/` | TCP 7003 | Trojan TLS |

The repository contains public templates and tools. Actual credentials, certificate keys, client links, host addresses and backup identities belong in ignored `private/` or their deployment's private owner. Never put them in Git or an image layer. S3 backups are encrypted on the client before upload.

The container uses an isolated bridge network and one supervised Xray process plus one sing-box process. Independent protocol folders feed the shared renderer. Certificate renewal remains with the external certificate owner; only the certificate directory is mounted read-only.

## Build and configure

The production image targets Linux ARM64. Host preparation tools use Python 3.9+ and its standard library. Actual runtime checks cover Linux ARM64 and the native macOS Shadowrocket client; Windows execution is not verified.

```text
docker compose build
```

Generate private credentials after building. macOS/Linux:

```text
python3 -B tools/dockervpn.py init --domain vpn.example.com
```

Windows PowerShell:

```text
py -3 -B tools/dockervpn.py init --domain vpn.example.com
```

Put the matching `vpn.example.com.crt` and `vpn.example.com.key` in `private/tls/`, or set `DVPN_TLS_DIR` to the certificate owner's directory. Copy `.env.example` to ignored `.env` when changing mount paths. Certificate verification remains enabled in the generated clients.

```text
docker compose run --rm --no-deps vpn check
docker compose up -d --wait
docker compose ps
```

Only the `vpn` service is started. A core crash stops its peer and exits the container so Docker can restart the complete service. Health requires both cores and all five listeners. Health alone is not an authenticated end-to-end check.

## Existing-host migration

On the Linux host, build first and provide private credentials plus a matching certificate directory. `tools/deploy_local.py` validates both real cores before stopping the explicitly named old containers, saves their native Docker metadata privately, and restores them if cutover fails. It never guesses which existing applications may be stopped. Example:

```text
python3 -B tools/deploy_local.py --private-dir /etc/dockervpn --tls-dir /path/to/certificates --previous-container old-vpn-container
```

Existing SNI-based HTTPS ingress must continue routing REALITY traffic to the new 443 backend. Keep the client server address as your own domain and the REALITY SNI as the selected REALITY target. Preserve unrelated website and certificate-renewal services.

The Docker bridge gives the cores their own UDP socket namespace. Do not add the former host-LAN `inet4_bind_address` to these container configurations. Review subnet overlap and set `DVPN_IPV4_SUBNET` / `DVPN_IPV6_SUBNET` when needed.

## Clients and measured names

Generate an import file privately; its URLs contain authentication material:

```text
python3 -B tools/dockervpn.py links --secrets private/secrets.json --output private/client-links.txt
```

Use `py -3` instead of `python3` on Windows. The native client action below runs only on an authorized macOS host with Shadowrocket installed and its existing proxy rule selected:

```text
python3 -B tools/shadowrocket_client.py --links /path/to/private/client-links.txt --expected-ip YOUR_SERVER_IPV4
```

It imports the five nodes through a temporary loopback subscription, detaches that subscription, preserves unrelated nodes, and saves native configuration recovery under the client's private owner. Each node must pass real HTTPS, exit-IP, full small transfer, HTTP/2 and UDP-DNS checks. The speed comparison uses three valid HTTP/1.1 transfers of the same Google CDN 32 MiB range, with a 15-second window. Partial successful transfers are measured by actual received bytes; transport failures remain in the result. Tests run sequentially.

Successful profiles are named `Technical-Name MedianMbps`, and the fastest accepted node is selected. The private owner receives `dockervpn-results.json`, `dockervpn-medians.json` and `dockervpn-client-links.txt`. These contain deployment-specific data and stay outside Git. Re-run after changing a core, protocol or network before claiming new performance.

## Private S3 backup

Install the official `age` / `age-keygen` tools and AWS CLI on the backup host. Use an existing authorized AWS profile and a bucket with all four S3 public-access blocks enabled:

```text
python3 -B tools/private_backup.py --private-dir private --work-dir Cache/YOUR_TASK_RUN --bucket YOUR_PRIVATE_BUCKET --key DockerVPN/private/config.tar.age
```

The work directory must already exist under the task's ignored Cache. The tool archives only `secrets.json`, optional `client-links.txt` and `medians.json`; it excludes the identity file. It encrypts locally, verifies decryption, uploads ciphertext with S3 server-side encryption, downloads it again and compares bytes. Consumed plaintext and transport copies are removed. Keep `private/backup-age.key` separately backed up; it is deliberately excluded from both Git and S3. Restore requires that identity and `age -d`.

## Verification

Run the focused contract suite with an isolated project Cache directory. macOS/Linux:

```text
DVPN_TEST_CACHE=Cache/YOUR_TASK_RUN python3 -B -m unittest discover -s .agents/skills/testing-skill/tests -v
```

Windows PowerShell:

```powershell
$env:DVPN_TEST_CACHE = 'Cache\YOUR_TASK_RUN'
py -3 -B -m unittest discover -s .agents/skills/testing-skill/tests -v
```

Then run the native core `check` command and actual affected client flow. Public tests use synthetic data. Never publish live reports, rendered configurations or import URLs as test fixtures. See [AGENTS.md](AGENTS.md) for source/private ownership and [THIRD_PARTY.md](THIRD_PARTY.md) for upstream components.
