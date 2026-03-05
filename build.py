#!/usr/bin/env python3
# Copyright: Contributors to the Ansible project
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

import argparse
import os
import pathlib
import platform
import subprocess
import sys
import tempfile


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument('src', type=pathlib.Path, help='Path to galaxy source')
    parser.add_argument('tag', help='Tag to apply to the built image')
    return parser.parse_args()


def dc_command(
    cmd: list[str],
    capture: bool = False,
    check: bool = True,
    **kwargs
) -> subprocess.CompletedProcess:

    if capture is False and 'stdout' not in kwargs:
        kwargs['stdout'] = sys.stderr
    return subprocess.run(
        ['docker', 'compose', '--progress', 'plain'] + cmd,
        capture_output=capture,
        check=check,
        **kwargs
    )


def docker_command(
    cmd: list[str],
    capture: bool = False,
    check: bool = True,
    **kwargs
) -> subprocess.CompletedProcess:

    if capture is False and 'stdout' not in kwargs:
        kwargs['stdout'] = sys.stderr
    return subprocess.run(
        ['docker'] + cmd,
        capture_output=capture,
        check=check,
        **kwargs
    )



def get_arch() -> str:
    machine = platform.machine().lower()
    if machine in ('x86_64', 'amd64'):
        arch = 'amd64'
    elif machine in ('aarch64', 'arm64'):
        arch = 'arm64'
    else:
        raise SystemExit(f'Unsupported architecture: {machine}')

    print(f'Detected architecture: {arch}', file=sys.stderr)

    return arch


def run_compose(tag: str, src: str) -> None:
    print('Clean up compose...', file=sys.stderr)
    dc_command(['down', '-v'])

    print('Bring up compose...', file=sys.stderr)
    dc_command(['up', '-d'], env=os.environ | {'TAG': tag, 'GALAXY_NG_SRC': src})

    print('Prepopulate galaxy...', file=sys.stderr)
    try:
        dc_command(['wait', 'setup_collections'])
    except subprocess.CalledProcessError:
        print('Setup collections failed, dumping logs:', file=sys.stderr)
        dc_command(['logs', 'setup_collections'], check=False)
        raise

    print('Stop compose...', file=sys.stderr)
    dc_command(['stop'])


def remove_compose() -> None:
    print('Clean up compose...', file=sys.stderr)
    dc_command(['down', '-v'])


def create_data_archive(tmpdir: str) -> str:
    print('Run temporary container to create volume tarball...', file=sys.stderr)
    volumes = [
        '--mount', 'type=volume,source=var_lib_pulp,target=/var/lib/pulp',
        '--mount', 'type=volume,source=etc_pulp_certs,target=/etc/pulp/certs',
        '--mount', 'type=volume,source=pg_data,target=/var/lib/postgresql/data',
        '--mount', 'type=volume,source=artifacts,target=/artifacts',
    ]
    alpine = docker_command(
        ['run', '-d'] + volumes + ['alpine:latest', 'sleep', 'infinity'],
        capture=True,
        text=True,
    )
    alpine_id = alpine.stdout.strip()

    archive = 'galaxy-archive.tar'
    print('Make volume tarball...', file=sys.stderr)
    docker_command(
        ['exec', '-ti', alpine_id] + [
            'tar', '-cf', f'/{archive}',
            '/var/lib/pulp', '/etc/pulp/certs', '/var/lib/postgresql/data',
            '/artifacts',
        ]
    )

    print('Fetch volume tarball...', file=sys.stderr)
    docker_command(
        [
            'cp', f'{alpine_id}:/{archive}', str(tmpdir)
        ]
    )
    print('Remove temporary container...', file=sys.stderr)
    docker_command(['rm', '-f', alpine_id])

    return os.path.join(tmpdir, archive)


def build_container(tag: str, arch: str, archive: str) -> None:
    DOCKERFILE = f'''
    FROM localhost/galaxy_ng:{tag}

    ADD {archive} /

    VOLUME /var/lib/postgresql/data
    VOLUME /artifacts
    '''.encode()

    print('Build galaxy-ng-test-container container...', file=sys.stderr)
    image_tag = f'galaxy-ng-test-container:{tag}-{arch}'
    with tempfile.NamedTemporaryFile() as f:
        f.write(DOCKERFILE)
        f.flush()
        docker_command(
            [
                'build',
                '-t', image_tag,
                '-f', f.name,
                '.'
            ],
            check=True,
        )


def main():
    args = parse_args()

    if not args.src.exists():
        raise SystemExit(f'{args.src} does not exist')

    arch = get_arch()

    run_compose(args.tag, args.src)

    cwd = os.getcwd()
    with tempfile.TemporaryDirectory(dir=cwd) as tmpdir:
        archive = create_data_archive(tmpdir)
        remove_compose()
        build_container(args.tag, arch, os.path.relpath(archive, cwd))

    print('DONE!', file=sys.stderr)

    # These values are directly consumed in GITHUB_OUTPUT
    print(f'tag={args.tag}')
    print(f'arch={arch}')


if __name__ == '__main__':
    main()
