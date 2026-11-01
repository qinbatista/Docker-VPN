# Upstream components

The MIT license in this repository covers its authored configuration templates and tooling. Upstream binaries and base images retain their own licenses; this repository does not relicense them.

| Component | Pinned input / source |
|---|---|
| Xray core | Existing `qinbatista/xray-reality` image pinned by digest in Dockerfile; [upstream source](https://github.com/XTLS/Xray-core), [upstream license](https://github.com/XTLS/Xray-core/blob/main/LICENSE) |
| sing-box | Official `ghcr.io/sagernet/sing-box` image pinned by digest; [source](https://github.com/SagerNet/sing-box), [license](https://github.com/SagerNet/sing-box/blob/dev/LICENSE) |
| Python / Alpine base | Official Python 3.13 Alpine image pinned by digest; [image source](https://github.com/docker-library/python), [Python license](https://docs.python.org/3/license.html) |
| age, optional backup host tool | [Official source and license](https://github.com/FiloSottile/age) |

The production image is built for Linux ARM64. No deployment credentials or third-party account credentials are included in image layers.
