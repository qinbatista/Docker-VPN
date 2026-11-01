# Hysteria2 + Salamander — UDP 7001

The template uses `hysteria2_salamander.password` for authentication and `obfs_password` for Salamander. Both client and server must use the same obfuscation password. TLS protection and certificate verification remain enabled.

This is the obfuscated mode of Hysteria2. Obfuscation changes packet appearance; it does not guarantee reachability when a network blocks UDP. Compare its measured speed and reliability on the actual client network.
