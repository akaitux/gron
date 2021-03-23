#!/usr/bin/env python3
import argparse
import logger as logger_module
import logging
import discovery
import pprint
import sys
import os


def parse_arguments():
    description = """
    ./main.py -s - Show current files state
    ./main.py -g domain.ru_year -t _deploy_cert -CD - Run all tasks from deployment group 'domain.ru_year' with ansible playbook flags '-CD'
    ./main.py -g domain.ru_year -t _deploy_cert --dry-run - will show the commands being run.
    """
    parser = argparse.ArgumentParser(description=description, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-c','--config', help="Config path")
    parser.add_argument('-nc','--no-config', action='store_true', help="Don't use config file")
    parser.add_argument('-s','--show', action='store_true', help="Show all collected data")
    parser.add_argument('-sg','--show-dg', action='store_true', help="Show deployment groups with available tags")
    parser.add_argument('-st','--show-tags', action='store_true', help="Show available tags")
    parser.add_argument('-g', '--deployment-group', help="Deployment group")
    parser.add_argument('-t','--deployment-task', help="Deployment task")
    parser.add_argument('-C','--ansible-dry-run', action='store_true', help="ansible's '-C' flag for all playbooks")
    parser.add_argument('-D', '--ansible-debug', action='store_true', help="ansible's '-D' flag for all playbooks")
    parser.add_argument('-e', '--environment', action='append', help="Additional variables for ansible: -e \"a='b' c='d'\"")
    parser.add_argument('-l', '--limit', help="Limit execution by host (ansible-playbook -l)")
    parser.add_argument('--root-dir', help="Dir with playbooks, ~/ansible by default")
    parser.add_argument('--ansible-bin', help="Path to ansible-playbook bin, by default /usr/bin/ansible-playbook")
    parser.add_argument('--dry-run', action='store_true', help="Dry run mode (without playbooks execution)")
    parser.add_argument('--debug', action='store_true', help="Debug")
    parser.add_argument('--silent', action='store_true', help="Show only critical logs")
    parser.add_argument('--skip-dg-notfound', action='store_true', help="Will not show an error if deployment group not found")
    return parser.parse_args()


def setup_logger(args):
    options = {'debug': False, 'silent': False}
    if args.debug:
        options['debug'] = True
    if args.silent:
        options['silent'] = True
    logger_module.setup(options=options)
    global logger
    logger = logging.getLogger('main')

def load_config(args):
    config_path = None
    if not args.config and not args.no_config:
        current_executed_file = os.path.realpath(__file__)
        current_dir = '/'.join(current_executed_file.split('/')[:-1])
        config_path = os.path.join(current_dir, 'config.yml')
        if not os.path.exists(config_path):
            config_path = None
    else:
        config_path = args.config
    if config_path:
        logger.info('Config: {}'.format(config_path))
        config = discovery.read_yaml(config_path)
    else:
        config = {}
    for arg_key, arg_value in args.__dict__.items():
        config[arg_key] = arg_value
    config['deployment_tasks'] = ['_deploy_cert', '_certbot_acme','_certbot_upload','_gcore_upload']
    return config


if __name__ == '__main__':
    args = parse_arguments()
    if args.environment:
        tmp_env = []
        for arg in args.environment:
            if '=' not in arg:
                continue
            arg = '-e {}'.format(arg)
            tmp_env.append(arg)
        args.environment = tmp_env
    else:
        args.environment = []
    setup_logger(args)
    config = load_config(args)
    required_arguments = [
        args.show,
        args.show_dg,
        args.show_tags,
        args.deployment_group and args.deployment_task
    ]
    if not any(required_arguments):
        print('Required arguments not set')
        sys.exit(1)
    deployment_groups = discovery.get_deployment_groups(config)
    if args.show:
        print('\n')
        print(deployment_groups)
        sys.exit(0)
    if args.show_dg:
        print('\n')
        print(deployment_groups.show_dg())
        sys.exit(0)
    if args.show_tags:
        print('\n')
        print(deployment_groups.show_tags())
        sys.exit(0)
    if not args.deployment_group and not args.deployment_task:
        print('deployment group (-g) and deployment task (-t) is required')
        sys.exit(1)
    deployment_groups.run(args.deployment_group, args.deployment_task)

