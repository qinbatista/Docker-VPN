# Runtime

Use configuration.load_private then render/write_runtime for the five fixed protocol folders. Template substitutions preserve JSON types and escaping. Generated secrets live in the container tmpfs; certificates and private inputs are read-only external mounts. The bridge owns an independent socket namespace. supervisor validates both real cores before serving, couples their failure lifetime and checks actual listeners. Dockerfile pins both upstream cores and the Python base. compose.yaml declares exactly one service and five protocol-specific published ports.
