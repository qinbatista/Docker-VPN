# VLESS REALITY / Vision — TCP 443

`inbound.json` is the Xray inbound template. Private inputs are `reality.uuid`, `private_key`, `public_key`, `short_id`, `server_name`, `target` and optional `clients` in the separate secrets file. Vision remains enabled for generated clients.

The client address is the VPN's own domain. REALITY SNI is the selected target, which may differ from that address. Keep an existing HTTPS/SNI frontend's website routes intact. This folder contributes one inbound to the shared container; it does not start a second Docker service.
