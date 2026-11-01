"""Client-encrypted backup to an existing private AWS S3 bucket."""
import argparse
import hashlib
import json
import pathlib
import stat
import sys
import tarfile

sys.dont_write_bytecode = True
from processes import run


def backup(private, work, bucket, key):
    private = private.resolve(strict=True)
    work = work.resolve(strict=True)
    if private == work or private in work.parents or work in private.parents:
        raise ValueError('Use an isolated task Cache as work directory')
    block = json.loads(run(['aws', 's3api', 'get-public-access-block', '--bucket', bucket], text=True).stdout)
    if not all(block['PublicAccessBlockConfiguration'].get(name) for name in ['BlockPublicAcls', 'IgnorePublicAcls', 'BlockPublicPolicy', 'RestrictPublicBuckets']):
        raise ValueError('Refusing a bucket without complete public access blocking')
    identity = private / 'backup-age.key'
    if not identity.exists():
        run(['age-keygen', '-o', str(identity)])
        identity.chmod(0o600)
    if identity.is_symlink() or (sys.platform != 'win32' and stat.S_IMODE(identity.stat().st_mode) & 0o077):
        raise ValueError('Backup identity must be a private regular file')
    recipient = run(['age-keygen', '-y', str(identity)], text=True).stdout.strip()
    archive, encrypted, restored, downloaded = [work / name for name in ['private-backup.tar', 'private-backup.tar.age', 'restore-check.tar', 's3-readback.age']]
    paths = [private / name for name in ['secrets.json', 'client-links.txt', 'medians.json'] if (private / name).is_file()]
    if not paths or not (private / 'secrets.json').is_file():
        raise ValueError('Missing private/secrets.json')
    if any(path.exists() for path in [archive, encrypted, restored, downloaded]):
        raise ValueError('Backup work paths must be absent')
    try:
        with tarfile.open(archive, 'w') as output:
            for path in paths:
                if path.is_symlink():
                    raise ValueError('Symlink private inputs are not allowed')
                output.add(path, arcname=path.name, recursive=False)
        archive.chmod(0o600)
        run(['age', '-r', recipient, '-o', str(encrypted), str(archive)])
        encrypted.chmod(0o600)
        run(['age', '-d', '-i', str(identity), '-o', str(restored), str(encrypted)])
        if restored.read_bytes() != archive.read_bytes():
            raise RuntimeError('Local encrypted backup restore did not match')
        digest = hashlib.sha256(encrypted.read_bytes()).hexdigest()
        run(['aws', 's3api', 'put-object', '--bucket', bucket, '--key', key, '--body', str(encrypted), '--server-side-encryption', 'AES256', '--metadata', json.dumps({'sha256': digest})])
        run(['aws', 's3api', 'get-object', '--bucket', bucket, '--key', key, str(downloaded)])
        downloaded.chmod(0o600)
        if hashlib.sha256(downloaded.read_bytes()).hexdigest() != digest:
            raise RuntimeError('Uploaded ciphertext readback did not match')
        receipt = {'bucket': bucket, 'key': key, 'ciphertext_sha256': digest, 'local_decrypt_verified': True, 'S3_bytes_verified': True, 'key_stored_only_in_private_owner': True}
        output = private / 'backup-receipt.json'
        output.write_text(json.dumps(receipt, indent=2) + '\n')
        output.chmod(0o600)
        print(json.dumps({'backup_uploaded': True, 'decrypt_verified': True, 'S3_bytes_verified': True}))
    finally:
        for path in [archive, encrypted, restored, downloaded]:
            if path.exists() and not path.is_symlink():
                path.unlink()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-dir', type=pathlib.Path, required=True)
    parser.add_argument('--work-dir', type=pathlib.Path, required=True)
    parser.add_argument('--bucket', required=True)
    parser.add_argument('--key', required=True)
    args = parser.parse_args()
    backup(args.private_dir, args.work_dir, args.bucket, args.key)
