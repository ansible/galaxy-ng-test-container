# galaxy-ng-test-container

Container for ansible core CI testing of ansible-galaxy

## Setup

This container runs `galaxy_ng` pre-populated with test collections for ansible core CI.

The container also exports 2 volumes for use with `--volumes-from` to support the pre-populated data for `postgres` and `amanda`:

1. `/var/lib/postgresql/data`
1. `/artifacts`

## Build

*Note*: Requires `docker-compose`
*Note*: This project uses calver in the format of `0Y.0M.MICRO`

```bash
git clone git@github.com:ansible/galaxy_ng.git
python3 build.py /path/to/galaxy_ng YY.MM.x
```

The above will produce a container image of `galaxy-ng-test-container:YY.MM.x-arch` such as `galaxy-ng-test-container:26.03.0-arm64'

## Running

This container does not provide postgres, which should be provided through a separate postgres container.

## Additional Info

This project also contains a `galaxy_ng.env` file required for our use of running `galaxy_ng`, and must stay in sync with `test/lib/ansible_test/_internal/commands/integration/cloud/galaxy.py` in ansible-core.

## Testing in ansible-test before tagging

1. Follow the build instructions from above
1. Execute `ansible-test` overriding the `galaxy_ng` container image using the `tag` and `arch` from building:

    ```bash
    ANSIBLE_GALAXY_CONTAINER=galaxy-ng-test-container:26.03.0-arm64 ansible-test integration --docker -v --python 3.14 shippable/galaxy/group1/
    ```
