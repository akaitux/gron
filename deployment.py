import yaml
import copy
import json
import logging
import sys
import os
import subprocess
import pprint

logger = logging.getLogger('deployment')

class DeploymentGroups(dict):
    
    def __init__(self, raw_deployment_groups, config):
        """
        raw_deployment_groups: dict
            returned from _find_deployment_groups(...) (discovery.py)
            {
                'domain.ru_year': {
                    '_deploy_cert': [
                        {
                            'dg': 'domain.ru_year',
                            'tags': ['nginx_ssl_conf'],
                            'args': ['-e \'dg="domain.ru_year"\''],
                            'hosts': ['host-*.domain.ru'],
                            'playbook': '/home/user/ansible/nginx/nginx.yml'
                        }, ...
                    ]
                }, ...
            }

        """
        self._config = config
        self.update(raw_deployment_groups)
        self._create_task_objects()

    def _create_task_objects(self):
        for dg_name, dtasks in self.items():
            for task_name, tasks in dtasks.items():
                dtasks[task_name] = [Task(task, self._config) for task in tasks]

    def __str__(self):
        return yaml.dump(json.loads(json.dumps(self)),)

    def show_dg(self):
        """
        returned `str` with:
            deployment_group1:
                task: _deployment_task1
            deployment_group2:
                task: _deployment_task2
        """
        result =  ''
        for dg_name, tags in self.items():
            result += '{}\n'.format(dg_name)
            for tag, tag_tasks in tags.items():
                result += "  {}\n".format(tag)
                for task in tag_tasks:
                    if "playbook" in task:
                        result += "    - {}\n".format(task["playbook"])
        return result

    def show_tags(self):
        result = ""
        for tag in self._config['deployment_tasks']:
            if tag is not None:
                result += "- {}\n".format(tag)
        return result


    def run(self, group, dt):
        if group not in self:
            msg = "Deployment group '{}' doesn't exists".format(group)
            if not self._config['skip_dg_notfound']:
                logger.error(msg)
                sys.exit(1)
            else:
                logger.info(msg)
                sys.exit(0)
        if dt not in self[group]:
            msg = "Group '{}' with deployment task '{}' not found".format(group, dt)
            if not self._config['skip_dg_notfound']:
                logger.error(msg)
                sys.exit(1)
            else:
                logger.info(msg)
                sys.exit(0)
        for task in self[group][dt]:
            task.run()


class Task(dict):
    def __init__(self, task, config):
        """
        task: dict
            {
              'dg': 'domain.ru_year',
              'tags': ['nginx_ssl_conf'],
              'args': ['-e \'dg="domain.ru_year"\''],
              'hosts': ['host-*.domain.ru'], 
              'playbook': '/home/user/ansible/nginx/nginx.yml'
            }
        """
        self._config = config
        self.update(task)
        self._configure()

    def _configure(self):
        cmd = '{bin} {playbook}'
        if isinstance(self['hosts'], list):
            self['hosts'] = ':'.join(self['hosts'])
        ansible_bin = self._config.get('ansible_bin')
        if not ansible_bin:
            ansible_bin = '/usr/bin/ansible-playbook'
        cmd = cmd.format(
            bin=ansible_bin,
            playbook=self['playbook'], 
        )
        if self.get('tags',False):
            cmd += ' -t \'{tags}\''.format(tags=','.join(self['tags']))
        if self.get('hosts',False):
            cmd += ' -l {hosts}'.format(hosts='"{}"'.format(self['hosts']))
        if 'args' in self:
            if self._config['ansible_dry_run'] and '-C' not in self['args']:
                self['args'].append('-C')
            if self._config['ansible_debug'] and '-D' not in self['args']:
                self['args'].append('-D')
            cmd_args = ' {args}'
            cmd += cmd_args.format(args=' '.join(self['args']))
        self['cmd'] = cmd
    
    def run(self):
        if not self.get('cmd'):
            logger.error('No "cmd" field in runned task (see debug)')
            logger.debug(str(self))
            sys.exit(1)
        if not self._config['dry_run']:
            env = os.environ
            new_env = {}
            for key, value in env.items():
                if not key.startswith('VIRTUALENVWRAPPER') and 'VIRTUALENV' not in key:
                    if 'VIRTUAL_ENV' not in key:
                        new_env[key] = value
            logger.info('Run {}'.format(self['cmd']))
            proc = subprocess.Popen(
                self['cmd'],
                shell=True,
                stdout=sys.stdout,
                stderr=sys.stderr,
                env=new_env,
            )
            proc.communicate()
            if proc.returncode != 0:
                logger.error("Error! {}".format(self['cmd']))
        else:
            logger.info('Dry run: {}'.format(self['cmd']))


