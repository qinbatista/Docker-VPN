# Hysteria2 — UDP 7000

`inbound.json` is the plain Hysteria2 template. The private password comes from `hysteria2.password`; the certificate filenames use `domain`. Generated client links keep certificate verification enabled. No bandwidth limit is imposed by this template.

This is a separate authenticated listener inside the shared sing-box core. It uses the container's bridge namespace, not a host-LAN source-address binding.
