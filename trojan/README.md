# Trojan TLS — TCP 7003

The template uses `trojan.password` and the domain's existing certificate directory. The public and container ports are both 7003. Generated clients set SNI to the VPN domain and retain certificate verification.

Only the TLS Trojan listener uses 7003 in this deployment. Old UDP7003 listeners are not part of the shared container.
