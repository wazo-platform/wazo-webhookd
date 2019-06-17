#!/usr/bin/env python3

import glob
import os
import subprocess
import yaml

from ansible.module_utils.basic import AnsibleModule


def main():
    module = AnsibleModule(
        argument_spec=dict(
            services=dict(required=True, type='list'),
            tox_envlist=dict(required=True, type='str'),
            project_dir=dict(required=True, type='str'),
            projects=dict(required=True, type='list'),
        )
    )
    envlist = module.params['tox_envlist']
    project_dir = module.params['project_dir']
    projects = module.params['projects']
    services = module.params['services']

    envdir = '{project_dir}/.tox/{envlist}'.format(
        project_dir=project_dir, envlist=envlist)
    if not os.path.exists(envdir):
        module.exit_json(
            changed=False, msg=("envdir does not exist, "
                                "skipping docker compose customisation"))
    tox_python = '{envdir}/bin/python'.format(envdir=envdir)

    volumes = set()
    for project in projects:
        root = project['src_dir']
        subprocess.check_output(
            [os.path.abspath(tox_python), 'setup.py', 'egg_info'],
            cwd=os.path.abspath(root))
        top_level = glob.glob("{}/*.egg-info/top_level.txt".format(root))[0]
        with open(top_level) as f:
            package = f.read().strip()

        volumes.add("{root}/{package}:/usr/local/lib/python3.5/site-packages/{package}".format(
            root=root, package=package
        ))

    volumes = list(volumes)
    docker_compose_override = {
        'version': '3',
        'services': dict([
            (service, {
                'volumes': volumes
            }) for service in services
        ])
    }

    docker_compose_override_contents = yaml.dump(docker_compose_override)
    docker_compose_override_file = (
        "{project_dir}/docker-compose.integration.override.yaml".format(
            project_dir=project_dir))

    with open(docker_compose_override_file, "w") as f:
        f.write(docker_compose_override_contents)

    module.exit_json(
        file=docker_compose_override_file,
        contents=docker_compose_override_contents
    )


if __name__ == '__main__':
    main()
